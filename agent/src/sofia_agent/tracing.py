"""Trazas §9.6 en Langfuse (SDK v4, sobre OpenTelemetry).

- 1 conversación = 1 trace: el `trace_id` sale de una semilla estable (el `thread_id` en el chat, el caso +
  una corrida en el harness), así todos los turnos caen en la misma traza.
- Cada turno, nodo del grafo, tool call y llamada a Gemini = 1 observación (agent / span / tool / generation).
- Atributos de la traza: `session_id`, `case_id`, `language`, `system_version`, `prompt_version`,
  `purpose_version` y `model`; cada span de nodo lleva `layer` (propuesta AG #12).

Si Langfuse no está configurado (tests, sin keys) todo es no-op: el agente nunca depende de la observabilidad.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from langfuse import Langfuse, propagate_attributes
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter

from sofia_agent.config import Settings
from sofia_contracts.tracing import SPAN_LAYER_ATTRIBUTE, TraceMetadata

log = logging.getLogger("sofia.tracing")

_client: Langfuse | None = None


def configure(settings: Settings, *, span_exporter: SpanExporter | None = None) -> Langfuse | None:
    """Crea el cliente si hay credenciales (o un exportador inyectado, en tests). Devuelve None si no aplica."""
    global _client
    has_keys = bool(settings.langfuse_host and settings.langfuse_public_key and settings.langfuse_secret_key)
    if not has_keys and span_exporter is None:
        _client = None
        return None
    _client = Langfuse(
        public_key=settings.langfuse_public_key or "pk-lf-test",
        secret_key=settings.langfuse_secret_key.get_secret_value() if settings.langfuse_secret_key else "sk-lf-test",
        host=settings.langfuse_host or "http://localhost:3000",
        environment=settings.env,
        span_exporter=span_exporter,
        # Proveedor propio: no se mezcla con otra instrumentación OpenTelemetry del proceso.
        tracer_provider=TracerProvider(),
    )
    return _client


def enabled() -> bool:
    return _client is not None


def trace_id_for(seed: str) -> str | None:
    """ID de traza determinístico: el mismo hilo → la misma traza en todos sus turnos."""
    return Langfuse.create_trace_id(seed=seed) if _client is not None else None


@contextmanager
def conversation(meta: TraceMetadata) -> Iterator[None]:
    """Atributos §9.6 que heredan todas las observaciones creadas adentro (también en las tareas del grafo)."""
    if _client is None:
        yield
        return
    metadata = {k: str(v) for k, v in meta.model_dump(exclude_none=True).items() if k != "session_id"}
    with propagate_attributes(
        session_id=meta.session_id,
        metadata=metadata,
        version=meta.prompt_version,
        tags=[meta.system_version, meta.language],
        trace_name="sofia.conversation",
    ):
        yield


@contextmanager
def observe(name: str, *, as_type: str = "span", trace_id: str | None = None, **fields: Any) -> Iterator[Any]:
    """Observación hija de la actual (o raíz de `trace_id`). Devuelve None si no hay tracing."""
    if _client is None:
        yield None
        return
    if trace_id is not None:
        fields["trace_context"] = {"trace_id": trace_id}
    with _client.start_as_current_observation(name=name, as_type=as_type, **fields) as observation:  # type: ignore[call-overload]
        yield observation


def node_metadata(layer: str, node: str) -> dict[str, str]:
    return {SPAN_LAYER_ATTRIBUTE: layer, "node": node}


def update(observation: Any, **fields: Any) -> None:
    if observation is not None:
        observation.update(**fields)


def current_span_id() -> str | None:
    return _client.get_current_observation_id() if _client is not None else None


def score(*, trace_id: str, name: str, value: float | str, data_type: str, comment: str | None = None) -> bool:
    """Score en la traza (LEARN). Nunca rompe el request si Langfuse no responde."""
    if _client is None:
        return False
    try:
        _client.create_score(trace_id=trace_id, name=name, value=value, data_type=data_type, comment=comment)  # type: ignore[arg-type]
    except Exception:  # la observabilidad no puede tumbar la consola
        log.warning("no se pudo registrar el score %s en %s", name, trace_id, exc_info=True)
        return False
    return True


def flush() -> None:
    if _client is not None:
        _client.flush()


def shutdown() -> None:
    global _client
    if _client is not None:
        _client.shutdown()
        _client = None
