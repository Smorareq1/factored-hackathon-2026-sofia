"""DS statistics layer over MET-01..MET-06 (§6, REQ-14, REQ-18, DEL-06).

It does not redefine metrics: everything goes through `calculate_metrics`/`MetricSummary`. It adds what the report
needs to avoid over-concluding from small samples:

- 95% Wilson CIs for proportions (+ a "rule of three" bound when there are 0 events: zero in a small sample ≠ zero
  risk).
- Bootstrap CIs (fixed seed, deterministic) for latency p50/p95, mean cost per case and handoff completeness,
  resampling cases and recomputing with `calculate_metrics`.
- Baseline vs proposed: difference, CI of the difference and p-value, always with n.
- Breakdown by language, level, type and segment; cells with n < 10 are marked "insufficient n" (REQ-18).

JSON keys stay as they are (Spanish) because the report placeholders point at them.
Standard library only (math, random, statistics): no new dependencies.
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

MIN_N = 10  # REQ-18: below it, report but do not conclude
DEFAULT_SEED = 20260
DEFAULT_N_BOOT = 1000
INSUFFICIENT = "insufficient n"

# Proportions: name -> (numerator, denominator, better_if) as MetricSummary fields.
PROPORTIONS: dict[str, tuple[str, str, str]] = {
    "met01_safe_auto_resolution": ("safe_automated_resolutions", "in_scope_auto_eligible", "higher"),
    "met01_auto_attempt": ("auto_attempted", "total_cases", "higher"),
    "met02_containment": ("contained_cases", "total_cases", "higher"),
    "met03_escalation_precision": ("escalation_true_positives", "escalations_actual", "higher"),
    "met03_escalation_recall": ("escalation_true_positives", "escalations_expected", "higher"),
    "met04_unsafe_outcomes": ("unsafe_outcomes_total", "total_cases", "lower"),
}

# Continuous (bootstrap): name -> (MetricSummary field, better_if).
CONTINUOUS: dict[str, tuple[str, str]] = {
    "met03_handoff_completeness": ("handoff_field_completeness", "higher"),
    "met05_latency_p50_ms": ("latency_p50_ms", "lower"),
    "met05_latency_p95_ms": ("latency_p95_ms", "lower"),
    "met06_cost_per_case_usd": ("cost_per_case_attempted_usd", "lower"),
    # None when there are no safe resolutions (§6: "not defined"); n = safe resolutions.
    "met06_cost_per_safe_resolution_usd": ("cost_per_safe_resolution_usd", "lower"),
}

NOT_DEFINED = "not defined (no safe resolutions)"


# ---------------------------------------------------------------------------
# Statistical primitives
# ---------------------------------------------------------------------------


def _z(alpha: float) -> float:
    return NormalDist().inv_cdf(1 - alpha / 2)


def wilson_interval(k: int, n: int, alpha: float = 0.05) -> tuple[float, float] | None:
    """Wilson CI for k/n. None if n = 0."""
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
    """~95% upper bound when 0 events are observed in n: 3/n."""
    return min(1.0, 3 / n) if n > 0 else None


def proportion_stat(k: int, n: int, alpha: float = 0.05, min_n: int = MIN_N) -> dict[str, Any]:
    """k/n with a Wilson CI; adds the rule of three when k = 0 and flags insufficient n."""
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
    """Two-sided exact Fisher p-value for the table [[k1, n1-k1], [k2, n2-k2]]."""
    total, col = n1 + n2, k1 + k2
    denom = math.comb(total, col)

    def prob(a: int) -> float:
        return math.comb(n1, a) * math.comb(n2, col - a) / denom

    observed = prob(k1)
    lo, hi = max(0, col - n2), min(n1, col)
    p = sum(pa for a in range(lo, hi + 1) if (pa := prob(a)) <= observed * (1 + 1e-7))
    return min(1.0, p)


def two_proportion_z(k1: int, n1: int, k2: int, n2: int) -> float:
    """Two-sided p-value of the two-proportion z test (pooled variance)."""
    pooled = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = (k2 / n2 - k1 / n1) / se
    return math.erfc(abs(z) / math.sqrt(2))


def compare_proportions(k1: int, n1: int, k2: int, n2: int, alpha: float = 0.05, min_n: int = MIN_N) -> dict:
    """Compares reference (k1/n1) vs test (k2/n2): diff = p2 - p1, Newcombe CI and p-value.

    Uses exact Fisher if any expected frequency is < 5; otherwise the two-proportion z test. Assumes independent
    samples (conservative when the same cases run on both systems).
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
    """Percentile CI from bootstrap replicates."""
    if not samples:
        return None
    s = sorted(samples)
    return [_quantile(s, alpha / 2), _quantile(s, 1 - alpha / 2)]


def _conclusion(n_min: int, p_value: float, alpha: float, min_n: int) -> str:
    if n_min < min_n:
        return INSUFFICIENT
    return "significant difference" if p_value < alpha else "no conclusive difference"


# ---------------------------------------------------------------------------
# Bootstrap over cases (reuses calculate_metrics)
# ---------------------------------------------------------------------------


def _rng(seed: int, label: str) -> random.Random:
    # Seed derived per cell: deterministic and independent of PYTHONHASHSEED.
    return random.Random(f"{seed}:{label}")  # noqa: S311 — bootstrap, not cryptography


def _group_by_case(cases: list[EvalCase], results: list[ConversationResult]) -> dict[str, list[ConversationResult]]:
    # Groups by case_id (cluster bootstrap when there are several runs per case); ignores results without a case.
    known = {c.case_id for c in cases}
    groups: dict[str, list[ConversationResult]] = defaultdict(list)
    for r in results:
        if r.case_id in known:
            groups[r.case_id].append(r)
    return dict(groups)


def _resample(groups: dict[str, list[ConversationResult]], ids: list[str], rng: random.Random) -> list:
    return [r for cid in rng.choices(ids, k=len(ids)) for r in groups[cid]]


def _fields(summary: MetricSummary) -> dict[str, float | None]:
    # None = metric undefined in that replicate (e.g. cost per resolution with no resolutions): dropped.
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
    """Bootstrap replicates of the continuous metrics, resampling cases."""
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
    """Replicates of (test - ref) per continuous metric.

    If both systems cover the same cases, case_ids are resampled jointly (paired); otherwise independently.
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
    # Approximate two-sided p-value: share of replicates on the other side of 0.
    if not diffs:
        return None
    le = sum(d <= 0 for d in diffs) / len(diffs)
    ge = sum(d >= 0 for d in diffs) / len(diffs)
    return min(1.0, 2 * min(le, ge))


# ---------------------------------------------------------------------------
# Per-system statistics and comparisons
# ---------------------------------------------------------------------------


def _only_known(cases: list[EvalCase], results: list[ConversationResult]) -> list[ConversationResult]:
    # calculate_metrics already ignores results without a known case (#17); filtered anyway so n and bootstrap agree.
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
    """MET-01..06 for one system with CIs: Wilson for proportions, bootstrap for continuous metrics."""
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
            "ci_method": "bootstrap_percentile",
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
    """Compares test vs ref (diff = test - ref) on every metric, with n, the CI of the difference and a p-value."""
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
            "ci_method": "bootstrap_percentile_paired" if paired else "bootstrap_percentile",
            "p_value": round(p, 4) if p is not None else None,
            "test": "bootstrap",
            "conclusion": _conclusion(min(n_ref, n_test), p, alpha, min_n) if p is not None else INSUFFICIENT,
            "mejor_si": better,
        }
    return out


# ---------------------------------------------------------------------------
# Breakdowns (REQ-18) and JSON output (DEL-06)
# ---------------------------------------------------------------------------


def segment_of(case: EvalCase, segments: dict[str, str]) -> str:
    """Segment by case_id or, failing that, by session_customer_id."""
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
            cell["nota"] = f"{INSUFFICIENT} (n={cell['n']} < {kw.get('min_n', MIN_N)}): reported, not concluded"
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
    """Builds the DS statistics block (JSON-serializable) for the evaluation report."""
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
        # REQ-18: PT - ES gap of the proposed system (independent samples).
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
                "proporciones": "Wilson CI; rule of three (3/n) when there are 0 events",
                "continuas": "percentile bootstrap resampling cases (calculate_metrics per replicate)",
                "diferencia_proporciones": "Newcombe (Wilson) CI; exact Fisher if an expected count < 5, otherwise z",
                "diferencia_continuas": "bootstrap of the difference (paired by case_id when possible)",
                "desglose": f"cells with n < {min_n} are marked '{INSUFFICIENT}'",
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
    """Writes `ds_stats.json` to output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "ds_stats.json"
    path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
