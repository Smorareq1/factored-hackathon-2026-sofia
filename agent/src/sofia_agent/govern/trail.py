"""Eventos de capa (§9.7): registro de ejecución por nodo, emitido en vivo por el stream del grafo."""

import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sofia_contracts.events import EventStatus, Layer, LayerEvent


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, list | tuple | set):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value


class Trail:
    """Colector de eventos de un nodo. Cada `emit` sale enseguida al SSE (la caja de cristal se ilumina)."""

    def __init__(
        self,
        *,
        turn: int,
        layer: Layer,
        node: str,
        writer: Callable[[Any], None] | None = None,
        span_id: str | None = None,
    ) -> None:
        self.turn, self.layer, self.node = turn, layer, node
        self._writer = writer
        # Span de Langfuse del nodo: la caja de cristal puede enlazar cada evento con su traza.
        self.span_id = span_id
        self._t0 = time.perf_counter()
        self.events: list[LayerEvent] = []

    def emit(self, code: str, status: EventStatus = "ok", *, layer: Layer | None = None, **params: Any) -> LayerEvent:
        now = datetime.now(UTC)
        event = LayerEvent(
            turn=self.turn,
            layer=layer or self.layer,
            node=self.node,
            status=status,
            code=code,
            params=_jsonable(params),
            started_at=now,
            duration_ms=int((time.perf_counter() - self._t0) * 1000),
            span_id=self.span_id,
        )
        self.events.append(event)
        if self._writer is not None:
            self._writer({"layer_event": event})
        return event
