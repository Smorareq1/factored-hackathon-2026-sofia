"""Trazas §9.6: 1 conversación = 1 trace; turno, nodos (con `layer`) y tool calls como observaciones."""

import pytest
from conftest import NOW, login
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from sofia_agent import tracing
from sofia_agent.config import Settings
from sofia_agent.deps import Deps
from sofia_agent.graph import compile_graph
from sofia_agent.llm import RulesOnlyLLM
from sofia_agent.prompts import load_prompts
from sofia_agent.purpose import load_purpose
from sofia_agent.tools.bank import BankClient
from sofia_agent.tools.router import RouterClient
from sofia_agent.turns import run_turn

THREAD = "thread-trace-0001"


@pytest.fixture(scope="module")
def exporter():
    exporter = InMemorySpanExporter()
    tracing.configure(Settings(SOFIA_LLM_MODE="rules", BANK_API_URL="fake"), span_exporter=exporter)
    yield exporter
    tracing.shutdown()


async def test_a_conversation_is_one_trace_with_layered_spans(exporter, bank, settings):
    http, _ = bank
    token = await login(http, "MX-DEMO-001")
    trace_id = tracing.trace_id_for(THREAD)
    graph = compile_graph()

    def deps() -> Deps:
        return Deps(
            settings=settings,
            purpose=load_purpose(),
            prompts=load_prompts(),
            bank=BankClient(http, token, backoff_s=0),
            router=RouterClient(None),
            llm=RulesOnlyLLM(),
            thread_id=THREAD,
            trace_id=trace_id,
            clock=lambda: NOW,
        )

    first = await run_turn(graph, deps(), message="No reconozco el cargo de Rappi", turn=1, language_hint=None)
    await run_turn(graph, deps(), message="Sí, confirmo", turn=2, language_hint=None, case_id="EV-TEST")
    tracing.flush()
    spans = exporter.get_finished_spans()

    assert trace_id is not None and trace_id == tracing.trace_id_for(THREAD)  # determinístico por hilo
    assert {format(s.context.trace_id, "032x") for s in spans} == {trace_id}
    names = [s.name for s in spans]
    assert {"turn 1", "turn 2", "sense", "interpret", "decide", "act", "verify", "respond"} <= set(names)
    assert {"GET /session/me", "POST /disputes/eligibility", "POST /disputes"} <= set(names)

    by_name = {s.name: s for s in spans}
    turn = by_name["turn 2"].attributes
    assert turn["session.id"] == THREAD
    assert turn["langfuse.observation.type"] == "agent"
    assert turn["langfuse.trace.metadata.system_version"] == "proposed"
    assert turn["langfuse.trace.metadata.case_id"] == "EV-TEST"
    assert turn["langfuse.trace.metadata.purpose_version"] == load_purpose().purpose_version
    assert by_name["decide"].attributes["langfuse.observation.metadata.layer"] == "DECIDE"
    assert by_name["POST /disputes"].attributes["langfuse.observation.type"] == "tool"
    assert by_name["POST /disputes"].attributes["langfuse.observation.metadata.node"] == "act"

    # Cada evento de la caja de cristal apunta al span de su nodo.
    node_span_ids = {format(s.context.span_id, "016x") for s in spans if s.name == "sense"}
    assert first.events[0].node == "sense" and first.events[0].span_id in node_span_ids


def test_tracing_is_a_no_op_without_langfuse():
    tracing.shutdown()
    assert tracing.trace_id_for("x") is None
    assert tracing.score(trace_id="t", name="n", value=1, data_type="NUMERIC") is False
    with tracing.observe("span") as span:
        assert span is None
