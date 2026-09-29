"""Harness en proceso: set dev completo en modo reglas, métricas, gate y la interfaz síncrona de SIM."""

from pathlib import Path

import pytest

from sofia_agent.config import Settings
from sofia_agent.evaluation import Evaluation, gate, load_cases, render_report
from sofia_agent.runner import Harness, run_conversation

DEV_CASES = Path(__file__).parents[1] / "evals" / "dev_cases.jsonl"
RULES = {"SOFIA_LLM_MODE": "rules", "BANK_API_URL": "fake"}


@pytest.fixture(scope="module")
def cases():
    return load_cases(DEV_CASES)


async def test_dev_set_passes_in_rules_mode(cases):
    async with Harness.open(Settings(**RULES), bank_backoff_s=0) as harness:
        assert harness.baseline is None  # sin LLM no hay baseline
        results = await harness.run_many(cases, ["proposed"])
    evaluation = Evaluation.build(cases, results)
    wrong = [
        (s.case.case_id, s.case.expected_route, s.result.routes_per_turn)
        for s in evaluation.scores["proposed"]
        if not s.route_ok
    ]
    unsafe = [(s.case.case_id, s.unsafe) for s in evaluation.scores["proposed"] if s.unsafe]
    assert wrong == [] and unsafe == []
    assert not any(r.errors for r in results)

    summary = evaluation.summary()
    overall = summary["proposed"]["overall"]
    assert overall["route_accuracy"] == 1.0
    assert overall["met03_escalation_recall"] == 1.0 and overall["met03_escalation_precision"] == 1.0
    assert overall["met03_handoff_completeness"] == 1.0
    assert overall["met04_unsafe_cases"] == 0
    assert set(summary["proposed"]["by_language"]) == {"es", "pt"}

    # Gate: la misma corrida contra sí misma pasa; una referencia mejor en MET-01 la frena.
    assert gate(summary, summary)[0]
    better = {"proposed": {"overall": overall | {"met01_safe_automated_resolution": 1.0}}}
    passed, reasons = gate(summary, better)
    assert not passed and "MET-01 bajó" in reasons[0]

    report = render_report(evaluation, title="Dev", context={"modo": "rules"})
    assert "MET-04 Casos inseguros" in report and "Por idioma" in report


async def test_level_5_faults_are_injected(cases):
    by_id = {c.case_id: c for c in cases}
    async with Harness.open(Settings(**RULES), bank_backoff_s=0) as harness:
        down = await harness.run(by_id["DEV-ES-021"])
        dropped = await harness.run(by_id["DEV-ES-023"])
    assert [c.status for c in down.tool_calls if c.path == "/disputes/eligibility"] == [503, 503, 503]
    assert down.handoff is not None and down.handoff.reason_for_handoff == "tool_unavailable"
    # La API "creó" la disputa pero no la guardó: VERIFY lo detecta y escala sin afirmar el caso.
    assert dropped.route_final == "escalate" and dropped.unverified_claims == []
    assert all(c.turn in (1, 2) for c in dropped.tool_calls)


def test_run_conversation_is_the_sync_entry_point_for_sim(cases):
    result = run_conversation(cases[0], settings=Settings(**RULES))
    assert result.case_id == cases[0].case_id and result.system_version == "proposed"
    assert result.route_final == "auto" and result.goal_status == "resolved"
    assert result.llm_calls == 0 and result.cost_usd == 0.0
    assert len(result.turns) == 2 and result.turns[1].route == "auto"

    baseline = run_conversation(cases[0], "baseline", settings=Settings(**RULES))
    assert baseline.route_final is None and baseline.errors[0].startswith("baseline_unavailable")
