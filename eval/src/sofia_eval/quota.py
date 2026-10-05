"""Which conversations measured the provider's quota instead of the system (DS).

A 429 / RESOURCE_EXHAUSTED is a quota event, not a system failure. The baseline records it in `errors`; the proposed
system degrades to its rules and records it in `llm_fallbacks`. After a failure the model chain's circuit breaker
answers `circuit_open` without calling the provider, so that reason counts too: those turns never reached Gemini.
"""

from sofia_contracts.eval_case import ConversationResult

RATE_LIMIT_MARKERS = ("429", "resource_exhausted", "rate limit", "quota")
FALLBACK_MARKERS = (*RATE_LIMIT_MARKERS, "circuit_open")


def is_rate_limited(result: ConversationResult) -> bool:
    return any(m in e.lower() for e in result.errors for m in RATE_LIMIT_MARKERS) or any(
        m in f.lower() for f in result.llm_fallbacks for m in FALLBACK_MARKERS
    )
