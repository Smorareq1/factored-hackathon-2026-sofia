"""Construcción de clientes compartidos del proceso (HTTP del banco y del router, LLM)."""

import httpx

from sofia_agent.config import FAKE_BANK, Settings
from sofia_agent.llm import GeminiLLM, LLMPort, Pricing, RulesOnlyLLM
from sofia_agent.prompts import PromptBook
from sofia_agent.purpose import Purpose
from sofia_agent.tools.fake_bank import default_fake_bank


def bank_http(settings: Settings, purpose: Purpose) -> httpx.AsyncClient:
    timeout = httpx.Timeout(purpose.limits.tool_timeout_s)
    if settings.bank_api_url == FAKE_BANK:
        app, _ = default_fake_bank()
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fake-bank", timeout=timeout)
    return httpx.AsyncClient(base_url=settings.bank_api_url, timeout=timeout)


def router_http(settings: Settings, purpose: Purpose) -> httpx.AsyncClient | None:
    if not settings.router_url:
        return None
    return httpx.AsyncClient(base_url=settings.router_url, timeout=httpx.Timeout(purpose.limits.tool_timeout_s))


def make_llm(settings: Settings, prompts: PromptBook) -> LLMPort:
    if settings.use_gemini and settings.gemini_api_key is not None:
        return GeminiLLM(
            models=settings.gemini_models,
            api_key=settings.gemini_api_key,
            prompts=prompts,
            timeout_s=settings.llm_timeout_s,
            attempt_timeout_s=settings.llm_attempt_timeout_s,
            thinking_level=None if settings.gemini_thinking_level == "default" else settings.gemini_thinking_level,
            pricing=pricing(settings),
        )
    return RulesOnlyLLM()


def pricing(settings: Settings) -> Pricing:
    return Pricing(settings.gemini_price_in_per_mtok, settings.gemini_price_out_per_mtok)
