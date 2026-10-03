"""Sessión de prueba + OTP simulado; token ligado a customer_id con expiración (REQ-11)."""

from sofia_services.auth.service import (
    get_current_session,
    harness_session,
    require_agent,
    require_customer,
    start_session,
    verify_session,
)

__all__ = [
    "get_current_session",
    "harness_session",
    "require_agent",
    "require_customer",
    "start_session",
    "verify_session",
]
