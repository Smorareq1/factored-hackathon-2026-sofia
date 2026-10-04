"""Capa estadística DS sobre MET-01..MET-06 (§6, REQ-14, REQ-18, DEL-06).

No redefine métricas: todo pasa por `calculate_metrics`/`MetricSummary`. Agrega lo que el reporte necesita para
no sobreconcluir con muestras chicas:

- IC 95% de Wilson para proporciones (+ cota "regla de tres" cuando hay 0 eventos: cero en muestra chica ≠ riesgo
  cero).
- IC bootstrap (semilla fija, determinista) para latencia p50/p95, costo medio por caso y completitud del handoff,
  remuestreando casos y recalculando con `calculate_metrics`.
- Baseline vs propuesto: diferencia, IC de la diferencia y p-valor, siempre con n.
- Desglose por idioma, nivel, tipo y segmento; celdas con n < 10 se marcan "n insuficiente" (REQ-18).

Solo stdlib (math, random, statistics): sin dependencias nuevas.
"""

import json
import math
import random
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from statistics import NormalDist
from typing import Any

from sofia_contracts.eval_case import ConversationResult, EvalCase
from sofia_eval.metrics import MetricSummary, calculate_metrics

MIN_N = 10  # REQ-18: por debajo, se reporta pero no se concluye
DEFAULT_SEED = 20260
DEFAULT_N_BOOT = 1000
INSUFFICIENT = "n insuficiente"

# Proporciones: nombre -> (numerador, denominador, mejor_si) en campos de MetricSummary.
PROPORTIONS: dict[str, tuple[str, str, str]] = {
    "met01_safe_auto_resolution": ("safe_automated_resolutions", "in_scope_auto_eligible", "mayor"),
    "met01_auto_attempt": ("auto_attempted", "total_cases", "mayor"),
    "met02_containment": ("contained_cases", "total_cases", "mayor"),
    "met03_escalation_precision": ("escalation_true_positives", "escalations_actual", "mayor"),
    "met03_escalation_recall": ("escalation_true_positives", "escalations_expected", "mayor"),
    "met04_unsafe_outcomes": ("unsafe_outcomes_total", "total_cases", "menor"),
}

# Continuas (bootstrap): nombre -> (campo de MetricSummary, mejor_si).
CONTINUOUS: dict[str, tuple[str, str]] = {
    "met03_handoff_completeness": ("handoff_field_completeness", "mayor"),
    "met05_latency_p50_ms": ("latency_p50_ms", "menor"),
    "met05_latency_p95_ms": ("latency_p95_ms", "menor"),
    "met06_cost_per_case_usd": ("cost_per_case_attempted_usd", "menor"),
    # None si no hay resoluciones seguras (§6: "not defined"); n = resoluciones seguras.
    "met06_cost_per_safe_resolution_usd": ("cost_per_safe_resolution_usd", "menor"),
}

NOT_DEFINED = "not defined (sin resoluciones seguras)"


# ---------------------------------------------------------------------------
# Primitivas estadísticas
# ---------------------------------------------------------------------------


def _z(alpha: float) -> float:
    return NormalDist().inv_cdf(1 - alpha / 2)


def wilson_interval(k: int, n: int, alpha: float = 0.05) -> tuple[float, float] | None:
    """IC de Wilson para k/n. None si n = 0."""
    if n <= 0:
        return None
    z = _z(alpha)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    lower = 0.0 if k == 0 else max(0.0, center - half)
    upper = 1.0 if k == n else min(1.0, center + half)
    return lower, upper


def rule_of_three_upper(n: int) -> float | None:
    """Cota superior ~95% cuando se observan 0 eventos en n: 3/n."""
    return min(1.0, 3 / n) if n > 0 else None


def proportion_stat(k: int, n: int, alpha: float = 0.05, min_n: int = MIN_N) -> dict[str, Any]:
    """k/n con IC de Wilson; agrega regla de tres si k = 0 y marca n insuficiente."""
    ci = wilson_interval(k, n, alpha)
    out: dict[str, Any] = {
        "k": k,
        "n": n,
        "rate": round(k / n, 4) if n > 0 else None,
        "ci": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
        "ci_method": "wilson",
        "n_insuficiente": n < min_n,
    }
    if k == 0 and n > 0:
        out["rule_of_three_upper"] = round(rule_of_three_upper(n) or 0.0, 4)
    return out


def fisher_exact(k1: int, n1: int, k2: int, n2: int) -> float:
    """p-valor bilateral exacto de Fisher para la tabla [[k1, n1-k1], [k2, n2-k2]]."""
    total, col = n1 + n2, k1 + k2
    denom = math.comb(total, col)

    def prob(a: int) -> float:
        return math.comb(n1, a) * math.comb(n2, col - a) / denom

    observed = prob(k1)
    lo, hi = max(0, col - n2), min(n1, col)
    p = sum(pa for a in range(lo, hi + 1) if (pa := prob(a)) <= observed * (1 + 1e-7))
    return min(1.0, p)


def two_proportion_z(k1: int, n1: int, k2: int, n2: int) -> float:
    """p-valor bilateral del test z de dos proporciones (varianza agrupada)."""
    pooled = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = (k2 / n2 - k1 / n1) / se
    return math.erfc(abs(z) / math.sqrt(2))


def compare_proportions(k1: int, n1: int, k2: int, n2: int, alpha: float = 0.05, min_n: int = MIN_N) -> dict:
    """Compara referencia (k1/n1) vs prueba (k2/n2): diff = p2 - p1, IC de Newcombe y p-valor.

    Usa Fisher exacto si alguna frecuencia esperada < 5; si no, z de dos proporciones. Asume muestras
    independientes (conservador si los mismos casos corren en ambos sistemas).
    """
    out: dict[str, Any] = {"n_ref": n1, "n_test": n2, "diff": None, "ci": None, "p_value": None, "test": None}
    if n1 <= 0 or n2 <= 0:
        out["conclusion"] = INSUFFICIENT
        return out
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson_interval(k1, n1, alpha) or (0.0, 1.0)
    l2, u2 = wilson_interval(k2, n2, alpha) or (0.0, 1.0)
    diff = p2 - p1
    lower = diff - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    upper = diff + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)

    total, col = n1 + n2, k1 + k2
    expected = [n * c / total for n in (n1, n2) for c in (col, total - col)]
    if min(expected) < 5:
        p_value, test = fisher_exact(k1, n1, k2, n2), "fisher_exact"
    else:
        p_value, test = two_proportion_z(k1, n1, k2, n2), "two_proportion_z"

    out.update(
        diff=round(diff, 4),
        ci=[round(max(-1.0, lower), 4), round(min(1.0, upper), 4)],
        ci_method="newcombe_wilson",
        p_value=round(p_value, 4),
        test=test,
    )
    out["conclusion"] = _conclusion(min(n1, n2), p_value, alpha, min_n)
    return out


def _quantile(sorted_vals: list[float], q: float) -> float:
    k = (len(sorted_vals) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def percentile_ci(samples: list[float], alpha: float = 0.05) -> list[float] | None:
    """IC percentil a partir de réplicas bootstrap."""
    if not samples:
        return None
    s = sorted(samples)
    return [_quantile(s, alpha / 2), _quantile(s, 1 - alpha / 2)]


def _conclusion(n_min: int, p_value: float, alpha: float, min_n: int) -> str:
    if n_min < min_n:
        return INSUFFICIENT
    return "diferencia significativa" if p_value < alpha else "sin diferencia concluyente"


# ---------------------------------------------------------------------------
# Bootstrap sobre casos (reusa calculate_metrics)
# ---------------------------------------------------------------------------


def _rng(seed: int, label: str) -> random.Random:
    # Semilla derivada por celda: determinista y sin depender de PYTHONHASHSEED.
    return random.Random(f"{seed}:{label}")  # noqa: S311 — bootstrap, no criptografía


def _group_by_case(cases: list[EvalCase], results: list[ConversationResult]) -> dict[str, list[ConversationResult]]:
    # Agrupa por case_id (bootstrap por clúster si hay varias corridas por caso); ignora resultados sin caso.
    known = {c.case_id for c in cases}
    groups: dict[str, list[ConversationResult]] = defaultdict(list)
    for r in results:
        if r.case_id in known:
            groups[r.case_id].append(r)
    return dict(groups)


def _resample(groups: dict[str, list[ConversationResult]], ids: list[str], rng: random.Random) -> list:
    return [r for cid in rng.choices(ids, k=len(ids)) for r in groups[cid]]


def _fields(summary: MetricSummary) -> dict[str, float | None]:
    # None = métrica no definida en esa réplica (p. ej. costo por resolución sin resoluciones): se descarta.
    return {
        name: None if (v := getattr(summary, field)) is None else float(v) for name, (field, _) in CONTINUOUS.items()
    }


def bootstrap_metrics(
    cases: list[EvalCase],
    results: list[ConversationResult],
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    label: str = "all",
) -> dict[str, list[float]]:
    """Réplicas bootstrap de las métricas continuas remuestreando casos."""
    groups = _group_by_case(cases, results)
    ids = sorted(groups)
    reps: dict[str, list[float]] = {name: [] for name in CONTINUOUS}
    if len(ids) < 2:
        return reps
    rng = _rng(seed, label)
    for _ in range(n_boot):
        vals = _fields(calculate_metrics(cases, _resample(groups, ids, rng)))
        for name, v in vals.items():
            if v is not None:
                reps[name].append(v)
    return reps


def bootstrap_diff(
    cases: list[EvalCase],
    ref_results: list[ConversationResult],
    test_results: list[ConversationResult],
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    label: str = "diff",
) -> tuple[dict[str, list[float]], bool]:
    """Réplicas de (test - ref) por métrica continua.

    Si ambos sistemas cubren los mismos casos, remuestrea case_id en conjunto (pareado); si no, independiente.
    """
    g_ref, g_test = _group_by_case(cases, ref_results), _group_by_case(cases, test_results)
    reps: dict[str, list[float]] = {name: [] for name in CONTINUOUS}
    paired = set(g_ref) == set(g_test)
    if len(g_ref) < 2 or len(g_test) < 2:
        return reps, paired
    rng = _rng(seed, label)
    ids_ref, ids_test = sorted(g_ref), sorted(g_test)
    for _ in range(n_boot):
        if paired:
            draw = rng.choices(ids_ref, k=len(ids_ref))
            res_ref = [r for cid in draw for r in g_ref[cid]]
            res_test = [r for cid in draw for r in g_test[cid]]
        else:
            res_ref, res_test = _resample(g_ref, ids_ref, rng), _resample(g_test, ids_test, rng)
        v_ref = _fields(calculate_metrics(cases, res_ref))
        v_test = _fields(calculate_metrics(cases, res_test))
        for name in CONTINUOUS:
            if v_test[name] is not None and v_ref[name] is not None:
                reps[name].append(v_test[name] - v_ref[name])
    return reps, paired


def _bootstrap_p(diffs: list[float]) -> float | None:
    # p-valor bilateral aproximado: proporción de réplicas al otro lado de 0.
    if not diffs:
        return None
    le = sum(d <= 0 for d in diffs) / len(diffs)
    ge = sum(d >= 0 for d in diffs) / len(diffs)
    return min(1.0, 2 * min(le, ge))


# ---------------------------------------------------------------------------
# Estadísticas por sistema y comparaciones
# ---------------------------------------------------------------------------


def _only_known(cases: list[EvalCase], results: list[ConversationResult]) -> list[ConversationResult]:
    # calculate_metrics ya ignora resultados sin caso conocido (#17); se filtra igual para que n y bootstrap coincidan.
    known = {c.case_id for c in cases}
    return [r for r in results if r.case_id in known]


def _handoff_n(cases: list[EvalCase], results: list[ConversationResult]) -> int:
    known = {c.case_id for c in cases}
    return sum(1 for r in results if r.case_id in known and r.handoff is not None)


def _cost_n(cases: list[EvalCase], results: list[ConversationResult]) -> int:
    known = {c.case_id for c in cases}
    return sum(1 for r in results if r.case_id in known and r.cost_usd is not None)


def system_stats(
    cases: list[EvalCase],
    results: list[ConversationResult],
    alpha: float = 0.05,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    label: str = "all",
    min_n: int = MIN_N,
) -> dict[str, Any]:
    """MET-01..06 de un sistema con IC: Wilson para proporciones, bootstrap para continuas."""
    results = _only_known(cases, results)
    summary = calculate_metrics(cases, results)
    out: dict[str, Any] = {"n": summary.total_cases, "n_insuficiente": summary.total_cases < min_n}
    metrics: dict[str, Any] = {}
    for name, (num, den, better) in PROPORTIONS.items():
        metrics[name] = proportion_stat(getattr(summary, num), getattr(summary, den), alpha, min_n) | {
            "mejor_si": better
        }

    reps = bootstrap_metrics(cases, results, n_boot=n_boot, seed=seed, label=label)
    n_by_metric = {
        "met03_handoff_completeness": _handoff_n(cases, results),
        "met06_cost_per_case_usd": summary.total_cases,
        "met06_cost_per_safe_resolution_usd": summary.safe_automated_resolutions,
    }
    for name, (field, better) in CONTINUOUS.items():
        ci = percentile_ci(reps[name], alpha)
        n = n_by_metric.get(name, summary.total_cases)
        metrics[name] = {
            "value": getattr(summary, field),
            "n": n,
            "ci": [round(x, 6) for x in ci] if ci else None,
            "ci_method": "bootstrap_percentil",
            "n_insuficiente": n < min_n,
            "mejor_si": better,
        }
        if metrics[name]["value"] is None:
            metrics[name]["nota"] = NOT_DEFINED
    metrics["met06_cost_per_case_usd"]["n_con_costo"] = _cost_n(cases, results)
    out["metricas"] = metrics
    return out


def compare(
    cases: list[EvalCase],
    ref_results: list[ConversationResult],
    test_results: list[ConversationResult],
    alpha: float = 0.05,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    label: str = "compare",
    min_n: int = MIN_N,
) -> dict[str, Any]:
    """Compara test vs ref (diff = test - ref) en cada métrica, con n, IC de la diferencia y p-valor."""
    ref_results, test_results = _only_known(cases, ref_results), _only_known(cases, test_results)
    s_ref, s_test = calculate_metrics(cases, ref_results), calculate_metrics(cases, test_results)
    out: dict[str, Any] = {}
    for name, (num, den, better) in PROPORTIONS.items():
        cmp = compare_proportions(
            getattr(s_ref, num), getattr(s_ref, den), getattr(s_test, num), getattr(s_test, den), alpha, min_n
        )
        out[name] = cmp | {"mejor_si": better}

    reps, paired = bootstrap_diff(cases, ref_results, test_results, n_boot=n_boot, seed=seed, label=label)
    n_ref, n_test = s_ref.total_cases, s_test.total_cases
    for name, (field, better) in CONTINUOUS.items():
        ci = percentile_ci(reps[name], alpha)
        p = _bootstrap_p(reps[name])
        v_ref, v_test = getattr(s_ref, field), getattr(s_test, field)
        out[name] = {
            "n_ref": n_ref,
            "n_test": n_test,
            "diff": round(v_test - v_ref, 6) if v_ref is not None and v_test is not None else None,
            "ci": [round(x, 6) for x in ci] if ci else None,
            "ci_method": "bootstrap_percentil_pareado" if paired else "bootstrap_percentil",
            "p_value": round(p, 4) if p is not None else None,
            "test": "bootstrap",
            "conclusion": _conclusion(min(n_ref, n_test), p, alpha, min_n) if p is not None else INSUFFICIENT,
            "mejor_si": better,
        }
    return out


# ---------------------------------------------------------------------------
# Desgloses (REQ-18) y salida JSON (DEL-06)
# ---------------------------------------------------------------------------


def segment_of(case: EvalCase, segments: dict[str, str]) -> str:
    """Segmento por case_id o, si no, por session_customer_id."""
    return segments.get(case.case_id) or segments.get(case.session_customer_id) or "sin_segmento"


def _breakdown(
    cases: list[EvalCase],
    proposed: list[ConversationResult],
    baseline: list[ConversationResult] | None,
    key: Callable[[EvalCase], Any],
    dim: str,
    **kw: Any,
) -> dict[str, Any]:
    cells: dict[str, Any] = {}
    for value in sorted({key(c) for c in cases}, key=str):
        sub = [c for c in cases if key(c) == value]
        label = f"{dim}={value}"
        cell = system_stats(sub, proposed, label=f"{label}:proposed", **kw)
        cell = {"n": cell["n"], "n_insuficiente": cell["n_insuficiente"], "proposed": cell}
        if baseline:
            cell["baseline"] = system_stats(sub, baseline, label=f"{label}:baseline", **kw)
            cell["comparacion"] = compare(sub, baseline, proposed, label=f"{label}:cmp", **kw)
        if cell["n_insuficiente"]:
            cell["nota"] = f"{INSUFFICIENT} (n={cell['n']} < {kw.get('min_n', MIN_N)}): se reporta, no se concluye"
        cells[str(value)] = cell
    return cells


def build_ds_stats(
    cases: list[EvalCase],
    proposed_results: list[ConversationResult],
    baseline_results: list[ConversationResult] | None = None,
    segments: dict[str, str] | None = None,
    alpha: float = 0.05,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    min_n: int = MIN_N,
) -> dict[str, Any]:
    """Arma el bloque estadístico DS (serializable a JSON) para el reporte de evaluación."""
    kw: dict[str, Any] = {"alpha": alpha, "n_boot": n_boot, "seed": seed, "min_n": min_n}
    baseline = baseline_results or None

    dims: dict[str, Callable[[EvalCase], Any]] = {
        "idioma": lambda c: c.language,
        "nivel": lambda c: c.level,
        "tipo": lambda c: c.type,
    }
    if segments:
        dims["segmento"] = lambda c: segment_of(c, segments)

    cases_es = [c for c in cases if c.language == "es"]
    cases_pt = [c for c in cases if c.language == "pt"]
    ids_es = {c.case_id for c in cases_es}
    ids_pt = {c.case_id for c in cases_pt}
    parity = None
    if cases_es and cases_pt:
        # REQ-18: brecha PT - ES del sistema propuesto (muestras independientes).
        parity = compare(
            cases,
            [r for r in proposed_results if r.case_id in ids_es],
            [r for r in proposed_results if r.case_id in ids_pt],
            label="paridad:es-pt",
            **kw,
        )

    return {
        "meta": {
            "alpha": alpha,
            "confianza": 1 - alpha,
            "n_boot": n_boot,
            "seed": seed,
            "min_n": min_n,
            "metodos": {
                "proporciones": "IC de Wilson; regla de tres (3/n) si 0 eventos",
                "continuas": "bootstrap percentil remuestreando casos (calculate_metrics por réplica)",
                "diferencia_proporciones": "IC de Newcombe (Wilson); Fisher exacto si esperado < 5, si no z",
                "diferencia_continuas": "bootstrap de la diferencia (pareado por case_id si aplica)",
                "desglose": f"celdas con n < {min_n} se marcan '{INSUFFICIENT}'",
            },
        },
        "proposed": system_stats(cases, proposed_results, label="proposed", **kw),
        "baseline": system_stats(cases, baseline, label="baseline", **kw) if baseline else None,
        "comparacion": compare(cases, baseline, proposed_results, label="baseline-vs-proposed", **kw)
        if baseline
        else None,
        "paridad_idioma": parity,
        "desglose": {dim: _breakdown(cases, proposed_results, baseline, key, dim, **kw) for dim, key in dims.items()},
    }


def save_ds_stats(stats: dict[str, Any], output_dir: Path | str = "eval/outputs") -> Path:
    """Escribe `ds_stats.json` en output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "ds_stats.json"
    path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
