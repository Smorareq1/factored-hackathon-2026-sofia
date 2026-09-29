# agent/ — dueño: AG

Agente Sofía: grafo LangGraph de 7 capas (PURPOSE, SENSE, INTERPRET, DECIDE, ORCHESTRATE, GOVERN, LEARN), Gemini
solo para extraer y redactar, servicio FastAPI/SSE para el frontend y baseline de sistema (§8.7) para comparar.

```
src/sofia_agent/
├── graph.py, state.py         StateGraph y AgentState (verified_facts con su fuente)
├── sense/ interpret/ decide/  capas del turno; orchestrate/ = act, verify, escalate, respond
├── govern/                    @governed: allowlist por nodo, grounding, guardia de salida, eventos §9.7
├── llm.py                     Gemini con cadena de modelos de respaldo, timeouts y costo por token
├── tracing.py                 trazas §9.6 en Langfuse (no-op sin keys)
├── turns.py                   un turno traceado (lo usan el chat y el harness)
├── runner.py                  run_conversation() para el harness (§9.5)
├── baseline/                  baseline §8.7: un LLM con las mismas tools, sin capas
├── evaluation.py              MET-01..06, reporte y gate de regresión
├── tools/                     cliente tipado de la API de SIM, banco falso en proceso, router
└── api/                       /v1/chat (SSE), sesión, consola y feedback
prompts/                       prompts versionados (su hash es prompt_version)
evals/dev_cases.jsonl          set dev (30 casos ES/PT, niveles 1–5, team_generated)
scripts/                       eval_gate.py, translate_cases.py
```

## Interfaz para el harness (propuesta #8)

```python
from sofia_agent.runner import run_conversation
from sofia_contracts.eval_case import EvalCase

result = run_conversation(EvalCase(...), "proposed")  # o "baseline"
result.route_final, result.tool_calls, result.handoff, result.trace_id, result.cost_usd
result.unverified_claims, result.foreign_references  # MET-04 (propuesta #17)
```

Corre en proceso contra `BANK_API_URL`: con `fake`, un banco nuevo por caso y las `faults` del caso aplicadas antes de
cada turno. Con la URL de SIM, la sesión sale de `POST /session/test` (propuesta #15). Para lotes está
`Harness.open()` + `run_many()`: van en serie porque el costo se mide como delta de tokens.

## Baseline de sistema (§8.7)

Bucle ReAct propio (máx. 8 pasos) sobre las mismas tools de la API, con el mismo modelo, la misma temperatura y la
misma cadena de respaldo. No tiene router, política propia, verificación, grounding ni allowlist. La ruta del turno
se infiere de lo que pasó en la API. Se usa por `/v1/chat` con `system_version: "baseline"` (el chat tiene un
selector) y por `run_conversation(case, "baseline")`. Necesita Gemini: en modo `rules` no hay baseline.

A diferencia del propuesto, el baseline sí envía los resultados de las tools (datos sintéticos) a Gemini.

## Evaluación y gate (LEARN)

```bash
make eval-gate                         # propuesto y baseline sobre el set dev; compara con la referencia
make eval-gate ARGS="--accept"         # fija esta corrida como referencia
make translate-cases ARGS="evals/dev_cases.jsonl --dry-run"
```

El gate promueve un cambio de prompt o de PURPOSE solo si MET-01 no baja y MET-04 no sube. Hay una referencia por
modo (`evals/reference.rules.json`, `evals/reference.gemini.json`) y los reportes quedan en `evals/reports/`
(ignorado por git). Para corridas reproducibles con LLM: `GEMINI_FALLBACK_MODELS=none`.

## Trazas (§9.6)

1 conversación = 1 trace (`trace_id` determinístico por hilo o por caso). El turno es una observación `agent` con
los nodos como hijos: cada nodo lleva `layer`, y debajo van las tools y las generaciones de Gemini (tokens y costo).
La traza lleva `session_id`, `case_id`, `language`, `system_version`, `prompt_version`, `purpose_version` y
`model`. El feedback de la consola llega a la traza como scores. Langfuse v4 local (`make langfuse`) corre en
modo `events_only`: se consulta con `GET /api/public/v2/observations?traceId=…`.

## Gemini en el free tier

`GEMINI_MODEL` + `GEMINI_FALLBACK_MODELS`: si un modelo da 503/429/timeout se prueba el siguiente (cada uno tiene
su propia cuota) y el que falló queda en pausa 30 s. Si ninguno responde, el turno sigue con reglas y plantillas
(REQ-16). La API rechaza plazos de servidor menores a 10 s: los cortes más cortos son locales.

## Chequeos

```bash
docker run --rm -v "$PWD/agent:/app/agent" -v "$PWD/contracts:/app/contracts" -w /app sofia/agent:dev \
  sh -c "ruff check agent contracts && pytest -q agent/tests"
```
