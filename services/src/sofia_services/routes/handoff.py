"""Rutas de recepción, consulta y feedback de handoffs estructurados (§9.4, REQ-05)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from sofia_contracts.bank_api import HandoffList, HandoffReceipt
from sofia_contracts.handoff import Handoff, HandoffDraft, HandoffFeedback, HandoffFeedbackRecord
from sofia_services.audit.logger import audit_trail
from sofia_services.auth.service import get_current_session, require_agent, require_customer
from sofia_services.faults.manager import fault_manager
from sofia_services.store import BankStore, SessionRecord, get_store

router = APIRouter(tags=["handoff"])


@router.post("/handoff", status_code=201)
def create_handoff(
    body: HandoffDraft,
    session: Annotated[SessionRecord, Depends(require_customer)],
    response: Response,
    store: Annotated[BankStore, Depends(get_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> HandoffReceipt:
    fault_manager.check_endpoint("POST", "/handoff")

    if body.customer_id != session.customer_id:
        raise HTTPException(status_code=403, detail="customer_mismatch")

    cache_key = f"handoff:{idempotency_key}" if idempotency_key else None
    if cache_key:
        cached = store.idempotency.get(cache_key)
        if isinstance(cached, HandoffReceipt):
            return cached

    handoff = Handoff(
        **body.model_dump(),
        handoff_id=store.next_id("HO"),
        created_at=store.now,
    )
    receipt = HandoffReceipt(handoff_id=handoff.handoff_id, created_at=handoff.created_at)

    if cache_key:
        store.idempotency[cache_key] = receipt

    store.handoffs[handoff.handoff_id] = handoff

    audit_trail.record(
        "handoff_received",
        customer_id=session.customer_id,
        handoff_id=handoff.handoff_id,
        reason=body.reason_for_handoff,
    )

    response.status_code = 201
    return receipt


@router.get("/handoffs/{handoff_id}")
def get_handoff(
    handoff_id: str,
    session: Annotated[SessionRecord, Depends(get_current_session)],
    store: Annotated[BankStore, Depends(get_store)],
) -> Handoff:
    fault_manager.check_endpoint("GET", f"/handoffs/{handoff_id}")
    handoff = store.handoffs.get(handoff_id)
    if handoff is None or (session.role != "agent" and handoff.customer_id != session.customer_id):
        raise HTTPException(status_code=404, detail="not_found")
    return handoff


@router.get("/handoffs")
def list_handoffs(
    session: Annotated[SessionRecord, Depends(require_agent)],
    store: Annotated[BankStore, Depends(get_store)],
) -> HandoffList:
    items = sorted(store.handoffs.values(), key=lambda h: h.created_at, reverse=True)
    return HandoffList(items=items)


@router.post("/handoffs/{handoff_id}/feedback")
def give_handoff_feedback(
    handoff_id: str,
    body: HandoffFeedback,
    session: Annotated[SessionRecord, Depends(require_agent)],
    store: Annotated[BankStore, Depends(get_store)],
) -> HandoffFeedbackRecord:
    if handoff_id not in store.handoffs:
        raise HTTPException(status_code=404, detail="not_found")

    record = HandoffFeedbackRecord(
        **body.model_dump(),
        handoff_id=handoff_id,
        reviewer_id=session.customer_id,
        submitted_at=store.now,
    )
    store.feedback[handoff_id] = record
    audit_trail.record("handoff_feedback_recorded", handoff_id=handoff_id, useful=body.useful)
    return record


@router.get("/handoffs/{handoff_id}/feedback")
def get_handoff_feedback(
    handoff_id: str,
    session: Annotated[SessionRecord, Depends(require_agent)],
    store: Annotated[BankStore, Depends(get_store)],
) -> HandoffFeedbackRecord:
    record = store.feedback.get(handoff_id)
    if record is None:
        raise HTTPException(status_code=404, detail="not_found")
    return record
