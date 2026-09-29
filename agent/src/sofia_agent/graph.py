"""StateGraph del sistema propuesto: sense → interpret → decide → act/verify/escalate → respond.

Cada nodo lleva `@governed` (GOVERN transversal). El ruteo entre nodos es determinístico y cualquier nodo
puede desviar a `reauth` (401) o `escalate` (tool caída, verificación fallida, guarda activada).
"""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from sofia_agent.decide.node import abstain, decide
from sofia_agent.deps import Deps
from sofia_agent.interpret.node import clarify, interpret
from sofia_agent.orchestrate.nodes import act, escalate, verify
from sofia_agent.orchestrate.respond import respond
from sofia_agent.sense.node import reauth, sense
from sofia_agent.state import CHECKPOINT_MODELS, PER_TURN_RESET, AgentState
from sofia_contracts.common import Language, SystemVersion


def _diverted(state: AgentState) -> str | None:
    route = state.get("route")
    if route == "reauth":
        return "reauth"
    if route == "escalate":
        return "escalate"
    return None


def after_sense(state: AgentState) -> str:
    return _diverted(state) or "interpret"


def after_interpret(state: AgentState) -> str:
    if diverted := _diverted(state):
        return diverted
    return "clarify" if state.get("route") == "clarify" else "decide"


def after_clarify(state: AgentState) -> str:
    return "escalate" if state.get("route") == "escalate" else "respond"


def after_decide(state: AgentState) -> str:
    if diverted := _diverted(state):
        return diverted
    if state.get("route") == "abstain" and not state.get("situation"):
        return "abstain"
    if state.get("ready_to_act"):
        return "act"
    return "respond"


def after_act(state: AgentState) -> str:
    return _diverted(state) or "verify"


def after_verify(state: AgentState) -> str:
    return _diverted(state) or "respond"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState, context_schema=Deps)
    for name, node in {
        "sense": sense,
        "reauth": reauth,
        "interpret": interpret,
        "clarify": clarify,
        "decide": decide,
        "abstain": abstain,
        "act": act,
        "verify": verify,
        "escalate": escalate,
        "respond": respond,
    }.items():
        graph.add_node(name, node)

    graph.add_edge(START, "sense")
    graph.add_conditional_edges("sense", after_sense, ["interpret", "reauth", "escalate"])
    graph.add_conditional_edges("interpret", after_interpret, ["clarify", "decide", "reauth", "escalate"])
    graph.add_conditional_edges("clarify", after_clarify, ["escalate", "respond"])
    graph.add_conditional_edges("decide", after_decide, ["abstain", "act", "respond", "reauth", "escalate"])
    graph.add_conditional_edges("act", after_act, ["verify", "reauth", "escalate"])
    graph.add_conditional_edges("verify", after_verify, ["respond", "reauth", "escalate"])
    for name in ("reauth", "abstain", "escalate"):
        graph.add_edge(name, "respond")
    graph.add_edge("respond", END)
    return graph


def checkpoint_serde() -> JsonPlusSerializer:
    """Deserialización estricta: solo nuestros modelos Pydantic, nunca pickle."""
    return JsonPlusSerializer(allowed_msgpack_modules=[(m.__module__, m.__name__) for m in CHECKPOINT_MODELS])


def compile_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    return build_graph().compile(checkpointer=checkpointer or InMemorySaver(serde=checkpoint_serde()))


def turn_input(
    *,
    message: str,
    turn: int,
    thread_id: str,
    language_hint: Language | None,
    system_version: SystemVersion = "proposed",
) -> dict[str, Any]:
    """Entrada de un turno: el mensaje crudo + el reinicio de los campos por turno."""
    return {
        **PER_TURN_RESET,
        "message": message,
        "turn": turn,
        "thread_id": thread_id,
        "language_hint": language_hint,
        "system_version": system_version,
    }
