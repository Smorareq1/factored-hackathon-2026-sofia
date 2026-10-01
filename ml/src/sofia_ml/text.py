"""Normalización de texto del router. Misma lógica que `sofia_agent.text` (ml no depende del agente)."""

import re
import unicodedata

_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def fold(text: str) -> str:
    """Minúsculas sin tildes, para comparar ES/PT sin depender de la ortografía del cliente."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def words(text: str) -> list[str]:
    return _WORD.findall(fold(text))
