"""Nodos de DECIDE: tabla de ruteo determinística. El LLM no participa (§8.4, REQ-10).

La política (POL-1..POL-7) vive en SIM: el agente llama `POST /disputes/eligibility` y solo lee `rule_id`,
`reason` y `route` para explicarlos y registrarlos.
"""

from datetime import timedelta
from typing import Any

from sofia_agent.deps import Deps
from sofia_agent.facts import dispute_facts, rule_fact, to_ref
from sofia_agent.govern.decorator import governed
from sofia_agent.govern.trail import Trail
from sofia_agent.state import AgentState, ConversationGoal, DisputeRef, VerifiedFact

_OTHER_CUSTOMER_SIGNALS = {"foreign_customer_id", "other_customer_reference"}
_OPEN_STATUSES = {"open", "in_review"}


def _close(goal: ConversationGoal | None, status: str) -> ConversationGoal | None:
    return goal.model_copy(update={"status": status}) if goal else None


def _escalate(reason: str) -> dict[str, Any]:
    return {"route": "escalate", "handoff_reason": reason}


@governed("DECIDE", "decide")
async def decide(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    goal = state.get("goal")
    reading = state["reading"]
    turn = state["turn"]
    signals = {s.code for s in state.get("signals", [])}

    # 1. Pedido de datos de otro cliente: se deniega sin tocar tools (POL-1, sin revelar si existe).
    if signals & _OTHER_CUSTOMER_SIGNALS:
        trail.emit("rule_applied", rule_id="POL-1", route="deny", reason="other_customer_data", source="SENSE")
        fact = VerifiedFact(
            key="rule.id",
            kind="rule",
            value="POL-1",
            fact="Política POL-1: el cliente pidió datos de otro cliente; se denegó sin consultar",
            source="SENSE:" + ",".join(sorted(signals & _OTHER_CUSTOMER_SIGNALS)),
            turn=turn,
        )
        return {
            "route": "deny",
            "situation": "deny_other_customer",
            "goal": _close(goal, "denied"),
            "verified_facts": [fact],
        }

    # 2. Respuesta a una oferta de humano (abstención o POL-3).
    if state.get("offered_human") and reading.confirmation == "yes":
        trail.emit("human_requested", reason="accepted_offer")
        return _escalate("customer_request") | {"offered_human": False}
    if state.get("offered_human") and reading.confirmation == "no":
        trail.emit("human_declined")
        return {
            "route": "abstain",
            "situation": "human_declined",
            "offered_human": False,
            "goal": _close(goal, "abstained"),
        }

    intent = goal.type if goal else None
    if intent == "needs_human" or reading.wants_human:
        trail.emit("human_requested", reason="customer_request")
        return _escalate("customer_request")
    if intent == "out_of_scope" or intent is None:
        trail.emit("out_of_scope", intent=intent)
        return {"route": "abstain"}
    if intent == "dispute_status":
        return await _dispute_status(state, deps, trail)
    if intent == "transaction_inquiry":
        return await _transaction_inquiry(state, deps, trail)
    return await _dispute_new(state, deps, trail)


async def _dispute_status(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    slots, turn, goal = state["slots"], state["turn"], state.get("goal")
    if slots.dispute_id:
        found = await deps.bank.get_dispute(slots.dispute_id)
        disputes = [found] if found else []
    else:
        disputes = [d for d in await deps.bank.list_disputes() if d.status in _OPEN_STATUSES]
    trail.emit("disputes_read", count=len(disputes))
    update: dict[str, Any] = {"route": "auto", "goal": _close(goal, "resolved")}
    if not disputes:
        return update | {"situation": "status_none"}
    if len(disputes) == 1:
        return update | {"situation": "status_one", "verified_facts": dispute_facts(disputes[0], turn=turn)}
    refs = [
        DisputeRef(dispute_id=d.dispute_id, transaction_id=d.transaction_id, status=d.status, verified=True)
        for d in disputes
    ]
    return update | {"situation": "status_list", "disputes_listed": refs}


async def _transaction_inquiry(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    goal = state.get("goal")
    if state.get("selected_tx"):
        trail.emit("transaction_read", transaction_id=state["selected_tx"].transaction_id)
        return {"route": "auto", "situation": "inquiry_one", "goal": _close(goal, "resolved")}
    if state.get("unverified_tx_id"):
        trail.emit("rule_applied", rule_id="POL-1", route="deny", reason="transaction_not_accessible", source="API 404")
        return {"route": "deny", "situation": "deny_POL-1", "goal": _close(goal, "denied")}
    since = deps.now().date() - timedelta(days=30)
    recent = [to_ref(t) for t in await deps.bank.list_transactions(since=since, limit=5)]
    trail.emit("transactions_read", count=len(recent))
    if not recent:
        return {"route": "auto", "situation": "inquiry_none", "goal": _close(goal, "resolved")}
    # La lista se renderiza de forma determinística desde `candidates` (datos de la API, sin LLM).
    return {"route": "auto", "situation": "inquiry_list", "candidates": recent, "goal": _close(goal, "resolved")}


async def _dispute_new(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    goal, reading, turn = state.get("goal"), state["reading"], state["turn"]
    selected = state.get("selected_tx")
    tx_id = selected.transaction_id if selected else state.get("unverified_tx_id")
    if tx_id is None:
        return {"route": "clarify", "situation": "clarify_tx_missing_details"}

    # Confirmación pendiente de un turno anterior (nunca se actúa en el mismo turno en que se pregunta).
    eligibility = state.get("eligibility")
    still_valid = (
        eligibility is not None
        and eligibility.route == "auto"
        and (eligibility.expires_at is None or eligibility.expires_at > deps.now())
    )
    if state.get("pending_confirmation") and still_valid and selected is not None:
        if reading.confirmation == "yes":
            if not deps.settings.auto_actions:
                trail.emit("kill_switch_active", "warn", layer="GOVERN")
                return _escalate("kill_switch") | {"pending_confirmation": False}
            trail.emit("confirmation_received", transaction_id=tx_id)
            return {"route": "auto", "ready_to_act": True}
        if reading.confirmation == "no":
            trail.emit("confirmation_declined")
            return {
                "route": "abstain",
                "situation": "dispute_cancelled",
                "pending_confirmation": False,
                "eligibility": None,
                "goal": _close(goal, "abstained"),
            }
        trail.emit("confirmation_pending", "warn")
        return {"route": "clarify", "situation": "confirm_again"}

    # Evaluar la política en SIM.
    eligibility = await deps.bank.check_eligibility(tx_id, state["slots"].customer_claim)
    trail.emit(
        "rule_applied",
        rule_id=eligibility.rule_id,
        route=eligibility.route,
        reason=eligibility.reason,
        risk_flags=eligibility.risk_flags,
    )
    update: dict[str, Any] = {"eligibility": eligibility, "verified_facts": rule_fact(eligibility, turn=turn)}
    if eligibility.route == "deny":
        update |= {"route": "deny", "situation": f"deny_{eligibility.rule_id}", "goal": _close(goal, "denied")}
        if eligibility.rule_id == "POL-3":
            update["offered_human"] = True
        return update
    if eligibility.route == "human":
        return update | _escalate(eligibility.rule_id)
    if not deps.settings.auto_actions:
        trail.emit("kill_switch_active", "warn", layer="GOVERN")
        return update | _escalate("kill_switch")
    trail.emit("confirmation_requested", transaction_id=tx_id)
    return update | {"route": "auto", "situation": "confirm_request", "pending_confirmation": True}


@governed("DECIDE", "abstain")
async def abstain(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    trail.emit("abstained", reason="out_of_scope", offer_human=True)
    return {
        "route": "abstain",
        "situation": "abstain",
        "offered_human": True,
        "goal": _close(state.get("goal"), "abstained"),
    }
