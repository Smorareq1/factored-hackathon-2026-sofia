# Atajos del proyecto. Todo corre en contenedores: solo hace falta Docker.
# En Windows sin make: copiar el comando de la receta (ver containers/README.md).

ENV_FILE := $(if $(wildcard .env),--env-file .env,)
COMPOSE  := docker compose -f containers/local/compose.yaml $(ENV_FILE)

.PHONY: setup up run dev down logs ps langfuse data data-fixture eval eval-gate translate-cases notebook test lint lock clean

setup: ## Construye todas las imágenes
	$(COMPOSE) --profile langfuse --profile data --profile eval --profile analysis build

up: ## Levanta el stack base: postgres, bank-api, router, agent, frontend
	$(COMPOSE) up -d --build

run: up

dev: ## Igual que up, con hot reload (docker compose watch)
	$(COMPOSE) watch

down: ## Apaga todo (los volúmenes se conservan)
	$(COMPOSE) --profile "*" down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

langfuse: ## Stack base + Langfuse self-hosted (UI en http://localhost:3100)
	$(COMPOSE) --profile langfuse up -d --build

data: ## Pipeline S3 → bronze → silver → gold (OPS). Sin credenciales de S3 usa lo que haya en data/raw
	$(COMPOSE) --profile data run --rm --build data

data-fixture: ## Mismo pipeline sobre datos sintéticos (team_generated) en data/fixture/, sin S3
	$(COMPOSE) --profile data run --rm --build data python -m sofia_data.pipeline --source fixture

eval: ## Harness baseline vs propuesto (SIM + DS)
	$(COMPOSE) --profile eval run --rm eval

eval-gate: ## Gate de regresión de AG (set dev, propuesto vs baseline). ARGS="--accept" para fijar referencia
	$(COMPOSE) run --rm --no-deps -v "$(CURDIR)/agent/evals:/app/agent/evals" -w /app/agent agent 		python scripts/eval_gate.py $(ARGS)

translate-cases: ## ES → PT de casos con Gemini (IDs enmascarados). ARGS="evals/dev_cases.jsonl --dry-run"
	$(COMPOSE) run --rm --no-deps -v "$(CURDIR)/agent/evals:/app/agent/evals" -w /app/agent agent 		python scripts/translate_cases.py $(ARGS)

notebook: ## JupyterLab para analysis/ (DS) en http://localhost:8888
	$(COMPOSE) --profile analysis up -d --build jupyter

test: ## Tests de Python dentro de los contenedores
	$(COMPOSE) run --rm --no-deps bank-api pytest services/tests
	$(COMPOSE) run --rm --no-deps router pytest ml/tests
	$(COMPOSE) run --rm --no-deps agent pytest agent/tests
	$(COMPOSE) --profile data run --rm --no-deps --build data pytest data/tests

lint:
	$(COMPOSE) run --rm --no-deps agent ruff check .

lock: ## Regenera uv.lock sin tener uv instalado
	docker run --rm -v "$(CURDIR):/app" -w /app ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv lock

clean: ## Apaga todo y BORRA los volúmenes (postgres, langfuse)
	$(COMPOSE) --profile "*" down -v
