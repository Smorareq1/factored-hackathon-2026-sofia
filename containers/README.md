# containers/

The whole project runs in containers: the machine only needs **Docker** (Compose v2.24 or later). Python, uv and Node are not installed on the host.

| File | What it is |
|---|---|
| `python.Dockerfile` | Image shared by every Python package of the uv workspace (`--build-arg PACKAGE=sofia-agent`, etc.). Targets `dev` (compose) and `runtime` (Cloud Run) |
| `frontend.Dockerfile` | Next.js. Targets `dev` (compose) and `runtime` (`standalone` output, port 8080) |
| `*.Dockerfile.dockerignore` | What goes into each image. **Secrets (`.env`) never go in** |
| `local/compose.yaml` | Full local environment |
| `local/postgres/init/` | Creates the `sofia_agent`, `sofia_bank` and `langfuse` databases on first start |

## Services

| Service | Owner | Port | Profile |
|---|---|---|---|
| `postgres` | OPS | 5433 (host) | base |
| `bank-api` (simulated bank API) | SIM | 8000 | base |
| `router` (intent + language) | DS | 8002 | base |
| `agent` (Sofía) | AG | 8001 | base |
| `frontend` | AG | 3000 | base |
| `langfuse-web` + worker, clickhouse, redis, minio | OPS | 3100 (UI), 9090 | `langfuse` |
| `data` (pipeline, job) | OPS | — | `data` |
| `eval` (harness, job) | SIM + DS | — | `eval` |
| `jupyter` | DS | 8888 | `analysis` |

## Usage

First, at the root: `cp .env.example .env` and fill in what you need (at least `GEMINI_API_KEY`).

| What | With make | Without make (Windows / PowerShell) |
|---|---|---|
| Start the base stack | `make up` | `docker compose -f containers/local/compose.yaml --env-file .env up -d --build` |
| Hot reload | `make dev` | `docker compose -f containers/local/compose.yaml --env-file .env watch` |
| + Langfuse | `make langfuse` | `docker compose -f containers/local/compose.yaml --env-file .env --profile langfuse up -d --build` |
| Data pipeline | `make data` | `docker compose -f containers/local/compose.yaml --env-file .env --profile data run --rm data` |
| Harness | `make eval` | `docker compose -f containers/local/compose.yaml --env-file .env --profile eval run --rm eval` |
| Jupyter | `make notebook` | `docker compose -f containers/local/compose.yaml --env-file .env --profile analysis up -d --build jupyter` |
| Tests | `make test` | `docker compose -f containers/local/compose.yaml run --rm --no-deps agent pytest agent/tests` |
| Shut down | `make down` | `docker compose -f containers/local/compose.yaml --profile "*" down` |
| Regenerate `uv.lock` | `make lock` | `docker run --rm -v "${PWD}:/app" -w /app ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv lock` |

- **Local Langfuse:** http://localhost:3100 · user `dev@sofia.local` · password `sofia-local`. The project and keys (`pk-lf-local-dev` / `sk-lf-local-dev`) are created on startup, so the agent traces without any setup. Those credentials are local-only.
- **Adding a Python dependency:** edit the package's `pyproject.toml` and run `make lock`. `compose watch` rebuilds the image on its own.
- **Data:** `data/` is mounted as a volume: the gold that `make data` produces is read by `bank-api` and `jupyter` without copying anything.
