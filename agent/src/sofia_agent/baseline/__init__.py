"""Baseline de sistema (§8.7): un solo LLM con tools, sin motor de política propio, sin verificación, sin router."""

from sofia_agent.baseline.agent import BaselineAgent, BaselineTurn, infer_route, make_baseline

__all__ = ["BaselineAgent", "BaselineTurn", "infer_route", "make_baseline"]
