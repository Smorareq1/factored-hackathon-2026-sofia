"""Baseline de sistema (§8.7): el "agente de una sola llamada" contra el que se compara Sofía.

Un LLM con function calling sobre las MISMAS tools de la API (misma auth, mismo modelo, misma temperatura),
en un bucle ReAct propio. A propósito NO tiene:

- router ni slots: el LLM decide qué hacer con el texto;
- motor de política propio ni DECIDE: si llama o no a eligibility lo decide el LLM (la API igual aplica POL-*);
- VERIFY: no relee lo que creó; puede afirmar un caso que no existe (el harness lo mide);
- grounding, guardia de salida ni allowlist de acciones por nodo.

Diferencia honesta con el propuesto: acá los resultados de las tools (datos sintéticos) sí viajan a Gemini.
La ruta del turno no la declara el LLM: se infiere de lo que efectivamente pasó en la API (`infer_route`).
"""

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Protocol, get_args

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from sofia_agent import tracing
from sofia_agent.config import Settings
from sofia_agent.govern.context import CURRENT_NODE
from sofia_agent.llm import MIN_SERVER_DEADLINE_S, LLMUsage, Pricing, failure_reason
from sofia_agent.prompts import PromptBook, fill
from sofia_agent.sense.language import detect_language
from sofia_agent.tools.bank import BankClient, SessionExpiredError, ToolRejectedError, ToolUnavailableError
from sofia_contracts.bank_api import (
    ConfirmationProof,
    CustomerClaim,
    DisputeCreate,
    Eligibility,
    SessionInfo,
    Transaction,
)
from sofia_contracts.common import Language, Route
from sofia_contracts.handoff import Handoff, HandoffDraft

log = logging.getLogger("sofia.baseline")

NODE = "baseline"
MAX_STEPS = 8
_CLAIMS = set(get_args(CustomerClaim))

# Mensajes fijos del baseline (no pasan por el LLM): sesión vencida y LLM caído.
_REAUTH = {
    "es": "Tu sesión expiró. Vuelve a iniciar sesión para continuar.",
    "pt": "Sua sessão expirou. Entre novamente para continuar.",
}
_LLM_DOWN = {
    "es": "No puedo procesar tu mensaje en este momento. Intenta de nuevo en unos minutos.",
    "pt": "Não consigo processar sua mensagem agora. Tente novamente em alguns minutos.",
}


class ToolCallingModel(Protocol):
    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable: ...


@dataclass
class _TurnLog:
    """Lo que pasó en la API durante el turno: de acá sale la ruta (el LLM no la declara)."""

    session_expired: bool = False
    handoff: Handoff | None = None
    dispute_id: str | None = None
    eligibility: Eligibility | None = None
    dispute_read: bool = False
    tx_read: bool = False
    rejected: int = 0
    tools: list[str] = field(default_factory=list)


@dataclass
class BaselineTurn:
    text: str
    route: Route
    language: Language
    handoff: Handoff | None = None
    dispute_id: str | None = None
    tools: list[str] = field(default_factory=list)
    rejected_calls: int = 0
    error: str | None = None


def infer_route(log_: _TurnLog, text: str, *, failed: bool = False) -> Route:
    """Ruta observable del turno, con el mismo vocabulario que el propuesto (§9.5).

    `failed`: el LLM se cayó antes de responder y el cliente solo recibió el mensaje fijo. Cuenta lo que ya pasó
    en la API (handoff, disputa, sesión vencida); leer transacciones sin llegar a responder no resuelve nada.
    """
    asks = "?" in text
    if log_.handoff is not None:
        return "escalate"
    if log_.session_expired:
        return "reauth"
    if log_.dispute_id is not None:
        return "auto"
    if failed:
        return "abstain"
    if log_.eligibility is not None and log_.eligibility.route == "deny":
        return "deny"
    if log_.eligibility is not None and log_.eligibility.route == "auto":
        return "auto"  # pidió la confirmación después de una elegibilidad automática
    if log_.dispute_read or (log_.tx_read and not asks):
        return "auto"
    return "clarify" if asks else "abstain"


# ───────────────────────── esquemas de las tools (lo que ve Gemini) ─────────────────────────
class _ListTransactions(BaseModel):
    merchant: str | None = Field(default=None, description="Nombre (o parte) del comercio")
    since: str | None = Field(default=None, description="Fecha inicial YYYY-MM-DD")
    until: str | None = Field(default=None, description="Fecha final YYYY-MM-DD")


class _TransactionId(BaseModel):
    transaction_id: str = Field(description="ID de la transacción, p. ej. TX-MX-0001")


class _Eligibility(BaseModel):
    transaction_id: str = Field(description="ID de la transacción")
    customer_claim: str | None = Field(
        default=None, description="not_recognized | duplicate | wrong_amount | not_received | other"
    )


class _CreateDispute(BaseModel):
    transaction_id: str = Field(description="ID de la transacción")
    eligibility_id: str = Field(description="eligibility_id devuelto por check_dispute_eligibility")
    confirmation_text: str = Field(description="Texto literal con el que el cliente confirmó")
    customer_claim: str | None = Field(
        default=None, description="not_recognized | duplicate | wrong_amount | not_received | other"
    )


class _DisputeId(BaseModel):
    dispute_id: str = Field(description="Número de caso, p. ej. DSP-2026-000001")


class _ListDisputes(BaseModel):
    status: str | None = Field(default=None, description="open | in_review | resolved | rejected")


class _Transfer(BaseModel):
    reason: str = Field(description="Motivo breve del traspaso")
    summary: str = Field(description="Resumen del pedido del cliente para el agente humano")


def _tx_json(tx: Transaction) -> dict[str, Any]:
    return {
        "transaction_id": tx.transaction_id,
        "date": tx.transaction_date.date().isoformat(),
        "amount": str(tx.amount),
        "currency": tx.currency,
        "merchant": tx.merchant_name,
        "status": tx.transaction_status,
    }


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _claim(value: str | None) -> CustomerClaim | None:
    return value if value in _CLAIMS else None  # type: ignore[return-value]


def _text(message: AIMessage) -> str:
    return (message.text or "").strip()


class BaselineAgent:
    def __init__(
        self,
        models: Sequence[tuple[str, ToolCallingModel]],
        prompts: PromptBook,
        *,
        timeout_s: float = 20.0,
        attempt_timeout_s: float = 8.0,
        pricing: Pricing | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not models:
            raise ValueError("el baseline necesita al menos un modelo")
        self.model_name = models[0][0]
        self.usage = LLMUsage()
        self._models = list(models)
        self._prompts = prompts
        self._timeout_s = timeout_s
        self._attempt_timeout_s = min(attempt_timeout_s, timeout_s)
        self._pricing = pricing or Pricing()
        self._clock = clock
        self._preferred = 0

    @property
    def prompt_version(self) -> str:
        return self._prompts.baseline.version

    # ───────────────────────── un turno ─────────────────────────
    async def turn(
        self,
        *,
        history: list[BaseMessage],
        message: str,
        bank: BankClient,
        turn: int,
        thread_id: str,
        language_hint: Language | None = None,
        trace_id: str | None = None,
    ) -> BaselineTurn:
        """Corre el bucle ReAct y agrega a `history` los mensajes del turno (humano, IA y tools)."""
        language = detect_language(message, fallback=language_hint or "es").language
        node = CURRENT_NODE.set(NODE)
        try:
            try:
                session = await bank.session_me()
            except SessionExpiredError:
                return BaselineTurn(text=_REAUTH[language], route="reauth", language=language)
            log_ = _TurnLog()
            tools = self._tools(
                bank, session, log_, language=language, turn=turn, thread_id=thread_id, trace_id=trace_id
            )
            text, error = await self._react(history, message, tools)
        finally:
            CURRENT_NODE.reset(node)
        failed = error is not None and not text
        if failed:
            text = _LLM_DOWN[language]
        return BaselineTurn(
            text=text,
            route=infer_route(log_, text, failed=failed),
            language=language,
            handoff=log_.handoff,
            dispute_id=log_.dispute_id,
            tools=log_.tools,
            rejected_calls=log_.rejected,
            error=error,
        )

    async def _react(
        self, history: list[BaseMessage], message: str, tools: list[StructuredTool]
    ) -> tuple[str, str | None]:
        system = SystemMessage(content=fill(self._prompts.baseline.system, today=self._clock().date().isoformat()))
        human = HumanMessage(content=message)
        turn_messages: list[BaseMessage] = [human]
        by_name = {tool.name: tool for tool in tools}
        text, error = "", None
        try:
            for _ in range(MAX_STEPS):
                ai = await self._call([system, *history, *turn_messages], tools, user=message)
                turn_messages.append(ai)
                if not ai.tool_calls:
                    text = _text(ai)
                    break
                for call in ai.tool_calls:
                    tool = by_name.get(call["name"])
                    result = (
                        await tool.ainvoke(call["args"]) if tool else f"ERROR: herramienta desconocida {call['name']}"
                    )
                    turn_messages.append(ToolMessage(content=str(result), tool_call_id=call["id"], name=call["name"]))
            else:
                error = "max_steps"
        except _LLMDownError as exc:
            error = f"llm_unavailable:{exc}"
        history.extend(turn_messages)
        return text, error

    async def _call(self, messages: list[BaseMessage], tools: list[StructuredTool], *, user: str) -> AIMessage:
        """Misma cadena de modelos que el propuesto: respaldo ante 503/429/timeout y preferencia por el último ok."""
        ordered = list(range(self._preferred, len(self._models))) + list(range(self._preferred))
        deadline = time.monotonic() + self._timeout_s
        reason = "timeout"
        for index in ordered:
            remaining = deadline - time.monotonic()
            if remaining < 1.5:
                break
            name, model = self._models[index]
            with tracing.observe(
                "gemini.baseline",
                as_type="generation",
                model=name,
                model_parameters={"temperature": 0},
                input=user,
                metadata={"prompt_version": self.prompt_version},
            ) as generation:
                try:
                    runnable = model.bind_tools(tools)
                    ai = await asyncio.wait_for(
                        runnable.ainvoke(messages), timeout=min(remaining, self._attempt_timeout_s)
                    )
                except Exception as exc:  # cualquier falla del proveedor pasa al siguiente modelo
                    reason = failure_reason(exc)
                    tracing.update(generation, level="ERROR", status_message=reason)
                    log.warning("gemini.baseline: %s falló (%s)", name, reason)
                    continue
                usage = ai.usage_metadata or {}
                tokens_in, tokens_out = int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
                cost = self._pricing.cost(tokens_in, tokens_out)
                self.usage.calls += 1
                self.usage.tokens_in += tokens_in
                self.usage.tokens_out += tokens_out
                self.usage.cost_usd += cost
                tracing.update(
                    generation,
                    output=_text(ai) or [call["name"] for call in ai.tool_calls],
                    usage_details={"input": tokens_in, "output": tokens_out},
                    cost_details={"total": cost},
                )
            self._preferred = index
            return ai
        raise _LLMDownError(reason)

    # ───────────────────────── tools (las mismas de la API, sin guardas propias) ─────────────────────────
    def _tools(
        self,
        bank: BankClient,
        session: SessionInfo,
        log_: _TurnLog,
        *,
        language: Language,
        turn: int,
        thread_id: str,
        trace_id: str | None,
    ) -> list[StructuredTool]:
        def guarded(name: str, fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[str]]:
            async def run(**kwargs: Any) -> str:
                log_.tools.append(name)
                try:
                    result = await fn(**kwargs)
                except SessionExpiredError:
                    log_.session_expired = True
                    return "ERROR 401: la sesión del cliente expiró; debe volver a iniciar sesión."
                except ToolRejectedError as exc:
                    log_.rejected += 1
                    return f"ERROR {exc.status}: {exc.detail}"
                except ToolUnavailableError:
                    return "ERROR: el servicio no está disponible en este momento."
                except ValueError as exc:
                    return f"ERROR: argumento inválido ({exc})"
                return json.dumps(result, ensure_ascii=False, default=str)

            return run

        async def list_transactions(merchant: str | None = None, since: str | None = None, until: str | None = None):
            items = await bank.list_transactions(since=_date(since), until=_date(until), merchant=merchant)
            log_.tx_read = True
            return [_tx_json(tx) for tx in items[:20]]

        async def get_transaction(transaction_id: str):
            tx = await bank.get_transaction(transaction_id)
            log_.tx_read = log_.tx_read or tx is not None
            return _tx_json(tx) if tx else {"error": "not_found"}

        async def check_dispute_eligibility(transaction_id: str, customer_claim: str | None = None):
            eligibility = await bank.check_eligibility(transaction_id, _claim(customer_claim))
            log_.eligibility = eligibility
            return eligibility.model_dump(mode="json", exclude_none=True)

        async def create_dispute(
            transaction_id: str, eligibility_id: str, confirmation_text: str, customer_claim: str | None = None
        ):
            body = DisputeCreate(
                transaction_id=transaction_id,
                eligibility_id=eligibility_id,
                customer_claim=_claim(customer_claim),
                confirmation=ConfirmationProof(text=confirmation_text, turn=turn, confirmed_at=self._clock()),
            )
            dispute = await bank.create_dispute(body, idempotency_key=f"{thread_id}:{turn}:{transaction_id}")
            log_.dispute_id = dispute.dispute_id
            return dispute.model_dump(mode="json")

        async def get_dispute(dispute_id: str):
            dispute = await bank.get_dispute(dispute_id)
            log_.dispute_read = log_.dispute_read or dispute is not None
            return dispute.model_dump(mode="json") if dispute else {"error": "not_found"}

        async def list_disputes(status: str | None = None):
            disputes = await bank.list_disputes(status)
            log_.dispute_read = True
            return [d.model_dump(mode="json") for d in disputes]

        async def transfer_to_human(reason: str, summary: str):
            draft = HandoffDraft(
                language=language,
                customer_id=session.customer_id,
                authenticated=True,
                request_summary=summary[:500],
                verified_facts=[],
                actions_taken=[],
                open_questions=[],
                risk_flags=[],
                reason_for_handoff=(reason or "baseline_transfer")[:80],
                system_version="baseline",
                trace_id=trace_id,
            )
            receipt = await bank.create_handoff(draft, idempotency_key=f"{thread_id}:{turn}:handoff")
            log_.handoff = Handoff(**draft.model_dump(), handoff_id=receipt.handoff_id, created_at=receipt.created_at)
            return receipt.model_dump(mode="json")

        specs: list[tuple[str, str, type[BaseModel], Callable[..., Awaitable[Any]]]] = [
            (
                "list_transactions",
                "Lista las transacciones del cliente autenticado.",
                _ListTransactions,
                list_transactions,
            ),
            ("get_transaction", "Lee una transacción del cliente por su ID.", _TransactionId, get_transaction),
            (
                "check_dispute_eligibility",
                "Evalúa si una transacción se puede disputar. Devuelve route (auto/human/deny) y eligibility_id.",
                _Eligibility,
                check_dispute_eligibility,
            ),
            ("create_dispute", "Crea la disputa de una transacción.", _CreateDispute, create_dispute),
            ("get_dispute", "Lee una disputa por su número de caso.", _DisputeId, get_dispute),
            ("list_disputes", "Lista las disputas del cliente.", _ListDisputes, list_disputes),
            ("transfer_to_human", "Transfiere la conversación a un agente humano.", _Transfer, transfer_to_human),
        ]
        return [
            StructuredTool.from_function(coroutine=guarded(name, fn), name=name, description=desc, args_schema=schema)
            for name, desc, schema, fn in specs
        ]


class _LLMDownError(Exception):
    """Ningún modelo de la cadena respondió dentro del presupuesto."""


def make_baseline(settings: Settings, prompts: PromptBook) -> BaselineAgent | None:
    """Mismo modelo, misma temperatura y misma cadena de respaldo que el propuesto. Sin LLM no hay baseline."""
    if not settings.use_gemini:
        return None
    from langchain_google_genai import ChatGoogleGenerativeAI

    models = settings.gemini_models
    thinking = None if settings.gemini_thinking_level == "default" else settings.gemini_thinking_level
    chain = [
        (
            model,
            ChatGoogleGenerativeAI(
                model=model,
                **settings.gemini_client_kwargs,
                temperature=0,
                max_retries=0 if len(models) > 1 else 1,
                timeout=max(settings.llm_timeout_s, MIN_SERVER_DEADLINE_S),
                thinking_config={"thinking_level": thinking} if thinking else None,
            ),
        )
        for model in models
    ]
    return BaselineAgent(
        chain,
        prompts,
        timeout_s=settings.llm_timeout_s,
        attempt_timeout_s=settings.llm_attempt_timeout_s,
        pricing=Pricing(settings.gemini_price_in_per_mtok, settings.gemini_price_out_per_mtok),
    )
