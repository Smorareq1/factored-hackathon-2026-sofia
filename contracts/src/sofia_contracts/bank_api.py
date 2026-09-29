"""§9.2 Requests/responses de la API bancaria simulada: SIM produce, AG consume.

Borrador de AG para la reunión del D1: incluye las propuestas #1–#6 del plan de AG (eligibility_id,
Idempotency-Key, GET /session/me, GET /disputes, handoff asignado por SIM, clientes demo con OTP).

| Método y ruta                   | Auth           | Request               | Response            |
|---------------------------------|----------------|-----------------------|---------------------|
| POST /session                   | —              | SessionStart          | SessionChallenge    |
| POST /session/verify            | —              | SessionVerify         | SessionToken        |
| GET  /session/me                | token          | —                     | SessionInfo         |
| GET  /transactions              | token          | ?since&until&merchant | TransactionList     |
| GET  /transactions/{id}         | token          | —                     | Transaction (404 si no es del cliente) |
| POST /disputes/eligibility      | token          | EligibilityRequest    | Eligibility         |
| POST /disputes                  | token + Idempotency-Key | DisputeCreate | Dispute             |
| GET  /disputes                  | token          | ?status               | DisputeList         |
| GET  /disputes/{id}             | token          | —                     | Dispute             |
| POST /handoff                   | token + Idempotency-Key | HandoffDraft  | HandoffReceipt      |
| GET  /handoffs/{id}             | token          | —                     | Handoff             |
| GET  /handoffs                  | token rol agent | —                    | HandoffList         |
| POST /handoffs/{id}/feedback    | token rol agent | HandoffFeedback      | HandoffFeedbackRecord (LEARN, #16) |
| GET  /handoffs/{id}/feedback    | token rol agent | —                    | HandoffFeedbackRecord |
| POST /session/test              | — (solo sandbox) | HarnessSessionRequest | SessionToken (harness, #15) |

Errores: 401 sesión inválida o expirada · 403 rol insuficiente · 404 no existe o no es del cliente
(no se distingue, POL-1) · 409 conflicto (disputa duplicada, eligibility vencido) · 422 request inválido.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from sofia_contracts.common import Country, Currency, PolicyRoute, RuleId
from sofia_contracts.handoff import Handoff

Role = Literal["customer", "agent"]
TransactionStatus = Literal["Approved", "Declined", "Pending", "Reversed"]
CustomerClaim = Literal["not_recognized", "duplicate", "wrong_amount", "not_received", "other"]
DisputeStatus = Literal["open", "in_review", "resolved", "rejected"]


# ───────────────────────── Sesión (REQ-11) ─────────────────────────
class SessionStart(BaseModel):
    """Paso 1: el número de documento solo NO basta; dispara un OTP simulado."""

    document_number: str


class SessionChallenge(BaseModel):
    challenge_id: str
    expires_at: datetime
    # Solo en el sandbox: el OTP que "llegaría por SMS", para mostrarlo en la demo.
    simulated_otp: str | None = None


class SessionVerify(BaseModel):
    challenge_id: str
    otp: str


class HarnessSessionRequest(BaseModel):
    """Solo sandbox/harness (propuesta AG #15): sesión directa para el `session_customer_id` de un caso §9.5.
    Deshabilitado en producción; la demo siempre usa documento + OTP."""

    customer_id: str


class SessionToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - tipo de token, no un secreto
    expires_at: datetime
    role: Role


class SessionInfo(BaseModel):
    """GET /session/me: el agente conoce al cliente sin manejar secretos de firma."""

    customer_id: str
    role: Role
    country: Country | None = None
    expires_at: datetime


class DemoCustomer(BaseModel):
    """Fixture de clientes demo (propuesta #6): sintéticos, etiquetados `team_generated`."""

    document_number: str
    label: str
    country: Country
    role: Role = "customer"


# ───────────────────────── Transacciones ─────────────────────────
class Transaction(BaseModel):
    transaction_id: str
    transaction_date: datetime
    amount: Decimal
    currency: Currency
    amount_usd: Decimal
    merchant_name: str
    transaction_status: TransactionStatus
    channel: str | None = None
    transaction_type: str | None = None


class TransactionList(BaseModel):
    items: list[Transaction]


# ───────────────────────── Disputas ─────────────────────────
class EligibilityRequest(BaseModel):
    transaction_id: str
    customer_claim: CustomerClaim | None = None


class Eligibility(BaseModel):
    """El motor de política vive en SIM; el agente solo lee `rule_id` y `reason` (REQ-10)."""

    eligible: bool
    rule_id: RuleId
    reason: str = Field(description="Código estable de la regla, p. ej. 'amount_over_threshold'")
    route: PolicyRoute
    # Solo si route == auto: prueba de que la elegibilidad se evaluó (propuesta #1). Tiene TTL.
    eligibility_id: str | None = None
    expires_at: datetime | None = None
    risk_flags: list[str] = Field(default_factory=list)
    # POL-4: número de caso ya abierto para esa transacción.
    existing_dispute_id: str | None = None


class ConfirmationProof(BaseModel):
    """Confirmación explícita del cliente previa a la acción (§9.2 `confirmation_id`)."""

    text: str
    turn: int
    confirmed_at: datetime


class DisputeCreate(BaseModel):
    transaction_id: str
    eligibility_id: str
    customer_claim: CustomerClaim | None = None
    confirmation: ConfirmationProof


class Dispute(BaseModel):
    dispute_id: str
    transaction_id: str
    customer_id: str
    status: DisputeStatus
    customer_claim: CustomerClaim | None = None
    created_at: datetime


class DisputeList(BaseModel):
    items: list[Dispute]


# ───────────────────────── Handoff ─────────────────────────
class HandoffReceipt(BaseModel):
    """SIM asigna el `handoff_id` (propuesta #5); el agente lo verifica con GET /handoffs/{id}."""

    handoff_id: str
    created_at: datetime


class HandoffList(BaseModel):
    items: list[Handoff]


class TransactionQuery(BaseModel):
    """Parámetros de GET /transactions. El monto se filtra del lado del agente."""

    since: date | None = None
    until: date | None = None
    merchant: str | None = None
    limit: int = Field(default=50, le=200)


class ApiError(BaseModel):
    code: str
    message: str
