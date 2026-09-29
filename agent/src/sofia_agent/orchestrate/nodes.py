"""Nodos de ORCHESTRATE que tocan el mundo: act (crear disputa), verify (releerla) y escalate (handoff).

REQ-09: nada se reporta al cliente sin releerlo. Si la verificación falla, no se afirma y se escala.
"""

import hashlib
from typing import Any

from sofia_agent.deps import Deps
from sofia_agent.facts import dispute_facts, plain_fact
from sofia_agent.govern.decorator import governed
from sofia_agent.govern.trail import Trail
from sofia_agent.orchestrate.handoff import build_handoff
from sofia_agent.state import ActionRecord, AgentState, DisputeRef
from sofia_agent.tools.bank import ToolRejectedError, ToolUnavailableError
from sofia_contracts.bank_api import ConfirmationProof, DisputeCreate


def _key(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:32]


@governed("ORCHESTRATE", "act")
async def act(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    eligibility, tx, turn = state["eligibility"], state["selected_tx"], state["turn"]
    assert eligibility is not None and eligibility.eligibility_id and tx is not None
    body = DisputeCreate(
        transaction_id=tx.transaction_id,
        eligibility_id=eligibility.eligibility_id,
        customer_claim=state["slots"].customer_claim,
        confirmation=ConfirmationProof(text=state["message"], turn=turn, confirmed_at=deps.now()),
    )
    # Mismo hilo + misma elegibilidad = misma llave: un reintento nunca duplica la disputa.
    idempotency_key = _key(deps.thread_id, eligibility.eligibility_id)
    try:
        dispute = await deps.bank.create_dispute(body, idempotency_key)
    except ToolRejectedError as exc:
        trail.emit("action_rejected", "error", http_status=exc.status, detail=exc.detail)
        record = ActionRecord(action="create_dispute", result=f"rejected:{exc.status}", verified=False, turn=turn)
        return {"route": "escalate", "handoff_reason": "action_rejected", "actions_taken": [record]}
    except ToolUnavailableError as exc:
        # No sabemos si se creó: no se afirma nada y el humano lo verifica.
        trail.emit("tool_unavailable", "error", method=exc.method, path=exc.path)
        record = ActionRecord(action="create_dispute", result="no_response", verified=False, turn=turn)
        return {"route": "escalate", "handoff_reason": "tool_unavailable", "actions_taken": [record]}
    trail.emit("dispute_submitted", dispute_id=dispute.dispute_id)
    return {
        "dispute": DisputeRef(
            dispute_id=dispute.dispute_id, transaction_id=dispute.transaction_id, status=dispute.status
        ),
        "actions_taken": [
            ActionRecord(action="create_dispute", result=f"dispute_id={dispute.dispute_id}", verified=False, turn=turn)
        ],
    }


@governed("ORCHESTRATE", "verify")
async def verify(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    ref, turn, session = state["dispute"], state["turn"], state["session"]
    assert ref is not None and session is not None
    try:
        found = await deps.bank.get_dispute(ref.dispute_id)
    except ToolUnavailableError:
        found = None
    ok = (
        found is not None
        and found.transaction_id == ref.transaction_id
        and found.customer_id == session.customer_id
        and found.status in ("open", "in_review")
    )
    if not ok:
        trail.emit("verification_failed", "error", dispute_id=ref.dispute_id)
        record = ActionRecord(action="verify_dispute", result="not_found_or_mismatch", verified=False, turn=turn)
        return {
            "route": "escalate",
            "handoff_reason": "verification_failed",
            "actions_taken": [record],
            "pending_confirmation": False,
        }
    assert found is not None
    trail.emit("action_verified", dispute_id=found.dispute_id, dispute_status=found.status)
    goal = state.get("goal")
    return {
        "dispute": ref.model_copy(update={"verified": True, "status": found.status}),
        "actions_taken": [
            ActionRecord(action="verify_dispute", result=f"exists=true status={found.status}", verified=True, turn=turn)
        ],
        "verified_facts": dispute_facts(found, turn=turn),
        "pending_confirmation": False,
        "eligibility": None,
        "goal": goal.model_copy(update={"status": "resolved"}) if goal else None,
        "route": "auto",
        "situation": "dispute_created",
    }


@governed("ORCHESTRATE", "escalate")
async def escalate(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    reason, turn = state.get("handoff_reason") or "customer_request", state["turn"]
    draft = build_handoff(state, reason=reason, trace_id=deps.trace_id)
    failed = {"route": "escalate", "situation": "escalate_failed", "pending_confirmation": False}
    try:
        receipt = await deps.bank.create_handoff(draft, _key(deps.thread_id, "handoff", turn))
        stored = await deps.bank.get_handoff(receipt.handoff_id)
    except (ToolUnavailableError, ToolRejectedError) as exc:
        trail.emit("handoff_failed", "error", detail=str(exc)[:120])
        return failed
    if stored is None or stored.customer_id != draft.customer_id or stored.reason_for_handoff != reason:
        trail.emit("handoff_unverified", "error", handoff_id=receipt.handoff_id)
        return failed
    trail.emit("handoff_created", handoff_id=stored.handoff_id, reason=reason, verified=True)
    goal = state.get("goal")
    fact = plain_fact(
        "handoff.id",
        stored.handoff_id,
        fact=f"Handoff {stored.handoff_id} registrado y verificado",
        source=f"GET /handoffs/{stored.handoff_id}",
        turn=turn,
    )
    return {
        "handoff": stored,
        "route": "escalate",
        "situation": f"escalated_{reason}",
        "goal": goal.model_copy(update={"status": "escalated"}) if goal else None,
        "pending_confirmation": False,
        "offered_human": False,
        "verified_facts": [fact],
        "actions_taken": [
            ActionRecord(action="create_handoff", result=f"handoff_id={stored.handoff_id}", verified=True, turn=turn)
        ],
    }
