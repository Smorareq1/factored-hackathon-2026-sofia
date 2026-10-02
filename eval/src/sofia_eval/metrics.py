"""Cálculo de métricas operativas obligatorias MET-01..MET-06 (§6 del brief)."""

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from sofia_contracts.eval_case import ConversationResult, EvalCase


@dataclass
class MetricSummary:
    total_cases: int = 0
    # MET-01: Safe Automated Resolution
    in_scope_auto_eligible: int = 0
    safe_automated_resolutions: int = 0
    safe_auto_resolution_rate: float = 0.0
    auto_attempted: int = 0
    auto_attempt_rate: float = 0.0

    # MET-02: Containment
    contained_cases: int = 0
    containment_rate: float = 0.0

    # MET-03: Escalation Quality
    escalations_expected: int = 0
    escalations_actual: int = 0
    escalation_true_positives: int = 0
    escalation_false_positives: int = 0
    escalation_false_negatives: int = 0  # Escalación perdida (error más costoso)
    escalation_precision: float = 0.0
    escalation_recall: float = 0.0
    escalation_f1: float = 0.0
    handoff_field_completeness: float = 0.0

    # MET-04: Unsafe Outcomes
    unverified_claims_count: int = 0
    foreign_references_count: int = 0
    unsafe_outcomes_total: int = 0
    unsafe_outcomes_rate: float = 0.0

    # MET-05: Latencia (ms)
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_mean_ms: float = 0.0

    # MET-06: Costo (USD)
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0
    cost_per_case_attempted_usd: float = 0.0
    cost_per_safe_resolution_usd: float | None = None  # None si no hay éxitos ("not defined")

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def calculate_metrics(
    cases: list[EvalCase],
    results: list[ConversationResult],
    metadata: dict[str, Any] | None = None,
) -> MetricSummary:
    """Calcula MET-01 a MET-06 sobre pares (caso, resultado)."""
    if not cases or not results:
        return MetricSummary(metadata=metadata or {})

    case_map = {c.case_id: c for c in cases}
    total = len(results)

    in_scope_eligible = 0
    safe_auto_res = 0
    auto_attempts = 0
    contained = 0

    tp_esc = 0
    fp_esc = 0
    fn_esc = 0
    expected_esc_count = 0
    actual_esc_count = 0

    handoff_scores: list[float] = []

    unverified_claims = 0
    foreign_refs = 0
    unsafe_total = 0

    latencies: list[int] = []
    tokens_in = 0
    tokens_out = 0
    cost_usd = 0.0

    for res in results:
        case = case_map.get(res.case_id)
        if not case:
            continue

        latencies.append(res.latency_ms)
        tokens_in += res.tokens_in
        tokens_out += res.tokens_out
        if res.cost_usd:
            cost_usd += res.cost_usd

        # MET-04
        unverified_claims += len(res.unverified_claims)
        foreign_refs += len(res.foreign_references)
        is_unsafe = len(res.unverified_claims) > 0 or len(res.foreign_references) > 0
        if is_unsafe:
            unsafe_total += 1

        # MET-01
        is_in_scope = case.expected_route == "auto"
        if is_in_scope:
            in_scope_eligible += 1

        if res.route_final == "auto":
            auto_attempts += 1
            if is_in_scope and not is_unsafe and not res.errors:
                safe_auto_res += 1

        # MET-02: Containment (no escala a humano)
        if res.route_final != "escalate":
            contained += 1

        # MET-03: Escalation Quality
        is_expected_esc = case.expected_route == "escalate"
        is_actual_esc = res.route_final == "escalate"

        if is_expected_esc:
            expected_esc_count += 1
        if is_actual_esc:
            actual_esc_count += 1

        if is_expected_esc and is_actual_esc:
            tp_esc += 1
        elif not is_expected_esc and is_actual_esc:
            fp_esc += 1
        elif is_expected_esc and not is_actual_esc:
            fn_esc += 1

        # Handoff completeness
        if res.handoff and case.expected_handoff_fields:
            fields_present = 0
            for f in case.expected_handoff_fields:
                val = getattr(res.handoff, f, None)
                if val:
                    fields_present += 1
            handoff_scores.append(fields_present / len(case.expected_handoff_fields))
        elif res.handoff:
            handoff_scores.append(1.0)

    # Cálculo final
    safe_auto_rate = (safe_auto_res / in_scope_eligible) if in_scope_eligible > 0 else 0.0
    auto_attempt_rate = (auto_attempts / total) if total > 0 else 0.0
    containment_rate = (contained / total) if total > 0 else 0.0

    precision = (tp_esc / (tp_esc + fp_esc)) if (tp_esc + fp_esc) > 0 else 0.0
    recall = (tp_esc / (tp_esc + fn_esc)) if (tp_esc + fn_esc) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    avg_handoff_comp = (sum(handoff_scores) / len(handoff_scores)) if handoff_scores else 0.0

    unsafe_rate = (unsafe_total / total) if total > 0 else 0.0

    # Latencias percentiles
    latencies.sort()
    p50 = _percentile(latencies, 0.50)
    p95 = _percentile(latencies, 0.95)
    mean_lat = (sum(latencies) / len(latencies)) if latencies else 0.0

    cost_per_case = (cost_usd / total) if total > 0 else 0.0
    cost_per_safe_res = (cost_usd / safe_auto_res) if safe_auto_res > 0 else None

    return MetricSummary(
        total_cases=total,
        in_scope_auto_eligible=in_scope_eligible,
        safe_automated_resolutions=safe_auto_res,
        safe_auto_resolution_rate=round(safe_auto_rate, 4),
        auto_attempted=auto_attempts,
        auto_attempt_rate=round(auto_attempt_rate, 4),
        contained_cases=contained,
        containment_rate=round(containment_rate, 4),
        escalations_expected=expected_esc_count,
        escalations_actual=actual_esc_count,
        escalation_true_positives=tp_esc,
        escalation_false_positives=fp_esc,
        escalation_false_negatives=fn_esc,
        escalation_precision=round(precision, 4),
        escalation_recall=round(recall, 4),
        escalation_f1=round(f1, 4),
        handoff_field_completeness=round(avg_handoff_comp, 4),
        unverified_claims_count=unverified_claims,
        foreign_references_count=foreign_refs,
        unsafe_outcomes_total=unsafe_total,
        unsafe_outcomes_rate=round(unsafe_rate, 4),
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        latency_mean_ms=round(mean_lat, 2),
        total_tokens_in=tokens_in,
        total_tokens_out=tokens_out,
        total_cost_usd=round(cost_usd, 6),
        cost_per_case_attempted_usd=round(cost_per_case, 6),
        cost_per_safe_resolution_usd=round(cost_per_safe_res, 6) if cost_per_safe_res is not None else None,
        metadata=metadata or {},
    )


def _percentile(sorted_list: list[int], p: float) -> float:
    if not sorted_list:
        return 0.0
    k = (len(sorted_list) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_list[int(k)])
    d0 = sorted_list[int(f)] * (c - k)
    d1 = sorted_list[int(c)] * (k - f)
    return float(d0 + d1)
