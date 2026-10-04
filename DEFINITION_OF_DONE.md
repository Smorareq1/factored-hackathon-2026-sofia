# Definition of Done (§13 del brief) — dueño: OPS

Checklist de entrega. Se revisa en la integración 2 (10-02) y antes del envío (10-05). Cada ítem lleva la evidencia o
lo que falta. Estado al 2026-10-04 (develop `d367776`).

## Entrega

- [ ] **REQ-01..REQ-19 con evidencia enlazada en el README.** La tabla ya existe ([Trazabilidad](README.md#trazabilidad-req-01req-19));
  quedan filas en `pendiente` / `parcial` (REQ-02, REQ-06, REQ-17) que se cierran con la corrida completa del harness.
- [ ] **DEL-01..DEL-07 listos; DEL-08 preparado por si se entra al Top 5.**
  - [x] DEL-01 Repo público con setup reproducible: [README](README.md#arrancar)
  - [x] DEL-02 Demo desplegada: https://frontend-i6dmh3qssa-uc.a.run.app
  - [ ] DEL-03 Slides 4–6 (DS): contenido en [slides-4-6.md](docs/slides/slides-4-6.md); faltan las cifras `{{…}}` y exportar
  - [ ] DEL-04 Video ≤ 3 min (DS): guion en [video-script.md](docs/video-script.md); faltan las tomas (AG) y la edición
  - [ ] DEL-05 README final (DS edita; OPS ya aportó despliegue, datos, CI, CD, observabilidad, reintentos/fallbacks y
    camino a producción); faltan los placeholders `{{…}}` de Resultados
  - [ ] DEL-06 Reporte de evaluación MET-01..06 (DS + SIM): estructura en [evaluation-report.md](docs/evaluation-report.md);
    faltan las cifras de la corrida baseline vs propuesto
  - [ ] DEL-07 Email de entrega (OPS): borrador listo; se envía cuando estén los links de video y slides
  - [ ] DEL-08 Guion de defensa en vivo (todos): [defense-notes.md](docs/defense-notes.md); faltan las cifras
- [ ] **Email enviado a hackathon.admin@factored.ai** (OPS, antes del 2026-10-05).

## Ingeniería

- [x] **Ningún secreto ni dato de cliente en el repo, incluido el historial de git.** gitleaks sobre todo el historial en
  cada PR ([ci.yml](.github/workflows/ci.yml)); `data/` y `.env` fuera de git, de Cloud Build y de las imágenes.
- [ ] **`make setup && make data && make run && make eval` funciona desde cero.**
  - [x] `make setup`, `make data` (S3 o `make data-fixture`) y `make run`
  - [ ] `make eval`: corre solo `proposed`; falta `--versions proposed,baseline` (SIM)
  - [ ] Probado desde un clon limpio
- [ ] **Demo en Cloud Run levantable bajo pedido, probada desde una red externa.** Deploy continuo en cada merge a
  `develop` ([deploy.yml](.github/workflows/deploy.yml)).
  - [x] Desplegada y probada de punta a punta (login con OTP → disputa con Gemini por Vertex AI)
  - [x] Agente conectado a la bank-api desplegada (2026-10-04). `deploy.sh` la usa por defecto, así que el CD ya no
    vuelve al banco en proceso
  - [ ] Rutas `/admin/*` y `/session/test` de bank-api cerradas en la nube (SIM)
  - [ ] Prueba de punta a punta del frontend contra la bank-api desplegada (OPS + AG)
  - [ ] Probada desde una red externa en la ventana acordada, con `MIN_INSTANCES=1`

## Evaluación

- [ ] **Reporte con MET-01..MET-06 por idioma y tipo de caso, con n y limitaciones** (DS + SIM). El harness debe leer
  latencia y costo con `GET /api/public/v2/observations` de Langfuse: la API clásica `/api/public/traces` no existe
  para organizaciones nuevas.
- [ ] **Evaluadores de Langfuse validados contra muestra humana y documentados** (DS).

## Documentación

- [x] **"Limitaciones, compromisos y camino a producción"**, parte de infra y datos:
  [README](README.md#limitaciones-y-camino-a-producción-infra-y-datos). La parte de agente, ML y evaluación también
  está ([README](README.md#limitaciones-y-camino-a-producción-agente-ml-y-evaluación)); se cierra con los resultados.
- [x] **Reintentos, timeouts y fallbacks documentados**, y qué queda fuera de la traza:
  [infra/README.md](infra/README.md#reintentos-timeouts-y-fallbacks).
- [ ] **Video ≤ 3 minutos** (DS).
