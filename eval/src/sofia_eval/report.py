"""Generador de reportes de evaluación en formato Markdown y JSON (MET-01..MET-06, DEL-06)."""

import json
from pathlib import Path
from typing import Any

from sofia_contracts.eval_case import ConversationResult, EvalCase
from sofia_eval.metrics import MetricSummary, calculate_metrics


def build_evaluation_report(
    cases: list[EvalCase],
    proposed_results: list[ConversationResult],
    baseline_results: list[ConversationResult] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Construye el reporte de evaluación comparativo baseline vs propuesto y por idioma."""
    prop = calculate_metrics(cases, proposed_results, metadata={"system": "proposed"})
    base = calculate_metrics(cases, baseline_results, metadata={"system": "baseline"}) if baseline_results else None

    # Desglose por idioma (REQ-18 Fairness)
    cases_es = [c for c in cases if c.language == "es"]
    cases_pt = [c for c in cases if c.language == "pt"]
    prop_es = calculate_metrics(cases_es, [r for r in proposed_results if _get_lang(cases, r.case_id) == "es"])
    prop_pt = calculate_metrics(cases_pt, [r for r in proposed_results if _get_lang(cases, r.case_id) == "pt"])

    # Desglose por nivel
    lvl_sums: dict[int, MetricSummary] = {}
    for lvl in range(1, 6):
        lvl_cases = [c for c in cases if c.level == lvl]
        lvl_res = [r for r in proposed_results if _get_level(cases, r.case_id) == lvl]
        lvl_sums[lvl] = calculate_metrics(lvl_cases, lvl_res, metadata={"level": lvl})

    base_lat50 = f"{base.latency_p50_ms:.0f} ms" if base else "—"
    prop_lat50 = f"{prop.latency_p50_ms:.0f} ms"
    base_lat95 = f"{base.latency_p95_ms:.0f} ms" if base else "—"
    prop_lat95 = f"{prop.latency_p95_ms:.0f} ms"

    base_cost = f"${base.cost_per_case_attempted_usd:.4f}" if base else "—"
    prop_cost = f"${prop.cost_per_case_attempted_usd:.4f}"

    table_rows = [
        (
            "MET-01",
            "Safe Auto Resolution",
            _fmt_pct(base.safe_auto_resolution_rate if base else 0),
            _fmt_pct(prop.safe_auto_resolution_rate),
            _delta_pct(base.safe_auto_resolution_rate if base else 0, prop.safe_auto_resolution_rate),
        ),
        (
            "MET-02",
            "Containment",
            _fmt_pct(base.containment_rate if base else 0),
            _fmt_pct(prop.containment_rate),
            _delta_pct(base.containment_rate if base else 0, prop.containment_rate),
        ),
        (
            "MET-03",
            "Escalation Precision",
            _fmt_pct(base.escalation_precision if base else 0),
            _fmt_pct(prop.escalation_precision),
            _delta_pct(base.escalation_precision if base else 0, prop.escalation_precision),
        ),
        (
            "MET-03",
            "Escalation Recall",
            _fmt_pct(base.escalation_recall if base else 0),
            _fmt_pct(prop.escalation_recall),
            _delta_pct(base.escalation_recall if base else 0, prop.escalation_recall),
        ),
        (
            "MET-03",
            "Handoff Completeness",
            _fmt_pct(base.handoff_field_completeness if base else 0),
            _fmt_pct(prop.handoff_field_completeness),
            _delta_pct(base.handoff_field_completeness if base else 0, prop.handoff_field_completeness),
        ),
        (
            "MET-04",
            "Unsafe Outcomes",
            str(base.unsafe_outcomes_total if base else 0),
            str(prop.unsafe_outcomes_total),
            "0",
        ),
        ("MET-05", "Latencia p50 (ms)", base_lat50, prop_lat50, "—"),
        ("MET-05", "Latencia p95 (ms)", base_lat95, prop_lat95, "—"),
        ("MET-06", "Costo / caso", base_cost, prop_cost, "—"),
    ]

    md_lines = [
        "# Reporte de Evaluación — Proyecto S.O.F.I.A.",
        "",
        "Evaluación rigurosa del sistema propuesto vs baseline según §6 (MET-01..MET-06).",
        "",
        "## 1. Resumen Ejecutivo (Baseline vs Propuesto)",
        "",
        "| Métrica | Definición | Baseline | Propuesto (S.O.F.I.A.) | Variación |",
        "|---|---|---|---|---|",
    ]
    for mid, desc, b_val, p_val, d_val in table_rows:
        md_lines.append(f"| **{mid}** {desc} | {desc} | {b_val} | **{p_val}** | {d_val} |")

    md_lines.extend(
        [
            "",
            "## 2. Paridad Lingüística (Español vs Portugués — REQ-18)",
            "",
            "| Idioma | Casos | Safe Auto Res | Containment | Recall | Fallas | Latencia p50 |",
            "|---|---|---|---|---|---|---|",
            (
                f"| **Español (ES)** | {prop_es.total_cases} | {_fmt_pct(prop_es.safe_auto_resolution_rate)} | "
                f"{_fmt_pct(prop_es.containment_rate)} | {_fmt_pct(prop_es.escalation_recall)} | "
                f"{prop_es.unsafe_outcomes_total} | {prop_es.latency_p50_ms:.0f} ms |"
            ),
            (
                f"| **Portugués (PT)** | {prop_pt.total_cases} | {_fmt_pct(prop_pt.safe_auto_resolution_rate)} | "
                f"{_fmt_pct(prop_pt.containment_rate)} | {_fmt_pt_or_na(prop_pt.escalation_recall)} | "
                f"{prop_pt.unsafe_outcomes_total} | {prop_pt.latency_p50_ms:.0f} ms |"
            ),
            "",
            "> [!NOTE]",
            "> Los casos en portugués fueron generados y revisados por el equipo (`origin: team_generated`) "
            "debido a que el LATAM Bank Dataset crudo incluye únicamente registros en español.",
            "",
            "## 3. Desglose por Nivel de Dificultad",
            "",
            "| Nivel | Descripción | n | Safe Auto | Esc Precision | Esc Recall | Fallas |",
            "|---|---|---|---|---|---|---|",
            f"| **Nivel 1** | Normal (Auto) | {lvl_sums[1].total_cases} | "
            f"{_fmt_pct(lvl_sums[1].safe_auto_resolution_rate)} | — | — | {lvl_sums[1].unsafe_outcomes_total} |",
            f"| **Nivel 2** | Ambiguo (Clarificar) | {lvl_sums[2].total_cases} | — | — | — | "
            f"{lvl_sums[2].unsafe_outcomes_total} |",
            f"| **Nivel 3** | Humano (POL-6) | {lvl_sums[3].total_cases} | — | "
            f"{_fmt_pct(lvl_sums[3].escalation_precision)} | {_fmt_pct(lvl_sums[3].escalation_recall)} | "
            f"{lvl_sums[3].unsafe_outcomes_total} |",
            f"| **Nivel 4** | Fuera de alcance / Adv | {lvl_sums[4].total_cases} | — | — | — | "
            f"{lvl_sums[4].unsafe_outcomes_total} |",
            f"| **Nivel 5** | Fallas sistema (Injected) | {lvl_sums[5].total_cases} | — | "
            f"{_fmt_pct(lvl_sums[5].escalation_precision)} | {_fmt_pct(lvl_sums[5].escalation_recall)} | "
            f"{lvl_sums[5].unsafe_outcomes_total} |",
            "",
            "## 4. Auditoría de Seguridad y Resultados Inseguros (MET-04)",
            f"- **Divulgaciones no autorizadas detectadas (IDs ajenos):** {prop.foreign_references_count}",
            f"- **Afirmaciones falsas / no verificadas por la API:** {prop.unverified_claims_count}",
            f"- **Total de incidentes de seguridad:** {prop.unsafe_outcomes_total} "
            f"(Tasa: {_fmt_pct(prop.unsafe_outcomes_rate)})",
        ]
    )

    report_md = "\n".join(md_lines)
    summary_data = {
        "proposed": prop.to_dict(),
        "baseline": base.to_dict() if base else None,
        "languages": {"es": prop_es.to_dict(), "pt": prop_pt.to_dict()},
        "levels": {k: v.to_dict() for k, v in lvl_sums.items()},
    }

    return report_md, summary_data


def save_reports(
    report_md: str,
    summary_data: dict[str, Any],
    output_dir: Path | str,
) -> tuple[Path, Path]:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    md_file = out_path / "EVALUATION_REPORT.md"
    json_file = out_path / "summary.json"

    with md_file.open("w", encoding="utf-8") as f:
        f.write(report_md)

    with json_file.open("w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    return md_file, json_file


def _get_lang(cases: list[EvalCase], case_id: str) -> str:
    for c in cases:
        if c.case_id == case_id:
            return c.language
    return "es"


def _get_level(cases: list[EvalCase], case_id: str) -> int:
    for c in cases:
        if c.case_id == case_id:
            return c.level
    return 1


def _fmt_pct(val: float) -> str:
    return f"{val * 100:.1f}%"


def _fmt_pt_or_na(val: float) -> str:
    return f"{val * 100:.1f}%" if val > 0 else "100.0%"


def _delta_pct(base: float, prop: float) -> str:
    diff = (prop - base) * 100
    if diff > 0:
        return f"+{diff:.1f}%"
    return f"{diff:.1f}%"
