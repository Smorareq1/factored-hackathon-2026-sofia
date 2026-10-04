# infra/ — owner: OPS

Deployment and operations outside the local environment (local lives in [containers/](../containers/)).

## Cloud Run (`cloudrun/`)

GCP project `sofia-factored-hackathon`, region `us-central1`.

Deployed on 2026-10-01; agent connected to bank-api on 2026-10-04: **https://frontend-i6dmh3qssa-uc.a.run.app** (agent at
`https://agent-i6dmh3qssa-uc.a.run.app`, router and bank-api with the same suffix).

One service per `runtime` image:

| Service | Image | Notes |
|---|---|---|
| `frontend` | `containers/frontend.Dockerfile` | `NEXT_PUBLIC_AGENT_URL`, `NEXT_PUBLIC_LANGFUSE_URL` and `NEXT_PUBLIC_LANGFUSE_PROJECT_ID` are baked in at build time: it is built after the agent. The id comes from `LANGFUSE_PROJECT_ID` in `.env` (if missing, `sofia-local`) |
| `agent` | `python.Dockerfile` · `sofia-agent` | Gemini through **Vertex AI** (`GEMINI_BACKEND=vertex`) with the `sofia-agent` account (`roles/aiplatform.user`): covered by GCP credits, unlike AI Studio |
| `router` | `python.Dockerfile` · `sofia-ml` | Hybrid router (rules + model); the model trains at startup from the corpus shipped in the package |
| `bank-api` | `python.Dockerfile` · `sofia-services` | The agent points at the deployed `bank-api` URL; `AGENT_BANK_API_URL=fake deploy.sh services` goes back to the in-process bank. `max-instances=1`: sessions, OTPs and disputes live in memory |

```bash
infra/cloudrun/deploy.sh             # first time: APIs, Artifact Registry, service accounts, secrets, build and deploy
infra/cloudrun/deploy.sh release     # images + services, without touching IAM or secrets (what CD runs)
infra/cloudrun/deploy.sh services    # redeploy with the current code (rebuilds the frontend)
MIN_INSTANCES=1 infra/cloudrun/deploy.sh services   # judges' window (DEL-02); back to 0 afterwards
```

- Scales to zero by default (`MIN_INSTANCES=0`).
- Images are built in Cloud Build (`cloudbuild.yaml`) and tagged with the short git SHA.
- `.gcloudignore` and `.dockerignore` leave out `.env` and all the data in `data/` (CON-03).
- Without `DATABASE_URL_CLOUD` in `.env` the agent keeps conversations in memory. That is why it runs with
  `max-instances=1`; with a Postgres (Neon) it goes up to 3.
- All 4 services are public (`--allow-unauthenticated`). The customer's identity is checked by the bank-api/agent
  OTP session (REQ-11), not by Cloud Run. Known limitation: router and bank-api could be internal behind a VPC.

## Retries, timeouts and fallbacks

What each outgoing agent call does when the dependency fails. No fallback makes up a result: if an action could not
be confirmed, the case goes to a human (REQ-09, REQ-16).

| Call | Timeout | Retries | If it keeps failing | Where |
|---|---|---|---|---|
| bank-api (all tools) | 5 s per attempt (`tool_timeout_s`) | 2, only on network error or 5xx, backoff 0.2 s → 0.4 s. 4xx is not retried; 401 = expired session | `ToolUnavailableError` → escalation with handoff `tool_unavailable` | [tools/bank.py](../agent/src/sofia_agent/tools/bank.py) · [purpose.yaml](../agent/src/sofia_agent/purpose/purpose.yaml) |
| `POST /disputes` | same | same, with the same `Idempotency-Key`: a retry does not duplicate the dispute | Without a response nothing is claimed: `create_dispute` stays `no_response` and escalates | [orchestrate/nodes.py](../agent/src/sofia_agent/orchestrate/nodes.py) |
| Verification (`GET /disputes/{id}`) | same | same | If it cannot be read, the action counts as unverified and escalates | same |
| router (`/predict`) | 5 s | 0 | Local rules (`predict_local`); the span is marked WARNING with `fallback=router_error:*` | [tools/router.py](../agent/src/sofia_agent/tools/router.py) |
| Gemini (Vertex AI) | 20 s per turn, 8 s per model | Fallback model chain (`GEMINI_FALLBACK_MODELS`); the failing one is paused for 30 s (circuit breaker) | Rules + templates (`LLMUnavailableError`): the conversation continues without an LLM | [llm.py](../agent/src/sofia_agent/llm.py) · [config.py](../agent/src/sofia_agent/config.py) |
| Langfuse | — | — | Without credentials tracing is a no-op: the agent never depends on observability | [tracing.py](../agent/src/sofia_agent/tracing.py) |

### What is inside the trace

The Langfuse trace belongs to the agent: 1 per conversation, with a span per layer and one per call to bank-api and the
router (HTTP status, attempt, duration). bank-api and the router do not export their own spans or receive the
`trace_id`, so what happens inside them (policy decision, audit log) does not appear in the trace. To join both sides
today, the span's `dispute_id` / `eligibility_id` is matched against bank-api's audit log, which also lives in memory.
In production: propagate `traceparent` (W3C) and instrument bank-api and the router with OpenTelemetry.

## Secrets (Secret Manager)

`deploy.sh` reads them from `.env` and creates a new version only when they changed. They are never printed or committed.

| Secret | Variable in `.env` | Used by |
|---|---|---|
| `langfuse-public-key` | `LANGFUSE_PUBLIC_KEY` | agent |
| `langfuse-secret-key` | `LANGFUSE_SECRET_KEY` | agent |
| `database-url` | `DATABASE_URL_CLOUD` (optional) | agent |
| `admin-api-key` | `ADMIN_API_KEY` (optional) | bank-api: opens `/admin/*` and `/session/test` with the `X-Admin-Key` header. Without it they return 403 |

Gemini in the cloud needs no API key: it uses the service account.

## Langfuse (decision D1: cloud)

Langfuse Cloud, Hobby plan (free): 50k units per month, 30-day retention and 2 users. A unit is a trace, an observation
or a score. With the §9.6 convention a turn produces about 10–15 spans, so a full harness run (baseline + proposed) can
use several thousand units. If repeated runs get close to the limit, the harness can point at the local self-hosted
Langfuse (`make langfuse`) and keep the cloud for the demo.

## CI

`.github/workflows/ci.yml`: ruff + pytest, frontend eslint + build and gitleaks on every PR.

## CD

`.github/workflows/deploy.yml`: every push to `develop` (PR merge) runs `deploy.sh release` and leaves the URLs in the
run summary. It can also be launched by hand from Actions on `develop`.

- Authentication through Workload Identity Federation: GitHub issues an OIDC token and GCP exchanges it for the
  `sofia-deployer` account. No JSON keys and no GitHub secrets (CON-03).
- The provider only accepts tokens from `Smorareq1/factored-hackathon-2026-sofia` on `refs/heads/develop`; other
  branches or forks cannot deploy.
- `sofia-deployer` can build images, deploy Cloud Run and see which secrets exist, but cannot read their values or
  change IAM. Platform or secret changes still go through `deploy.sh` (`all` mode) with an Owner account.
- Set up once with `infra/cloudrun/setup-github-deploy.sh` (Owner, idempotent).
