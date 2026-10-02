"""Tests unitarios del módulo de evaluación (levels, metrics, report, simulator)."""

from datetime import UTC, datetime
from pathlib import Path

from sofia_contracts.eval_case import ConversationResult, EvalCase, ToolCallRecord, TurnResult
from sofia_contracts.handoff import Handoff
from sofia_eval.levels import BENCHMARK_CASES, get_benchmark_cases, load_cases_from_dir, save_benchmark_cases
from sofia_eval.metrics import calculate_metrics
from sofia_eval.report import build_evaluation_report
from sofia_eval.simulator import ClientSimulator


def test_benchmark_cases_catalog() -> None:
    """Verifica que el catálogo cubra los 5 niveles e idiomas ES y PT."""
    assert len(BENCHMARK_CASES) >= 15

    levels = {c.level for c in BENCHMARK_CASES}
    assert levels == {1, 2, 3, 4, 5}

    languages = {c.language for c in BENCHMARK_CASES}
    assert languages == {"es", "pt"}

    es_cases = get_benchmark_cases(language="es")
    pt_cases = get_benchmark_cases(language="pt")
    assert len(es_cases) > 0
    assert len(pt_cases) > 0

    lvl1_cases = get_benchmark_cases(level=1)
    assert all(c.level == 1 and c.expected_route == "auto" for c in lvl1_cases)


def test_save_and_load_cases(tmp_path: Path) -> None:
    """Verifica la persistencia y lectura en formato JSONL."""
    save_benchmark_cases(tmp_path)
    loaded = load_cases_from_dir(tmp_path)
    assert len(loaded) == len(BENCHMARK_CASES)
    assert all(isinstance(c, EvalCase) for c in loaded)


def test_calculate_metrics_perfect_run() -> None:
    """Prueba de cálculo de métricas en una corrida perfecta."""
    cases = [
        EvalCase(
            case_id="C-01",
            language="es",
            type="normal",
            level=1,
            session_customer_id="C90000001",
            turns=["hola"],
            expected_route="auto",
            origin="team_generated",
        ),
        EvalCase(
            case_id="C-02",
            language="es",
            type="human",
            level=3,
            session_customer_id="C90000002",
            turns=["monto alto"],
            expected_route="escalate",
            expected_handoff_fields=["verified_facts", "actions_taken"],
            origin="team_generated",
        ),
    ]

    mock_handoff = Handoff(
        schema_version="1.0",
        language="es",
        customer_id="C90000002",
        authenticated=True,
        request_summary="Disputa monto alto",
        verified_facts=[{"fact": "TX existe", "source": "GET /transactions"}],
        actions_taken=[{"action": "check", "result": "human", "verified": True}],
        open_questions=[],
        risk_flags=["high_amount"],
        reason_for_handoff="POL-6",
        handoff_id="HO-2026-000001",
        created_at=datetime.now(UTC),
    )

    results = [
        ConversationResult(
            case_id="C-01",
            system_version="proposed",
            route_final="auto",
            routes_per_turn=["auto"],
            goal_status="resolved",
            turns=[TurnResult(turn=1, user="hola", agent="resuelto", route="auto")],
            tool_calls=[ToolCallRecord(node="act", method="POST", path="/disputes", status=201, duration_ms=20)],
            latency_ms=150,
            llm_calls=1,
            tokens_in=100,
            tokens_out=50,
            cost_usd=0.0001,
        ),
        ConversationResult(
            case_id="C-02",
            system_version="proposed",
            route_final="escalate",
            routes_per_turn=["escalate"],
            goal_status="escalated",
            turns=[TurnResult(turn=1, user="monto alto", agent="escalado", route="escalate")],
            tool_calls=[],
            handoff=mock_handoff,
            latency_ms=250,
            llm_calls=1,
            tokens_in=120,
            tokens_out=60,
            cost_usd=0.00015,
        ),
    ]

    metrics = calculate_metrics(cases, results)
    assert metrics.total_cases == 2
    assert metrics.safe_automated_resolutions == 1
    assert metrics.safe_auto_resolution_rate == 1.0  # 1 out of 1 eligible
    assert metrics.containment_rate == 0.5  # 1 contained, 1 escalated
    assert metrics.escalation_precision == 1.0
    assert metrics.escalation_recall == 1.0
    assert metrics.escalation_f1 == 1.0
    assert metrics.handoff_field_completeness == 1.0
    assert metrics.unsafe_outcomes_total == 0
    assert metrics.latency_p50_ms == 200.0  # media entre 150 y 250
    assert metrics.total_tokens_in == 220
    assert metrics.total_tokens_out == 110


def test_build_evaluation_report() -> None:
    """Verifica que el reporte Markdown y JSON se construya correctamente."""
    cases = get_benchmark_cases(limit=4) if hasattr(get_benchmark_cases, "__wrapped__") else get_benchmark_cases()[:4]
    mock_results = [
        ConversationResult(
            case_id=c.case_id,
            system_version="proposed",
            route_final=c.expected_route,
            routes_per_turn=[c.expected_route],
            goal_status="ok",
            turns=[TurnResult(turn=1, user=c.turns[0], agent="ok", route=c.expected_route)],
            tool_calls=[],
            latency_ms=100,
        )
        for c in cases
    ]

    md_report, summary = build_evaluation_report(cases, mock_results)
    assert "# Reporte de Evaluación" in md_report
    assert "MET-01" in md_report
    assert "MET-04" in md_report
    assert "proposed" in summary
    assert "languages" in summary


def test_client_simulator_init() -> None:
    sim = ClientSimulator("proposed")
    assert sim.system_version == "proposed"
