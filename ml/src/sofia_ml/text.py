"""Router text normalization. Same logic as `sofia_agent.text` (ml does not depend on the agent)."""

import re
import unicodedata

_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def fold(text: str) -> str:
    """Lowercase without accents, to compare ES/PT regardless of the customer's spelling."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def words(text: str) -> list[str]:
    return _WORD.findall(fold(text))
