"""Recursos del proceso (grafo compilado, checkpointer, clientes HTTP, LLM, baseline) y `Deps` por request."""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import httpx
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from sofia_agent.baseline import BaselineAgent, make_baseline
from sofia_agent.config import Settings
from sofia_agent.deps import Deps
from sofia_agent.graph import checkpoint_serde, compile_graph
from sofia_agent.llm import LLMPort
from sofia_agent.prompts import PromptBook, load_prompts
from sofia_agent.purpose import Purpose, load_purpose
from sofia_agent.tools.bank import BankClient
from sofia_agent.tools.router import RouterClient
from sofia_agent.wiring import bank_http, make_llm, router_http


@asynccontextmanager
async def open_checkpointer(settings: Settings) -> AsyncIterator[BaseCheckpointSaver]:
    """Postgres si hay DATABASE_URL (local: contenedor; Cloud Run: Neon); si no, memoria."""
    if not settings.database_url:
        yield InMemorySaver(serde=checkpoint_serde())
        return
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    # prepare_threshold=0 y autocommit: requisitos del pooler de Neon (y de AsyncPostgresSaver).
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        max_size=5,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await pool.open()
    try:
        saver = AsyncPostgresSaver(pool, serde=checkpoint_serde())  # type: ignore[arg-type]
        await saver.setup()
        yield saver
    finally:
        await pool.close()


@dataclass
class BaselineThread:
    """Hilo del baseline (§8.7): solo en memoria; el baseline no tiene checkpointer ni estado propio."""

    owner_customer_id: str
    history: list[BaseMessage] = field(default_factory=list)
    turn: int = 0


@dataclass
class AgentRuntime:
    settings: Settings
    purpose: Purpose
    prompts: PromptBook
    graph: CompiledStateGraph
    bank_http: httpx.AsyncClient
    router_http: httpx.AsyncClient | None
    llm: LLMPort
    checkpointer_kind: str
    baseline: BaselineAgent | None = None
    baseline_threads: dict[str, BaselineThread] = field(default_factory=dict)
    _locks: defaultdict[str, asyncio.Lock] = field(default_factory=lambda: defaultdict(asyncio.Lock))
    _tasks: set[asyncio.Task] = field(default_factory=set)

    def bank(self, token: str | None, *, enforce_allowlist: bool = True) -> BankClient:
        return BankClient(
            self.bank_http,
            token,
            max_retries=self.purpose.limits.max_tool_retries,
            enforce_allowlist=enforce_allowlist,
        )

    def spawn(self, coro: Coroutine[object, object, None]) -> asyncio.Task:
        """El turno corre fuera del request: termina (y queda en el checkpoint) aunque el cliente se desconecte."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def drain_tasks(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def deps(self, token: str, thread_id: str, trace_id: str | None = None) -> Deps:
        return Deps(
            settings=self.settings,
            purpose=self.purpose,
            prompts=self.prompts,
            bank=self.bank(token),
            router=RouterClient(self.router_http),
            llm=self.llm,
            thread_id=thread_id,
            trace_id=trace_id,
        )

    def thread_lock(self, thread_id: str) -> asyncio.Lock:
        """Un turno a la vez por hilo: dos pestañas no pueden intercalar confirmaciones."""
        return self._locks[thread_id]


@asynccontextmanager
async def open_runtime(settings: Settings) -> AsyncIterator[AgentRuntime]:
    purpose, prompts = load_purpose(), load_prompts()
    bank = bank_http(settings, purpose)
    router = router_http(settings, purpose)
    try:
        async with open_checkpointer(settings) as saver:
            runtime = AgentRuntime(
                settings=settings,
                purpose=purpose,
                prompts=prompts,
                graph=compile_graph(saver),
                bank_http=bank,
                router_http=router,
                llm=make_llm(settings, prompts),
                checkpointer_kind=type(saver).__name__,
                baseline=make_baseline(settings, prompts),
            )
            try:
                yield runtime
            finally:
                await runtime.drain_tasks()  # los turnos en curso terminan antes de cerrar clientes y checkpointer
    finally:
        await bank.aclose()
        if router is not None:
            await router.aclose()
