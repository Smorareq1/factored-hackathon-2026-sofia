"""§9.6 Convención de trazas de Langfuse: OPS define, todos usan.

Cada conversación = 1 trace; cada nodo del grafo y cada tool call = 1 span.
Propuesta AG #12: se suman `purpose_version` (en la traza) y `layer` (en cada span).
"""

from pydantic import BaseModel

from sofia_contracts.common import Language, SystemVersion


class TraceMetadata(BaseModel):
    session_id: str
    case_id: str | None = None
    language: Language
    system_version: SystemVersion
    prompt_version: str
    purpose_version: str
    model: str
    router_version: str | None = None


# Atributo que cada span de nodo lleva para filtrar por capa en Langfuse.
SPAN_LAYER_ATTRIBUTE = "layer"
