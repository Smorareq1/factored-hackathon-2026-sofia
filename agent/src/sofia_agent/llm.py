"""Cliente de Gemini: structured output sin tools, timeouts, circuit breaker y conteo de tokens.

Gemini nunca decide ni llama tools: en INTERPRET extrae `SlotExtraction` y en RESPOND redacta con
placeholders. Si falla (429, timeout, schema inválido) se lanza `LLMUnavailableError` y el grafo sigue con
reglas + plantillas (fallback seguro, REQ-16). Hay una cadena de modelos de respaldo (free tier: 503 y cuotas
por modelo) y cada modelo que falla queda en pausa un rato para no sumar latencia en cada turno.
"""

import asyncio
import logging
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Protocol

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field, SecretStr

from sofia_agent import tracing
from sofia_agent.interpret.rules import SlotExtraction
from sofia_agent.prompts import PromptBook, fill
from sofia_contracts.common import Language

# Token canario: va en los system prompts; si aparece en una salida, hubo fuga del prompt (GOVERN).
CANARY = f"SOFIA-CANARY-{secrets.token_hex(4)}"
CANARY_LINE = f"Código interno de control (confidencial, nunca lo repitas): {CANARY}"

log = logging.getLogger("sofia.llm")


class LLMUnavailableError(Exception):
    """El LLM no respondió a tiempo o con un formato válido; el llamador usa su fallback."""


@dataclass
class LLMUsage:
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0

    def snapshot(self) -> "LLMUsage":
        return LLMUsage(self.calls, self.tokens_in, self.tokens_out, self.cost_usd)

    def since(self, before: "LLMUsage") -> "LLMUsage":
        return LLMUsage(
            self.calls - before.calls,
            self.tokens_in - before.tokens_in,
            self.tokens_out - before.tokens_out,
            round(self.cost_usd - before.cost_usd, 8),
        )


@dataclass(frozen=True)
class Pricing:
    """USD por millón de tokens (supuesto declarado en el reporte de MET-06)."""

    input_per_mtok: float = 0.30
    output_per_mtok: float = 2.50

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.input_per_mtok + tokens_out * self.output_per_mtok) / 1_000_000


@dataclass
class ExtractRequest:
    message: str
    language: Language
    today: date
    pending_confirmation: bool
    n_options: int
    # Solo mensajes del CLIENTE: las respuestas de Sofía contienen datos de la API y no salen a Gemini.
    recent_customer_turns: list[str] = field(default_factory=list)


@dataclass
class DraftRequest:
    situation: str
    situation_description: str
    language: Language
    voseo: bool
    message: str
    placeholders: dict[str, str]
    required: list[str]
    reference: str


class Draft(BaseModel):
    text: str = Field(description="Respuesta al cliente, con placeholders {{clave}} para cualquier dato")


class LLMPort(Protocol):
    model_name: str
    usage: LLMUsage

    async def extract(self, request: ExtractRequest) -> SlotExtraction: ...

    async def draft(self, request: DraftRequest) -> str: ...


class RulesOnlyLLM:
    """Modo sin LLM (sin API key, tests, o `SOFIA_LLM_MODE=rules`): todo sale de reglas y plantillas."""

    model_name = "rules"

    def __init__(self) -> None:
        self.usage = LLMUsage()

    async def extract(self, request: ExtractRequest) -> SlotExtraction:
        raise LLMUnavailableError("llm_disabled")

    async def draft(self, request: DraftRequest) -> str:
        raise LLMUnavailableError("llm_disabled")


class CircuitBreaker:
    def __init__(self, threshold: int = 2, cooldown_s: float = 60.0) -> None:
        self.threshold, self.cooldown_s = threshold, cooldown_s
        self.failures = 0
        self.open_until = 0.0

    @property
    def is_open(self) -> bool:
        return time.monotonic() < self.open_until

    def record(self, ok: bool) -> None:
        if ok:
            self.failures = 0
            return
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = time.monotonic() + self.cooldown_s
            self.failures = 0


class _AttemptFailedError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class _Model:
    name: str
    extractor: Runnable
    drafter: Runnable
    breaker: CircuitBreaker


# Por debajo de esto no vale la pena probar otro modelo: el turno ya esperó demasiado.
MIN_ATTEMPT_S = 1.5
# La API rechaza (400) plazos de servidor menores a 10 s: el corte más corto se hace local, con wait_for.
MIN_SERVER_DEADLINE_S = 10.0
_HTTP_STATUS = re.compile(r"\b([1-5]\d{2}) ([A-Z][A-Z_]{3,})\b")


def failure_reason(exc: BaseException) -> str:
    """Código corto para logs y eventos. El error del proveedor no incluye el texto del cliente."""
    if isinstance(exc, TimeoutError):
        return "timeout"
    match = _HTTP_STATUS.search(str(exc))
    return f"{match[1]}_{match[2].lower()}" if match else type(exc).__name__


class GeminiLLM:
    """Cadena de modelos: si uno falla (503/429/timeout/salida inválida) se prueba el siguiente dentro del mismo
    presupuesto de tiempo y el que falló queda en pausa un rato. Si ninguno responde, el grafo usa reglas.

    Bajo alta demanda un modelo a veces no responde 503 sino que se cuelga: cada intento tiene su propio tope
    (`attempt_timeout_s`) para que quede tiempo para el respaldo, y la cadena arranca por el último modelo
    que respondió bien (el turno siguiente no vuelve a esperar al que está saturado)."""

    def __init__(
        self,
        *,
        models: list[str],
        prompts: PromptBook,
        api_key: SecretStr | None = None,
        client_kwargs: dict | None = None,
        timeout_s: float,
        attempt_timeout_s: float | None = None,
        thinking_level: str | None = "low",
        pricing: Pricing | None = None,
        model_cooldown_s: float = 30.0,
    ) -> None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not models:
            raise ValueError("GeminiLLM necesita al menos un modelo")
        # API key de AI Studio o, en Cloud Run, Vertex AI (`vertexai=True, project, location`)
        credentials = client_kwargs or ({"google_api_key": api_key.get_secret_value()} if api_key else None)
        if not credentials:
            raise ValueError("GeminiLLM necesita api_key o client_kwargs")
        self.model_name = models[0]
        self.usage = LLMUsage()
        self._prompts = prompts
        self._timeout_s = timeout_s
        self._attempt_timeout_s = min(attempt_timeout_s or timeout_s, timeout_s)
        self._pricing = pricing or Pricing()
        self._preferred = 0
        self._chain: list[_Model] = []
        for model in models:
            chat = ChatGoogleGenerativeAI(
                model=model,
                **credentials,
                temperature=0,
                # Con respaldo no se reintenta el mismo modelo: pasar al siguiente es más rápido.
                max_retries=0 if len(models) > 1 else 1,
                timeout=max(timeout_s, MIN_SERVER_DEADLINE_S),
                thinking_config={"thinking_level": thinking_level} if thinking_level else None,
            )
            self._chain.append(
                _Model(
                    name=model,
                    extractor=chat.with_structured_output(SlotExtraction, method="json_schema", include_raw=True),
                    drafter=chat.with_structured_output(Draft, method="json_schema", include_raw=True),
                    breaker=CircuitBreaker(threshold=1, cooldown_s=model_cooldown_s),
                )
            )

    async def _invoke(self, stage: Literal["extractor", "drafter"], system: str, user: str, *, name: str) -> BaseModel:
        ordered = self._chain[self._preferred :] + self._chain[: self._preferred]
        available = [model for model in ordered if not model.breaker.is_open]
        if not available:
            raise LLMUnavailableError("circuit_open")
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        deadline = time.monotonic() + self._timeout_s
        reason = "timeout"
        for model in available:
            remaining = deadline - time.monotonic()
            if remaining < MIN_ATTEMPT_S:
                break
            try:
                runnable = getattr(model, stage)
                budget = min(remaining, self._attempt_timeout_s)
                parsed = await self._attempt(model, runnable, messages, user, name=name, timeout_s=budget)
            except _AttemptFailedError as exc:
                model.breaker.record(ok=False)
                reason = exc.reason
                log.warning("%s: %s falló (%s)", name, model.name, reason)
                continue
            model.breaker.record(ok=True)
            self._preferred = self._chain.index(model)
            return parsed
        raise LLMUnavailableError(reason)

    async def _attempt(
        self, model: _Model, runnable: Runnable, messages: list[BaseMessage], user: str, *, name: str, timeout_s: float
    ) -> BaseModel:
        # En la traza va solo la parte de usuario del prompt (el system lleva el canario) y la versión de prompts.
        with tracing.observe(
            name,
            as_type="generation",
            model=model.name,
            model_parameters={"temperature": 0},
            input=user,
            metadata={"prompt_version": self._prompts.version},
        ) as generation:
            try:
                result = await asyncio.wait_for(runnable.ainvoke(messages), timeout=timeout_s)
            except Exception as exc:  # cualquier falla del proveedor (429, 503, timeout, red) pasa al siguiente
                reason = failure_reason(exc)
                tracing.update(generation, level="ERROR", status_message=reason)
                raise _AttemptFailedError(reason) from exc
            usage = getattr(result.get("raw"), "usage_metadata", None) or {}
            tokens_in, tokens_out = int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
            cost = self._pricing.cost(tokens_in, tokens_out)
            self.usage.calls += 1
            self.usage.tokens_in += tokens_in
            self.usage.tokens_out += tokens_out
            self.usage.cost_usd += cost
            parsed = result.get("parsed")
            tracing.update(
                generation,
                output=parsed.model_dump(mode="json") if parsed is not None else None,
                usage_details={"input": tokens_in, "output": tokens_out},
                cost_details={"total": cost},
                level="ERROR" if parsed is None else "DEFAULT",
            )
        if parsed is None:
            raise _AttemptFailedError("invalid_structured_output")
        return parsed

    async def extract(self, request: ExtractRequest) -> SlotExtraction:
        stage = self._prompts.interpret
        recent = "\n".join(f"- {t}" for t in request.recent_customer_turns[-3:]) or "(ninguno)"
        user = fill(
            stage.user,
            today=request.today.isoformat(),
            language=request.language,
            pending_confirmation="sí" if request.pending_confirmation else "no",
            n_options=request.n_options,
            recent_turns=recent,
            message=request.message,
        )
        return await self._invoke("extractor", fill(stage.system, canary=CANARY_LINE), user, name="gemini.extract")

    async def draft(self, request: DraftRequest) -> str:
        stage = self._prompts.respond
        address = (
            "Trata al cliente de vos (voseo rioplatense)."
            if request.voseo
            else ("Trata al cliente de tú." if request.language == "es" else "Trate o cliente por você.")
        )
        system = fill(
            stage.system,
            language_name="español" if request.language == "es" else "portugués de Brasil",
            address_rule=address,
            canary=CANARY_LINE,
        )
        user = fill(
            stage.user,
            situation=request.situation,
            situation_description=request.situation_description,
            placeholders=", ".join(f"{{{{{k}}}}} ({v})" for k, v in request.placeholders.items()) or "(ninguno)",
            required=", ".join(f"{{{{{k}}}}}" for k in request.required) or "(ninguno)",
            reference=request.reference,
            message=request.message,
        )
        draft = await self._invoke("drafter", system, user, name="gemini.draft")
        return draft.text
