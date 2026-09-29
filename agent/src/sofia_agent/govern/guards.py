"""Guardas de salida: grounding check del borrador del LLM y guardia del texto final.

El grounding check es lo que hace cumplir REQ-08 por construcción: el LLM solo puede referirse a datos
mediante placeholders, así que cualquier dígito literal, placeholder desconocido u obligatorio ausente
invalida el borrador y se usa la plantilla determinística.
"""

import re
from dataclasses import dataclass

from sofia_agent.llm import CANARY
from sofia_agent.sense.language import detect_language
from sofia_contracts.common import Language

PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+\.[a-z_]+)\s*\}\}")
_DIGIT = re.compile(r"\d")
_CUSTOMER_ID = re.compile(r"\b[CA]\d{8}\b", re.IGNORECASE)
_CARD_NUMBER = re.compile(r"\b(?:\d[ -]?){13,19}\b")
MAX_DRAFT_CHARS = 600


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reason: str | None = None
    detail: str | None = None


def grounding_check(draft: str, *, allowed: set[str], required: set[str], language: Language) -> GuardResult:
    if CANARY in draft:
        return GuardResult(False, "canary_leak")
    if len(draft) > MAX_DRAFT_CHARS:
        return GuardResult(False, "too_long", str(len(draft)))
    used = set(PLACEHOLDER.findall(draft))
    if unknown := used - allowed:
        return GuardResult(False, "unknown_placeholder", ",".join(sorted(unknown)))
    if missing := required - used:
        return GuardResult(False, "missing_placeholder", ",".join(sorted(missing)))
    bare = PLACEHOLDER.sub(" ", draft)
    if "{" in bare or "}" in bare:
        return GuardResult(False, "malformed_placeholder")
    if _DIGIT.search(bare):
        return GuardResult(False, "literal_number")
    guess = detect_language(bare, fallback=language)
    if guess.decided and guess.language != language and guess.confidence >= 0.7:
        return GuardResult(False, "language_mismatch", guess.language)
    return GuardResult(True)


def output_guard(text: str, *, session_customer_id: str | None) -> GuardResult:
    """Última barrera antes de mostrar el texto: IDs de otros clientes, números de tarjeta, canario."""
    if CANARY in text:
        return GuardResult(False, "canary_leak")
    foreign = {m.upper() for m in _CUSTOMER_ID.findall(text)} - {(session_customer_id or "").upper()}
    if foreign:
        return GuardResult(False, "foreign_customer_id")
    if _CARD_NUMBER.search(text):
        return GuardResult(False, "card_number")
    return GuardResult(True)
