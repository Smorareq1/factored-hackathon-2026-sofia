"""Contexto de ejecución que GOVERN fija alrededor de cada nodo (lo leen las guardas de las tools)."""

from contextvars import ContextVar

# Nodo del grafo que está corriendo; lo fija el decorador @governed.
CURRENT_NODE: ContextVar[str | None] = ContextVar("sofia_current_node", default=None)

# Allowlist de acciones por nodo: se aplica en código, no en el prompt.
ACTION_ALLOWLIST: dict[str, frozenset[str]] = {
    "create_dispute": frozenset({"act"}),
    "create_handoff": frozenset({"escalate"}),
}


class ToolNotAllowedError(RuntimeError):
    """Un nodo intentó una acción fuera de su allowlist."""
