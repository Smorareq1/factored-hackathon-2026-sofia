"""Tests de la capa estadística DS (IC, baseline vs propuesto, desgloses) con resultados sintéticos."""

import json
from pathlib import Path

import pytest

from sofia_contracts.eval_case import ConversationResult, EvalCase, TurnResult
from sofia_eval.ds_stats import (
    INSUFFICIENT,
    build_ds_stats,
    compare_proportions,
    fisher_exact,
    proportion_stat,
    save_ds_stats,
    system_stats,
    two_proportion_z,
    wilson_interval,
)


def _case(i: int, language: str = "es", route: str = "auto", level: int = 1) -> EvalCase:
    return EvalCase(
        case_id=f"C-{i:03d}",
        language=language,
        type="normal" if route == "auto" else "human",
        level=level,
        session_customer_id=f"C9{i:07d}",
        turns=["hola"],
        expected_route=route,
        origin="team_generated",
    )


def _result(case: EvalCase, version: str, route: str, latency: int, unsafe: bool = False) -> ConversationResult:
    return ConversationResult(
        case_id=case.case_id,
        system_version=version,
        route_final=route,
        routes_per_turn=[route],
        goal_status="ok",
        turns=[TurnResult(turn=1, user=case.turns[0], agent="ok", route=route)],
        tool_calls=[],
        latency_ms=latency,
        cost_usd=0.001,
        unverified_claims=["CASE-X"] if unsafe else [],
    )


def _dataset() -> tuple[list[EvalCase], list[ConversationResult], list[ConversationResult]]:
    """24 casos (16 ES, 8 PT); el baseline escala todo, el propuesto resuelve lo auto y es más rápido."""
    cases = [_case(i, "es" if i < 16 else "pt", "auto" if i % 3 else "escalate", 1 if i % 3 else 3) for i in range(24)]
    proposed = [_result(c, "proposed", c.expected_route, 200 + 10 * i) for i, c in enumerate(cases)]
    baseline = [_result(c, "baseline", "escalate", 900 + 10 * i) for i, c in enumerate(cases)]
    return cases, proposed, baseline


def test_wilson_interval_known_values() -> None:
    lo, hi = wilson_interval(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-4)
    assert hi == pytest.approx(0.7634, abs=1e-4)
    lo0, hi0 = wilson_interval(0, 10)
    assert lo0 == 0.0
    assert hi0 == pytest.approx(0.2775, abs=1e-4)
    assert wilson_interval(0, 0) is None


def test_proportion_stat_zero_events_rule_of_three() -> None:
    """Cero en muestra chica ≠ riesgo cero: se reporta cota 3/n y n insuficiente."""
    stat = proportion_stat(0, 6)
    assert stat["rate"] == 0.0
    assert stat["rule_of_three_upper"] == 0.5
    assert stat["n_insuficiente"] is True
    assert stat["ci"][1] > 0.3
    assert "rule_of_three_upper" not in proportion_stat(2, 30)


def test_fisher_exact_and_z_test() -> None:
    # Tabla [[8, 2], [1, 5]]: p bilateral conocido ≈ 0.0350.
    assert fisher_exact(8, 10, 1, 6) == pytest.approx(0.03497, abs=1e-4)
    assert fisher_exact(3, 10, 3, 10) == pytest.approx(1.0)
    assert two_proportion_z(50, 100, 50, 100) == pytest.approx(1.0)
    assert two_proportion_z(20, 100, 50, 100) < 0.001


def test_compare_proportions_picks_test_and_flags_small_n() -> None:
    small = compare_proportions(1, 6, 5, 6)
    assert small["test"] == "fisher_exact"
    assert small["conclusion"] == INSUFFICIENT
    assert small["n_ref"] == 6 and small["n_test"] == 6

    big = compare_proportions(40, 100, 70, 100)
    assert big["test"] == "two_proportion_z"
    assert big["diff"] == pytest.approx(0.3)
    assert big["ci"][0] < 0.3 < big["ci"][1]
    assert big["ci"][0] > 0
    assert big["conclusion"] == "diferencia significativa"

    assert compare_proportions(0, 0, 1, 5)["conclusion"] == INSUFFICIENT


def test_system_stats_reuses_metrics_and_bootstrap_is_deterministic() -> None:
    cases, proposed, _ = _dataset()
    a = system_stats(cases, proposed, n_boot=200, seed=7)
    b = system_stats(cases, proposed, n_boot=200, seed=7)
    assert a == b
    m = a["metricas"]
    assert a["n"] == 24
    assert m["met01_safe_auto_resolution"]["rate"] == 1.0
    assert m["met04_unsafe_outcomes"]["k"] == 0
    assert m["met04_unsafe_outcomes"]["rule_of_three_upper"] == pytest.approx(3 / 24, abs=1e-4)
    p50 = m["met05_latency_p50_ms"]
    assert p50["ci"][0] <= p50["value"] <= p50["ci"][1]
    assert m["met06_cost_per_case_usd"]["n_con_costo"] == 24


def test_subset_ignores_results_of_other_cases() -> None:
    """calculate_metrics cuenta resultados sin caso: el subconjunto debe filtrarlos."""
    cases, proposed, _ = _dataset()
    es = [c for c in cases if c.language == "es"]
    assert system_stats(es, proposed, n_boot=10)["n"] == 16


def test_build_ds_stats_full_report(tmp_path: Path) -> None:
    cases, proposed, baseline = _dataset()
    segments = {c.case_id: ("premium" if i < 12 else "masivo") for i, c in enumerate(cases)}
    stats = build_ds_stats(cases, proposed, baseline, segments=segments, n_boot=100, seed=1)

    # Serializable a JSON y determinista.
    json.dumps(stats)
    assert stats == build_ds_stats(cases, proposed, baseline, segments=segments, n_boot=100, seed=1)

    cmp = stats["comparacion"]
    containment = cmp["met02_containment"]
    assert containment["n_ref"] == 24 and containment["n_test"] == 24
    assert containment["diff"] > 0
    assert containment["conclusion"] == "diferencia significativa"
    lat = cmp["met05_latency_p50_ms"]
    assert lat["diff"] < 0
    assert lat["ci_method"] == "bootstrap_percentil_pareado"
    assert lat["ci"][1] < 0

    lang = stats["desglose"]["idioma"]
    assert lang["es"]["n"] == 16 and not lang["es"]["n_insuficiente"]
    assert lang["pt"]["n"] == 8 and lang["pt"]["n_insuficiente"]
    assert INSUFFICIENT in lang["pt"]["nota"]
    assert lang["pt"]["comparacion"]["met02_containment"]["conclusion"] == INSUFFICIENT

    assert set(stats["desglose"]) == {"idioma", "nivel", "tipo", "segmento"}
    assert stats["desglose"]["segmento"]["premium"]["n"] == 12
    assert sum(cell["n"] for cell in stats["desglose"]["nivel"].values()) == 24
    assert stats["paridad_idioma"]["met02_containment"]["n_ref"] == 16

    path = save_ds_stats(stats, tmp_path)
    assert path.name == "ds_stats.json"
    assert json.loads(path.read_text(encoding="utf-8"))["meta"]["n_boot"] == 100


def test_build_ds_stats_without_baseline_or_segments() -> None:
    cases, proposed, _ = _dataset()
    stats = build_ds_stats(cases, proposed, n_boot=20)
    assert stats["baseline"] is None and stats["comparacion"] is None
    assert "segmento" not in stats["desglose"]
    assert "baseline" not in stats["desglose"]["idioma"]["es"]


def test_cost_per_safe_resolution_defined_and_not_defined() -> None:
    """MET-06 por resolución segura: con éxitos tiene valor e IC; sin éxitos queda "not defined" sin romper."""
    cases, proposed, baseline = _dataset()
    name = "met06_cost_per_safe_resolution_usd"

    prop = system_stats(cases, proposed, n_boot=200)["metricas"][name]
    assert prop["value"] is not None and prop["value"] > 0
    assert prop["ci"] is not None and prop["ci"][0] <= prop["value"] <= prop["ci"][1]
    assert prop["n"] == 16  # resoluciones seguras (los casos auto)
    assert "nota" not in prop

    base = system_stats(cases, baseline, n_boot=200)["metricas"][name]
    assert base["value"] is None
    assert base["ci"] is None
    assert base["n"] == 0
    assert base["nota"].startswith("not defined")

    cmp = build_ds_stats(cases, proposed, baseline, n_boot=200)["comparacion"][name]
    assert cmp["diff"] is None
    assert cmp["conclusion"] == INSUFFICIENT
    json.dumps(cmp)
