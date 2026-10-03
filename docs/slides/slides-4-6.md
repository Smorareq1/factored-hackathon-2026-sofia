# Slides 4–6 (DS) · DEL-03

Deck de 4–6 slides (DEL-03: problema, solución, arquitectura, resultados, limitaciones). DS es dueño de las slides
4–6; las 1–3 (problema, workflow elegido, demo) las arma el equipo. Cada slide: título, máximo 5 bullets, **un solo
gráfico** (con el JSON del que sale) y notas del orador.

> **Regla de cifras:** ninguna cifra se escribe a mano. Cada número es un placeholder `{{archivo:clave}}` que se
> reemplaza con el valor del JSON versionado justo antes de exportar el deck. Si un JSON no tiene la clave, el bullet
> se reescribe sin la cifra; nunca se estima. Lo simulado y lo proyectado se etiqueta como tal (CON-07).

---

## Slide 4 · Los datos eligieron el workflow

**Título:** *Las disputas de transacciones: volumen alto, SLA roto y una acción segura*

- Las interacciones **Transaccionales** son `{{results/workflow_justification.json:reason_categories[Transaccional].pct}}`%
  del call center, con escalación de `{{results/workflow_justification.json:reason_categories[Transaccional].p_escalado}}`.
- "Cargo no reconocido" + "Cobro indebido" = `{{results/workflow_justification.json:dispute_share_pct}}`% de las quejas;
  SLA incumplido en `{{results/workflow_justification.json:complaint_subcategories[Cargo no reconocido].p_sla_roto}}`.
- `complaints` no trae `transaction_id`: el vínculo producto + ventana de fechas cubre
  `{{results/workflow_justification.json:link_coverage_pct}}`% de las disputas (riesgo §14, medido, no supuesto).
- Política calibrada con datos, no por intuición: ventana **N = `{{results/policy_calibration.json:N_days.value}}` días**,
  umbral **U = `{{results/policy_calibration.json:U_usd.value}}` USD** (`{{results/policy_calibration.json:U_usd.pct_auto}}`%
  de disputas quedan en ruta auto), fraude ≥ `{{results/policy_calibration.json:fraud_score_threshold.value}}`.
- Acción segura: **registrar** la disputa; nunca se mueve dinero (CON-05).

**Gráfico único:** barras horizontales "Interacciones por categoría de contacto" con la tasa de escalación como
etiqueta, resaltando Transaccional. Fuente: `analysis/results/workflow_justification.json` → `reason_categories`
(figura en `analysis/figures/`). Como inserto pequeño opcional: CDF de `claimed_amount` en USD con la línea de U,
de `analysis/results/policy_calibration.json` (solo si cabe sin recargar; si no, va al README).

**Notas del orador (~35 s):**
No elegimos el workflow por gusto: lo elegimos porque es donde el dataset tiene más evidencia conectable.
Transacciones, quejas e interacciones se unen por llaves, así que podemos medir volumen, SLA roto y escalación
del mismo fenómeno. Teníamos un criterio de salida escrito antes del EDA: si las disputas resultaban marginales,
cambiábamos a soporte de tarjetas. No se activó: `{{results/workflow_justification.json:decision}}`.
N y U no son números redondos elegidos a ojo: N es el percentil que cubre la mayoría de las disputas legítimas y U
deja en automático solo la parte de bajo monto donde un error es barato. La justificación completa está en el
notebook 02: `{{results/policy_calibration.json:U_usd.rationale}}`.

---

## Slide 5 · Arquitectura: el LLM entiende y redacta; la política decide

**Título:** *7 capas: la seguridad vive fuera del prompt*

- **PURPOSE → SENSE → INTERPRET → DECIDE → ORCHESTRATE (act · verify · escalate) → GOVERN → LEARN**, como grafo
  LangGraph explícito; cada capa deja un evento auditable (caja de cristal, REQ-19).
- **Auditamos los labels antes de entrenar:** `call_transcripts` son `{{results/label_audit.json:transcript_templates[0].plantillas}}`
  plantillas de consulta de saldo repartidas por igual entre las categorías, y `detected_intents` es siempre
  `consulta_general` → el dataset **no tiene labels de intención válidos**. *Propuesta (pendiente de aprobación):*
  entrenar el router con un corpus ES/PT generado por el equipo (`team_generated`), con split por grupo.
- **Router aprendido vs reglas** en el mismo test held-out (split por familia de paráfrasis, sin textos repetidos):
  macro-F1 `{{eval/outputs/ds_stats.json:router.baseline_rules.macro_f1}}` → `{{eval/outputs/ds_stats.json:router.proposed.macro_f1}}`;
  recall de `needs_human` `{{eval/outputs/ds_stats.json:router.baseline_rules.needs_human_recall}}` →
  `{{eval/outputs/ds_stats.json:router.proposed.needs_human_recall}}` (n = `{{eval/outputs/ds_stats.json:router.split.n_test}}`).
- **Política POL-1..7 en la API (FastAPI)**, no en el prompt: permisos por `customer_id` del token, elegibilidad
  determinística, confirmación explícita antes de actuar y relectura para verificar (REQ-09/10).
- Gemini solo extrae slots y redacta (si falla, reglas y plantillas, REQ-16); todo trazado en **Langfuse**: 1 traza
  por conversación, 1 span por capa y por tool call → latencia y costo reales.

**Gráfico único:** diagrama de las 7 capas (izquierda) contra la capa determinística de la API (derecha), con una
línea punteada roja "frontera de confianza" entre ambas. Al pie, mini-tabla de 2 filas del router (reglas vs
aprendido: macro-F1, recall `needs_human`, n). Fuente del diagrama: §8.4 del brief + `agent/README.md`; fuente de la
mini-tabla: `eval/outputs/ds_stats.json` → `router` (copiado de `ml/reports/router_eval.json`).

**Notas del orador (~40 s):**
La decisión de arquitectura más importante es dónde NO está el LLM. Gemini entiende lo que el cliente dice y
redacta la respuesta; nunca decide quién puede ver qué, ni si una disputa es elegible. Eso lo decide la API con
el token de la sesión y las reglas POL-1 a POL-7. Por eso un prompt malicioso no puede saltarse la política: no hay
nada que convencer, la regla no está en el texto. El componente aprendido es el router de intención, y antes de
entrenarlo auditamos los labels: los transcripts del dataset son plantillas de consulta de saldo repartidas por
igual entre categorías, y la intención detectada es siempre la misma. Entrenar con eso habría dado un número alto y
vacío. Por eso proponemos entrenar con un corpus ES/PT generado por el equipo, etiquetado como tal, y usar la
auditoría como evidencia (REQ-13); esa decisión está pendiente de aprobación del equipo. Lo comparamos contra el
baseline de palabras clave en el mismo test, separado por grupo para que no haya leakage. La métrica que más nos importa es el recall de `needs_human`: dejar pasar un caso que debía ir a un humano
es el error más caro. Por debajo del umbral de confianza `{{eval/outputs/ds_stats.json:router.threshold}}`,
Sofía no adivina: pregunta.

---

## Slide 6 · Resultados: baseline vs Sofía, por idioma

**Título:** *Medido, no prometido: MET-01..06 en el set held-out*

- Mismo set y misma carga para los dos sistemas: n = `{{eval/outputs/ds_stats.json:n_cases.es}}` casos ES y
  `{{eval/outputs/ds_stats.json:n_cases.pt}}` PT, `{{eval/outputs/ds_stats.json:n_runs}}` corridas repetidas; IC 95 %
  (`{{eval/outputs/ds_stats.json:ci_method}}`).
- **Resolución automatizada segura (MET-01):** `{{eval/outputs/ds_stats.json:baseline.all.met01}}` →
  `{{eval/outputs/ds_stats.json:proposed.all.met01}}`; **unsafe outcomes (MET-04):**
  `{{eval/outputs/ds_stats.json:baseline.all.met04_count}}` → `{{eval/outputs/ds_stats.json:proposed.all.met04_count}}`
  de `{{eval/outputs/ds_stats.json:n_cases.total}}` casos.
- **Escalación (MET-03):** recall `{{eval/outputs/ds_stats.json:proposed.all.met03_recall}}`, precisión
  `{{eval/outputs/ds_stats.json:proposed.all.met03_precision}}`, campos de handoff completos
  `{{eval/outputs/ds_stats.json:proposed.all.met03_handoff_completeness}}`.
- **Costo y latencia (MET-05/06):** p95 `{{eval/outputs/ds_stats.json:proposed.all.met05_p95_s}}` s;
  `{{eval/outputs/ds_stats.json:proposed.all.met06_cost_per_resolution_usd}}` USD por resolución exitosa
  (precio público de Gemini, supuestos en el README).
- **Límites honestos:** PT es traducido por el equipo (no hay PT en el dataset); 0 unsafe en n casos ≠ riesgo cero
  (cota superior 95 % ≈ `{{eval/outputs/ds_stats.json:proposed.all.met04_upper95}}`); resultados offline, no producción (CON-07).

**Tabla de respaldo (va en el reporte DEL-06; en la slide solo si cabe).** Convención: cada placeholder de
`ds_stats.json` en esta tabla trae el valor ya formateado como `valor [IC95 bajo–alto]`.

| Métrica | Baseline ES | Sofía ES | Baseline PT | Sofía PT |
|---|---|---|---|---|
| MET-01 resolución auto segura | `{{eval/outputs/ds_stats.json:baseline.es.met01}}` | `{{eval/outputs/ds_stats.json:proposed.es.met01}}` | `{{eval/outputs/ds_stats.json:baseline.pt.met01}}` | `{{eval/outputs/ds_stats.json:proposed.pt.met01}}` |
| MET-02 containment | `{{eval/outputs/ds_stats.json:baseline.es.met02}}` | `{{eval/outputs/ds_stats.json:proposed.es.met02}}` | `{{eval/outputs/ds_stats.json:baseline.pt.met02}}` | `{{eval/outputs/ds_stats.json:proposed.pt.met02}}` |
| MET-03 recall escalación | `{{eval/outputs/ds_stats.json:baseline.es.met03_recall}}` | `{{eval/outputs/ds_stats.json:proposed.es.met03_recall}}` | `{{eval/outputs/ds_stats.json:baseline.pt.met03_recall}}` | `{{eval/outputs/ds_stats.json:proposed.pt.met03_recall}}` |
| MET-04 unsafe (conteo / n) | `{{eval/outputs/ds_stats.json:baseline.es.met04}}` | `{{eval/outputs/ds_stats.json:proposed.es.met04}}` | `{{eval/outputs/ds_stats.json:baseline.pt.met04}}` | `{{eval/outputs/ds_stats.json:proposed.pt.met04}}` |
| MET-05 latencia p50 / p95 (s) | `{{eval/outputs/ds_stats.json:baseline.es.met05}}` | `{{eval/outputs/ds_stats.json:proposed.es.met05}}` | `{{eval/outputs/ds_stats.json:baseline.pt.met05}}` | `{{eval/outputs/ds_stats.json:proposed.pt.met05}}` |
| MET-06 USD / caso intentado | `{{eval/outputs/ds_stats.json:baseline.es.met06}}` | `{{eval/outputs/ds_stats.json:proposed.es.met06}}` | `{{eval/outputs/ds_stats.json:baseline.pt.met06}}` | `{{eval/outputs/ds_stats.json:proposed.pt.met06}}` |

**Gráfico único:** dot plot con barras de error (IC 95 %): una fila por métrica (MET-01..04), dos puntos por idioma
(baseline gris, Sofía color), ES y PT en paneles lado a lado. Latencia y costo van como texto en los bullets, no en
el gráfico (otra escala). Fuente: `eval/outputs/ds_stats.json` (agregado por DS a partir de `eval/outputs/summary.json`
del harness de SIM). Fairness por segmento (REQ-18): `analysis/results/fairness.json`, solo en el reporte.

**Notas del orador (~40 s):**
Todo lo que mostramos es offline, sobre el set held-out, con el mismo set para el baseline y para Sofía. El baseline
es un LLM con las mismas tools pero sin capas: sin router, sin política propia y sin verificación. Reportamos por
idioma porque es un requisito, y porque el portugués es nuestra mayor debilidad: el dataset no trae portugués,
así que los casos PT los tradujimos y revisamos nosotros. Fíjense en los intervalos, no solo en los puntos: con
`{{eval/outputs/ds_stats.json:n_cases.total}}` casos, cero resultados inseguros no significa riesgo cero; significa
que el riesgo está por debajo de `{{eval/outputs/ds_stats.json:proposed.all.met04_upper95}}` con 95 % de confianza.
Y containment no es resolución: contamos aparte los casos que Sofía resolvió bien sin humano.

---

## Claves de placeholders que este archivo espera

Para la sesión que escribe los JSON. Notación: `a.b` = clave anidada; `lista[X]` = el elemento de la lista cuyo
primer campo vale `X` (p. ej. `reason_category = "Transaccional"`); `lista[0]` = el primer elemento.

| Archivo | Claves | Estado |
|---|---|---|
| `analysis/results/workflow_justification.json` | `reason_categories[...]` (`pct`, `p_escalado`), `complaint_subcategories[...]` (`p_sla_roto`), `decision` | existen en el notebook 01 |
| `analysis/results/workflow_justification.json` | `dispute_share_pct`, `link_coverage_pct` | **por agregar** (notebook 01 §3–§4) |
| `analysis/results/policy_calibration.json` | `N_days.value`, `N_days.rationale`, `U_usd.value`, `U_usd.rationale`, `fraud_score_threshold.value` | definidas en el notebook 02, **bloqueado** (sin JSON aún) |
| `analysis/results/policy_calibration.json` | `U_usd.pct_auto` | **por agregar** (notebook 02 bloqueado) |
| `analysis/results/label_audit.json` | `transcript_templates[0].{filas,plantillas}` | existe |
| `eval/outputs/ds_stats.json` | `router.{baseline_rules,proposed}.{macro_f1,needs_human_recall}`, `router.split.n_test`, `router.threshold` | **por crear** (copiar de `ml/reports/router_eval.json`; los nombres de sistema se ajustan a los de ese reporte) |
| `eval/outputs/ds_stats.json` | `n_cases.{es,pt,total}`, `n_runs`, `ci_method`, `{baseline,proposed}.{es,pt,all}.met0X[...]`, `proposed.all.met04_upper95` | **por crear** (desde `eval/outputs/summary.json`) |
| Solo en `docs/defense-notes.md` | `ds_stats.json`: `router.split.dropped_for_leakage`, `router.proposed.by_language.pt.macro_f1`, `judge_agreement`, `pt_review.{n_reviewed,n_total,n_corrected}`, `pricing.{model,usd_per_1m_input,usd_per_1m_output}`; `fairness.json`: `summary` | **por crear**; `fairness` **bloqueado** |
