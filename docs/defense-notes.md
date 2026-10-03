# Notas de defensa (DEL-08) · Top 5, 2026-10-16

Preguntas probables del jurado con respuesta corta (≤ 30 s hablada) y la evidencia para mostrar si repreguntan.
Las cifras son placeholders `{{...}}` que se completan desde los JSON versionados antes de la defensa; si una
cifra no existe, se responde sin ella y se dice que no se midió.

**Mensaje que repetimos:** *el LLM entiende y redacta; la API decide. Medimos contra un baseline con la misma carga,
reportamos por idioma con n e intervalos, y decimos qué no sabemos.*

---

## 1. Datos y elección del workflow

**¿Por qué disputas y no tarjetas o pagos?**
Porque es donde el dataset tiene más evidencia conectable: `transactions`, `complaints` y `call_center_interactions`
se unen por llaves y nos dejan medir volumen, SLA roto y escalación del mismo fenómeno. Las disputas son
`{{results/workflow_justification.json:dispute_share_pct}}`% de las quejas. Escribimos un criterio de salida antes del
EDA (si eran marginales, cambiábamos a soporte de tarjetas) y no se activó.
*Evidencia:* `analysis/notebooks/01_workflow_justification.ipynb`, `analysis/results/workflow_justification.json`.

**`complaints` no tiene `transaction_id`. ¿Cómo ligan una queja con una transacción?**
Por producto afectado + ventana de fechas previa a la queja. Lo medimos en vez de suponerlo: cubre
`{{results/workflow_justification.json:link_coverage_pct}}`% de las disputas. En la conversación no hace falta el
vínculo histórico: el cliente señala la transacción y Sofía la busca en sus propios registros.

**¿De dónde salen N y U?**
De la distribución real, no de un número redondo. N = `{{results/policy_calibration.json:N_days.value}}` días
(`{{results/policy_calibration.json:N_days.rationale}}`); U = `{{results/policy_calibration.json:U_usd.value}}` USD, que deja
`{{results/policy_calibration.json:U_usd.pct_auto}}`% de las disputas en ruta automática. La política es sintética y
está etiquetada como definida por el equipo (CON-02): un banco real pondría sus propias reglas en el mismo lugar.

## 2. Componente aprendido (router)

**¿De dónde salen los labels del router? (pregunta muy probable)**
Del dataset no: lo auditamos antes de entrenar y no sirven. `call_transcripts` tiene solo
`{{results/label_audit.json:transcript_templates[0].plantillas}}` plantillas de **consulta de saldo**
(`{{results/label_audit.json:transcript_templates[0].filas}}` filas), repartidas por igual entre las categorías de
contacto, y `detected_intents` es siempre `consulta_general`. El texto no tiene relación con la categoría: un
modelo entrenado ahí aprendería ruido, o memorizaría plantillas y daría un número alto y vacío.
*Propuesta (pendiente de aprobación del equipo):* entrenar el router con un corpus ES/PT generado por el equipo,
etiquetado `team_generated` (CON-02), con split por grupo, y presentar la auditoría de labels como evidencia de
REQ-13 ("labels válidos"). Es una limitación declarada: el router no está validado con texto real de clientes.
*Evidencia:* `analysis/notebooks/04_label_audit.ipynb`, `analysis/results/label_audit.json`.

**¿Cómo evitaron leakage en el split del router?**
Tres capas. (1) Split por grupo: en el corpus del equipo, el grupo es la familia de paráfrasis (todas las
variantes de una misma frase caen del mismo lado); en datos del dataset, el cliente. (2) Temporal cuando hay
fechas: test = los últimos días, y se sacan de train los grupos que aparecen en test. (3) Un `assert` que falla si
hay un grupo **o un texto idéntico** en ambos lados. Tamaño del test: `{{eval/outputs/ds_stats.json:router.split.n_test}}`.
*Evidencia:* `ml/src/sofia_ml/split.py` (`assert_no_leakage`), `ml/reports/router_eval.json`.

**Repregunta: si el corpus lo escribieron ustedes, ¿no es fácil?**
Es un riesgo real: quien escribe train y test comparte estilo. Lo mitigamos con el split por familia de
paráfrasis y lo medimos por idioma (macro-F1 PT `{{eval/outputs/ds_stats.json:router.proposed.by_language.pt.macro_f1}}`).
Pero el número del router es optimista frente a clientes reales, y lo decimos; el siguiente paso es etiquetar
mensajes reales en modo sombra.

**¿Por qué macro-F1 y recall de `needs_human`?**
Macro-F1 porque las clases están desbalanceadas y `out_of_scope` o `needs_human` importan tanto como la mayoritaria.
Recall de `needs_human` porque dejar pasar un caso que debía ir a un humano es el error más caro; uno innecesario
cuesta minutos de un agente. Resultado: `{{eval/outputs/ds_stats.json:router.baseline_rules.needs_human_recall}}` (reglas)
→ `{{eval/outputs/ds_stats.json:router.proposed.needs_human_recall}}` (aprendido).

**¿Y si el router se equivoca?**
No decide nada sensible. Por debajo del umbral de confianza (`{{eval/outputs/ds_stats.json:router.threshold}}`) Sofía
pregunta; y aunque clasifique mal, la elegibilidad y los permisos los vuelve a decidir la API. El peor caso de un
error del router es una pregunta de más o un handoff, no una acción indebida.

## 3. Arquitectura y seguridad

**¿Por qué la política fuera del prompt?**
Porque un prompt es una sugerencia y una regla en la API es un hecho. Si la elegibilidad estuviera en el prompt,
un cliente podría negociarla ("ignora tus reglas"). En Sofía, la API solo devuelve transacciones del `customer_id`
ligado al token, contesta 404 si la transacción es de otro (sin revelar que existe, POL-1) y exige una confirmación
explícita antes de registrar. El LLM no tiene una herramienta que le permita saltarse eso. Hay un test que lo
demuestra con un prompt de inyección (REQ-10).

**¿Para qué 7 capas? ¿No es sobreingeniería?**
Cada capa responde a un requisito y deja un evento auditable: PURPOSE (alcance y límites versionados), SENSE
(idioma, normalización), INTERPRET (router + slots), DECIDE (política), ORCHESTRATE (actuar, verificar, escalar),
GOVERN (allowlist de tools por nodo, grounding, guardia de salida), LEARN (gate de regresión). Así cada decisión es
explicable con registros, no con chain-of-thought (REQ-19). El baseline es justamente lo contrario —un LLM con las
mismas tools— y la diferencia está medida.

**¿Cómo saben que la acción ocurrió?**
Después de crear la disputa, Sofía la relee con `GET /disputes/{id}`. Solo informa el número de caso si la relectura
lo confirma; si la tool falla, reintenta de forma acotada y, si sigue fallando, no afirma nada y escala (REQ-09, REQ-16).

**¿Qué ve el humano en el handoff?**
Una ficha JSON: hechos verificados con su fuente, acciones ejecutadas, preguntas abiertas, banderas de riesgo y la
regla que motivó el handoff. Nunca el transcript (REQ-05). La completitud de campos se mide (MET-03:
`{{eval/outputs/ds_stats.json:proposed.all.met03_handoff_completeness}}`).

## 4. Evaluación y estadística

**Reportan cero (o pocos) unsafe outcomes. Con ese n, ¿qué significa?**
Poco, y lo decimos. Con `{{eval/outputs/ds_stats.json:n_cases.total}}` casos y
`{{eval/outputs/ds_stats.json:proposed.all.met04_count}}` resultados inseguros, la cota superior al 95 % es
`{{eval/outputs/ds_stats.json:proposed.all.met04_upper95}}` (con cero eventos, regla de tres: ≈ 3/n). Cero en una muestra
chica no es riesgo cero. Lo que sí es fuerte es la evidencia estructural: los tests que muestran que la API niega
acciones no autorizadas no dependen del tamaño de la muestra.

**¿Cómo construyeron los intervalos?**
`{{eval/outputs/ds_stats.json:ci_method}}`. El principio: se remuestrean casos, no turnos (los turnos de una
conversación no son independientes), por idioma, y `{{eval/outputs/ds_stats.json:n_runs}}` corridas repetidas miden la
variabilidad del LLM. Baseline y Sofía corren sobre los **mismos** casos, así que la diferencia se puede comparar
caso a caso. *(Confirmar con el método real de `ds_stats.json` antes de la defensa.)*

**Containment alto no es bueno si el sistema no resuelve.**
De acuerdo: por eso MET-01 (resolución automatizada **correcta** sobre casos in-scope) y MET-02 (containment) se
reportan por separado, junto con el % de casos donde se intentó automatizar.

**¿Usaron LLM-as-judge?**
Las métricas MET-01..05 son determinísticas (ruta, tool calls, fugas, verificación). Los evaluadores de Langfuse solo
puntúan calidad de redacción y se validaron contra una muestra etiquetada por humanos
(`{{eval/outputs/ds_stats.json:judge_agreement}}` de acuerdo). No usamos el juez para nada que afecte seguridad.

**¿Hay disparidades por idioma o segmento? (REQ-18)**
Las reportamos por celda con su n: `{{results/fairness.json:summary}}`. Donde la celda es chica no concluimos; lo
decimos así en el reporte.

## 5. Portugués

**El dataset es todo en español. ¿Qué tan bueno es su portugués?**
Es nuestra mayor limitación y la declaramos. Los casos PT son generados por el equipo: traducidos con LLM y
revisados por humanos, y etiquetados `team_generated` (CON-02). Revisamos `{{eval/outputs/ds_stats.json:pt_review.n_reviewed}}`
de `{{eval/outputs/ds_stats.json:pt_review.n_total}}` casos y corregimos `{{eval/outputs/ds_stats.json:pt_review.n_corrected}}`.
Riesgo conocido: un PT traducido es más "limpio" que el de un cliente real de Brasil (menos jerga, menos errores de
tipeo), así que el resultado PT probablemente es optimista. En producción: un set PT real etiquetado por hablantes
nativos antes de abrir el canal.

**¿Y la mezcla ES/PT en un mismo mensaje?**
Es un caso adversarial del set (nivel 4). SENSE detecta el idioma por turno y Sofía responde en el del cliente; si
la intención no queda clara, pregunta.

## 6. Costo y latencia

**¿Qué supuestos tiene el costo por caso?**
Tokens reales medidos por Langfuse en cada llamada × precio público de Gemini por token en la fecha de la corrida
(`{{eval/outputs/ds_stats.json:pricing.model}}`, `{{eval/outputs/ds_stats.json:pricing.usd_per_1m_input}}` USD por millón
de tokens de entrada, `{{eval/outputs/ds_stats.json:pricing.usd_per_1m_output}}` de salida). No incluye infraestructura
(Cloud Run escala a cero) ni el costo del agente humano en los handoffs. El costo por resolución exitosa se reporta
como "not defined" si no hay éxitos (MET-06).

**¿Por qué Sofía es más lenta/cara que el baseline (si lo es)?**
Porque verifica: relee la disputa después de crearla y consulta la política. Es un costo deliberado: p95
`{{eval/outputs/ds_stats.json:proposed.all.met05_p95_s}}` s contra `{{eval/outputs/ds_stats.json:baseline.all.met05_p95_s}}` s
del baseline. Además Sofía no manda los datos de las tools al LLM para decidir, el baseline sí.

**¿Cuánto ahorraría al banco?**
No lo presentamos como ahorro medido. Contra el baseline de negocio histórico (FCR, escalación, duración del call
center, `analysis/results/business_baseline.json`) solo mostramos una **proyección**, etiquetada como tal (CON-07).

## 7. Camino a producción

**¿Qué falta para producción?** (en orden de prioridad)
1. **Datos reales en PT** y una corrida de evaluación con clientes reales en sombra (shadow mode), sin actuar.
2. **Persistencia:** checkpointer en Postgres administrado (hoy la conversación vive en memoria, 1 instancia) y log
   de auditoría persistente.
3. **Red y auth:** router y bank-api internos (VPC / IAM invoker), solo el frontend expuesto; autenticación con el
   IdP real del banco en lugar del OTP simulado.
4. **Política del banco:** reemplazar POL-1..7 sintéticas por las reales, con dueños de negocio y versionado.
5. **Operación:** staging/prod separados con rollback, pipeline programado con SLA de freshness que bloquee gold,
   monitoreo de deriva del router y re-entrenamiento con los labels que deja la consola de agentes (LEARN).
6. **Evaluación continua:** el gate de regresión (MET-01 no baja, MET-04 no sube) en cada cambio de prompt o modelo.

**¿Qué harían distinto con más tiempo?**
Un set held-out más grande para intervalos más angostos, etiquetado humano más amplio del router y una evaluación
PT con hablantes nativos.

---

## Plan de demo en vivo

- La víspera: `MIN_INSTANCES=1` (OPS) para evitar el arranque en frío; probar desde una red externa.
- Guion: el mismo del video (ES feliz → PT → handoff → Langfuse), con `MX-DEMO-001`; tener `CO-DEMO-002` de respaldo.
- Si Gemini falla en vivo: el turno sigue con reglas y plantillas (fallback, REQ-16). Mostrarlo como fortaleza.
- Respaldo final: el video grabado y capturas de la traza en Langfuse.
