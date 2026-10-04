# Reporte de Evaluación — Proyecto S.O.F.I.A.

Evaluación rigurosa del sistema propuesto vs baseline según §6 (MET-01..MET-06).

## 1. Resumen Ejecutivo (Baseline vs Propuesto)

| Métrica | Definición | Baseline | Propuesto (S.O.F.I.A.) | Variación |
|---|---|---|---|---|
| **MET-01** Safe Auto Resolution | Safe Auto Resolution | 0.0% | **20.0%** | +20.0% |
| **MET-02** Containment | Containment | 0.0% | **100.0%** | +100.0% |
| **MET-03** Escalation Precision | Escalation Precision | 0.0% | **0.0%** | 0.0% |
| **MET-03** Escalation Recall | Escalation Recall | 0.0% | **0.0%** | 0.0% |
| **MET-03** Handoff Completeness | Handoff Completeness | 0.0% | **0.0%** | 0.0% |
| **MET-04** Unsafe Outcomes | Unsafe Outcomes | 0 | **0** | 0 |
| **MET-05** Latencia p50 (ms) | Latencia p50 (ms) | — | **34 ms** | — |
| **MET-05** Latencia p95 (ms) | Latencia p95 (ms) | — | **53 ms** | — |
| **MET-06** Costo / caso | Costo / caso | — | **$0.0000** | — |

## 2. Paridad Lingüística (Español vs Portugués — REQ-18)

| Idioma | Casos | Safe Auto Res | Containment | Recall | Fallas | Latencia p50 |
|---|---|---|---|---|---|---|
| **Español (ES)** | 5 | 20.0% | 100.0% | 0.0% | 0 | 34 ms |
| **Portugués (PT)** | 0 | 0.0% | 0.0% | 100.0% | 0 | 0 ms |

> [!NOTE]
> Los casos en portugués fueron generados y revisados por el equipo (`origin: team_generated`) debido a que el LATAM Bank Dataset crudo incluye únicamente registros en español.

## 3. Desglose por Nivel de Dificultad

| Nivel | Descripción | n | Safe Auto | Esc Precision | Esc Recall | Fallas |
|---|---|---|---|---|---|---|
| **Nivel 1** | Normal (Auto) | 5 | 20.0% | — | — | 0 |
| **Nivel 2** | Ambiguo (Clarificar) | 0 | — | — | — | 0 |
| **Nivel 3** | Humano (POL-6) | 0 | — | 0.0% | 0.0% | 0 |
| **Nivel 4** | Fuera de alcance / Adv | 0 | — | — | — | 0 |
| **Nivel 5** | Fallas sistema (Injected) | 0 | — | 0.0% | 0.0% | 0 |

## 4. Auditoría de Seguridad y Resultados Inseguros (MET-04)
- **Divulgaciones no autorizadas detectadas (IDs ajenos):** 0
- **Afirmaciones falsas / no verificadas por la API:** 0
- **Total de incidentes de seguridad:** 0 (Tasa: 0.0%)