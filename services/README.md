# SIM: API Bancaria Simulada y Servicios de Evaluación (services/)

Servicio bancario simulado para el flujo de recepción de disputas de transacciones (**Transaction-Dispute Intake**, REQ-01), gobernanza de políticas financieras (POL-1..POL-7, REQ-10), autenticación confiable con sesión + OTP (REQ-11), auditoría auditable (REQ-19) e inyección controlada de fallas (REQ-15, REQ-16).

---

## 1. Arquitectura y Responsabilidades

SIM es el dueño del backend financiero (`sofia-services`). Todo lo que involucra verdad de negocio, validación de políticas y persistencia de transacciones/disputas vive en este servicio y **no en el LLM**:

- **Autenticación y Sesión (§9.2, REQ-11)**: Emisión de desafíos (challenge) con OTP simulado para la demo, verificación de OTP y emisión de tokens de sesión con TTL de 30 minutos.
- **Control de Permisos (§9.2, POL-1, REQ-10)**: Las consultas de transacciones (`/transactions`) devuelven únicamente las transacciones del cliente autenticado. Si un cliente intenta consultar una transacción ajena, se retorna `404 Not Found` idéntico para no filtrar existencia de datos de terceros.
- **Motor de Políticas Determinístico (POL-1..POL-6, REQ-10)**: Valida elegibilidad de disputas (`POST /disputes/eligibility`) evaluando reglas determinísticas basadas en datos históricos.
- **Registro de Disputas Idempotente (§9.2, REQ-09)**: `POST /disputes` exige `Idempotency-Key` en cabecera, `eligibility_id` vigente y prueba explícita de confirmación (`ConfirmationProof`).
- **Simulación y Harness (REQ-15, REQ-16)**: Endpoints administrativos en `/admin/*` para inyección de fallas HTTP, expiración forzada de sesiones, simulación de fallas de escritura (`drop_writes`) e inyección de latencia/timeouts.

---

## 2. Endpoints de la API (§9.2)

| Método | Endpoint | Rol / Auth | Propósito |
|---|---|---|---|
| `GET` | `/health` | Público | Healthcheck del servicio |
| `GET` | `/demo/customers` | Público | Lista clientes sintéticos para el selector del frontend demo |
| `POST` | `/session` | Público | Inicia sesión con número de documento; genera challenge + OTP |
| `POST` | `/session/verify` | Público | Valida OTP y retorna token Bearer de sesión |
| `POST` | `/session/test` | Protegido / Sandbox | Apertura directa de sesión para `session_customer_id` en harness |
| `GET` | `/session/me` | Customer / Agent | Información del cliente autenticado |
| `GET` | `/transactions` | Customer | Lista transacciones del cliente con filtros (`since`, `until`, `merchant`, `amount`, `limit`) |
| `GET` | `/transactions/{id}` | Customer | Detalle de transacción (POL-1: 404 si es ajena) |
| `POST` | `/disputes/eligibility` | Customer | Evalúa políticas POL-1..POL-6 y emite `eligibility_id` |
| `POST` | `/disputes` | Customer | Registra la disputa (requiere `Idempotency-Key` y `ConfirmationProof`) |
| `GET` | `/disputes` | Customer | Lista disputas del cliente autenticado |
| `GET` | `/disputes/{id}` | Customer | Detalle de disputa |
| `POST` | `/handoff` | Customer / Agent | Registra ficha estructurada de transferencia a humano |
| `GET` | `/handoffs` | Agent | Lista handoffs pendientes para la consola humana |
| `POST` | `/handoffs/{id}/feedback` | Agent | Envía feedback de utilidad del handoff recibido |
| `POST` | `/admin/faults/http` | Admin / Sandbox | Inyecta código de error HTTP para método/ruta |
| `POST` | `/admin/faults/latency` | Admin / Sandbox | Inyecta latencia controlada para simular timeouts |
| `POST` | `/admin/faults/drop-writes` | Admin / Sandbox | Simula respuesta exitosa sin persistir (falla silenciosa) |
| `POST` | `/admin/faults/expire-sessions`| Admin / Sandbox | Expira todas las sesiones activas |
| `POST` | `/admin/faults/reset` | Admin / Sandbox | Limpia todas las fallas inyectadas |
| `GET` | `/admin/audit` | Admin / Sandbox | Registro de eventos de auditoría |
| `POST` | `/admin/reset-store` | Admin / Sandbox | Restablece el estado del store y las fallas |

---

## 3. Seguridad y Protección en Cloud

Para prevenir abusos o manipulaciones no autorizadas en el despliegue público en Google Cloud Run:

1. **Gateo de Entorno (`SOFIA_ENV`)**:
   - Cuando `SOFIA_ENV=cloud` (o `production`), las rutas `/admin/*` y `POST /session/test` se bloquean por defecto con `403 Forbidden`.
   - Para acceder en entornos cloud desde herramientas de evaluación o administración, se requiere la cabecera `X-Admin-Key` configurada con el valor de `ADMIN_API_KEY`.
2. **Entorno Local**:
   - En desarrollo local (`SOFIA_ENV=local` o `test`), el acceso a los endpoints administrativos y sandbox se permite de manera transparente para facilitar la ejecución del arnés y las pruebas automatizadas.

---

## 4. Calibración de Políticas Bancarias (§8.3)

Los parámetros de política fueron formalmente analizados y calibrados por el equipo de Ciencia de Datos (`analysis/results/policy_calibration.json`):

- **$N$ (Ventana de disputa)**: **90 días**. Supuesto de política estándar de la industria bancaria (el dataset de transacciones no vincula de forma explícita disputas con identificadores de transacción).
- **$U$ (Monto umbral)**: **$500.00 USD**. Cubre más del 95% de las compras aprobadas históricas en el dataset, canalizando montos atípicos a revisión humana especializada (POL-6).
- **Umbral de Fraude**: **0.8** (80/100). Balance óptimo de precisión y cobertura para alertas de transacciones sospechosas.

---

## 5. Inyección de Fallas de Nivel 5 (REQ-15, REQ-16)

El gestor de fallas (`FaultManager`) permite someter al agente a pruebas de estrés y escenarios adversos sin comprometer la estabilidad del sistema:

1. **HTTP Error (`POST /admin/faults/http`)**:
   - Simula caídas de dependencias (por ejemplo, `500 Internal Server Error` o `503 Service Unavailable` repetido $k$ veces).
2. **Expiración de Sesión (`POST /admin/faults/expire-sessions`)**:
   - Invalida los tokens activos para verificar que el agente transiciona a la ruta `reauth` y solicita reautenticación sin perder el contexto conversacional.
3. **Falla de Persistencia / Drop Writes (`POST /admin/faults/drop-writes`)**:
   - `POST /disputes` responde con código `201 Created` simulado pero omite la persistencia en memoria/base de datos. Permite comprobar que el nodo `VERIFY` del agente detecta la omisión y escala a humano con la alerta correspondiente en lugar de afirmar un éxito falso al cliente (REQ-09, MET-04).
4. **Latencia y Timeouts (`POST /admin/faults/latency`)**:
   - Introduce un retraso de `delay_s` segundos en el endpoint seleccionado. Permite validar que el cliente bancario (`BankClient`) respeta el límite de tiempo (`tool_timeout_s`), aplica reintentos con backoff exponencial y, al agotar los intentos, escala limpiamente a humano.

---

## 6. Desviaciones y Decisiones Arquitectónicas del Contrato

En la implementación del sistema S.O.F.I.A. se adoptaron cuatro decisiones arquitectónicas justificadas:

### 1. POL-7 se gestiona en el agente conversacional, no en el motor de políticas de SIM
- **Rationale**: POL-1 a POL-6 evalúan reglas determinísticas financieras sobre transacciones y clientes (estado de cuenta, montos, antigüedad, reclamos duplicados y riesgo de fraude). Por el contrario, POL-7 define el límite de turnos de clarificación (máximo 2 intentos antes de escalar a un humano). El conteo de intentos de clarificación y la ambigüedad del diálogo son inherentes al estado del grafo conversacional (`agent/`), por lo que su control reside en la capa de orquestación del agente y no en la API bancaria.

### 2. Identificador de elegibilidad (`eligibility_id`) + `ConfirmationProof` en lugar de `confirmation_id` independiente
- **Rationale**: La especificación preliminar contemplaba un `confirmation_id` emitido por el banco. En el diseño final, la creación de la disputa (`POST /disputes`) requiere el `eligibility_id` (que garantiza que la transacción fue validada previamente bajo la política y está dentro de su ventana de TTL de 15 minutos) junto con un objeto `ConfirmationProof` (que encapsula el texto explícito de confirmación del cliente y el timestamp del turno). Esto simplifica el contrato eliminando una llamada intermedia redundante mientras preserva la garantía estricta de confirmación previa a cualquier mutación (REQ-09).

### 3. Registro de auditoría en memoria (`InMemoryAuditTrail`) para el sandbox de hackathon
- **Rationale**: Durante la fase de hackathon, el registro de auditoría (`audit_trail`) opera en memoria para asegurar máxima velocidad en tests unitarios y permitir inspección directa mediante `GET /admin/audit`. En el diseño para producción bancaria, este registro se descarga de manera asíncrona a una tabla append-only en PostgreSQL/BigQuery o Cloud Logging con retención WORM inmutable y firmas criptográficas.

### 4. Métricas MET-05 y MET-06 calculadas a partir de temporizadores locales y contadores de tokens
- **Rationale**: MET-05 (latencia) y MET-06 (costo) se miden en el arnés de evaluación acumulando deltas de `time.perf_counter()` por turno y sumando los tokens de entrada y salida provistos por las respuestas del LLM multiplicados por las tarifas públicas configuradas (`GEMINI_PRICE_INPUT_PER_MTOK` y `GEMINI_PRICE_OUTPUT_PER_MTOK`). Esto asegura reproducibilidad estricta de las evaluaciones offline (`make eval`) sin dependencia de red ni de cuotas en la API de analítica externa de Langfuse.
