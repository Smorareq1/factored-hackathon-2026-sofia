"""Dependencias por turno que el grafo recibe como `context` de LangGraph (no se guardan en el checkpoint).

Así el token del cliente viaja con el request y nunca queda persistido.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sofia_agent.config import Settings
from sofia_agent.llm import LLMPort
from sofia_agent.prompts import PromptBook
from sofia_agent.purpose import Purpose
from sofia_agent.tools.bank import BankClient
from sofia_agent.tools.router import RouterClient


@dataclass
class Deps:
    settings: Settings
    purpose: Purpose
    prompts: PromptBook
    bank: BankClient
    router: RouterClient
    llm: LLMPort
    thread_id: str
    trace_id: str | None = None
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def now(self) -> datetime:
        return self.clock()
