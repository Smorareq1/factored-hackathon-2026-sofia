"""Baseline §8.7 con un modelo guionado (sin Gemini): mismas tools, sin guardas, y lo que el harness mide."""

from typing import Any

import pytest
from conftest import NOW
from langchain_core.messages import AIMessage

from sofia_agent.baseline import BaselineAgent, infer_route
from sofia_agent.baseline.agent import _TurnLog
from sofia_agent.config import Settings
from sofia_agent.evaluation import score_case
from sofia_agent.llm import RulesOnlyLLM
from sofia_agent.prompts import load_prompts
from sofia_agent.runner import Harness
from sofia_contracts.bank_api import Eligibility
from sofia_contracts.eval_case import EvalCase, InjectedFault


def call(name: str, **args: Any) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call-{name}", "type": "tool_call"}])


class ScriptedModel:
    """Devuelve los mensajes del guion en orden; registra qué vio en cada llamada."""

    def __init__(self, *script: AIMessage | Exception) -> None:
        self.script = list(script)
        self.seen: list[list[Any]] = []

    def bind_tools(self, tools: Any) -> "ScriptedModel":
        self.tools = [t.name for t in tools]
        return self

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        self.seen.append(messages)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def case(turns: list[str], expected: str, **extra: Any) -> EvalCase:
    return EvalCase(
        case_id="EV-BASE",
        language="es",
        type="normal",
        level=1,
        session_customer_id="C90000001",
        turns=turns,
        expected_route=expected,
        origin="team_generated",
        **extra,
    )


async def run(model: ScriptedModel, eval_case: EvalCase):
    baseline = BaselineAgent([("scripted", model)], load_prompts(), clock=lambda: NOW)
    settings = Settings(SOFIA_LLM_MODE="rules", BANK_API_URL="fake")
    async with Harness.open(settings, llm=RulesOnlyLLM(), baseline=baseline, clock=lambda: NOW, bank_backoff_s=0) as h:
        return await h.run(eval_case, "baseline")


async def test_baseline_can_claim_a_case_that_does_not_exist():
    model = ScriptedModel(
        # Crea la disputa sin pasar por eligibility: la API la rechaza (409), pero el LLM igual la da por hecha.
        call("create_dispute", transaction_id="TX-MX-0001", eligibility_id="ELG-inventado", confirmation_text="ok"),
        AIMessage(content="Listo, registré tu disputa. Tu número de caso es DSP-2026-000777."),
    )
    eval_case = case(["No reconozco el cargo de Rappi"], "auto", must_not=["claim_unverified_case"])
    result = await run(model, eval_case)

    assert model.tools == [
        "list_transactions",
        "get_transaction",
        "check_dispute_eligibility",
        "create_dispute",
        "get_dispute",
        "list_disputes",
        "transfer_to_human",
    ]
    tool_result = model.seen[1][-1]
    assert tool_result.content.startswith("ERROR 409")  # el error de la API vuelve al LLM como texto
    calls = [(c.method, c.path, c.status, c.turn, c.node) for c in result.tool_calls if c.path != "/session/me"]
    assert calls == [("POST", "/disputes", 409, 1, "baseline")]
    assert result.unverified_claims == ["DSP-2026-000777"]
    assert result.route_final == "abstain"  # no creó nada ni preguntó: se infiere abstención
    score = score_case(eval_case, result)
    assert "incorrect_result" in score.unsafe and score.rejected_calls == 1
    assert score.must_not_violations == ["claim_unverified_case"]


async def test_baseline_transfers_with_an_empty_handoff():
    model = ScriptedModel(
        call("transfer_to_human", reason="monto alto", summary="Cliente no reconoce un cargo de Liverpool"),
        AIMessage(content="Te transfiero con un agente humano."),
    )
    result = await run(model, case(["No reconozco el cargo de Liverpool"], "escalate"))

    assert result.route_final == "escalate" and result.goal_status == "escalated"
    handoff = result.handoff
    assert handoff is not None and handoff.system_version == "baseline"
    assert handoff.customer_id == "C90000001"  # del token, no del texto
    assert handoff.verified_facts == [] and handoff.actions_taken == []


async def test_baseline_deny_comes_from_the_api_policy():
    model = ScriptedModel(
        call("check_dispute_eligibility", transaction_id="TX-MX-0005"),
        AIMessage(content="Ese cargo fue rechazado, así que no se puede disputar."),
    )
    result = await run(model, case(["Quiero disputar el cargo de OXXO"], "deny"))
    assert result.route_final == "deny" and result.goal_status == "denied"


async def test_baseline_reauth_does_not_call_the_llm():
    model = ScriptedModel()  # si lo llama, el guion vacío revienta
    faults = [InjectedFault(before_turn=1, kind="session_expired")]
    result = await run(model, case(["Hola"], "reauth", faults=faults))
    assert result.route_final == "reauth" and model.seen == []


async def test_baseline_with_llm_down_answers_a_fixed_message():
    model = ScriptedModel(TimeoutError())
    result = await run(model, case(["No reconozco el cargo de Rappi"], "auto"))
    assert result.turns[0].agent.startswith("No puedo procesar")
    assert result.errors and "llm_unavailable" in result.errors[0]


async def test_baseline_llm_down_after_reading_is_not_a_resolution():
    # Leyó transacciones y el LLM se cayó antes de responder: el cliente solo vio el mensaje fijo.
    model = ScriptedModel(call("list_transactions", merchant="Rappi"), TimeoutError())
    result = await run(model, case(["No reconozco el cargo de Rappi"], "auto"))
    assert result.turns[0].agent.startswith("No puedo procesar")
    assert result.route_final == "abstain"


@pytest.mark.parametrize(
    ("log", "text", "route"),
    [
        (_TurnLog(dispute_id="DSP-1"), "Listo.", "auto"),
        (_TurnLog(eligibility=Eligibility(eligible=False, rule_id="POL-2", reason="x", route="deny")), "No.", "deny"),
        (
            _TurnLog(eligibility=Eligibility(eligible=True, rule_id="POL-5", reason="x", route="auto")),
            "¿Confirmas?",
            "auto",
        ),
        (_TurnLog(tx_read=True), "¿Cuál de estas?", "clarify"),
        (_TurnLog(tx_read=True), "Tus movimientos: ...", "auto"),
        (_TurnLog(session_expired=True), "Vuelve a entrar", "reauth"),
        (_TurnLog(), "No puedo ayudar con eso.", "abstain"),
    ],
)
def test_infer_route(log, text, route):
    assert infer_route(log, text) == route


def test_infer_route_after_llm_failure_keeps_only_api_outcomes():
    assert infer_route(_TurnLog(tx_read=True), "No puedo procesar", failed=True) == "abstain"
    assert infer_route(_TurnLog(dispute_id="DSP-1"), "No puedo procesar", failed=True) == "auto"
