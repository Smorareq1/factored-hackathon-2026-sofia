"""Servicio HTTP del agente: chat por SSE (eventos de capa + respuesta) y BFF de sesión/consola.

El frontend habla solo con este servicio. El token del cliente (emitido por SIM) viaja en cada request
hacia SIM y nunca se guarda en el checkpointer. El agente no emite ni firma tokens.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from sofia_agent import tracing
from sofia_agent.api.runtime import AgentRuntime, BaselineThread, open_runtime
from sofia_agent.config import get_settings
from sofia_agent.tools.bank import SessionExpiredError, ToolRejectedError, ToolUnavailableError
from sofia_agent.turns import run_turn, traced_turn
from sofia_contracts.bank_api import (
    DemoCustomer,
    HandoffList,
    SessionChallenge,
    SessionInfo,
    SessionStart,
    SessionToken,
    SessionVerify,
)
from sofia_contracts.events import (
    AgentMessage,
    ChatRequest,
    EventStatus,
    Layer,
    LayerEvent,
    TurnDone,
    TurnError,
)
from sofia_contracts.handoff import Handoff, HandoffFeedback, HandoffFeedbackRecord
from sofia_contracts.tracing import TraceMetadata

log = logging.getLogger("sofia.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    tracing.configure(settings)
    try:
        async with open_runtime(settings) as runtime:
            app.state.runtime = runtime
            log.info(
                "agente listo: banco=%s llm=%s baseline=%s checkpointer=%s purpose=%s prompts=%s langfuse=%s",
                runtime.settings.bank_api_url,
                runtime.llm.model_name,
                "on" if runtime.baseline else "off",
                runtime.checkpointer_kind,
                runtime.purpose.purpose_version,
                runtime.prompts.version,
                "on" if tracing.enabled() else "off",
            )
            yield
    finally:
        tracing.shutdown()


app = FastAPI(title="S.O.F.I.A. — agente Sofía", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
bearer = HTTPBearer(auto_error=False)


def runtime_of(request: Request) -> AgentRuntime:
    return request.app.state.runtime


Runtime = Annotated[AgentRuntime, Depends(runtime_of)]


def require_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="missing_token")
    return credentials.credentials


Token = Annotated[str, Depends(require_token)]


@app.exception_handler(SessionExpiredError)
async def _expired(_: Request, __: SessionExpiredError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": "session_invalid_or_expired"})


@app.exception_handler(ToolRejectedError)
async def _rejected(_: Request, exc: ToolRejectedError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"detail": exc.detail})


@app.exception_handler(ToolUnavailableError)
async def _unavailable(_: Request, __: ToolUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "bank_unavailable"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent"}


@app.get("/v1/meta")
def meta(runtime: Runtime) -> dict[str, Any]:
    """Versiones activas: la caja de cristal las muestra y las trazas las registran (§9.6)."""
    return {
        "purpose_version": runtime.purpose.purpose_version,
        "prompt_version": runtime.prompts.version,
        "model": runtime.llm.model_name,
        "bank": "fake" if runtime.settings.bank_api_url == "fake" else "sim",
        "auto_actions": runtime.settings.auto_actions,
        "langfuse_url": runtime.settings.langfuse_host,
        # Umbrales de PURPOSE que la caja de cristal dibuja junto a las confianzas.
        "router_threshold": runtime.purpose.interpret.router_confidence_threshold,
        "max_clarifications": runtime.purpose.limits.max_clarifications,
        # El selector Sofía / Baseline del chat solo aparece si hay LLM para el baseline (§8.7).
        "baseline_available": runtime.baseline is not None,
        "tracing": tracing.enabled(),
    }


# ───────────────────────── chat (SSE) ─────────────────────────
async def _owned_thread(runtime: AgentRuntime, token: str, thread_id: str) -> tuple[SessionInfo, dict[str, Any]]:
    """El hilo queda ligado al cliente del primer turno: otro cliente no puede leerlo ni escribirlo."""
    session = await runtime.bank(token).session_me()
    if session.role != "customer":
        raise HTTPException(status_code=403, detail="customer_role_required")
    snapshot = await runtime.graph.aget_state({"configurable": {"thread_id": thread_id}})
    values = snapshot.values or {}
    owner = values.get("owner_customer_id")
    if owner and owner != session.customer_id:
        raise HTTPException(status_code=403, detail="thread_not_owned")
    return session, values


Event = tuple[str, BaseModel] | None


def _single(name: str, payload: BaseModel) -> EventSourceResponse:
    async def once() -> AsyncIterator[dict[str, str]]:
        yield {"event": name, "data": payload.model_dump_json()}

    return EventSourceResponse(once())


def _sse(queue: "asyncio.Queue[Event]") -> EventSourceResponse:
    """El SSE solo lee la cola: si el cliente se va, el turno sigue y queda en el checkpoint."""

    async def stream() -> AsyncIterator[dict[str, str]]:
        while (item := await queue.get()) is not None:
            name, payload = item
            yield {"event": name, "data": payload.model_dump_json()}

    return EventSourceResponse(stream(), ping=15)


_INTERNAL_ERROR = TurnError(code="internal_error", message="No pude procesar tu mensaje. Intenta de nuevo.")


@app.post("/v1/chat")
async def chat(body: ChatRequest, runtime: Runtime, token: Token) -> EventSourceResponse:
    if body.system_version == "baseline":
        return await _baseline_chat(body, runtime, token)
    try:
        await _owned_thread(runtime, token, body.thread_id)
    except SessionExpiredError:
        # No se toca el hilo sin un dueño autenticado: la UI muestra el banner de reautenticación.
        return _single("error", TurnError(code="session_expired", message="reauth"))

    # 1 conversación = 1 traza: el mismo hilo cae siempre en el mismo trace_id (§9.6).
    trace_id = tracing.trace_id_for(body.thread_id)
    queue: asyncio.Queue[Event] = asyncio.Queue()

    async def work() -> None:
        try:
            async with runtime.thread_lock(body.thread_id):
                config = {"configurable": {"thread_id": body.thread_id}}
                values = (await runtime.graph.aget_state(config)).values or {}
                turn = int(values.get("turn") or 0) + 1
                outcome = await run_turn(
                    runtime.graph,
                    runtime.deps(token, body.thread_id, trace_id),
                    message=body.message,
                    turn=turn,
                    language_hint=body.language_hint,
                    on_event=lambda event: queue.put_nowait(("layer", event)),
                )
            final = outcome.state
            if (response := final.get("response")) is not None:
                queue.put_nowait(("message", response))
            handoff: Handoff | None = final.get("handoff")
            if handoff is not None and str(final.get("situation", "")).startswith("escalated_"):
                queue.put_nowait(("handoff", handoff))
            goal = final.get("goal")
            done = TurnDone(
                turn=turn,
                route=final.get("route"),
                goal_status=goal.status if goal else None,
                latency_ms=outcome.latency_ms,
                trace_id=trace_id,
            )
            queue.put_nowait(("done", done))
        except Exception:  # un error inesperado no debe dejar al cliente colgado
            log.exception("turno fallido thread=%s", body.thread_id)
            queue.put_nowait(("error", _INTERNAL_ERROR))
        finally:
            queue.put_nowait(None)

    runtime.spawn(work())
    return _sse(queue)


async def _baseline_chat(body: ChatRequest, runtime: AgentRuntime, token: str) -> EventSourceResponse:
    """Baseline §8.7 por la misma interfaz: la caja de cristal muestra solo sus tool calls (no tiene capas)."""
    baseline = runtime.baseline
    if baseline is None:
        return _single("error", TurnError(code="baseline_unavailable", message="El baseline necesita Gemini."))
    bank = runtime.bank(token, enforce_allowlist=False)
    try:
        session = await bank.session_me()
    except SessionExpiredError:
        return _single("error", TurnError(code="session_expired", message="reauth"))
    if session.role != "customer":
        raise HTTPException(status_code=403, detail="customer_role_required")
    thread = runtime.baseline_threads.setdefault(body.thread_id, BaselineThread(session.customer_id))
    if thread.owner_customer_id != session.customer_id:
        raise HTTPException(status_code=403, detail="thread_not_owned")
    bank.drain()  # la lectura de sesión de arriba no es parte del turno
    trace_id = tracing.trace_id_for(body.thread_id)
    queue: asyncio.Queue[Event] = asyncio.Queue()

    def event(turn: int, layer: Layer, code: str, status: EventStatus = "ok", **params: Any) -> LayerEvent:
        return LayerEvent(
            turn=turn,
            layer=layer,
            node="baseline",
            status=status,
            code=code,
            params=params,
            started_at=datetime.now(UTC),
            duration_ms=int(params.get("ms", 0)),
        )

    async def work() -> None:
        try:
            async with runtime.thread_lock(body.thread_id):
                thread.turn += 1
                turn, started = thread.turn, time.perf_counter()
                queue.put_nowait(("layer", event(turn, "GOVERN", "baseline_mode", "warn", model=baseline.model_name)))
                meta = TraceMetadata(
                    session_id=body.thread_id,
                    language=body.language_hint or "es",
                    system_version="baseline",
                    prompt_version=baseline.prompt_version,
                    purpose_version="none",
                    model=baseline.model_name,
                )
                with traced_turn(meta=meta, trace_id=trace_id, turn=turn, message=body.message) as span:
                    reply = await baseline.turn(
                        history=thread.history,
                        message=body.message,
                        bank=bank,
                        turn=turn,
                        thread_id=body.thread_id,
                        language_hint=body.language_hint,
                        trace_id=trace_id,
                    )
                    tracing.update(span, output=reply.text, metadata={"route": reply.route, "tools": reply.tools})
            for record in bank.drain():
                failed = record.error is not None or (record.status or 0) >= 500
                params: dict[str, Any] = {"method": record.method, "path": record.path, "http_status": record.status}
                params |= {"attempt": record.attempt, "ms": record.duration_ms}
                queue.put_nowait(
                    ("layer", event(turn, "ORCHESTRATE", "tool_call", "error" if failed else "ok", **params))
                )
            queue.put_nowait(("message", AgentMessage(text=reply.text, language=reply.language, route=reply.route)))
            if reply.handoff is not None:
                queue.put_nowait(("handoff", reply.handoff))
            latency = int((time.perf_counter() - started) * 1000)
            done = TurnDone(turn=turn, route=reply.route, goal_status=None, latency_ms=latency, trace_id=trace_id)
            queue.put_nowait(("done", done))
        except Exception:
            log.exception("turno baseline fallido thread=%s", body.thread_id)
            queue.put_nowait(("error", _INTERNAL_ERROR))
        finally:
            queue.put_nowait(None)

    runtime.spawn(work())
    return _sse(queue)


@app.get("/v1/threads/{thread_id}")
async def thread(thread_id: str, runtime: Runtime, token: Token) -> dict[str, Any]:
    """Estado resumido para recargar la página (sin datos internos de GOVERN)."""
    _, values = await _owned_thread(runtime, token, thread_id)
    goal = values.get("goal")
    response = values.get("response")
    return {
        "thread_id": thread_id,
        "turn": values.get("turn", 0),
        "language": values.get("language"),
        "messages": [m.model_dump() for m in values.get("messages", [])],
        "goal": goal.model_dump() if goal else None,
        "pending_confirmation": bool(values.get("pending_confirmation")),
        "last_response": response.model_dump(mode="json") if response else None,
    }


# ───────────────────────── sesión (proxy a SIM) ─────────────────────────
@app.get("/v1/demo/customers")
async def demo_customers(runtime: Runtime) -> list[DemoCustomer]:
    return await runtime.bank(None).demo_customers()


@app.post("/v1/session")
async def start_session(body: SessionStart, runtime: Runtime) -> SessionChallenge:
    return await runtime.bank(None).start_session(body)


@app.post("/v1/session/verify")
async def verify_session(body: SessionVerify, runtime: Runtime) -> SessionToken:
    return await runtime.bank(None).verify_session(body)


@app.get("/v1/session/me")
async def session_me(runtime: Runtime, token: Token) -> SessionInfo:
    return await runtime.bank(token).session_me()


# ───────────────────────── consola del agente humano ─────────────────────────
@app.get("/v1/console/handoffs")
async def console_handoffs(runtime: Runtime, token: Token) -> HandoffList:
    return HandoffList(items=await runtime.bank(token).list_handoffs())


@app.get("/v1/console/handoffs/{handoff_id}")
async def console_handoff(handoff_id: str, runtime: Runtime, token: Token) -> Handoff:
    handoff = await runtime.bank(token).read_handoff(handoff_id)
    if handoff is None:
        raise HTTPException(status_code=404, detail="not_found")
    return handoff


@app.post("/v1/console/handoffs/{handoff_id}/feedback")
async def console_feedback(
    handoff_id: str, body: HandoffFeedback, runtime: Runtime, token: Token
) -> HandoffFeedbackRecord:
    """LEARN: el agente humano califica la ficha; SIM la guarda y la traza de la conversación recibe el score."""
    bank = runtime.bank(token)
    record = await bank.send_feedback(handoff_id, body)
    if record is None:
        raise HTTPException(status_code=404, detail="not_found")
    handoff = await bank.read_handoff(handoff_id)
    if handoff is not None and handoff.trace_id:
        tracing.score(
            trace_id=handoff.trace_id,
            name="handoff_quality",
            value=1.0 if body.useful else 0.0,
            data_type="BOOLEAN",
            comment=body.comment,
        )
        tracing.score(
            trace_id=handoff.trace_id,
            name="handoff_missing_fields",
            value=float(len(body.missing_fields)),
            data_type="NUMERIC",
            comment=", ".join(body.missing_fields) or None,
        )
    return record


@app.get("/v1/console/handoffs/{handoff_id}/feedback")
async def console_feedback_read(handoff_id: str, runtime: Runtime, token: Token) -> HandoffFeedbackRecord:
    record = await runtime.bank(token).read_feedback(handoff_id)
    if record is None:
        raise HTTPException(status_code=404, detail="not_found")
    return record
