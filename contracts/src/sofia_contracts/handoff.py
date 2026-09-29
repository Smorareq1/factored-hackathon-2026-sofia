"""§9.4 Handoff JSON: AG produce, SIM almacena, frontend muestra. Nunca incluye el transcript (REQ-05).

Propuesta AG #9 para el D1: se suman `schema_version`, `created_at`, `system_version` y `customer_claim`.
`HandoffDraft` es lo que el agente envía a `POST /handoff`; SIM asigna `handoff_id` y `created_at`.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from sofia_contracts.common import Language, SystemVersion

HANDOFF_SCHEMA_VERSION = "1.0"


class HandoffFact(BaseModel):
    fact: str
    source: str = Field(description="Tool call o regla que respalda el hecho: 'GET /transactions/TX123', 'POL-6'")


class HandoffAction(BaseModel):
    action: str
    result: str
    verified: bool


class HandoffDraft(BaseModel):
    # extra=forbid: nadie puede colar un campo `transcript` o `messages` (REQ-05).
    model_config = ConfigDict(extra="forbid")

    schema_version: str = HANDOFF_SCHEMA_VERSION
    language: Language
    customer_id: str
    authenticated: bool
    request_summary: str
    customer_claim: str | None = None
    verified_facts: list[HandoffFact]
    actions_taken: list[HandoffAction]
    open_questions: list[str]
    risk_flags: list[str]
    reason_for_handoff: str = Field(description="Regla (POL-6, POL-7) o causa operativa (verification_failed…)")
    system_version: SystemVersion = "proposed"
    trace_id: str | None = None


class Handoff(HandoffDraft):
    handoff_id: str
    created_at: datetime


class HandoffFeedback(BaseModel):
    """LEARN: juicio del agente humano sobre la ficha (score `handoff_quality` en Langfuse)."""

    useful: bool
    missing_fields: list[str] = Field(default_factory=list)
    comment: str | None = Field(default=None, max_length=500)


class HandoffFeedbackRecord(HandoffFeedback):
    """Feedback guardado junto al handoff (SIM) y enviado como score a la traza de la conversación."""

    handoff_id: str
    reviewer_id: str
    submitted_at: datetime
