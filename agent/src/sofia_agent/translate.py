"""Traducción ES → PT de casos de evaluación (set PT `team_generated`; §8.5: revisión humana después).

Antes de salir a Gemini se enmascaran los IDs (clientes, transacciones, casos, handoffs, elegibilidades): el
modelo solo ve ⟦0⟧, ⟦1⟧… y el script los restituye. Los casos son sintéticos del equipo, pero igual se
minimiza lo que sale del proceso (CON-03). Si un marcador se pierde o cambia la cantidad de turnos, el caso
se descarta en vez de guardarse roto.
"""

import re
from collections.abc import Sequence

from pydantic import BaseModel, Field

from sofia_contracts.eval_case import EvalCase

ID_PATTERN = re.compile(
    r"\b(?:[CA]\d{8}|TX-[A-Z]{2}-\d{4}|TX\d{6,}|TRX-?\d{6,}|DSP-\d{4}-\d{6}|HO-\d{4}-\d{6}|ELG-[0-9a-f]{6,})\b"
)
_MARKER = re.compile(r"⟦(\d+)⟧")

SYSTEM_PROMPT = (
    "Traduces mensajes de clientes de un banco del español al portugués de Brasil. Conserva el tono "
    "(coloquial, apurado, molesto), los errores de tipeo naturales y la intención; no agregues ni quites "
    "información. Los marcadores ⟦n⟧ son identificadores: cópialos tal cual, sin traducirlos ni moverlos "
    "de lugar en la frase. Devuelve exactamente la misma cantidad de mensajes, en el mismo orden."
)


class Translation(BaseModel):
    turns: list[str] = Field(description="Un mensaje traducido por cada mensaje de entrada, en orden")


class TranslationError(ValueError):
    """La traducción no conserva los turnos o los marcadores: el caso no se guarda."""


def mask_ids(texts: Sequence[str]) -> tuple[list[str], list[str]]:
    """Reemplaza cada ID por ⟦n⟧ (el mismo ID → el mismo n en todos los turnos)."""
    ids: list[str] = []

    def replace(match: re.Match[str]) -> str:
        if match.group(0) not in ids:
            ids.append(match.group(0))
        return f"⟦{ids.index(match.group(0))}⟧"

    return [ID_PATTERN.sub(replace, text) for text in texts], ids


def unmask_ids(texts: Sequence[str], ids: Sequence[str]) -> list[str]:
    def restore(match: re.Match[str]) -> str:
        index = int(match.group(1))
        if index >= len(ids):
            raise TranslationError(f"marcador desconocido ⟦{index}⟧")
        return ids[index]

    return [_MARKER.sub(restore, text) for text in texts]


def check_translation(masked: Sequence[str], translated: Sequence[str]) -> None:
    if len(translated) != len(masked):
        raise TranslationError(f"{len(masked)} turnos de entrada, {len(translated)} de salida")
    for source, target in zip(masked, translated, strict=True):
        if sorted(_MARKER.findall(source)) != sorted(_MARKER.findall(target)):
            raise TranslationError(f"marcadores alterados en: {target[:80]!r}")


def translated_case(case: EvalCase, turns: list[str]) -> EvalCase:
    must_not = [*case.must_not, *(["respond_wrong_language"] if "respond_wrong_language" not in case.must_not else [])]
    return case.model_copy(
        update={
            "case_id": f"{case.case_id}-pt",
            "language": "pt",
            "turns": turns,
            "must_not": must_not,
            "origin": "team_generated",
        }
    )
