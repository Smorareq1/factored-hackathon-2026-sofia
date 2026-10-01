# infra/ — dueño: OPS

Despliegue y operación fuera del entorno local (el local vive en [containers/](../containers/)).

## Cloud Run (`cloudrun/`)

Proyecto GCP `sofia-factored-hackathon`, región `us-central1`.

Desplegado el 2026-10-01: **https://frontend-i6dmh3qssa-uc.a.run.app** (agente en
`https://agent-i6dmh3qssa-uc.a.run.app`, router y bank-api con el mismo sufijo).

Un servicio por imagen `runtime`:

| Servicio | Imagen | Notas |
|---|---|---|
| `frontend` | `containers/frontend.Dockerfile` | `NEXT_PUBLIC_AGENT_URL` se incrusta al compilar: se construye después del agente |
| `agent` | `python.Dockerfile` · `sofia-agent` | Gemini por **Vertex AI** (`GEMINI_BACKEND=vertex`) con la cuenta `sofia-agent` (`roles/aiplatform.user`): lo cubren los créditos de GCP, a diferencia de AI Studio |
| `router` | `python.Dockerfile` · `sofia-ml` | |
| `bank-api` | `python.Dockerfile` · `sofia-services` | El agente usa `BANK_API_URL=fake` hasta que SIM publique la API; luego `AGENT_BANK_API_URL=<url> deploy.sh services` |

```bash
infra/cloudrun/deploy.sh             # primera vez: APIs, Artifact Registry, cuentas de servicio, secretos, build y deploy
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

## Secretos (Secret Manager)

`deploy.sh` los toma de `.env` y crea una versión nueva solo si cambiaron. Nunca se imprimen ni se commitean.

| Secreto | Variable en `.env` | Lo usa |
|---|---|---|
| `langfuse-public-key` | `LANGFUSE_PUBLIC_KEY` | agent |
| `langfuse-secret-key` | `LANGFUSE_SECRET_KEY` | agent |
| `database-url` | `DATABASE_URL_CLOUD` (opcional) | agent |

Gemini en la nube no necesita API key: usa la cuenta de servicio.

## Langfuse (decisión D1: cloud)

Langfuse Cloud, plan Hobby (gratis): 50k unidades al mes, 30 días de retención y 2 usuarios. Una unidad es una
traza, una observación o un score. Con la convención de §9.6 un turno genera unos 10–15 spans, así que una corrida
completa del harness (baseline + propuesto) puede gastar varios miles de unidades. Si las corridas repetidas se
acercan al límite, el harness puede apuntar al Langfuse self-hosted local (`make langfuse`) y la nube queda para
la demo.

## CI

`.github/workflows/ci.yml`: ruff + pytest, eslint + build del frontend y gitleaks en cada PR.
