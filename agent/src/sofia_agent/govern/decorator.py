"""`@governed(layer, node)`: envuelve cada nodo del grafo (capa GOVERN).

- Fija el nodo en curso (lo lee la allowlist de acciones del cliente del banco).
- Convierte fallas conocidas en rutas seguras: 401 → reauth, tool caída → escalate, acción fuera de su
  nodo → escalate con la guarda registrada.
- Registra cada tool call como evento de capa y en `tool_log` (auditoría y trazas §9.6).
- Abre el span del nodo en Langfuse con su capa; las tool calls y las llamadas a Gemini quedan como hijas.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.runtime import Runtime

from sofia_agent import tracing
from sofia_agent.deps import Deps
from sofia_agent.govern.context import CURRENT_NODE, ToolNotAllowedError
from sofia_agent.govern.trail import Trail
from sofia_agent.state import AgentState, Fault
from sofia_agent.tools.bank import SessionExpiredError, ToolUnavailableError
from sofia_contracts.events import Layer

NodeFn = Callable[[AgentState, Deps, Trail], Awaitable[dict[str, Any]]]


def governed(layer: Layer, node: str) -> Callable[[NodeFn], Callable[[AgentState, Runtime[Deps]], Awaitable[dict]]]:
    def decorator(fn: NodeFn) -> Callable[[AgentState, Runtime[Deps]], Awaitable[dict]]:
        async def wrapper(state: AgentState, runtime: Runtime[Deps]) -> dict[str, Any]:
            with tracing.observe(node, metadata=tracing.node_metadata(layer, node)) as span:
                update = await _run(state, runtime, span)
            return update

        async def _run(state: AgentState, runtime: Runtime[Deps], span: Any) -> dict[str, Any]:
            deps = runtime.context
            trail = Trail(
                turn=state.get("turn", 0),
                layer=layer,
                node=node,
                writer=runtime.stream_writer,
                span_id=tracing.current_span_id(),
            )
            token = CURRENT_NODE.set(node)
            try:
                update = await fn(state, deps, trail)
            except SessionExpiredError:
                trail.emit("session_expired", "error")
                update = {"route": "reauth", "fault": Fault(code="session_expired", node=node)}
            except ToolUnavailableError as exc:
                trail.emit("tool_unavailable", "error", method=exc.method, path=exc.path, detail=exc.detail)
                update = {
                    "route": "escalate",
                    "handoff_reason": "tool_unavailable",
                    "fault": Fault(code="tool_unavailable", node=node, detail=str(exc)),
                }
            except ToolNotAllowedError as exc:
                trail.emit("tool_blocked", "error", layer="GOVERN", detail=str(exc))
                update = {
                    "route": "escalate",
                    "handoff_reason": "guard_blocked",
                    "fault": Fault(code="tool_blocked", node=node, detail=str(exc)),
                }
            finally:
                CURRENT_NODE.reset(token)

            records = [r.model_copy(update={"turn": trail.turn}) for r in deps.bank.drain()]
            for record in records:
                failed = record.error is not None or (record.status or 0) >= 500
                trail.emit(
                    "tool_call",
                    "error" if failed else "ok",
                    method=record.method,
                    path=record.path,
                    http_status=record.status,
                    attempt=record.attempt,
                    ms=record.duration_ms,
                )
            update["events"] = trail.events
            if records:
                update["tool_log"] = records
            statuses = {e.status for e in trail.events}
            tracing.update(
                span,
                output={k: str(update[k]) for k in ("route", "situation", "handoff_reason") if update.get(k)},
                metadata={"events": [e.code for e in trail.events]},
                level="ERROR" if "error" in statuses else "WARNING" if "warn" in statuses else "DEFAULT",
            )
            return update

        # Sin functools.wraps: LangGraph inspecciona la firma para inyectar `runtime`.
        wrapper.__name__ = wrapper.__qualname__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        return wrapper

    return decorator
