"""Punto de entrada CLI para ejecutar la suite de evaluación (make eval, §6, §11 SIM)."""

import argparse
import asyncio
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sofia_agent.runner import Harness
from sofia_contracts.eval_case import ConversationResult
from sofia_eval.ds_stats import build_ds_stats, save_ds_stats
from sofia_eval.levels import get_benchmark_cases, load_cases_from_dir, save_benchmark_cases
from sofia_eval.report import build_evaluation_report, save_reports

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sofia_eval.run")


def save_results(results: list[ConversationResult], path: Path) -> Path:
    """Resultados por caso (JSONL): insumo de ds_stats y de cualquier re-análisis sin volver a correr."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(r.model_dump_json() + "\n")
    return path


def load_segments(gold_dir: Path) -> dict[str, str]:
    """customer_id -> segmento desde gold_customers (REQ-18). Vacío si no hay gold."""
    path = gold_dir / "gold_customers.parquet"
    if not path.exists():
        return {}
    import polars as pl

    df = pl.read_parquet(path, columns=["customer_id", "segment"]).drop_nulls()
    return dict(zip(df["customer_id"].to_list(), df["segment"].to_list(), strict=True))


def run_metadata(versions: list[str], n_cases: int) -> dict[str, str | int | list[str]]:
    """Qué se corrió (§6: variabilidad por versión de modelo/prompt). Sin secretos."""
    return {
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "versions": versions,
        "n_cases": n_cases,
        "llm_mode": os.getenv("SOFIA_LLM_MODE", "auto"),
        "gemini_model": os.getenv("GEMINI_MODEL") or "default",
        "gemini_fallback_models": os.getenv("GEMINI_FALLBACK_MODELS") or "default",
        "git_sha": os.getenv("GIT_SHA", "unknown"),
    }


async def run_evaluation(
    cases_dir: str = "eval/cases",
    output_dir: str = "eval/outputs",
    versions: list[str] | None = None,
    language: str | None = None,
    level: int | None = None,
    limit: int | None = None,
) -> int:
    versions = versions or ["proposed"]
    cases_path = Path(cases_dir)

    # Si no existen los casos en disco, guardarlos
    if not (cases_path / "es" / "cases.jsonl").exists():
        save_benchmark_cases(cases_path)

    cases = load_cases_from_dir(cases_path)
    if not cases:
        cases = get_benchmark_cases()

    if language:
        cases = [c for c in cases if c.language == language]
    if level:
        cases = [c for c in cases if c.level == level]
    if limit:
        cases = cases[:limit]

    logger.info("Cargados %d casos para evaluación. Versiones: %s", len(cases), versions)
    meta = run_metadata(versions, len(cases))

    proposed_results: list[ConversationResult] = []
    baseline_results: list[ConversationResult] = []

    async with Harness.open() as harness:
        if "proposed" in versions:
            logger.info("Ejecutando sistema propuesto (S.O.F.I.A.)...")
            for c in cases:
                proposed_results.append(await harness.run(c, "proposed"))

        if "baseline" in versions:
            logger.info("Ejecutando sistema baseline...")
            for c in cases:
                baseline_results.append(await harness.run(c, "baseline"))

    md_report, summary = build_evaluation_report(
        cases,
        proposed_results,
        baseline_results if baseline_results else None,
    )

    md_file, json_file = save_reports(md_report, summary, output_dir)
    logger.info("Reportes generados exitosamente en:\n  - %s\n  - %s", md_file, json_file)

    out = Path(output_dir)
    for name, results in (("proposed", proposed_results), ("baseline", baseline_results)):
        if results:
            save_results(results, out / f"results_{name}.jsonl")
    if proposed_results:
        segments = load_segments(Path(os.getenv("GOLD_DIR", "data/gold")))
        stats = build_ds_stats(cases, proposed_results, baseline_results or None, segments=segments or None)
        stats["meta"]["run"] = meta
        logger.info("Estadística DS (IC, baseline vs propuesto): %s", save_ds_stats(stats, out))

    # Imprimir resumen en consola
    print("\n" + "=" * 70)
    print("RESUMEN DE EVALUACIÓN MET-01..MET-06 (S.O.F.I.A.)")
    print("=" * 70)
    prop = summary["proposed"]
    print(f"Total casos evaluados:          {prop['total_cases']}")
    print(f"Safe Auto Resolution (MET-01): {prop['safe_auto_resolution_rate'] * 100:.1f}%")
    print(f"Containment Rate (MET-02):     {prop['containment_rate'] * 100:.1f}%")
    print(f"Escalation Precision (MET-03): {prop['escalation_precision'] * 100:.1f}%")
    print(f"Escalation Recall (MET-03):    {prop['escalation_recall'] * 100:.1f}%")
    print(f"Handoff Completeness (MET-03): {prop['handoff_field_completeness'] * 100:.1f}%")
    uns_tot = prop["unsafe_outcomes_total"]
    uns_rate = prop["unsafe_outcomes_rate"] * 100
    print(f"Unsafe Outcomes (MET-04):      {uns_tot} (tasa: {uns_rate:.1f}%)")
    print(f"Latencia p50 / p95 (MET-05):   {prop['latency_p50_ms']:.0f} ms / {prop['latency_p95_ms']:.0f} ms")
    print(f"Costo total (MET-06):          ${prop['total_cost_usd']:.4f} USD")
    print("=" * 70 + "\n")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Harness de evaluación S.O.F.I.A. (SIM + DS)")
    parser.add_argument("--cases-dir", default="eval/cases", help="Directorio con casos JSONL")
    parser.add_argument("--output-dir", default="eval/outputs", help="Directorio de salida para reportes")
    parser.add_argument(
        "--versions", default="proposed", help="Versiones a evaluar separadas por coma (proposed,baseline)"
    )
    parser.add_argument("--language", default=None, choices=["es", "pt"], help="Filtrar por idioma")
    parser.add_argument("--level", type=int, default=None, choices=[1, 2, 3, 4, 5], help="Filtrar por nivel")
    parser.add_argument("--limit", type=int, default=None, help="Límite máximo de casos")

    args = parser.parse_args()
    versions = [v.strip() for v in args.versions.split(",") if v.strip()]

    exit_code = asyncio.run(
        run_evaluation(
            cases_dir=args.cases_dir,
            output_dir=args.output_dir,
            versions=versions,
            language=args.language,
            level=args.level,
            limit=args.limit,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
