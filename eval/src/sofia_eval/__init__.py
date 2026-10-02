"""Harness de evaluación: baseline vs propuesto sobre el set held-out (REQ-14, MET-01..MET-06)."""

from sofia_eval.levels import BENCHMARK_CASES, get_benchmark_cases
from sofia_eval.metrics import MetricSummary, calculate_metrics
from sofia_eval.report import build_evaluation_report
from sofia_eval.simulator import ClientSimulator

__all__ = [
    "BENCHMARK_CASES",
    "ClientSimulator",
    "MetricSummary",
    "build_evaluation_report",
    "calculate_metrics",
    "get_benchmark_cases",
]
