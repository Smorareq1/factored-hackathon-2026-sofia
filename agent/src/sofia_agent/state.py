"""AgentState y modelos auxiliares del grafo.

`verified_facts` es la columna vertebral: solo entra ahí lo que devolvió una tool o una regla de
política, siempre con su `source`. La redacción, el handoff y la caja de cristal leen de ahí (REQ-08).
"""

import operator
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel

from sofia_contracts.bank_api import CustomerClaim, Eligibility, SessionInfo
from sofia_contracts.common import Language, Route, SystemVersion
from sofia_contracts.eval_case import ToolCallRecord
from sofia_contracts.events import AgentMessage, CandidateCard, CaseCard, GoalStatus, LayerEvent, TransactionCard
from sofia_contracts.handoff import Handoff, HandoffAction, HandoffFact
from sofia_contracts.router import Intent, IntentPrediction

FactKind = Literal["money", "text", "date", "id", "rule", "tx_status", "dispute_status"]
Confirmation = Literal["yes", "no", "none"]


class Versions(BaseModel):
    purpose: str
    prompts: str
    model: str
    router: str | None = None


class ConversationGoal(BaseModel):
    """PURPOSE dinámico: qué quiere lograr el cliente y en qué estado está."""

    type: Intent
    status: GoalStatus = "open"
    target_ref: str | None = None
    opened_turn: int


class RiskSignal(BaseModel):
    code: str  # prompt_injection_suspected | mixed_language | foreign_customer_id | ...
    evidence: str | None = None


class Slots(BaseModel):
    """Datos acumulados entre turnos (REQ-07). Un valor nuevo explícito pisa al anterior."""

    transaction_id: str | None = None
    amount: Decimal | None = None
    currency: Literal["MXN", "COP", "ARS", "USD"] | None = None
    merchant: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    customer_claim: CustomerClaim | None = None
    dispute_id: str | None = None


class TurnReading(BaseModel):
    """Lo que el turno actual dice más allá de los slots; no se acumula."""

    confirmation: Confirmation = "none"
    wants_human: bool = False
    selection: int | None = None  # "la segunda" → 2 cuando hay candidatos listados


class TxRef(BaseModel):
    transaction_id: str
    date: datetime
    amount: Decimal
    currency: str
    amount_usd: Decimal
    merchant: str
    status: str


class DisputeRef(BaseModel):
    dispute_id: str
    transaction_id: str
    status: str
    verified: bool = False


class VerifiedFact(BaseModel):
    key: str  # tx.amount, tx.merchant, case.id, handoff.id…
    kind: FactKind
    value: str  # canónico: Decimal como str, fechas ISO
    currency: str | None = None
    fact: str  # frase para el handoff (es la lengua de trabajo del back office)
    source: str  # "GET /transactions/TX123", "POL-6"
    turn: int


class ActionRecord(BaseModel):
    action: str
    result: str
    verified: bool
    turn: int


class ChatTurn(BaseModel):
    role: Literal["customer", "agent"]
    text: str
    turn: int


class Fault(BaseModel):
    code: str  # session_expired | tool_unavailable | verification_failed | llm_unavailable…
    node: str
    detail: str | None = None


def events_of_turn(left: list[LayerEvent] | None, right: list[LayerEvent] | None) -> list[LayerEvent]:
    """Reducer: los eventos se acumulan dentro de un turno y se reinician al empezar el siguiente."""
    left, right = left or [], right or []
    if left and right and right[0].turn != left[-1].turn:
        return list(right)
    return left + right


def facts_by_key(left: list[VerifiedFact] | None, right: list[VerifiedFact] | None) -> list[VerifiedFact]:
    """Reducer: un hecho nuevo con la misma clave reemplaza al anterior (conserva el orden de llegada)."""
    merged = {f.key: f for f in (left or [])}
    for fact in right or []:
        merged.pop(fact.key, None)
        merged[fact.key] = fact
    return list(merged.values())


class AgentState(TypedDict, total=False):
    # --- identidad y versión ---
    thread_id: str
    session: SessionInfo | None  # customer_id SIEMPRE del token (vía SIM), nunca del texto
    owner_customer_id: str  # el hilo queda ligado al cliente del primer turno
    system_version: SystemVersion
    versions: Versions

    # --- PURPOSE dinámico ---
    goal: ConversationGoal | None

    # --- SENSE ---
    turn: int
    message: str
    language_hint: Language | None
    language: Language
    language_confidence: float
    signals: list[RiskSignal]

    # --- INTERPRET ---
    intent: IntentPrediction | None
    slots: Slots
    reading: TurnReading
    candidates: list[TxRef]
    selected_tx: TxRef | None
    unverified_tx_id: str | None  # ID que dio el cliente y la API no devolvió: eligibility decide (POL-1)
    clarifications: int
    clarify_reason: str | None
    messages: Annotated[list[ChatTurn], operator.add]  # nunca va al handoff (REQ-05)

    # --- DECIDE ---
    eligibility: Eligibility | None
    pending_confirmation: bool
    offered_human: bool  # se ofreció un humano (abstención, POL-3); el próximo sí/no responde a eso
    ready_to_act: bool
    route: Route | None
    situation: str | None  # clave de la respuesta: confirm_request, dispute_created, deny_POL-2…
    handoff_reason: str | None

    # --- ORCHESTRATE ---
    dispute: DisputeRef | None
    disputes_listed: list[DisputeRef]
    handoff: Handoff | None
    verified_facts: Annotated[list[VerifiedFact], facts_by_key]
    actions_taken: Annotated[list[ActionRecord], operator.add]
    response: AgentMessage | None

    # --- GOVERN ---
    llm_calls: int
    tool_log: Annotated[list[ToolCallRecord], operator.add]
    events: Annotated[list[LayerEvent], events_of_turn]
    fault: Fault | None


# Campos que se reinician al empezar cada turno (el resto persiste en el checkpointer).
PER_TURN_RESET: dict[str, object] = {
    "route": None,
    "situation": None,
    "clarify_reason": None,
    "handoff_reason": None,
    "response": None,
    "fault": None,
    "llm_calls": 0,
    "signals": [],
    "reading": TurnReading(),
    "intent": None,
    "disputes_listed": [],
    "ready_to_act": False,
}

# Modelos que el checkpointer puede deserializar (allowlist estricta, sin pickle).
CHECKPOINT_MODELS: tuple[type[BaseModel], ...] = (
    Versions,
    ConversationGoal,
    RiskSignal,
    Slots,
    TurnReading,
    TxRef,
    DisputeRef,
    VerifiedFact,
    ActionRecord,
    ChatTurn,
    Fault,
    SessionInfo,
    Eligibility,
    IntentPrediction,
    Handoff,
    HandoffFact,
    HandoffAction,
    AgentMessage,
    CandidateCard,
    TransactionCard,
    CaseCard,
    LayerEvent,
    ToolCallRecord,
)
