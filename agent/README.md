# agent/ — owner: AG

The Sofía agent: a 7-layer LangGraph graph (PURPOSE, SENSE, INTERPRET, DECIDE, ORCHESTRATE, GOVERN, LEARN), Gemini
only to extract and write, a FastAPI/SSE service for the frontend and a system baseline (§8.7) for comparison.

```
src/sofia_agent/
├── graph.py, state.py         StateGraph and AgentState (verified_facts with their source)
├── sense/ interpret/ decide/  turn layers; orchestrate/ = act, verify, escalate, respond
├── govern/                    @governed: per-node allowlist, grounding, output guard, §9.7 events
├── llm.py                     Gemini with a fallback model chain, timeouts and per-token cost
├── tracing.py                 §9.6 traces in Langfuse (no-op without keys)
├── turns.py                   one traced turn (used by the chat and the harness)
├── runner.py                  run_conversation() for the harness (§9.5)
├── baseline/                  §8.7 baseline: one LLM with the same tools, no layers
├── evaluation.py              MET-01..06, report and regression gate
├── tools/                     typed client for SIM's API, in-process fake bank, router
└── api/                       /v1/chat (SSE), session, console and feedback
prompts/                       versioned prompts (their hash is prompt_version)
evals/dev_cases.jsonl          dev set (30 ES/PT cases, levels 1–5, team_generated)
scripts/                       eval_gate.py, translate_cases.py
```

## Harness interface (proposal #8)

```python
from sofia_agent.runner import run_conversation
from sofia_contracts.eval_case import EvalCase

result = run_conversation(EvalCase(...), "proposed")  # or "baseline"
result.route_final, result.tool_calls, result.handoff, result.trace_id, result.cost_usd
result.unverified_claims, result.foreign_references  # MET-04 (proposal #17)
```

It runs in-process against `BANK_API_URL`: with `fake`, a fresh bank per case with the case's `faults` applied before
each turn. With SIM's URL, the session comes from `POST /session/test` (proposal #15). For batches there is
`Harness.open()` + `run_many()`: they run serially because cost is measured as a token delta.

## System baseline (§8.7)

A custom ReAct loop (max. 8 steps) over the same API tools, with the same model, the same temperature and the same
fallback chain. It has no router, no policy of its own, no verification, no grounding and no allowlist. The turn's route
is inferred from what happened in the API. It is used through `/v1/chat` with `system_version: "baseline"` (the chat has
a selector) and through `run_conversation(case, "baseline")`. It needs Gemini: in `rules` mode there is no baseline.

Unlike the proposed system, the baseline does send tool results (synthetic data) to Gemini.

## Evaluation and gate (LEARN)

```bash
make eval-gate                         # proposed and baseline over the dev set; compared with the reference
make eval-gate ARGS="--accept"         # sets this run as the reference
make translate-cases ARGS="evals/dev_cases.jsonl --dry-run"
```

The gate promotes a prompt or PURPOSE change only if MET-01 does not drop and MET-04 does not rise. There is one
reference per mode (`evals/reference.rules.json`, `evals/reference.gemini.json`) and reports go to `evals/reports/`
(ignored by git). For reproducible LLM runs: `GEMINI_FALLBACK_MODELS=none`.

## Handoff (§9.4)

The assembler (`orchestrate/handoff.py`) builds the card from verified state only. It does not copy the transcript (REQ-05).

Compared with the brief's JSON, the card adds four fields (AG proposal #9, contract in `contracts/.../handoff.py`):

| Field | Set by | Purpose |
|---|---|---|
| `schema_version` | agent (`1.0`) | JSON version |
| `customer_claim` | agent | structured reason, in addition to the summary |
| `system_version` | agent | `proposed` or `baseline` |
| `created_at` | SIM, when storing | not part of the draft |

`request_summary` and `open_questions` are written in the conversation's language (es or pt). `verified_facts` stay in Spanish: it is the back office's language. In the baseline the model writes the summary, in that same language; `open_questions` stays empty because the baseline has no question catalog.

## Portuguese cases

The harness catalog (`eval/src/sofia_eval/generator.py`) is balanced: 100 ES and 100 PT, all `origin: team_generated`. The dataset has no native Portuguese. `scripts/translate_cases.py` translates with identifiers masked. The fixes already made to the router corpus are in `ml/reports/corpus_audit.md` (DS owner). We do not publish a count of "corrected cases" for the evaluation catalog because that review was not measured case by case, and the PT text has not been reviewed by a native speaker.

The agent's development set (`evals/dev_cases.jsonl`, 23 ES and 7 PT) feeds the regression gate. It is not the report's sample, so it was not rebalanced: changing it invalidates `evals/reference.*.json` without a new run.

## Traces (§9.6)

1 conversation = 1 trace (`trace_id` deterministic per thread or per case). The turn is an `agent` observation with the
nodes as children: each node carries `layer`, and below it go the tools and the Gemini generations (tokens and cost).
The trace carries `session_id`, `case_id`, `language`, `system_version`, `prompt_version`, `purpose_version` and
`model`. Console feedback reaches the trace as scores. Local Langfuse v4 (`make langfuse`) runs in `events_only` mode:
query it with `GET /api/public/v2/observations?traceId=…`.

## Gemini on the free tier

`GEMINI_MODEL` + `GEMINI_FALLBACK_MODELS`: if a model returns 503/429/timeout the next one is tried (each has its own
quota) and the failing one is paused for 30 s. If none answers, the turn continues with rules and templates (REQ-16).
The API rejects server deadlines under 10 s: shorter cutoffs are local.

## Checks

```bash
docker run --rm -v "$PWD/agent:/app/agent" -v "$PWD/contracts:/app/contracts" -w /app sofia/agent:dev \
  sh -c "ruff check agent contracts && pytest -q agent/tests"
```
