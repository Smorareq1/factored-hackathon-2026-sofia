"""Un turno del sistema propuesto, igual para el chat (SSE) y para el harness (`run_conversation`).

Abre la traza de la conversación (§9.6) y el span del turno; los nodos, las tool calls y Gemini quedan como
hijos. Los eventos de capa se entregan en vivo por `on_event` (la caja de cristal se ilumina mientras corre).
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from sofia_agent import tracing
from sofia_agent.deps import Deps
from sofia_agent.graph import turn_input
from sofia_contracts.common import Language, SystemVersion
from sofia_contracts.events import LayerEvent
from sofia_contracts.tracing import TraceMetadata


@dataclass
class TurnOutcome:
    state: dict[str, Any]
    latency_ms: int
    events: list[LayerEvent] = field(default_factory=list)


@contextmanager
def traced_turn(*, meta: TraceMetadata, trace_id: str | None, turn: int, message: str) -> Iterator[Any]:
    """Atributos de la traza + span `turn N` (tipo agent). Lo comparten el propuesto y el baseline."""
    with (
        tracing.conversation(meta),
        tracing.observe(
            f"turn {turn}", as_type="agent", trace_id=trace_id, input=message, metadata={"turn": turn}
        ) as span,
    ):
        yield span


async def run_turn(
    graph: CompiledStateGraph,
    deps: Deps,
    *,
    message: str,
    turn: int,
    language_hint: Language | None,
    language: Language | None = None,
    case_id: str | None = None,
    on_event: Callable[[LayerEvent], None] | None = None,
) -> TurnOutcome:
    config = {"configurable": {"thread_id": deps.thread_id}}
    started = time.perf_counter()
    events: list[LayerEvent] = []
    system_version: SystemVersion = "proposed"
    meta = TraceMetadata(
        session_id=deps.thread_id,
        case_id=case_id,
        language=language or language_hint or "es",
        system_version=system_version,
        prompt_version=deps.prompts.version,
        purpose_version=deps.purpose.purpose_version,
        model=deps.llm.model_name,
    )
    with traced_turn(meta=meta, trace_id=deps.trace_id, turn=turn, message=message) as span:
        async for chunk in graph.astream(
            turn_input(
                message=message,
                turn=turn,
                thread_id=deps.thread_id,
                language_hint=language_hint,
                system_version=system_version,
            ),
            config,
            context=deps,
            stream_mode="custom",
        ):
            if isinstance(chunk, dict) and "layer_event" in chunk:
                events.append(chunk["layer_event"])
                if on_event is not None:
                    on_event(chunk["layer_event"])
        state = (await graph.aget_state(config)).values
        response, goal, versions = state.get("response"), state.get("goal"), state.get("versions")
        tracing.update(
            span,
            output=response.text if response is not None else None,
            metadata={
                "route": state.get("route") or "",
                "situation": state.get("situation") or "",
                "goal_status": goal.status if goal else "",
                "language": state.get("language") or "",
                "router_version": versions.router if versions else "",
            },
        )
    return TurnOutcome(state=state, latency_ms=int((time.perf_counter() - started) * 1000), events=events)
