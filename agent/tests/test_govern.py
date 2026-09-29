"""GOVERN: grounding check, guardia de salida, allowlist de acciones y el camino con LLM (guionado)."""

import pytest

from sofia_agent.govern.context import CURRENT_NODE, ToolNotAllowedError
from sofia_agent.govern.guards import grounding_check, output_guard
from sofia_agent.interpret.rules import SlotExtraction
from sofia_agent.llm import CANARY, DraftRequest, ExtractRequest, LLMUnavailableError, LLMUsage
from sofia_agent.tools.bank import BankClient
from sofia_contracts.bank_api import ConfirmationProof, DisputeCreate

ALLOWED = {"tx.amount", "tx.merchant", "tx.date"}
REQUIRED = {"tx.amount", "tx.merchant"}


@pytest.mark.parametrize(
    ("draft", "reason"),
    [
        ("Registré tu disputa por {{tx.amount}} en {{tx.merchant}}, son 349 pesos.", "literal_number"),
        ("Encontré {{tx.amount}} en {{tx.merchant}}, caso {{case.id}}.", "unknown_placeholder"),
        ("Encontré la transacción de {{tx.amount}}.", "missing_placeholder"),
        (f"Encontré {{{{tx.amount}}}} en {{{{tx.merchant}}}} {CANARY}", "canary_leak"),
        (
            "Encontrei a transação de {{tx.amount}} em {{tx.merchant}}. Você confirma que quer contestar?",
            "language_mismatch",
        ),
        ("Encontré {{tx.amount}} en {{tx.merchant}} el {tx.date}.", "malformed_placeholder"),
    ],
)
def test_grounding_check_rejects(draft, reason):
    result = grounding_check(draft, allowed=ALLOWED, required=REQUIRED, language="es")
    assert not result.ok
    assert result.reason == reason


def test_grounding_check_accepts_placeholder_only_draft():
    draft = "Encontré el cargo de {{tx.amount}} en {{tx.merchant}} del {{tx.date}}. ¿Confirmas que lo disputamos?"
    assert grounding_check(draft, allowed=ALLOWED, required=REQUIRED, language="es").ok


def test_output_guard_blocks_other_customer_ids_and_card_numbers():
    assert not output_guard("El cliente C90000002 compró…", session_customer_id="C90000001").ok
    assert not output_guard("Tu tarjeta 4111 1111 1111 1111", session_customer_id="C90000001").ok
    assert output_guard("Tu caso es DSP-2026-000123", session_customer_id="C90000001").ok


async def test_only_act_can_create_disputes(bank):
    http, _ = bank
    client = BankClient(http, "token-irrelevante")
    body = DisputeCreate(
        transaction_id="TX-MX-0001",
        eligibility_id="ELG-x",
        confirmation=ConfirmationProof(text="sí", turn=1, confirmed_at="2026-09-27T18:00:00Z"),
    )
    token = CURRENT_NODE.set("interpret")
    try:
        with pytest.raises(ToolNotAllowedError):
            await client.create_dispute(body, "k")
    finally:
        CURRENT_NODE.reset(token)


class ScriptedLLM:
    """Gemini falso: devuelve lo que el test le indique (para probar guardas y fallbacks)."""

    model_name = "scripted"

    def __init__(self, *, extraction: SlotExtraction | None = None, draft: str | None = None) -> None:
        self.usage = LLMUsage()
        self._extraction, self._draft = extraction, draft
        self.drafts: list[DraftRequest] = []

    async def extract(self, request: ExtractRequest) -> SlotExtraction:
        if self._extraction is None:
            raise LLMUnavailableError("scripted_none")
        return self._extraction

    async def draft(self, request: DraftRequest) -> str:
        self.drafts.append(request)
        if self._draft is None:
            raise LLMUnavailableError("scripted_none")
        return self._draft


async def test_llm_draft_is_rendered_with_verified_values(start):
    llm = ScriptedLLM(
        draft="¡Claro! Veo un cargo de {{tx.amount}} en {{tx.merchant}}. ¿Lo disputamos? Di «Sí, confirmo»."
    )
    conv = await start("MX-DEMO-001", llm=llm)
    state = await conv.say("No reconozco el cargo de Rappi")
    assert state["response"].text.startswith("¡Claro! Veo un cargo de $349.00 MXN en Rappi.")
    # CON-03: el LLM recibe claves y descripciones, nunca valores del dataset.
    request = llm.drafts[-1]
    assert "349" not in repr(request) and "Rappi" not in repr(request.placeholders)
    assert "grounding_passed" in conv.codes()


async def test_hallucinated_number_falls_back_to_template(start):
    llm = ScriptedLLM(draft="Registré tu disputa por $999 en {{tx.merchant}}.")
    conv = await start("MX-DEMO-001", llm=llm)
    state = await conv.say("No reconozco el cargo de Rappi")
    assert "999" not in state["response"].text
    assert "$349.00 MXN" in state["response"].text
    assert "grounding_fallback" in conv.codes()


async def test_malicious_llm_slots_cannot_reach_another_customer(start):
    # Un LLM "secuestrado" devuelve el ID de una transacción ajena: la API responde 404 y se deniega (POL-1).
    llm = ScriptedLLM(extraction=SlotExtraction(transaction_id="TX-CO-0002", customer_claim="not_recognized"))
    conv = await start("MX-DEMO-001", llm=llm)
    state = await conv.say("quiero disputar esa compra que te dije")
    assert state["route"] == "deny"
    assert state["eligibility"].rule_id == "POL-1"
    assert "Falabella" not in state["response"].text


async def test_llm_outage_keeps_working_with_rules(start):
    conv = await start("MX-DEMO-001", llm=ScriptedLLM())
    state = await conv.say("No reconozco el cargo de Rappi")
    assert state["situation"] == "confirm_request"
    assert conv.codes().count("llm_fallback") == 2
