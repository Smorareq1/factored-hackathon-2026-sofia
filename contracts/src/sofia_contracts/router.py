"""§9.3 Router: predict(text, language_hint) -> {intent, confidence, language}. DS produce, AG consume.

Propuesta AG #11: la predicción suma `router_version` y `language_confidence`.
Propuesta AG #13: además de la interfaz Python, el router corre como servicio HTTP (`POST /predict`).
"""

from typing import Literal

from pydantic import BaseModel, Field

from sofia_contracts.common import Language

Intent = Literal["dispute_new", "dispute_status", "transaction_inquiry", "out_of_scope", "needs_human"]
IN_SCOPE_INTENTS: tuple[Intent, ...] = ("dispute_new", "dispute_status", "transaction_inquiry")


class RouterRequest(BaseModel):
    text: str
    language_hint: Language | None = None


class IntentPrediction(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0, le=1)
    language: Language
    language_confidence: float | None = Field(default=None, ge=0, le=1)
    router_version: str | None = None
