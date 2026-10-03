"""Rutas de sesión y autenticación (§9.2)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from sofia_contracts.bank_api import (
    DemoCustomer,
    HarnessSessionRequest,
    SessionChallenge,
    SessionInfo,
    SessionStart,
    SessionToken,
    SessionVerify,
)
from sofia_services.auth.service import (
    get_current_session,
    harness_session,
    start_session,
    verify_session,
)
from sofia_services.faults.manager import fault_manager
from sofia_services.store import BankStore, SessionRecord, get_store

router = APIRouter(tags=["session"])


@router.get("/demo/customers")
def get_demo_customers(store: Annotated[BankStore, Depends(get_store)]) -> list[DemoCustomer]:
    return [
        DemoCustomer(
            document_number=c.document_number,
            label=c.label,
            country=c.country,
            role=c.role,
        )
        for c in store.customers.values()
    ]


@router.post("/session")
def post_start_session(
    body: SessionStart, store: Annotated[BankStore, Depends(get_store)]
) -> SessionChallenge:
    fault_manager.check_endpoint("POST", "/session")
    return start_session(body, store)


@router.post("/session/verify")
def post_verify_session(
    body: SessionVerify, store: Annotated[BankStore, Depends(get_store)]
) -> SessionToken:
    fault_manager.check_endpoint("POST", "/session/verify")
    return verify_session(body, store)


@router.post("/session/test")
def post_harness_session(
    body: HarnessSessionRequest, store: Annotated[BankStore, Depends(get_store)]
) -> SessionToken:
    """Solo sandbox: sesión directa para el cliente del caso de evaluación."""
    fault_manager.check_endpoint("POST", "/session/test")
    return harness_session(body.customer_id, store)


@router.get("/session/me")
def get_session_me(session: Annotated[SessionRecord, Depends(get_current_session)]) -> SessionInfo:
    fault_manager.check_endpoint("GET", "/session/me")
    return SessionInfo(
        customer_id=session.customer_id,
        role=session.role,
        country=session.country,
        expires_at=session.expires_at,
    )
