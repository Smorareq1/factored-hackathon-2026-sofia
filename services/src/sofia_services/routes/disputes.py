"""Rutas de elegibilidad y creación/consulta de disputas (§9.2, REQ-09, REQ-10)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from sofia_contracts.bank_api import (
    Dispute,
    DisputeCreate,
    DisputeList,
    Eligibility,
    EligibilityRequest,
)
from sofia_services.audit.logger import audit_trail
from sofia_services.auth.service import get_current_session, require_customer
from sofia_services.faults.manager import fault_manager
from sofia_services.policy.engine import evaluate_dispute_policy
from sofia_services.store import BankStore, SessionRecord, get_store

router = APIRouter(tags=["disputes"])


@router.post("/disputes/eligibility")
def check_dispute_eligibility(
    body: EligibilityRequest,
    session: Annotated[SessionRecord, Depends(require_customer)],
    store: Annotated[BankStore, Depends(get_store)],
) -> Eligibility:
    fault_manager.check_endpoint("POST", "/disputes/eligibility")
    return evaluate_dispute_policy(session.customer_id, body.transaction_id, store)


@router.post("/disputes", status_code=201)
def create_dispute(
    body: DisputeCreate,
    session: Annotated[SessionRecord, Depends(require_customer)],
    response: Response,
    store: Annotated[BankStore, Depends(get_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Dispute:
    fault_manager.check_endpoint("POST", "/disputes")

    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=422, detail="idempotency_key_required")

    cache_key = f"dispute:{idempotency_key}"
    cached = store.idempotency.get(cache_key)
    if isinstance(cached, Dispute):
        return cached

    # Validar que el eligibility_id exista, pertenezca a esta transacción y cliente, y no haya expirado
    entry = store.eligibilities.get(body.eligibility_id)
    if entry is None or entry[0] != session.customer_id or entry[1] != body.transaction_id:
        audit_trail.record(
            "dispute_rejected",
            customer_id=session.customer_id,
            transaction_id=body.transaction_id,
            reason="eligibility_not_found",
        )
        raise HTTPException(status_code=409, detail="eligibility_not_found")

    if entry[2] <= store.now:
        audit_trail.record(
            "dispute_rejected",
            customer_id=session.customer_id,
            transaction_id=body.transaction_id,
            reason="eligibility_expired",
        )
        raise HTTPException(status_code=409, detail="eligibility_expired")

    if not body.confirmation.text or not body.confirmation.text.strip():
        raise HTTPException(status_code=422, detail="confirmation_required")

    dispute = Dispute(
        dispute_id=store.next_id("DSP"),
        transaction_id=body.transaction_id,
        customer_id=session.customer_id,
        status="open",
        customer_claim=body.customer_claim,
        created_at=store.now,
    )

    # Consumir prueba de elegibilidad
    store.eligibilities.pop(body.eligibility_id, None)

    # Cache de idempotencia
    store.idempotency[cache_key] = dispute

    # Inyección de fallas: si drop_writes está activo, responde ok pero no persiste (prueba de REQ-09 VERIFY)
    if not fault_manager.drop_writes:
        store.disputes[dispute.dispute_id] = dispute

    audit_trail.record(
        "dispute_created",
        customer_id=session.customer_id,
        dispute_id=dispute.dispute_id,
        transaction_id=body.transaction_id,
        persisted=not fault_manager.drop_writes,
    )

    response.status_code = 201
    return dispute


@router.get("/disputes")
def list_disputes(
    session: Annotated[SessionRecord, Depends(require_customer)],
    store: Annotated[BankStore, Depends(get_store)],
    status: str | None = None,
) -> DisputeList:
    fault_manager.check_endpoint("GET", "/disputes")
    items = [d for d in store.disputes.values() if d.customer_id == session.customer_id]
    if status:
        items = [d for d in items if d.status == status]
    items.sort(key=lambda d: d.created_at, reverse=True)
    return DisputeList(items=items)


@router.get("/disputes/{dispute_id}")
def get_dispute(
    dispute_id: str,
    session: Annotated[SessionRecord, Depends(get_current_session)],
    store: Annotated[BankStore, Depends(get_store)],
) -> Dispute:
    fault_manager.check_endpoint("GET", f"/disputes/{dispute_id}")
    dispute = store.disputes.get(dispute_id)
    if dispute is None or (session.role != "agent" and dispute.customer_id != session.customer_id):
        raise HTTPException(status_code=404, detail="not_found")
    return dispute
