"""GOVERN: guardas por nodo, allowlist de tools, grounding check, kill switch, auditoría.

- `decorator.governed`: envuelve cada nodo (fallas → rutas seguras, eventos de capa, tool_log).
- `context`: nodo en curso + allowlist de acciones.
- `guards`: grounding check del borrador del LLM y guardia del texto final.
- `trail`: eventos de capa (§9.7).
"""
