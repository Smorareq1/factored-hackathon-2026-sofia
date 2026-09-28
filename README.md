# S.O.F.I.A. — Sistema Orquestado de Filtrado e Intención Automatizada

Agente bancario **Sofía** para la recepción de disputas de transacciones, en español y portugués. Factored AI & Data Hackathon 2026.

> README de desarrollo. La versión final (rationale, arquitectura, resultados, limitaciones, camino a producción; DEL-05) la edita DS con los aportes de cada dueño.

## Arrancar

Solo hace falta Docker.

```bash
cp .env.example .env      # completar GEMINI_API_KEY como mínimo
make up                   # o: docker compose -f containers/local/compose.yaml --env-file .env up -d --build
```

Frontend http://localhost:3000 · agente http://localhost:8001/docs · API bancaria http://localhost:8000/docs · router http://localhost:8002/docs

Más comandos (Langfuse, pipeline, harness, Jupyter, sin make): [containers/README.md](containers/README.md).

## Estructura y dueños

| Carpeta | Dueño | Qué va |
|---|---|---|
| [contracts/](contracts/) | Todos | Contratos Pydantic de §9 + JSON Schema exportado. Se cambian solo con aviso |
| [data/](data/) | OPS | Pipeline S3 → bronze → silver → gold, calidad, lineage, freshness |
| [infra/](infra/) | OPS | Cloud Run, Secret Manager, configuración de Langfuse en la nube |
| [containers/](containers/) | OPS | Dockerfiles y compose local |
| [analysis/](analysis/) | DS | EDA, justificación del workflow, baseline de negocio, calibración de N y U |
| [ml/](ml/) | DS | Router de intención: labels, entrenamiento, evaluación, servicio |
| [services/](services/) | SIM | API bancaria simulada: auth, permisos, política POL-1..7, auditoría, fallas |
| [eval/](eval/) | SIM + DS | Simulador, harness baseline vs propuesto, métricas MET-01..06, reporte |
| [agent/](agent/) | AG | Grafo LangGraph de 7 capas, Gemini, handoff, baseline de sistema |
| [frontend/](frontend/) | AG | Chat ES/PT, caja de cristal, consola del agente humano |
| [docs/](docs/) | DS | Reporte de evaluación, slides, guion del video |

Python: un **workspace de uv** (`pyproject.toml` en la raíz + uno por carpeta, un solo `uv.lock`). Los paquetes se importan como `sofia_contracts`, `sofia_agent`, etc.

## Reglas

- **Nada de secretos ni registros de clientes en el repo** (CON-03). Van en `.env`, que está en `.gitignore`.
- Una carpeta, un dueño; los cambios cruzados van por PR aprobado por el dueño.
- Ramas cortas desde `develop` (`feat/...`) y PRs chicos.
