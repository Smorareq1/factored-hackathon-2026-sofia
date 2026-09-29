"""§9.7 (propuesto por AG) Contrato agente ↔ frontend: eventos de capa y payloads del SSE de `/v1/chat`.

Los eventos son registros de ejecución (`code` + `params`), no texto de un LLM: el frontend los traduce
y la caja de cristal los dibuja (REQ-19). Cada evento corresponde también a un span de Langfuse (§9.6).

SSE de `POST /v1/chat`:
    event: layer    data: LayerEvent
    event: message  data: AgentMessage
    event: handoff  data: Handoff
    event: done     data: TurnDone
    event: error    data: TurnError
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, JsonValue

from sofia_contracts.common import Language, Route, SystemVersion

Layer = Literal["PURPOSE", "SENSE", "INTERPRET", "DECIDE", "ORCHESTRATE", "GOVERN", "LEARN"]
EventStatus = Literal["ok", "warn", "error", "skipped"]
GoalStatus = Literal["open", "resolved", "escalated", "abstained", "denied"]


class LayerEvent(BaseModel):
    turn: int
    layer: Layer
    node: str
    status: EventStatus = "ok"
    code: str
    params: dict[str, JsonValue] = Field(default_factory=dict)
    started_at: datetime
    duration_ms: int = 0
    span_id: str | None = None


class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    message: str = Field(min_length=1, max_length=2000)
    language_hint: Language | None = None
    system_version: SystemVersion = "proposed"


class TransactionCard(BaseModel):
    """Transacción tal como la devolvió la API, ya formateada para el idioma del cliente (no la escribe el LLM)."""

    transaction_id: str
    date: str
    merchant: str
    amount: Decimal
    currency: str
    amount_display: str


class CandidateCard(TransactionCard):
    """Transacción candidata cuando INTERPRET necesita aclarar."""

    option: int


class CaseCard(BaseModel):
    """Disputa leída de la API (REQ-09: `verified` solo es true si se releyó después de crearla)."""

    dispute_id: str
    status: str
    status_display: str
    verified: bool


class AgentMessage(BaseModel):
    """Texto para el cliente + los mismos datos en estructura para la UI (el harness solo lee `text`)."""

    text: str
    language: Language
    route: Route | None = None
    quick_replies: list[str] = Field(default_factory=list)
    candidates: list[CandidateCard] = Field(default_factory=list)
    subject: TransactionCard | None = None  # la transacción de la que habla el mensaje
    case: CaseCard | None = None


class TurnDone(BaseModel):
    turn: int
    route: Route | None
    goal_status: GoalStatus | None
    latency_ms: int
    trace_id: str | None = None


class TurnError(BaseModel):
    code: str
    message: str
