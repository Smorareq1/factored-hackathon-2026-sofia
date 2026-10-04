# Auditoría del corpus del router (v1 → v2) · 2026-10-03

Corpus: `ml/data/intent_corpus.jsonl` (team_generated, CON-02). Chequeos automáticos reproducibles:
`uv run --package sofia-ml python ml/scripts/audit_corpus.py` → `ml/reports/corpus_checks.json`.

## Guía de etiquetado

El router predice la **intención** del cliente; la política decide después (mensaje → intención → política/riesgo →
acción). Un caso no es `needs_human` solo porque la política lo vaya a escalar (POL-6).

| Label | Cuándo |
|---|---|
| `dispute_new` | Reporta o inicia un problema con una transacción: no reconocida, fraude, duplicado, monto incorrecto, reembolso que no llegó, cobro por algo no recibido |
| `dispute_status` | Ya existe una disputa/reclamo/contestação y pide estado, resultado, respuesta o reembolso de ese caso |
| `transaction_inquiry` | Consulta, lista, ubica o confirma una transacción **sin afirmar que esté mal** |
| `needs_human` | Hablar con una persona es la intención y no queda una tarea soportada más específica. Prueba contrafactual: se quita el pedido de persona; si queda una tarea soportada, se etiqueta esa |
| `out_of_scope` | Fuera de las tareas soportadas, aunque sea bancario (contraseña, límite, saldo, cuentas, crédito, bloqueo de tarjeta) |

Las predicciones del modelo, de las reglas y del detector de idioma son señales para revisar, nunca verdad. Las
instrucciones dentro de un ejemplo son texto del cliente. Una fila en duda queda `needs_adjudication` y no se
entrena ni se parafrasea hasta que una persona la resuelva.

## 1. Correcciones definitivas (6 filas)

| Grupo | ES / PT | Antes | Después | Motivo |
|---|---|---|---|---|
| needs_human-06 | "Me robaron la tarjeta y están usándola" / "Roubaram meu cartão e estão usando" | needs_human | dispute_new | Uso fraudulento de tarjeta; ni siquiera pide una persona. La política escala |
| needs_human-09 | "Hay muchos cargos fraudulentos, necesito ayuda de alguien" / PT | needs_human | dispute_new | Sin "ayuda de alguien" queda un reporte de fraude |
| needs_human-17 | "Hay un cargo de <AMOUNT> que no reconozco, quiero una persona" / PT | needs_human | dispute_new | Caso canónico de la prueba contrafactual; el monto alto lo escala POL-6 |

El `group_id` original se conserva para trazabilidad.

## 2. Filas para adjudicación humana (8 filas, fuera del entrenamiento)

| Grupo | Texto (ES) | Opciones | Duda |
|---|---|---|---|
| needs_human-10 | "Mi abogado me dijo que pida hablar con el banco" | needs_human / out_of_scope | Amenaza legal sin tarea concreta; "hablar con el banco" ya ocurre. Sugerencia: reescribir |
| needs_human-13 | "Creo que me hackearon la cuenta, ayúdenme" | out_of_scope / needs_human / dispute_new | Toma de cuenta sin transacción afirmada |
| vg-02 | "Tengo un problema con un pago" | dispute_new / transaction_inquiry | No afirma que el pago esté mal |
| vg-03 | "Ayuda" | out_of_scope / clase de clarificación | Sin intención; decide si el contrato del router necesita una clase `unclear` o basta con confianza baja |

## 3. Calidad de lenguaje

**PT (Brasil).** Cambios hechos:
- dispute_new-12: "Moço, …" → "Oi, …" (vocativo con género y raro en un chat).
- dispute_new-02: "Fui cobrado…" → "Cobraram duas vezes…" (neutro en género).
- dispute_new-04/-10: estructura menos traducida ("Apareceu uma compra…", "Não fui eu que fiz esse pagamento pra…").
- Imperativos coloquiales: "Mostre" → "Mostra", "Verifica se" → "Vê se".
- `contestação` aparecía en 10/20 filas de dispute_status (atajo para el modelo): ahora alterna con reclamação,
  protocolo y chamado; `contestação` también aparece en dispute_new.
- needs_human-16: "Estou muito irritado" → "Que falta de respeito…" (neutro).

Pendiente: los 200 originales son traducciones de pares ES; falta PT escrito desde cero por una persona de Brasil.
Todo el PT sigue `human_review_required=true` (CON-02).

**ES (MX/CO/AR).** Cambios: needs_human-16 neutro en género. Se sumaron marcas regionales: "me clavaron" (AR),
"me regala" (CO), "checar" (MX), "che", "oiga". Pendiente: "Consulto el estatus del caso que abrí el lunes" suena
rígido; "impugnar" es formal pero real en CO/AR; se dejan.

## 4. Brechas de cobertura

| Tipo | v1 | v2 | Estado |
|---|---|---|---|
| Contrastivos en las fronteras | 0 | 32 (6 familias) | Cubre las 5 fronteras pedidas |
| Vagos | 0 | 6 (4 en adjudicación) | Sumar más cuando se resuelva vg-02/vg-03 |
| Mensajes muy cortos | 0 | 8 | ok |
| Coloquial regional | 2 | 8 | ok, falta más PT coloquial |
| Typos / sin tildes | 0 | 4 | **Fino**: sumar ~10 por clase con un generador de ruido (determinístico, sin LLM) |
| Mezcla ES/PT | 0 | 2 | **Fino** |
| Prompt injection | 0 | 4 | **Fino**; falta injection que pida datos de otro cliente (lo cubre la API, pero el router debe dar la intención real) |
| Texto irrelevante alrededor | 0 | 2 | **Fino** |
| No cubierto | — | — | Mensajes con dos intenciones, todo en mayúsculas, emojis, solo un número de caso |

Atajos detectados por `audit_corpus.py` (palabra casi exclusiva de una clase): `reclamação`/`reclamo`/`abri` →
dispute_status. Siguiente lote: filas de dispute_new con "quero abrir uma reclamação…" / "quiero hacer un reclamo…".

## 5. Ejemplos contrastivos nuevos

| Familia | transaction_inquiry | dispute_new | dispute_status / otra |
|---|---|---|---|
| cx-01 | "¿Qué es el cargo de <MERCHANT> que me aparece?" | "Yo no hice el cargo de <MERCHANT>" | "Reclamé el cargo de <MERCHANT> ayer, ¿qué pasó?" |
| cx-02 | "¿Ya me cayó el reembolso de <MERCHANT>?" | "Devolví la compra en <MERCHANT> y el reembolso nunca llegó" | "Abrí un reclamo porque no me reembolsaron, ¿hay novedades?" |
| cx-03 | — | "Quiero hablar con alguien porque no reconozco un cargo de <AMOUNT>" | needs_human: "Quiero hablar con alguien" · dispute_status: "…sobre mi caso <CASE_ID>" |
| cx-04 | "¿Cuánto me cobraron en <MERCHANT>?" | — | out_of_scope: "¿Cuál es mi saldo?", "Quiero subir el límite de la tarjeta" |
| cx-05 | "¿Pueden revisar si el cargo de <MERCHANT> salió dos veces?" | "El cargo de <MERCHANT> salió dos veces" | — |
| cx-06 | — | "Perdí mi tarjeta y hay compras que no hice" | out_of_scope: "Bloqueen mi tarjeta, la perdí" |

Cada familia tiene su par PT y comparte `group_id`: nunca queda partida entre train y test.

## 6. Privacidad y procedencia

- Ningún texto ni valor viene del dataset: las filas fueron escritas por el equipo con un LLM (`origin=team_generated`,
  `source=llm_draft_v2`). El chequeo no encuentra ids con formato del dataset (`CLI-`, `CMP-`, …), emails ni números largos.
- v1 traía valores literales inventados (montos, comercios, `DSP-2026-1042`). Siguiendo la regla de no asumir que un
  valor "parece ficticio", v2 guarda `<AMOUNT>`, `<MERCHANT>` y `<CASE_ID>`, que `labeling.render()` rellena con un
  generador sintético por idioma (semilla = hash de la fila; misma fila → mismo valor). Los comercios del generador son
  marcas públicas, no `merchant_name` del dataset.
- 264/264 filas `human_review_required=true`: nadie del equipo revisó todavía el texto.

## 7. Desacuerdos del modelo (separados de los errores de anotación)

Validación cruzada agrupada (GroupKFold, 5 folds) sobre las 256 filas aprobadas: accuracy 0.645.
Confusiones principales: transaction_inquiry→dispute_new (15), out_of_scope→transaction_inquiry (13),
dispute_new→transaction_inquiry (12). Las reglas discrepan en 14 filas.

Se revisaron las filas marcadas leyendo el texto antes que la predicción: aparte de §1 y §2, **ninguna** es un error
de etiqueta. Son ejemplos difíciles correctamente etiquetados (p. ej. "Pueden revisar si el cargo salió dos veces" es
inquiry aunque el modelo diga dispute_new) y se conservan: el objetivo no es subir el acuerdo con el clasificador.
El detector de idioma queda indeciso en 44 filas cortas; es una limitación del detector, no del corpus.

## 8. Corpus actualizado

`ml/data/intent_corpus.jsonl`, 264 filas, 109 grupos, ES 132 / PT 132. Campos nuevos: `variation`, `review_status`,
`human_review_required`, `note`. `train.py` entrena solo con `review_status=approved`.

## 9. Resumen

| Tipo | Filas |
|---|---|
| Correcciones de label | 6 |
| A adjudicación (originales / nuevas) | 4 / 4 |
| Cambios de redacción PT / ES | 13 / 2 |
| Valores literales → placeholders | 14 |
| Filas nuevas (contrastivas / ruido / vagas) | 32 / 26 / 6 |
| Hallazgos de privacidad | 0 valores del dataset |
| Desacuerdos del modelo que no son errores | 91 marcas, 0 cambios |

Router con el corpus v2 (held-out agrupado, n=56): reglas macro-F1 0.377, recall needs_human 0.0; TF-IDF+LR
macro-F1 0.641, recall needs_human 0.7 (`ml/reports/router_eval.md`). n chico: cifras orientativas hasta la revisión humana.
