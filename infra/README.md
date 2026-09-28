# infra/ — dueño: OPS

Despliegue y operación fuera del entorno local (el local vive en [containers/](../containers/)).

- `cloudrun/`: un servicio por imagen (`bank-api`, `router`, `agent`, `frontend`), con escala a cero y `min-instances=1` solo en la ventana con jueces (DEL-02).
- Secretos en Secret Manager (`GEMINI_API_KEY`, `DATABASE_URL` de Neon, llaves de Langfuse); nunca en el repo (CON-03).
- Langfuse cloud vs self-hosted: decisión pendiente de OPS (D1).
- CI en `.github/workflows/`: lint + tests + chequeo de secretos en cada PR.
