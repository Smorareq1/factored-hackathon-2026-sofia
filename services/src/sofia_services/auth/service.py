"""Servicio de autenticación, sesión y dependencias de autorización (REQ-10, REQ-11)."""

import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from sofia_contracts.bank_api import (
    SessionChallenge,
    SessionStart,
    SessionToken,
    SessionVerify,
)
from sofia_services.audit.logger import audit_trail
from sofia_services.store import BankStore, SessionRecord, get_store


def start_session(body: SessionStart, store: BankStore | None = None) -> SessionChallenge:
    store = store or get_store()
    now = store.now
    settings = store.settings

    customer = store.customers_by_doc.get(body.document_number)
    challenge_id = secrets.token_urlsafe(12)
    otp = f"{secrets.randbelow(10**6):06d}"
    expires = now + timedelta(minutes=settings.CHALLENGE_TTL_MINUTES)

    if customer is not None:
        store.challenges[challenge_id] = (customer.customer_id, otp, expires)
        audit_trail.record(
            "auth_challenge_created",
            customer_id=customer.customer_id,
            challenge_id=challenge_id,
        )

    return SessionChallenge(challenge_id=challenge_id, expires_at=expires, simulated_otp=otp)


def verify_session(body: SessionVerify, store: BankStore | None = None) -> SessionToken:
    store = store or get_store()
    now = store.now
    settings = store.settings

    entry = store.challenges.get(body.challenge_id)
    if entry is None or entry[1] != body.otp or entry[2] <= now:
        audit_trail.record("auth_otp_failed", challenge_id=body.challenge_id)
        raise HTTPException(status_code=401, detail="otp_invalid")

    store.challenges.pop(body.challenge_id, None)
    customer_id, _, _ = entry
    customer = store.customers[customer_id]
    token = secrets.token_urlsafe(24)
    expires = now + timedelta(minutes=settings.SESSION_TTL_MINUTES)

    store.sessions[token] = SessionRecord(
        customer_id=customer.customer_id,
        role=customer.role,
        country=customer.country,
        expires_at=expires,
    )
    audit_trail.record(
        "auth_session_verified",
        customer_id=customer.customer_id,
        role=customer.role,
    )

    return SessionToken(access_token=token, expires_at=expires, role=customer.role)


def harness_session(customer_id: str, store: BankStore | None = None) -> SessionToken:
    """Solo sandbox: sesión directa para el cliente del harness (§9.5) sin OTP."""
    store = store or get_store()
    now = store.now
    settings = store.settings

    customer = store.customers.get(customer_id)
    if customer is None:
        audit_trail.record("auth_harness_customer_not_found", customer_id=customer_id)
        raise HTTPException(status_code=404, detail="customer_not_found")

    token = secrets.token_urlsafe(24)
    expires = now + timedelta(minutes=settings.SESSION_TTL_MINUTES)
    store.sessions[token] = SessionRecord(
        customer_id=customer.customer_id,
        role=customer.role,
        country=customer.country,
        expires_at=expires,
    )
    audit_trail.record(
        "auth_session_harness",
        customer_id=customer.customer_id,
        role=customer.role,
    )

    return SessionToken(access_token=token, expires_at=expires, role=customer.role)


def get_current_session(
    authorization: Annotated[str | None, Header()] = None,
    store: Annotated[BankStore, Depends(get_store)] = None,  # type: ignore[assignment]
) -> SessionRecord:
    store = store or get_store()
    token = (authorization or "").removeprefix("Bearer ").strip()
    session = store.sessions.get(token)
    if session is None or session.expires_at <= store.now:
        audit_trail.record("auth_session_expired", token=token[:6] if token else None)
        raise HTTPException(status_code=401, detail="session_invalid_or_expired")
    return session


def require_customer(session: Annotated[SessionRecord, Depends(get_current_session)]) -> SessionRecord:
    if session.role != "customer":
        audit_trail.record(
            "auth_forbidden_role",
            customer_id=session.customer_id,
            role=session.role,
            expected="customer",
        )
        raise HTTPException(status_code=403, detail="customer_role_required")
    return session


def require_agent(session: Annotated[SessionRecord, Depends(get_current_session)]) -> SessionRecord:
    if session.role != "agent":
        audit_trail.record(
            "auth_forbidden_role",
            customer_id=session.customer_id,
            role=session.role,
            expected="agent",
        )
        raise HTTPException(status_code=403, detail="agent_role_required")
    return session


def require_admin_or_local(
    x_admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
    store: Annotated[BankStore, Depends(get_store)] = None,  # type: ignore[assignment]
) -> None:
    """Protege rutas administrativas y sandbox en entornos cloud (SOFIA_ENV=cloud).

    En cloud, sólo se permite acceso si ADMIN_API_KEY está configurada y coincide
    con el header X-Admin-Key. En local/test, se permite acceso irrestricto salvo que
    se configure explícitamente ADMIN_API_KEY y no coincida.
    """
    store = store or get_store()
    settings = store.settings
    is_cloud = settings.SOFIA_ENV.lower() in ("cloud", "production", "prod")
    if is_cloud:
        if not settings.ADMIN_API_KEY or x_admin_key != settings.ADMIN_API_KEY:
            audit_trail.record("admin_access_forbidden", reason="cloud_restricted")
            raise HTTPException(
                status_code=403,
                detail="Admin and test endpoints are restricted in cloud environment",
            )

