"""Interfaz del harness (propuesta AG #8): `run_conversation(case, system_version) -> ConversationResult`.

Corre los turnos de un caso §9.5 en proceso (sin pasar por el HTTP del agente) contra la API bancaria:

- `BANK_API_URL=fake`: un banco falso NUEVO por caso (una disputa creada en un caso no cambia el siguiente) y
  las fallas del caso (`faults`, nivel 5) se aplican en proceso.
- URL de SIM: la sesión sale de `POST /session/test` (propuesta #15) y las fallas las aplica SIM.

Además de las rutas, mide lo que MET-04 necesita sin releer el transcript a mano: IDs de caso/handoff que el
agente afirmó y la API no devuelve (`unverified_claims`) e IDs ajenos que mencionó (`foreign_references`).
"""

import asyncio
import re
import secrets
import time
from collections.abc import AsyncIterator, Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from langchain_core.messages import BaseMessage

from sofia_agent import tracing
from sofia_agent.baseline import BaselineAgent, make_baseline
from sofia_agent.config import FAKE_BANK, Settings, get_settings
from sofia_agent.deps import Deps
from sofia_agent.graph import compile_graph
from sofia_agent.llm import LLMPort, LLMUsage
from sofia_agent.prompts import PromptBook, load_prompts
from sofia_agent.purpose import Purpose, load_purpose
from sofia_agent.tools.bank import BankClient, SessionExpiredError, ToolRejectedError, ToolUnavailableError
from sofia_agent.tools.fake_bank import FakeBankState, create_fake_bank
from sofia_agent.tools.router import RouterClient
from sofia_agent.turns import run_turn, traced_turn
from sofia_agent.wiring import make_llm, router_http
from sofia_contracts.common import Route, SystemVersion
from sofia_contracts.eval_case import ConversationResult, EvalCase, InjectedFault, ToolCallRecord, TurnResult
from sofia_contracts.handoff import Handoff
from sofia_contracts.tracing import TraceMetadata

DISPUTE_REF = re.compile(r"\bDSP-\d{4}-\d{6}\b")
HANDOFF_REF = re.compile(r"\bHO-\d{4}-\d{6}\b")
CUSTOMER_REF = re.compile(r"\bC\d{8}\b")
TX_REF = re.compile(r"\b(?:TX-[A-Z]{2}-\d{4}|TX\d{6,}|TRX-?\d{6,})\b", re.IGNORECASE)


@dataclass
class _CaseBank:
    http: httpx.AsyncClient
    state: FakeBankState | None  # None = SIM (las fallas las aplica SIM)
    owned: bool

    async def aclose(self) -> None:
        if self.owned:
            await self.http.aclose()


@dataclass
class _Run:
    """Acumulador de un caso, igual para los dos sistemas."""

    case: EvalCase
    system_version: SystemVersion
    thread_id: str
    trace_id: str | None
    turns: list[TurnResult] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    handoff: Handoff | None = None
    goal_status: str | None = None
    latency_ms: int = 0


class Harness:
    def __init__(
        self,
        *,
        settings: Settings,
        purpose: Purpose,
        prompts: PromptBook,
        llm: LLMPort,
        baseline: BaselineAgent | None,
        router_http: httpx.AsyncClient | None = None,
        sim_http: httpx.AsyncClient | None = None,
        clock: Callable[[], datetime] | None = None,
        bank_backoff_s: float = 0.2,
    ) -> None:
        self.settings, self.purpose, self.prompts = settings, purpose, prompts
        self.llm, self.baseline = llm, baseline
        self._router_http, self._sim_http = router_http, sim_http
        self._clock = clock
        self._backoff_s = bank_backoff_s

    @classmethod
    @asynccontextmanager
    async def open(
        cls,
        settings: Settings | None = None,
        *,
        llm: LLMPort | None = None,
        baseline: BaselineAgent | None = None,
        clock: Callable[[], datetime] | None = None,
        bank_backoff_s: float = 0.2,
    ) -> AsyncIterator["Harness"]:
        settings = settings or get_settings()
        purpose, prompts = load_purpose(), load_prompts()
        if not tracing.enabled():
            tracing.configure(settings)
        router = router_http(settings, purpose)
        sim = None
        if settings.bank_api_url != FAKE_BANK:
            sim = httpx.AsyncClient(
                base_url=settings.bank_api_url, timeout=httpx.Timeout(purpose.limits.tool_timeout_s)
            )
        try:
            yield cls(
                settings=settings,
                purpose=purpose,
                prompts=prompts,
                llm=llm or make_llm(settings, prompts),
                baseline=baseline if baseline is not None else make_baseline(settings, prompts),
                router_http=router,
                sim_http=sim,
                clock=clock,
                bank_backoff_s=bank_backoff_s,
            )
        finally:
            tracing.flush()
            for client in (router, sim):
                if client is not None:
                    await client.aclose()

    # ───────────────────────── un caso ─────────────────────────
    async def run(self, case: EvalCase, system_version: SystemVersion = "proposed") -> ConversationResult:
        bank = self._open_bank()
        thread_id = f"eval-{case.case_id}-{system_version[:4]}-{secrets.token_hex(4)}"
        run = _Run(case, system_version, thread_id, tracing.trace_id_for(thread_id))
        usage = self._usage(system_version)
        before = usage.snapshot() if usage else LLMUsage()
        try:
            if system_version == "baseline" and self.baseline is None:
                run.errors.append("baseline_unavailable: el baseline necesita Gemini (SOFIA_LLM_MODE=rules o sin key)")
            else:
                await self._drive(run, bank)
            texts = [t.agent for t in run.turns]
            claims, foreign = await self._audit(bank, case, texts, run.errors)
        finally:
            await bank.aclose()
        spent = usage.since(before) if usage else LLMUsage()
        routes = [t.route for t in run.turns]
        return ConversationResult(
            case_id=case.case_id,
            system_version=system_version,
            route_final=routes[-1] if routes else None,
            routes_per_turn=routes,
            goal_status=run.goal_status,
            turns=run.turns,
            tool_calls=run.tool_calls,
            handoff=run.handoff,
            trace_id=run.trace_id,
            latency_ms=run.latency_ms,
            llm_calls=spent.calls,
            tokens_in=spent.tokens_in,
            tokens_out=spent.tokens_out,
            cost_usd=round(spent.cost_usd, 6),
            errors=run.errors,
            unverified_claims=claims,
            foreign_references=foreign,
        )

    async def run_many(
        self, cases: Iterable[EvalCase], system_versions: Iterable[SystemVersion] = ("proposed",)
    ) -> list[ConversationResult]:
        """En serie: el costo se mide como delta del contador de uso y el free tier no tolera ráfagas."""
        results = []
        for case in cases:
            for version in system_versions:
                results.append(await self.run(case, version))
        tracing.flush()
        return results

    # ───────────────────────── internos ─────────────────────────
    def _usage(self, system_version: SystemVersion) -> LLMUsage | None:
        if system_version == "baseline":
            return self.baseline.usage if self.baseline else None
        return self.llm.usage

    def _open_bank(self) -> _CaseBank:
        if self._sim_http is not None:
            return _CaseBank(self._sim_http, None, owned=False)
        app, state = create_fake_bank(now=self._clock() if self._clock else None)
        http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fake-bank")
        return _CaseBank(http, state, owned=True)

    def _client(self, bank: _CaseBank, token: str | None, *, baseline: bool = False) -> BankClient:
        return BankClient(
            bank.http,
            token,
            max_retries=self.purpose.limits.max_tool_retries,
            backoff_s=self._backoff_s,
            enforce_allowlist=not baseline,
        )

    async def _session(self, bank: _CaseBank, case: EvalCase) -> str:
        token = await BankClient(bank.http, None).harness_session(case.session_customer_id)
        return token.access_token

    def _apply_faults(self, run: _Run, bank: _CaseBank, turn: int) -> None:
        faults = [f for f in run.case.faults if f.before_turn == turn]
        if not faults:
            return
        if bank.state is None:
            run.errors.append(f"turn {turn}: fallas delegadas a SIM ({', '.join(f.kind for f in faults)})")
            return
        for fault in faults:
            _inject(bank.state, fault)

    async def _drive(self, run: _Run, bank: _CaseBank) -> None:
        case = run.case
        token = await self._session(bank, case)
        graph = compile_graph() if run.system_version == "proposed" else None
        history: list[BaseMessage] = []
        for turn, message in enumerate(case.turns, start=1):
            self._apply_faults(run, bank, turn)
            started = time.perf_counter()
            try:
                if graph is not None:
                    text, route = await self._proposed_turn(run, bank, graph, token, turn, message)
                else:
                    text, route = await self._baseline_turn(run, bank, history, token, turn, message)
            except Exception as exc:  # un caso roto se reporta como error, no tumba la corrida entera
                run.errors.append(f"turn {turn}: {type(exc).__name__}: {exc}"[:300])
                break
            finally:
                run.latency_ms += int((time.perf_counter() - started) * 1000)
            run.turns.append(TurnResult(turn=turn, user=message, agent=text, route=route))
            if route == "reauth":
                token = await self._session(bank, case)  # el cliente vuelve a iniciar sesión

    async def _proposed_turn(
        self, run: _Run, bank: _CaseBank, graph: Any, token: str, turn: int, message: str
    ) -> tuple[str, Route | None]:
        deps = Deps(
            settings=self.settings,
            purpose=self.purpose,
            prompts=self.prompts,
            bank=self._client(bank, token),
            router=RouterClient(self._router_http),
            llm=self.llm,
            thread_id=run.thread_id,
            trace_id=run.trace_id,
            **({"clock": self._clock} if self._clock else {}),
        )
        # Sin language_hint: el harness no le regala el idioma al propuesto (el baseline tampoco lo recibe).
        outcome = await run_turn(
            graph,
            deps,
            message=message,
            turn=turn,
            language_hint=None,
            language=run.case.language,
            case_id=run.case.case_id,
        )
        state = outcome.state
        run.tool_calls = list(state.get("tool_log") or [])
        run.handoff = state.get("handoff")
        goal = state.get("goal")
        run.goal_status = goal.status if goal else None
        response = state.get("response")
        return (response.text if response else ""), state.get("route")

    async def _baseline_turn(
        self, run: _Run, bank: _CaseBank, history: list[BaseMessage], token: str, turn: int, message: str
    ) -> tuple[str, Route | None]:
        assert self.baseline is not None
        client = self._client(bank, token, baseline=True)
        meta = TraceMetadata(
            session_id=run.thread_id,
            case_id=run.case.case_id,
            language=run.case.language,
            system_version="baseline",
            prompt_version=self.baseline.prompt_version,
            purpose_version="none",
            model=self.baseline.model_name,
        )
        with traced_turn(meta=meta, trace_id=run.trace_id, turn=turn, message=message) as span:
            reply = await self.baseline.turn(
                history=history,
                message=message,
                bank=client,
                turn=turn,
                thread_id=run.thread_id,
                trace_id=run.trace_id,
            )
            tracing.update(span, output=reply.text, metadata={"route": reply.route, "tools": reply.tools})
        run.tool_calls.extend(record.model_copy(update={"turn": turn}) for record in client.drain())
        run.handoff = reply.handoff or run.handoff
        run.goal_status = _baseline_goal(reply.route, reply.text, created=reply.dispute_id is not None)
        if reply.error:
            run.errors.append(f"turn {turn}: {reply.error}")
        return reply.text, reply.route

    async def _audit(
        self, bank: _CaseBank, case: EvalCase, texts: list[str], errors: list[str]
    ) -> tuple[list[str], list[str]]:
        """Relee en la API los IDs que el agente escribió (con una sesión nueva y sin fallas inyectadas)."""
        agent_text = "\n".join(texts)
        typed = {ref.upper() for turn in case.turns for ref in (*CUSTOMER_REF.findall(turn), *TX_REF.findall(turn))}
        if not agent_text.strip():
            return [], []
        if bank.state is not None:
            bank.state.faults.clear()
        try:
            client = BankClient(bank.http, await self._session(bank, case), max_retries=0, backoff_s=0)
            claims = [
                ref for ref in sorted(set(DISPUTE_REF.findall(agent_text))) if await client.get_dispute(ref) is None
            ]
            claims += [
                ref for ref in sorted(set(HANDOFF_REF.findall(agent_text))) if await client.get_handoff(ref) is None
            ]
            foreign = [
                ref
                for ref in sorted(set(CUSTOMER_REF.findall(agent_text)))
                if ref != case.session_customer_id and ref not in typed
            ]
            for ref in sorted({r.upper() for r in TX_REF.findall(agent_text)} - typed):
                if await client.get_transaction(ref) is None:
                    foreign.append(ref)
        except (SessionExpiredError, ToolRejectedError, ToolUnavailableError) as exc:
            errors.append(f"audit: {type(exc).__name__}")
            return [], []
        return claims, foreign


def _baseline_goal(route: Route, text: str, *, created: bool) -> str:
    """El baseline no tiene PURPOSE: el estado de la meta se aproxima con lo observable (misma escala que §9.7)."""
    if route == "auto":
        return "resolved" if created or "?" not in text else "open"
    return {"deny": "denied", "escalate": "escalated", "abstain": "abstained"}.get(route, "open")


def _inject(state: FakeBankState, fault: InjectedFault) -> None:
    if fault.kind == "session_expired":
        state.expire_sessions()
    elif fault.kind == "drop_writes":
        state.drop_dispute_writes = True
    elif fault.endpoint:
        state.faults.setdefault(fault.endpoint, []).extend([fault.status] * fault.times)


# ───────────────────────── API pública para el harness de SIM ─────────────────────────
async def arun_conversation(
    case: EvalCase,
    system_version: SystemVersion = "proposed",
    *,
    harness: Harness | None = None,
    settings: Settings | None = None,
) -> ConversationResult:
    if harness is not None:
        return await harness.run(case, system_version)
    async with Harness.open(settings) as opened:
        return await opened.run(case, system_version)


def run_conversation(
    case: EvalCase, system_version: SystemVersion = "proposed", *, settings: Settings | None = None
) -> ConversationResult:
    """Síncrona, para el harness de SIM: `run_conversation(case, "baseline")`."""
    return asyncio.run(arun_conversation(case, system_version, settings=settings))
