# containers/

Todo el proyecto corre en contenedores: en la máquina solo hace falta **Docker** (Compose v2.24 o superior). Python, uv y Node no se instalan en el host.

| Archivo | Qué es |
|---|---|
| `python.Dockerfile` | Imagen compartida por todos los paquetes Python del workspace de uv (`--build-arg PACKAGE=sofia-agent`, etc.). Targets `dev` (compose) y `runtime` (Cloud Run) |
| `frontend.Dockerfile` | Next.js. Targets `dev` (compose) y `runtime` (salida `standalone`, puerto 8080) |
| `*.Dockerfile.dockerignore` | Qué entra a cada imagen. **Los secretos (`.env`) nunca entran** |
| `local/compose.yaml` | Entorno local completo |
| `local/postgres/init/` | Crea las bases `sofia_agent`, `sofia_bank` y `langfuse` la primera vez |

## Servicios

| Servicio | Dueño | Puerto | Perfil |
|---|---|---|---|
| `postgres` | OPS | 5433 (host) | base |
| `bank-api` (API bancaria simulada) | SIM | 8000 | base |
| `router` (intención + idioma) | DS | 8002 | base |
| `agent` (Sofía) | AG | 8001 | base |
| `frontend` | AG | 3000 | base |
| `langfuse-web` + worker, clickhouse, redis, minio | OPS | 3100 (UI), 9090 | `langfuse` |
| `data` (pipeline, job) | OPS | — | `data` |
| `eval` (harness, job) | SIM + DS | — | `eval` |
| `jupyter` | DS | 8888 | `analysis` |

## Uso

Primero, en la raíz: `cp .env.example .env` y completar lo que haga falta (como mínimo `GEMINI_API_KEY`).

| Qué | Con make | Sin make (Windows / PowerShell) |
|---|---|---|
| Levantar la base | `make up` | `docker compose -f containers/local/compose.yaml --env-file .env up -d --build` |
| Hot reload | `make dev` | `docker compose -f containers/local/compose.yaml --env-file .env watch` |
| + Langfuse | `make langfuse` | `docker compose -f containers/local/compose.yaml --env-file .env --profile langfuse up -d --build` |
| Pipeline de datos | `make data` | `docker compose -f containers/local/compose.yaml --env-file .env --profile data run --rm data` |
| Harness | `make eval` | `docker compose -f containers/local/compose.yaml --env-file .env --profile eval run --rm eval` |
| Jupyter | `make notebook` | `docker compose -f containers/local/compose.yaml --env-file .env --profile analysis up -d --build jupyter` |
| Tests | `make test` | `docker compose -f containers/local/compose.yaml run --rm --no-deps agent pytest agent/tests` |
| Apagar | `make down` | `docker compose -f containers/local/compose.yaml --profile "*" down` |
| Regenerar `uv.lock` | `make lock` | `docker run --rm -v "${PWD}:/app" -w /app ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv lock` |

- **Langfuse local:** http://localhost:3100 · usuario `dev@sofia.local` · clave `sofia-local`. El proyecto y las llaves (`pk-lf-local-dev` / `sk-lf-local-dev`) se crean solos al arrancar, así que el agente queda trazando sin configurar nada. Esas credenciales son solo para local.
- **Agregar una dependencia Python:** editar el `pyproject.toml` del paquete y correr `make lock`. `compose watch` reconstruye la imagen sola.
- **Datos:** `data/` se monta como volumen: el gold que genera `make data` lo leen `bank-api` y `jupyter` sin copiar nada.
