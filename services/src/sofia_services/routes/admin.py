"""Rutas de administración y control de fallas para simulación y harness (REQ-15, REQ-16)."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from sofia_services.audit.logger import audit_trail
from sofia_services.auth.service import require_admin_or_local
from sofia_services.faults.manager import fault_manager
from sofia_services.store import get_store, reset_store

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_or_local)])


class HttpFaultRequest(BaseModel):
    method: str
    path: str
    status: int = 500
    times: int = Field(default=1, ge=1)


class LatencyFaultRequest(BaseModel):
    method: str
    path: str
    delay_s: float = Field(default=1.0, ge=0.0)
    times: int = Field(default=1, ge=1)


class DropWritesRequest(BaseModel):
    enabled: bool = True


@router.post("/faults/http")
def inject_http_fault(body: HttpFaultRequest) -> dict[str, Any]:
    fault_manager.inject_http_error(body.method, body.path, body.status, body.times)
    return {"status": "ok", "fault": body.model_dump()}


@router.post("/faults/latency")
def inject_latency_fault(body: LatencyFaultRequest) -> dict[str, Any]:
    fault_manager.inject_latency(body.method, body.path, body.delay_s, body.times)
    return {"status": "ok", "fault": body.model_dump()}


@router.post("/faults/drop-writes")
def set_drop_writes_fault(body: DropWritesRequest) -> dict[str, Any]:
    fault_manager.set_drop_writes(body.enabled)
    return {"status": "ok", "drop_writes": body.enabled}


@router.post("/faults/expire-sessions")
def expire_sessions() -> dict[str, str]:
    get_store().expire_all_sessions()
    return {"status": "ok", "message": "all_sessions_expired"}


@router.post("/faults/reset")
def reset_faults() -> dict[str, str]:
    fault_manager.reset()
    return {"status": "ok", "message": "faults_reset"}


@router.get("/audit")
def get_audit_trail(customer_id: str | None = None) -> list[dict[str, Any]]:
    return [r.to_dict() for r in audit_trail.list_records(customer_id)]


@router.post("/reset-store")
def reset_bank_store() -> dict[str, str]:
    reset_store()
    fault_manager.reset()
    audit_trail.clear()
    return {"status": "ok", "message": "store_reset"}
