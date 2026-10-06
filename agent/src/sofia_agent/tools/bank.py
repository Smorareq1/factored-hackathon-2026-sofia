"""Cliente tipado de la API bancaria de SIM (§9.2).

- El token del cliente viaja en cada request y nunca se guarda en el checkpointer.
- 401 → `SessionExpiredError` (ruta reauth). 404 → `None` (no se distingue "no existe" de "no es tuyo").
- 5xx / timeout → reintento acotado con backoff; al agotarse, `ToolUnavailableError` (fallback seguro).
- Las acciones (crear disputa, crear handoff) solo se permiten desde su nodo (allowlist de GOVERN).
- Cada intento queda registrado como `ToolCallRecord` (auditoría) y como span `tool` en la traza (§9.6).
"""

import asyncio
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from sofia_agent import tracing
from sofia_agent.govern.context import ACTION_ALLOWLIST, CURRENT_NODE, ToolNotAllowedError
from sofia_contracts.bank_api import (
    CustomerClaim,
    DemoCustomer,
    Dispute,
    DisputeCreate,
    DisputeList,
    Eligibility,
    EligibilityRequest,
    HandoffList,
    HandoffReceipt,
    HarnessSessionRequest,
    SessionChallenge,
    SessionInfo,
    SessionStart,
    SessionToken,
    SessionVerify,
    Transaction,
    TransactionList,
)
from sofia_contracts.eval_case import ToolCallRecord
from sofia_contracts.handoff import Handoff, HandoffDraft, HandoffFeedback, HandoffFeedbackRecord


class SessionExpiredError(Exception):
    """La API respondió 401: sesión inválida o expirada."""


class ToolUnavailableError(Exception):
    """La tool falló (5xx, timeout, red) después de los reintentos."""

    def __init__(self, method: str, path: str, detail: str) -> None:
        super().__init__(f"{method} {path}: {detail}")
        self.method, self.path, self.detail = method, path, detail


class ToolRejectedError(Exception):
    """La API rechazó la llamada (403, 409, 422): la regla vive en SIM, no se reintenta."""

    def __init__(self, method: str, path: str, status: int, detail: str) -> None:
        super().__init__(f"{method} {path} → {status} {detail}")
        self.method, self.path, self.status, self.detail = method, path, status, detail


class BankClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        token: str | None,
        *,
        max_retries: int = 2,
        backoff_s: float = 0.2,
        enforce_allowlist: bool = True,
        admin_key: str | None = None,
    ) -> None:
        self._http = http
        self._token = token
        self._admin_key = admin_key
        self._max_retries = max_retries
        self._backoff_s = backoff_s
        # El baseline de sistema (§8.7) corre SIN esta guarda: es parte de lo que se compara.
        self._enforce_allowlist = enforce_allowlist
        self._records: list[ToolCallRecord] = []

    # ───────────────────────── infraestructura ─────────────────────────
    def drain(self) -> list[ToolCallRecord]:
        """Devuelve y limpia las tool calls registradas desde la última vez."""
        records, self._records = self._records, []
        return records

    async def _call(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        headers: dict[str, str] | None = None,
        action: str | None = None,
        record: bool = True,
    ) -> httpx.Response | None:
        node = CURRENT_NODE.get() or "-"
        if self._enforce_allowlist and action is not None and node not in ACTION_ALLOWLIST[action]:
            raise ToolNotAllowedError(f"{node} no puede ejecutar {action}")
        request_headers = dict(headers or {})
        if self._token:
            request_headers["Authorization"] = f"Bearer {self._token}"

        for attempt in range(1, self._max_retries + 2):
            started = time.perf_counter()
            status: int | None = None
            error: str | None = None
            span_fields: dict[str, Any] = {"metadata": {"node": node, "attempt": attempt}, "input": params or None}
            with tracing.observe(f"{method} {path}", as_type="tool", **span_fields) if record else _no_span() as span:
                try:
                    response = await self._http.request(method, path, json=json, params=params, headers=request_headers)
                    status = response.status_code
                except httpx.HTTPError as exc:
                    error = type(exc).__name__
                    response = None
                finally:
                    if record:
                        self._records.append(
                            ToolCallRecord(
                                node=node,
                                method=method,
                                path=path,
                                status=status,
                                duration_ms=int((time.perf_counter() - started) * 1000),
                                attempt=attempt,
                                error=error,
                            )
                        )
                failed = status is None or status >= 500
                tracing.update(
                    span,
                    output={"http_status": status, "error": error},
                    level="ERROR" if failed else "WARNING" if status and status >= 400 else "DEFAULT",
                )

            if response is not None and status is not None and status < 500:
                if status == 401:
                    raise SessionExpiredError(path)
                if status == 404:
                    return None
                if status >= 400:
                    raise ToolRejectedError(method, path, status, _detail(response))
                return response
            if attempt <= self._max_retries:
                await asyncio.sleep(self._backoff_s * 2 ** (attempt - 1))
        raise ToolUnavailableError(method, path, error or f"HTTP {status}")

    # ───────────────────────── sesión ─────────────────────────
    async def harness_session(self, customer_id: str) -> SessionToken:
        """Solo sandbox: sesión directa para el cliente de un caso de evaluación (§9.5)."""
        body = HarnessSessionRequest(customer_id=customer_id)
        headers = {"X-Admin-Key": self._admin_key} if self._admin_key else None
        response = await self._call("POST", "/session/test", json=body.model_dump(), headers=headers, record=False)
        if response is None:
            raise ToolRejectedError("POST", "/session/test", 404, "customer_not_found")
        return SessionToken.model_validate(response.json())

    async def session_me(self) -> SessionInfo:
        response = await self._call("GET", "/session/me")
        if response is None:
            raise SessionExpiredError("/session/me")
        return SessionInfo.model_validate(response.json())

    # ───────────────────────── lecturas ─────────────────────────
    async def list_transactions(
        self,
        *,
        since: date | None = None,
        until: date | None = None,
        merchant: str | None = None,
        amount: Decimal | None = None,
        limit: int = 50,
    ) -> list[Transaction]:
        params = {
            k: v
            for k, v in {
                "since": since,
                "until": until,
                "merchant": merchant,
                "amount": amount,
                "limit": limit,
            }.items()
            if v is not None
        }
        response = await self._call("GET", "/transactions", params={k: str(v) for k, v in params.items()})
        return TransactionList.model_validate(response.json()).items if response else []

    async def get_transaction(self, transaction_id: str) -> Transaction | None:
        response = await self._call("GET", f"/transactions/{transaction_id}")
        return Transaction.model_validate(response.json()) if response else None

    async def check_eligibility(self, transaction_id: str, claim: CustomerClaim | None) -> Eligibility:
        body = EligibilityRequest(transaction_id=transaction_id, customer_claim=claim)
        response = await self._call("POST", "/disputes/eligibility", json=body.model_dump(mode="json"))
        if response is None:
            # La API no distingue 404 de "no es tuyo": se trata como POL-1.
            return Eligibility(eligible=False, rule_id="POL-1", reason="transaction_not_accessible", route="deny")
        return Eligibility.model_validate(response.json())

    async def get_dispute(self, dispute_id: str) -> Dispute | None:
        response = await self._call("GET", f"/disputes/{dispute_id}")
        return Dispute.model_validate(response.json()) if response else None

    async def list_disputes(self, status: str | None = None) -> list[Dispute]:
        response = await self._call("GET", "/disputes", params={"status": status} if status else None)
        return DisputeList.model_validate(response.json()).items if response else []

    async def get_handoff(self, handoff_id: str) -> Handoff | None:
        response = await self._call("GET", f"/handoffs/{handoff_id}")
        return Handoff.model_validate(response.json()) if response else None

    # ───────────────────────── acciones (allowlist) ─────────────────────────
    async def create_dispute(self, body: DisputeCreate, idempotency_key: str) -> Dispute:
        response = await self._call(
            "POST",
            "/disputes",
            json=body.model_dump(mode="json"),
            headers={"Idempotency-Key": idempotency_key},
            action="create_dispute",
        )
        if response is None:
            raise ToolRejectedError("POST", "/disputes", 404, "not_found")
        return Dispute.model_validate(response.json())

    async def create_handoff(self, draft: HandoffDraft, idempotency_key: str) -> HandoffReceipt:
        response = await self._call(
            "POST",
            "/handoff",
            json=draft.model_dump(mode="json"),
            headers={"Idempotency-Key": idempotency_key},
            action="create_handoff",
        )
        if response is None:
            raise ToolRejectedError("POST", "/handoff", 404, "not_found")
        return HandoffReceipt.model_validate(response.json())

    # ───────────────────────── proxy para el frontend (fuera del grafo) ─────────────────────────
    async def demo_customers(self) -> list[DemoCustomer]:
        response = await self._call("GET", "/demo/customers", record=False)
        return [DemoCustomer.model_validate(c) for c in response.json()] if response else []

    async def start_session(self, body: SessionStart) -> SessionChallenge:
        response = await self._call("POST", "/session", json=body.model_dump(), record=False)
        if response is None:
            raise ToolRejectedError("POST", "/session", 404, "not_found")
        return SessionChallenge.model_validate(response.json())

    async def verify_session(self, body: SessionVerify) -> SessionToken:
        response = await self._call("POST", "/session/verify", json=body.model_dump(), record=False)
        if response is None:
            raise ToolRejectedError("POST", "/session/verify", 404, "not_found")
        return SessionToken.model_validate(response.json())

    async def list_handoffs(self) -> list[Handoff]:
        response = await self._call("GET", "/handoffs", record=False)
        return HandoffList.model_validate(response.json()).items if response else []

    async def read_handoff(self, handoff_id: str) -> Handoff | None:
        response = await self._call("GET", f"/handoffs/{handoff_id}", record=False)
        return Handoff.model_validate(response.json()) if response else None

    async def send_feedback(self, handoff_id: str, feedback: HandoffFeedback) -> HandoffFeedbackRecord | None:
        response = await self._call(
            "POST", f"/handoffs/{handoff_id}/feedback", json=feedback.model_dump(mode="json"), record=False
        )
        return HandoffFeedbackRecord.model_validate(response.json()) if response else None

    async def read_feedback(self, handoff_id: str) -> HandoffFeedbackRecord | None:
        response = await self._call("GET", f"/handoffs/{handoff_id}/feedback", record=False)
        return HandoffFeedbackRecord.model_validate(response.json()) if response else None


@contextmanager
def _no_span() -> Iterator[None]:
    yield None


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    return str(body.get("detail", body))[:200] if isinstance(body, dict) else str(body)[:200]
