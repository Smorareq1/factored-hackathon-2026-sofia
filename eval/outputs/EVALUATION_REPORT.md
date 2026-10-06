# Reporte de Evaluación — Proyecto S.O.F.I.A.

Evaluación rigurosa del sistema propuesto vs baseline según §6 (MET-01..MET-06).

## 1. Resumen Ejecutivo (Baseline vs Propuesto)

| Métrica | Definición | Baseline | Propuesto (S.O.F.I.A.) | Variación |
|---|---|---|---|---|
| **MET-01** Safe Auto Resolution | Safe Auto Resolution | 13.3% | **5.0%** | -8.3% |
| **MET-02** Containment | Containment | 97.5% | **82.0%** | -15.5% |
| **MET-03** Escalation Precision | Escalation Precision | 100.0% | **100.0%** | 0.0% |
| **MET-03** Escalation Recall | Escalation Recall | 8.1% | **58.1%** | +50.0% |
| **MET-03** Handoff Completeness | Handoff Completeness | 25.0% | **60.4%** | +35.4% |
| **MET-04** Unsafe Outcomes | Unsafe Outcomes | 0 | **0** | 0 |
| **MET-05** Latencia p50 (ms) | Latencia p50 (ms) | 556 ms | **216 ms** | — |
| **MET-05** Latencia p95 (ms) | Latencia p95 (ms) | 5199 ms | **11415 ms** | — |
| **MET-06** Costo / caso | Costo / caso | $0.0004 | **$0.0004** | — |

## 2. Paridad Lingüística (Español vs Portugués — REQ-18)

| Idioma | Casos | Safe Auto Res | Containment | Recall | Fallas | Latencia p50 |
|---|---|---|---|---|---|---|
| **Español (ES)** | 100 | 6.7% | 80.0% | 64.5% | 0 | 221 ms |
| **Portugués (PT)** | 100 | 3.3% | 84.0% | 51.6% | 0 | 212 ms |

> [!NOTE]
> Los casos en portugués fueron generados y revisados por el equipo (`origin: team_generated`) debido a que el LATAM Bank Dataset crudo incluye únicamente registros en español.

## 3. Desglose por Nivel de Dificultad

| Nivel | Descripción | n | Safe Auto | Esc Precision | Esc Recall | Fallas |
|---|---|---|---|---|---|---|
| **Nivel 1** | Normal (Auto) | 60 | 5.0% | — | — | 0 |
| **Nivel 2** | Ambiguo (Clarificar) | 40 | — | — | — | 0 |
| **Nivel 3** | Humano (POL-6) | 40 | — | 100.0% | 80.0% | 0 |
| **Nivel 4** | Fuera de alcance / Adv | 30 | — | — | — | 0 |
| **Nivel 5** | Fallas sistema (Injected) | 30 | — | 100.0% | 18.2% | 0 |

## 4. Auditoría de Seguridad y Resultados Inseguros (MET-04)
- **Divulgaciones no autorizadas detectadas (IDs ajenos):** 0
- **Afirmaciones falsas / no verificadas por la API:** 0
- **Total de incidentes de seguridad:** 0 (Tasa: 0.0%)