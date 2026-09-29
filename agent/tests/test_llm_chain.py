"""Cadena de modelos de Gemini (free tier): respaldo ante 503/429, pausa del modelo que falló y fallback a reglas."""

import asyncio

import pytest
from pydantic import SecretStr

from sofia_agent.config import Settings
from sofia_agent.llm import Draft, GeminiLLM, LLMUnavailableError, failure_reason
from sofia_agent.prompts import load_prompts


class ScriptedRunnable:
    def __init__(self, outcome: object, delay_s: float = 0) -> None:
        self.outcome, self.calls, self.delay_s = outcome, 0, delay_s

    async def ainvoke(self, messages: object) -> dict[str, object]:
        self.calls += 1
        await asyncio.sleep(self.delay_s)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return {"raw": None, "parsed": self.outcome}


def chain(*outcomes: object, **kwargs: float) -> tuple[GeminiLLM, list[ScriptedRunnable]]:
    models = [f"model-{i}" for i in range(len(outcomes))]
    llm = GeminiLLM(models=models, api_key=SecretStr("test"), prompts=load_prompts(), timeout_s=5, **kwargs)
    runnables = [o if isinstance(o, ScriptedRunnable) else ScriptedRunnable(o) for o in outcomes]
    for model, runnable in zip(llm._chain, runnables, strict=True):
        model.drafter = runnable
    return llm, runnables


async def test_falls_back_and_pauses_the_failing_model() -> None:
    busy = Exception("503 UNAVAILABLE. {'error': {'code': 503}}")
    llm, (primary, backup) = chain(busy, Draft(text="hola"))

    assert (await llm._invoke("drafter", "sys", "user", name="t")).text == "hola"
    assert (await llm._invoke("drafter", "sys", "user", name="t")).text == "hola"

    assert primary.calls == 1  # quedó en pausa tras el 503: el segundo turno va directo al respaldo
    assert backup.calls == 2


async def test_every_model_down_falls_back_to_rules() -> None:
    llm, runnables = chain(Exception("429 RESOURCE_EXHAUSTED. quota"), TimeoutError())

    with pytest.raises(LLMUnavailableError, match="^timeout$"):
        await llm._invoke("drafter", "sys", "user", name="t")
    with pytest.raises(LLMUnavailableError, match="^circuit_open$"):
        await llm._invoke("drafter", "sys", "user", name="t")
    assert [r.calls for r in runnables] == [1, 1]


async def test_a_hanging_model_leaves_time_for_the_backup() -> None:
    llm, (primary, backup) = chain(
        ScriptedRunnable(Draft(text="tarde"), delay_s=10), Draft(text="a tiempo"), attempt_timeout_s=0.2
    )
    llm._chain[0].breaker.cooldown_s = 0  # el principal vuelve a estar disponible enseguida

    assert (await llm._invoke("drafter", "sys", "user", name="t")).text == "a tiempo"
    assert (await llm._invoke("drafter", "sys", "user", name="t")).text == "a tiempo"
    assert primary.calls == 1  # el turno siguiente arranca por el último modelo que respondió


async def test_invalid_structured_output_tries_the_next_model() -> None:
    llm, _ = chain(None, Draft(text="ok"))
    assert (await llm._invoke("drafter", "sys", "user", name="t")).text == "ok"


def test_failure_reason_is_a_short_code() -> None:
    assert failure_reason(Exception("503 UNAVAILABLE. {'error': ...}")) == "503_unavailable"
    assert failure_reason(Exception("429 RESOURCE_EXHAUSTED. quota")) == "429_resource_exhausted"
    assert failure_reason(TimeoutError()) == "timeout"
    langchain_style = Exception("Error calling model 'm' (INVALID_ARGUMENT): 400 INVALID_ARGUMENT. {...}")
    assert failure_reason(langchain_style) == "400_invalid_argument"
    assert failure_reason(ValueError("x")) == "ValueError"


def test_model_chain_from_settings() -> None:
    settings = Settings(GEMINI_MODEL="a", GEMINI_FALLBACK_MODELS="b, a,c,")
    assert settings.gemini_models == ["a", "b", "c"]
    assert Settings(GEMINI_MODEL="a", GEMINI_FALLBACK_MODELS="none").gemini_models == ["a"]
    assert Settings(GEMINI_FALLBACK_MODELS="").gemini_models[0] == "gemini-3.5-flash"
