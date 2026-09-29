"""§9.5 Caso de evaluación: SIM y DS producen, el harness consume.

Propuesta AG #8: el harness llama `run_conversation(case, system_version) -> ConversationResult` en proceso
(`sofia_agent.runner`). Propuesta AG #17: `ToolCallRecord.turn`, `unverified_claims` y `foreign_references`
(campos opcionales, compatibles hacia atrás) para medir MET-04 sin releer el transcript.
"""

from typing import Literal

from pydantic import BaseModel, Field

from sofia_contracts.common import Language, Route, SystemVersion
from sofia_contracts.handoff import Handoff

CaseType = Literal["normal", "ambiguous", "human", "out_of_scope", "adversarial"]
Origin = Literal["real", "de_identified", "synthetic", "team_generated"]


class InjectedFault(BaseModel):
    """Falla controlada antes de un turno (nivel 5). Propuesta AG #15: SIM la aplica en su API; el banco falso
    del agente la aplica en proceso.

    - `http_error`: los próximos `times` llamados a `endpoint` ("POST /disputes/eligibility") devuelven `status`.
    - `session_expired`: la sesión vence antes del turno.
    - `drop_writes`: `POST /disputes` responde ok pero no persiste (prueba de VERIFY).
    """

    before_turn: int = Field(default=1, ge=1)
    kind: Literal["http_error", "session_expired", "drop_writes"]
    endpoint: str | None = None
    status: int = 500
    times: int = Field(default=1, ge=1)


class EvalCase(BaseModel):
    case_id: str
    language: Language
    type: CaseType
    level: int = Field(ge=1, le=5)
    session_customer_id: str
    turns: list[str]
    expected_route: Route
    expected_handoff_fields: list[str] = Field(default_factory=list)
    must_not: list[str] = Field(default_factory=list)
    origin: Origin
    faults: list[InjectedFault] = Field(default_factory=list)


class ToolCallRecord(BaseModel):
    node: str
    method: str
    path: str
    status: int | None
    duration_ms: int
    attempt: int = 1
    error: str | None = None
    turn: int | None = None


class TurnResult(BaseModel):
    turn: int
    user: str
    agent: str
    route: Route | None


class ConversationResult(BaseModel):
    case_id: str
    system_version: SystemVersion
    route_final: Route | None
    routes_per_turn: list[Route | None]
    goal_status: str | None
    turns: list[TurnResult]
    tool_calls: list[ToolCallRecord]
    handoff: Handoff | None = None
    trace_id: str | None = None
    latency_ms: int
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float | None = None
    errors: list[str] = Field(default_factory=list)
    # MET-04: IDs de caso/handoff que el agente afirmó y la API no devuelve (resultado materialmente incorrecto).
    unverified_claims: list[str] = Field(default_factory=list)
    # MET-04: IDs de otro cliente que el agente mencionó sin que el cliente los haya escrito (divulgación).
    foreign_references: list[str] = Field(default_factory=list)
