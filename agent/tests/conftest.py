"""Fixtures: banco falso en proceso, reglas en vez de Gemini y un helper para conversar con el grafo."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from sofia_agent.config import Settings
from sofia_agent.deps import Deps
from sofia_agent.graph import compile_graph, turn_input
from sofia_agent.llm import LLMPort, RulesOnlyLLM
from sofia_agent.prompts import load_prompts
from sofia_agent.purpose import load_purpose
from sofia_agent.tools.bank import BankClient
from sofia_agent.tools.fake_bank import FakeBankState, create_fake_bank
from sofia_agent.tools.router import RouterClient
from sofia_contracts.bank_api import SessionStart, SessionVerify

NOW = datetime(2026, 9, 27, 18, 0, tzinfo=UTC)


@dataclass
class Conversation:
    """Un hilo de chat contra el grafo, con el banco falso detrás."""

    graph: Any
    http: httpx.AsyncClient
    bank_state: FakeBankState
    token: str
    llm: LLMPort
    settings: Settings
    thread_id: str = "thread-test-0001"
    turn: int = 0
    events: list[Any] = field(default_factory=list)

    def deps(self) -> Deps:
        return Deps(
            settings=self.settings,
            purpose=load_purpose(),
            prompts=load_prompts(),
            bank=BankClient(self.http, self.token, backoff_s=0),
            router=RouterClient(None),
            llm=self.llm,
            thread_id=self.thread_id,
            clock=lambda: NOW,
        )

    async def say(self, message: str, language_hint: str | None = None) -> dict[str, Any]:
        self.turn += 1
        config = {"configurable": {"thread_id": self.thread_id}}
        self.events = []
        async for chunk in self.graph.astream(
            turn_input(message=message, turn=self.turn, thread_id=self.thread_id, language_hint=language_hint),
            config,
            context=self.deps(),
            stream_mode="custom",
        ):
            self.events.append(chunk["layer_event"])
        return (await self.graph.aget_state(config)).values

    def codes(self) -> list[str]:
        return [e.code for e in self.events]


async def login(http: httpx.AsyncClient, document: str) -> str:
    client = BankClient(http, None)
    challenge = await client.start_session(SessionStart(document_number=document))
    token = await client.verify_session(SessionVerify(challenge_id=challenge.challenge_id, otp=challenge.simulated_otp))
    return token.access_token


@pytest.fixture
def bank():
    app, state = create_fake_bank(now=NOW)
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fake-bank")
    return http, state


@pytest.fixture
def settings() -> Settings:
    return Settings(SOFIA_LLM_MODE="rules", BANK_API_URL="fake")


@pytest.fixture
def start(bank, settings):
    """`conv = await start("MX-DEMO-001")` abre un hilo autenticado como ese cliente demo."""
    http, state = bank

    async def _start(document: str, *, llm: LLMPort | None = None, **overrides: Any) -> Conversation:
        token = await login(http, document)
        conv_settings = settings.model_copy(update=overrides) if overrides else settings
        return Conversation(
            graph=compile_graph(),
            http=http,
            bank_state=state,
            token=token,
            llm=llm or RulesOnlyLLM(),
            settings=conv_settings,
        )

    return _start
