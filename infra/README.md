# infra/ — dueño: OPS

Despliegue y operación fuera del entorno local (el local vive en [containers/](../containers/)).

## Cloud Run (`cloudrun/`)

Proyecto GCP `sofia-factored-hackathon`, región `us-central1`.

Desplegado el 2026-10-01; agente conectado a bank-api el 2026-10-04: **https://frontend-i6dmh3qssa-uc.a.run.app** (agente en
`https://agent-i6dmh3qssa-uc.a.run.app`, router y bank-api con el mismo sufijo).

Un servicio por imagen `runtime`:

| Servicio | Imagen | Notas |
|---|---|---|
| `frontend` | `containers/frontend.Dockerfile` | `NEXT_PUBLIC_AGENT_URL` se incrusta al compilar: se construye después del agente |
| `agent` | `python.Dockerfile` · `sofia-agent` | Gemini por **Vertex AI** (`GEMINI_BACKEND=vertex`) con la cuenta `sofia-agent` (`roles/aiplatform.user`): lo cubren los créditos de GCP, a diferencia de AI Studio |
| `router` | `python.Dockerfile` · `sofia-ml` | |
| `bank-api` | `python.Dockerfile` · `sofia-services` | El agente apunta a la URL de `bank-api` desplegada; `AGENT_BANK_API_URL=fake deploy.sh services` vuelve al banco en proceso. `max-instances=1`: sesiones, OTP y disputas viven en memoria |

```bash
infra/cloudrun/deploy.sh             # primera vez: APIs, Artifact Registry, cuentas de servicio, secretos, build y deploy
infra/cloudrun/deploy.sh release     # imágenes + servicios, sin tocar IAM ni secretos (lo que corre el CD)
infra/cloudrun/deploy.sh services    # re-desplegar con el código actual (reconstruye el frontend)
MIN_INSTANCES=1 infra/cloudrun/deploy.sh services   # ventana con jueces (DEL-02); volver a 0 después
```

- Escala a cero por defecto (`MIN_INSTANCES=0`).
- Las imágenes se construyen en Cloud Build (`cloudbuild.yaml`) y se etiquetan con el SHA corto de git.
- `.gcloudignore` y `.dockerignore` dejan fuera `.env` y todos los datos de `data/` (CON-03).
- Sin `DATABASE_URL_CLOUD` en `.env` el agente guarda las conversaciones en memoria. Por eso corre con
  `max-instances=1`; con una Postgres (Neon) sube a 3.
- Los 4 servicios son públicos (`--allow-unauthenticated`). La identidad del cliente la valida la sesión con OTP de
  bank-api/agente (REQ-11), no Cloud Run. Limitación conocida: router y bank-api podrían quedar internos detrás de una VPC.

## Reintentos, timeouts y fallbacks

Lo que hace cada llamada saliente del agente cuando la dependencia falla. Ningún fallback inventa un resultado:
si una acción no se pudo confirmar, el caso pasa a un humano (REQ-09, REQ-16).

| Llamada | Timeout | Reintentos | Si sigue fallando | Dónde |
|---|---|---|---|---|
| bank-api (todas las tools) | 5 s por intento (`tool_timeout_s`) | 2, solo ante error de red o 5xx, backoff 0,2 s → 0,4 s. 4xx no se reintenta; 401 = sesión vencida | `ToolUnavailableError` → escalamiento con handoff `tool_unavailable` | [tools/bank.py](../agent/src/sofia_agent/tools/bank.py) · [purpose.yaml](../agent/src/sofia_agent/purpose/purpose.yaml) |
| `POST /disputes` | igual | igual, con la misma `Idempotency-Key`: un reintento no duplica la disputa | Sin respuesta no se afirma nada: `create_dispute` queda `no_response` y escala | [orchestrate/nodes.py](../agent/src/sofia_agent/orchestrate/nodes.py) |
| Verificación (`GET /disputes/{id}`) | igual | igual | Si no se puede leer, la acción cuenta como no verificada y escala | idem |
| router (`/predict`) | 5 s | 0 | Reglas locales (`predict_local`); el span queda en WARNING con `fallback=router_error:*` | [tools/router.py](../agent/src/sofia_agent/tools/router.py) |
| Gemini (Vertex AI) | 20 s por turno, 8 s por modelo | Cadena de modelos de respaldo (`GEMINI_FALLBACK_MODELS`); el que falla queda en pausa 30 s (circuit breaker) | Reglas + plantillas (`LLMUnavailableError`): la conversación sigue sin LLM | [llm.py](../agent/src/sofia_agent/llm.py) · [config.py](../agent/src/sofia_agent/config.py) |
| Langfuse | — | — | Sin credenciales el tracing es no-op: el agente nunca depende de la observabilidad | [tracing.py](../agent/src/sofia_agent/tracing.py) |

### Qué queda dentro de la traza

La traza de Langfuse es del agente: 1 por conversación, con un span por capa y uno por cada llamada a bank-api y al
router (status HTTP, intento, duración). bank-api y router no exportan spans propios ni reciben el `trace_id`, así que
lo que pasa dentro de ellos (decisión de política, log de auditoría) no aparece en la traza. Para unir ambos lados hoy
se cruza el `dispute_id` / `eligibility_id` del span con el log de auditoría de bank-api, que además vive en memoria.
En producción: propagar `traceparent` (W3C) e instrumentar bank-api y router con OpenTelemetry.

## Secretos (Secret Manager)

`deploy.sh` los toma de `.env` y crea una versión nueva solo si cambiaron. Nunca se imprimen ni se commitean.

| Secreto | Variable en `.env` | Lo usa |
|---|---|---|
| `langfuse-public-key` | `LANGFUSE_PUBLIC_KEY` | agent |
| `langfuse-secret-key` | `LANGFUSE_SECRET_KEY` | agent |
| `database-url` | `DATABASE_URL_CLOUD` (opcional) | agent |
| `admin-api-key` | `ADMIN_API_KEY` (opcional) | bank-api: abre `/admin/*` y `/session/test` con el header `X-Admin-Key`. Sin él quedan en 403 |

Gemini en la nube no necesita API key: usa la cuenta de servicio.

## Langfuse (decisión D1: cloud)

Langfuse Cloud, plan Hobby (gratis): 50k unidades al mes, 30 días de retención y 2 usuarios. Una unidad es una
traza, una observación o un score. Con la convención de §9.6 un turno genera unos 10–15 spans, así que una corrida
completa del harness (baseline + propuesto) puede gastar varios miles de unidades. Si las corridas repetidas se
acercan al límite, el harness puede apuntar al Langfuse self-hosted local (`make langfuse`) y la nube queda para
la demo.

## CI

`.github/workflows/ci.yml`: ruff + pytest, eslint + build del frontend y gitleaks en cada PR.

## CD

`.github/workflows/deploy.yml`: cada push a `develop` (merge de PR) corre `deploy.sh release` y deja las URLs en el
resumen del run. También se puede lanzar a mano desde Actions sobre `develop`.

- Autenticación por Workload Identity Federation: GitHub entrega un token OIDC y GCP lo cambia por la cuenta
  `sofia-deployer`. No hay llaves JSON ni secretos de GitHub (CON-03).
- El provider solo acepta tokens de `Smorareq1/factored-hackathon-2026-sofia` en `refs/heads/develop`; otras ramas
  o forks no pueden desplegar.
- `sofia-deployer` puede construir imágenes, desplegar Cloud Run y ver qué secretos existen, pero no leer su valor
  ni cambiar IAM. Cambios de plataforma o de secretos siguen siendo `deploy.sh` (modo `all`) con una cuenta Owner.
- Se configura una sola vez con `infra/cloudrun/setup-github-deploy.sh` (Owner, idempotente).
