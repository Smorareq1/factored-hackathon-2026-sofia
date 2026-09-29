"""Normalización del mensaje: largo máximo, caracteres de control, zero-width y homoglifos."""

import re
import unicodedata

_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES = re.compile(r"[ \t]+")
# Letras cirílicas o griegas mezcladas con latinas: truco típico para evadir filtros.
_NON_LATIN_LETTERS = re.compile(r"[\u0370-\u03ff\u0400-\u04ff]")


def normalize_message(text: str, max_chars: int) -> tuple[str, list[str]]:
    """Devuelve el texto limpio y las anomalías encontradas (se registran como señales)."""
    flags: list[str] = []
    clean = unicodedata.normalize("NFKC", text)
    if _ZERO_WIDTH.search(clean):
        flags.append("hidden_characters")
        clean = _ZERO_WIDTH.sub("", clean)
    clean = _CONTROL.sub("", clean)
    if _NON_LATIN_LETTERS.search(clean):
        flags.append("non_latin_script")
    clean = "\n".join(_SPACES.sub(" ", line).strip() for line in clean.splitlines()).strip()
    if len(clean) > max_chars:
        flags.append("truncated")
        clean = clean[:max_chars]
    return clean, flags
