"""quota: conversations that measured the provider's quota (429 or a fallback caused by one) are told apart."""

import asyncio

import pytest

from sofia_agent.runner import Harness
from sofia_contracts.eval_case import ConversationResult
from sofia_eval.levels import get_benchmark_cases
from sofia_eval.quota import is_rate_limited


def _result(errors: list[str] | None = None, fallbacks: list[str] | None = None) -> ConversationResult:
    return ConversationResult(
        case_id="EV-X",
        system_version="proposed",
        route_final="clarify",
        routes_per_turn=["clarify"],
        goal_status=None,
        turns=[],
        tool_calls=[],
        latency_ms=1,
        errors=errors or [],
        llm_fallbacks=fallbacks or [],
    )


@pytest.mark.parametrize(
    ("errors", "fallbacks", "limited"),
    [
        ([], [], False),
        (["turn 1: llm_unavailable:429_resource_exhausted"], [], True),  # baseline records the 429 as an error
        ([], ["turn 1: 429_resource_exhausted"], True),  # proposed degrades to rules
        ([], ["turn 2: circuit_open"], True),  # breaker opened by an earlier failure: never reached the provider
        ([], ["turn 1: llm_disabled"], False),  # rules mode by design, not a quota event
        ([], ["turn 1: timeout"], False),
    ],
)
def test_is_rate_limited(errors: list[str], fallbacks: list[str], limited: bool) -> None:
    assert is_rate_limited(_result(errors, fallbacks)) is limited


def test_harness_records_proposed_llm_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOFIA_LLM_MODE", "rules")
    case = next(c for c in get_benchmark_cases() if c.level == 1)

    async def run() -> ConversationResult:
        async with Harness.open() as harness:
            return await harness.run(case, "proposed")

    result = asyncio.run(run())
    assert result.llm_fallbacks, "rules mode must surface its fallbacks"
    assert all("llm_disabled" in f for f in result.llm_fallbacks)
    assert not result.errors
    assert not is_rate_limited(result)
