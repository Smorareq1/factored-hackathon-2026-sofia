# Definition of Done (§13 del brief) — dueño: OPS

Checklist de entrega. Se revisa en la integración 2 (10-02) y antes del envío (10-05). Cada ítem lleva la evidencia o
lo que falta. Estado al 2026-10-01.

## Entrega

- [ ] **REQ-01..REQ-19 con evidencia enlazada en el README.** Falta la tabla de trazabilidad (DS, con aportes de cada dueño).
- [ ] **DEL-01..DEL-07 listos; DEL-08 preparado por si se entra al Top 5.**
  - [x] DEL-01 Repo público con setup reproducible: [README](README.md#arrancar)
  - [x] DEL-02 Demo desplegada: https://frontend-i6dmh3qssa-uc.a.run.app
  - [ ] DEL-03 Slides 4–6 (DS)
  - [ ] DEL-04 Video ≤ 3 min (DS)
  - [ ] DEL-05 README final (DS edita; OPS ya aportó despliegue, datos, CI, observabilidad y camino a producción)
  - [ ] DEL-06 Reporte de evaluación MET-01..06 (DS + SIM)
  - [ ] DEL-07 Email de entrega (OPS)
  - [ ] DEL-08 Guion de defensa en vivo (todos)
- [ ] **Email enviado a hackathon.admin@factored.ai** (OPS, antes del 2026-10-05).

## Ingeniería

- [x] **Ningún secreto ni dato de cliente en el repo, incluido el historial de git.** gitleaks sobre todo el historial en
  cada PR ([ci.yml](.github/workflows/ci.yml)); `data/` y `.env` fuera de git, de Cloud Build y de las imágenes.
- [ ] **`make setup && make data && make run && make eval` funciona desde cero.**
  - [x] `make setup`, `make data` (S3 o `make data-fixture`) y `make run`
  - [ ] `make eval`: depende del harness (SIM + DS)
  - [ ] Probado desde un clon limpio
- [ ] **Demo en Cloud Run levantable bajo pedido, probada desde una red externa.**
  - [x] Desplegada y probada de punta a punta (login con OTP → disputa con Gemini por Vertex AI)
  - [ ] Agente conectado a la bank-api real (hoy usa el banco simulado en proceso)
  - [ ] Probada desde una red externa en la ventana acordada, con `MIN_INSTANCES=1`

## Evaluación

- [ ] **Reporte con MET-01..MET-06 por idioma y tipo de caso, con n y limitaciones** (DS + SIM). El harness debe leer
  latencia y costo con `GET /api/public/v2/observations` de Langfuse: la API clásica `/api/public/traces` no existe
  para organizaciones nuevas.
- [ ] **Evaluadores de Langfuse validados contra muestra humana y documentados** (DS).

## Documentación

- [x] **"Limitaciones, compromisos y camino a producción"**, parte de infra y datos:
  [README](README.md#limitaciones-y-camino-a-producción-infra-y-datos). Falta la parte de agente, ML y evaluación.
- [ ] **Video ≤ 3 minutos** (DS).
