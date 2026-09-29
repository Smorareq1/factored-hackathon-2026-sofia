"""Nodos de INTERPRET: entender el turno (router + slots + anclaje) y pedir aclaraciones (POL-7)."""

import re
from datetime import date
from decimal import Decimal
from typing import Any

from sofia_agent.deps import Deps
from sofia_agent.govern.decorator import governed
from sofia_agent.govern.trail import Trail
from sofia_agent.interpret.anchor import anchor_transaction
from sofia_agent.interpret.rules import SlotExtraction, read_confirmation, read_selection, rules_extract
from sofia_agent.llm import ExtractRequest, LLMUnavailableError
from sofia_agent.state import AgentState, ConversationGoal, Slots, TurnReading, VerifiedFact, Versions
from sofia_agent.text import fold
from sofia_agent.tools.router import mentions_human
from sofia_contracts.router import IN_SCOPE_INTENTS, Intent

_GREETING = re.compile(
    r"^(hola|buenas|buenos dias|buenas tardes|buenas noches|oi|ola|bom dia|boa tarde|boa noite|hey)\b"
)
# Campos que identifican la transacción: si cambian, la confirmación pendiente deja de valer.
_ANCHOR_FIELDS = ("transaction_id", "amount", "merchant", "date_from", "date_to")


def _merge_extractions(llm: SlotExtraction | None, rules: SlotExtraction) -> SlotExtraction:
    """El LLM entiende mejor el lenguaje libre; las reglas son exactas en IDs. Se completa campo por campo."""
    if llm is None:
        return rules
    merged = llm.model_copy()
    for name in SlotExtraction.model_fields:
        if getattr(merged, name) in (None, "none", False) and getattr(rules, name) not in (None, "none", False):
            setattr(merged, name, getattr(rules, name))
    merged.transaction_id = rules.transaction_id or llm.transaction_id
    merged.dispute_id = rules.dispute_id or llm.dispute_id
    return merged


def _slots_delta(extraction: SlotExtraction) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    if extraction.transaction_id:
        delta["transaction_id"] = extraction.transaction_id.strip().upper()
    if extraction.amount is not None and extraction.amount > 0:
        delta["amount"] = Decimal(str(extraction.amount))
    if extraction.currency:
        delta["currency"] = extraction.currency
    if extraction.merchant and extraction.merchant.strip():
        delta["merchant"] = extraction.merchant.strip()[:60]
    for name in ("date_from", "date_to"):
        raw = getattr(extraction, name)
        if raw:
            try:
                delta[name] = date.fromisoformat(raw)
            except ValueError:
                pass
    if extraction.customer_claim:
        delta["customer_claim"] = extraction.customer_claim
    if extraction.dispute_id:
        delta["dispute_id"] = extraction.dispute_id.strip().upper()
    return delta


def _reading(
    message: str, extraction: SlotExtraction, *, n_options: int, pending: bool, wants_human: bool
) -> tuple[TurnReading, bool]:
    """Confirmación determinística primero; el LLM solo desempata mensajes cortos sin condiciones.

    `pending` = hay una confirmación o una oferta de humano esperando respuesta; si no, un "No reconozco…"
    no es una respuesta ambigua, es un mensaje nuevo.
    """
    deterministic = read_confirmation(message)
    ambiguous = pending and deterministic == "ambiguous"
    if deterministic in ("yes", "no"):
        confirmation = deterministic
    elif (
        not ambiguous and pending and len(message.split()) <= 6 and not re.search(r"\b(pero|mas|but)\b", fold(message))
    ):
        confirmation = extraction.confirmation
    else:
        confirmation = "none"
    selection = read_selection(message, n_options)
    if selection is None and extraction.selection and 1 <= extraction.selection <= n_options:
        selection = extraction.selection
    return TurnReading(confirmation=confirmation, wants_human=wants_human, selection=selection), ambiguous


def _effective_intent(
    *,
    predicted: Intent | None,
    goal: ConversationGoal | None,
    reading: TurnReading,
    has_new_slots: bool,
    claim: str | None,
) -> Intent | None:
    goal_open = goal is not None and goal.status == "open"
    if reading.wants_human or predicted == "needs_human":
        return "needs_human"
    if goal_open and goal is not None:
        continuing = (
            reading.confirmation != "none"
            or reading.selection is not None
            or predicted is None
            or predicted == goal.type
            or (has_new_slots and predicted in ("transaction_inquiry", "out_of_scope"))
        )
        if continuing:
            return goal.type
    if predicted is not None:
        return predicted
    if claim:
        return "dispute_new"
    return None


@governed("INTERPRET", "interpret")
async def interpret(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    cfg, limits = deps.purpose.interpret, deps.purpose.limits
    message, language, turn = state["message"], state["language"], state["turn"]
    today = deps.now().date()
    goal = state.get("goal")
    candidates = state.get("candidates") or []
    pending = bool(state.get("pending_confirmation"))
    llm_calls = state.get("llm_calls", 0)
    update: dict[str, Any] = {}

    # 1. Intención (router de DS; reglas locales si no está disponible).
    routed = await deps.router.predict(message, language)
    prediction = routed.prediction
    trail.emit(
        "intent_classified",
        intent=prediction.intent,
        confidence=prediction.confidence,
        router_version=prediction.router_version,
    )
    if routed.fallback_reason:
        trail.emit("router_fallback", "warn", layer="GOVERN", reason=routed.fallback_reason)
    versions = state.get("versions") or Versions(purpose="", prompts="", model="")
    update["versions"] = versions.model_copy(update={"router": prediction.router_version})
    predicted = prediction.intent if prediction.confidence >= cfg.router_confidence_threshold else None

    # 2. Slots: reglas siempre; Gemini salvo que la lectura determinística ya sea decisiva.
    wants_human = mentions_human(message)
    rules = rules_extract(message, today, n_options=len(candidates), wants_human=wants_human)
    decisive = read_confirmation(message) in ("yes", "no") or rules.selection is not None
    llm_extraction: SlotExtraction | None = None
    if not decisive and llm_calls < limits.max_llm_calls_per_turn:
        try:
            llm_extraction = await deps.llm.extract(
                ExtractRequest(
                    message=message,
                    language=language,
                    today=today,
                    pending_confirmation=pending,
                    n_options=len(candidates),
                    recent_customer_turns=[m.text for m in state.get("messages", []) if m.role == "customer"][-4:-1],
                )
            )
            llm_calls += 1
        except LLMUnavailableError as exc:
            trail.emit("llm_fallback", "warn", layer="GOVERN", reason=str(exc))
    extraction = _merge_extractions(llm_extraction, rules)
    delta = _slots_delta(extraction)
    trail.emit("slots_extracted", source="llm+rules" if llm_extraction else "rules", fields=sorted(delta))
    update["llm_calls"] = llm_calls

    reading, ambiguous = _reading(
        message,
        extraction,
        n_options=len(candidates),
        pending=pending or bool(state.get("offered_human")),
        wants_human=wants_human or extraction.wants_human,
    )
    if ambiguous:
        trail.emit("confirmation_ambiguous", "warn")
    update["reading"] = reading

    # 3. Meta de la conversación (PURPOSE dinámico).
    intent = _effective_intent(
        predicted=predicted, goal=goal, reading=reading, has_new_slots=bool(delta), claim=extraction.customer_claim
    )
    slots = state.get("slots") or Slots()
    selected = state.get("selected_tx")
    if intent is not None and (goal is None or goal.status != "open" or goal.type != intent):
        # Pasar a humano a mitad de una disputa conserva lo recogido (va al handoff).
        keep_context = intent == "needs_human" and goal is not None and goal.status == "open"
        goal = ConversationGoal(type=intent, opened_turn=goal.opened_turn if keep_context and goal else turn)
        trail.emit("goal_opened", layer="PURPOSE", goal=intent)
        if not keep_context:
            # Una elección sobre la lista anterior ("quiero disputar la segunda") sobrevive al cambio de meta.
            slots, selected = Slots(), None
            candidates = candidates if reading.selection is not None else []
            update |= {
                "clarifications": 0,
                "pending_confirmation": False,
                "eligibility": None,
                "unverified_tx_id": None,
                "dispute": None,
            }
            pending = False
    update["goal"] = goal
    update["intent"] = prediction

    # 4. Acumular slots (REQ-07); si cambia la transacción referida, se invalida la confirmación.
    changed = [k for k, v in delta.items() if getattr(slots, k) is not None and getattr(slots, k) != v]
    slots = slots.model_copy(update=delta)
    if changed and any(k in _ANCHOR_FIELDS for k in changed):
        trail.emit("slots_changed", "warn", fields=changed)
        selected, pending = None, False
        update |= {"pending_confirmation": False, "eligibility": None}

    # Respuesta a una oferta de humano: DECIDE la resuelve.
    if state.get("offered_human") and reading.confirmation in ("yes", "no"):
        update |= {"slots": slots}
        return update

    if intent is None:
        if any(s.code == "prompt_injection_suspected" for s in state.get("signals", [])):
            # Sin un pedido reconocible y con intento de inyección no se invita a reformular: DECIDE se abstiene.
            trail.emit("injection_without_request", "warn", layer="GOVERN")
            return update | {"slots": slots}
        reason = "greeting" if _GREETING.match(fold(message)) and turn == 1 else "intent_unclear"
        return update | {"slots": slots, "route": "clarify", "clarify_reason": reason}

    # 5. Anclar la transacción cuando la meta la necesita.
    needs_tx = intent == "dispute_new" or (
        intent == "transaction_inquiry"
        and (slots.transaction_id or slots.merchant or slots.amount or reading.selection)
    )
    reuse = selected is not None and not delta and reading.selection is None
    if needs_tx and not reuse and not (pending and reading.confirmation != "none"):
        result = await anchor_transaction(
            bank=deps.bank,
            slots=slots,
            message=message,
            today=today,
            config=cfg,
            turn=turn,
            previous_candidates=candidates,
            selection=reading.selection,
        )
        if result.merchant_from_text and not slots.merchant:
            slots = slots.model_copy(update={"merchant": result.merchant_from_text})
        facts: list[VerifiedFact] = result.facts
        update |= {
            "selected_tx": result.selected,
            "candidates": result.candidates,
            "unverified_tx_id": result.unverified_tx_id,
            "verified_facts": facts,
        }
        if result.selected:
            trail.emit("transaction_anchored", transaction_id=result.selected.transaction_id)
            if selected is None or selected.transaction_id != result.selected.transaction_id:
                update |= {"pending_confirmation": False, "eligibility": None}
        elif result.unverified_tx_id:
            trail.emit("transaction_not_accessible", "warn")
        else:
            trail.emit(
                "transaction_unresolved", "warn", reason=result.clarify_reason, candidates=len(result.candidates)
            )
            return update | {"slots": slots, "route": "clarify", "clarify_reason": result.clarify_reason}
    elif intent in IN_SCOPE_INTENTS and intent != "dispute_new":
        update["candidates"] = candidates if reading.selection is None else []

    return update | {"slots": slots}


@governed("INTERPRET", "clarify")
async def clarify(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    """POL-7: se aclara hasta `max_clarifications` veces para identificar la transacción; luego, humano."""
    reason = state.get("clarify_reason") or "intent_unclear"
    attempts = state.get("clarifications", 0)
    limit = deps.purpose.limits.max_clarifications
    counts = reason.startswith("tx_") or reason in ("candidates", "selection")
    if counts and attempts >= limit:
        trail.emit("clarification_limit", "warn", layer="DECIDE", rule_id="POL-7", attempts=attempts)
        pol7 = VerifiedFact(
            key="rule.id",
            kind="rule",
            value="POL-7",
            fact=f"Política POL-7: la transacción no se identificó tras {attempts} aclaraciones",
            source="POL-7",
            turn=state["turn"],
        )
        return {"route": "escalate", "handoff_reason": "POL-7", "verified_facts": [pol7]}
    attempts = attempts + 1 if counts else attempts
    trail.emit("clarification_requested", reason=reason, attempt=attempts, max=limit)
    situation = "greeting" if reason == "greeting" else f"clarify_{reason}"
    return {"route": "clarify", "situation": situation, "clarifications": attempts}
