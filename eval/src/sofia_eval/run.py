"""Punto de entrada CLI para ejecutar la suite de evaluación (make eval, §6, §11 SIM).

Soporta ejecución por lotes (batches), control de rate-limiting (delay) y checkpoints
para permitir evaluar sets grandes (100–200+ casos) de forma segura en free tier.
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sofia_agent.runner import Harness
from sofia_contracts.eval_case import ConversationResult, EvalCase
from sofia_eval.ds_stats import build_ds_stats, save_ds_stats
from sofia_eval.levels import get_benchmark_cases, load_cases_from_dir, save_benchmark_cases
from sofia_eval.quota import is_rate_limited
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


def _git_sha() -> str:
    try:
        # Fixed argv, no user input: the run records which commit it measured.
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True  # noqa: S607
        ).stdout
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True  # noqa: S607
        )
        return sha.strip() + ("-dirty" if dirty.stdout.strip() else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_metadata(versions: list[str], n_cases: int) -> dict[str, object]:
    """Qué se corrió (§6: variabilidad por versión de modelo/prompt). Sin secretos."""
    return {
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "versions": versions,
        "n_cases": n_cases,
        "llm_mode": os.getenv("SOFIA_LLM_MODE", "auto"),
        "gemini_model": os.getenv("GEMINI_MODEL") or "default",
        "gemini_fallback_models": os.getenv("GEMINI_FALLBACK_MODELS") or "default",
        "git_sha": os.getenv("GIT_SHA") or _git_sha(),
    }


async def _run_version_batched(
    harness: Harness,
    cases: list[EvalCase],
    version: str,
    output_dir: Path,
    batch_size: int = 20,
    delay_s: float = 0.0,
    resume: bool = True,
) -> list[ConversationResult]:
    results_file = output_dir / f"results_{version}.jsonl"
    results: list[ConversationResult] = []

    if resume and results_file.exists():
        try:
            with results_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        results.append(ConversationResult.model_validate_json(line))
            logger.info("Reanudando versión '%s': %d casos ya evaluados.", version, len(results))
        except Exception as exc:
            logger.warning("Error leyendo checkpoint previo de %s: %s", results_file, exc)
            results = []

    # A checkpointed conversation that hit the quota did not measure the system: it runs again.
    limited = [r.case_id for r in results if is_rate_limited(r)]
    if limited:
        logger.warning("%s: %d casos del checkpoint con 429/fallback por cuota se re-ejecutan.", version, len(limited))
        results = [r for r in results if not is_rate_limited(r)]
    done_ids = {r.case_id for r in results}
    pending = [c for c in cases if c.case_id not in done_ids]

    logger.info("Ejecutando versión '%s': %d casos pendientes de %d.", version, len(pending), len(cases))

    for i, case in enumerate(pending, 1):
        res = await harness.run(case, version)
        results.append(res)

        if delay_s > 0 and i < len(pending):
            await asyncio.sleep(delay_s)

        if batch_size > 0 and (i % batch_size == 0 or i == len(pending)):
            save_results(results, results_file)
            logger.info("Checkpoint guardado (%d/%d casos) para %s.", len(results), len(cases), version)

    save_results(results, results_file)
    return results


async def run_evaluation(
    cases_dir: str = "eval/cases",
    output_dir: str = "eval/outputs",
    versions: list[str] | None = None,
    language: str | None = None,
    level: int | None = None,
    limit: int | None = None,
    batch_size: int = 20,
    delay: float = 0.0,
    resume: bool = True,
) -> int:
    versions = versions or ["proposed"]
    cases_path = Path(cases_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

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

    logger.info(
        "Cargados %d casos para evaluación. Versiones: %s | Batch size: %d | Delay: %.1fs | Resume: %s",
        len(cases),
        versions,
        batch_size,
        delay,
        resume,
    )
    meta = run_metadata(versions, len(cases))

    proposed_results: list[ConversationResult] = []
    baseline_results: list[ConversationResult] = []

    async with Harness.open() as harness:
        if "proposed" in versions:
            proposed_results = await _run_version_batched(
                harness, cases, "proposed", out, batch_size=batch_size, delay_s=delay, resume=resume
            )

        if "baseline" in versions:
            baseline_results = await _run_version_batched(
                harness, cases, "baseline", out, batch_size=batch_size, delay_s=delay, resume=resume
            )

    meta["rate_limited"] = {
        v: [r.case_id for r in rs if is_rate_limited(r)]
        for v, rs in (("proposed", proposed_results), ("baseline", baseline_results))
    }
    n_limited = sum(len(ids) for ids in meta["rate_limited"].values())
    if n_limited:
        logger.error(
            "%d conversaciones midieron la cuota del proveedor y no el sistema (meta.rate_limited). No publicar estas "
            "cifras: correr de nuevo con --resume (re-ejecuta solo esos casos) o filtrarlas con merge_runs.",
            n_limited,
        )

    md_report, summary = build_evaluation_report(
        cases,
        proposed_results,
        baseline_results if baseline_results else None,
    )

    md_file, json_file = save_reports(md_report, summary, output_dir)
    logger.info("Reportes generados exitosamente en:\n  - %s\n  - %s", md_file, json_file)

    # Exportar resultados individuales por caso (para DS y trazabilidad)
    case_map = {c.case_id: c for c in cases}
    results_path = out / "results.json"
    results_data = {
        "proposed": [
            {
                "case_id": r.case_id,
                "language": case_map[r.case_id].language if r.case_id in case_map else "es",
                "level": case_map[r.case_id].level if r.case_id in case_map else 1,
                "type": case_map[r.case_id].type if r.case_id in case_map else "normal",
                "session_customer_id": case_map[r.case_id].session_customer_id if r.case_id in case_map else "",
                "system_version": r.system_version,
                "route_final": r.route_final,
                "expected_route": case_map[r.case_id].expected_route if r.case_id in case_map else "",
                "latency_ms": r.latency_ms,
                "cost_usd": r.cost_usd or 0.0,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "llm_calls": r.llm_calls,
                "unverified_claims": r.unverified_claims,
                "foreign_references": r.foreign_references,
                "errors": r.errors,
                "llm_fallbacks": r.llm_fallbacks,
            }
            for r in proposed_results
        ],
        "baseline": [
            {
                "case_id": r.case_id,
                "language": case_map[r.case_id].language if r.case_id in case_map else "es",
                "level": case_map[r.case_id].level if r.case_id in case_map else 1,
                "type": case_map[r.case_id].type if r.case_id in case_map else "normal",
                "session_customer_id": case_map[r.case_id].session_customer_id if r.case_id in case_map else "",
                "system_version": r.system_version,
                "route_final": r.route_final,
                "expected_route": case_map[r.case_id].expected_route if r.case_id in case_map else "",
                "latency_ms": r.latency_ms,
                "cost_usd": r.cost_usd or 0.0,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "llm_calls": r.llm_calls,
                "unverified_claims": r.unverified_claims,
                "foreign_references": r.foreign_references,
                "errors": r.errors,
                "llm_fallbacks": r.llm_fallbacks,
            }
            for r in baseline_results
        ],
    }
    with results_path.open("w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)
    logger.info("Resultados detallados por caso guardados en: %s", results_path)

    # Integración con la capa estadística DS: resultados completos por caso (JSONL) y ds_stats.json con
    # segmentos (REQ-18) y metadatos de la corrida. Si falla, la evaluación no se cae.
    if proposed_results:
        try:
            segments = load_segments(Path(os.getenv("GOLD_DIR", "data/gold")))
            stats = build_ds_stats(cases, proposed_results, baseline_results or None, segments=segments or None)
            stats["meta"]["run"] = meta
            logger.info("Estadística DS (IC, baseline vs propuesto): %s", save_ds_stats(stats, out))
        except Exception as exc:
            logger.warning("No se pudo generar ds_stats.json: %s", exc)

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
        "--versions", default="proposed,baseline", help="Versiones a evaluar separadas por coma (proposed,baseline)"
    )
    parser.add_argument("--language", default=None, choices=["es", "pt"], help="Filtrar por idioma")
    parser.add_argument("--level", type=int, default=None, choices=[1, 2, 3, 4, 5], help="Filtrar por nivel")
    parser.add_argument("--limit", type=int, default=None, help="Límite máximo de casos")
    parser.add_argument("--batch-size", type=int, default=20, help="Tamaño de lote para checkpoints")
    parser.add_argument("--delay", type=float, default=0.0, help="Segundos de pausa entre casos (rate-limiting)")
    parser.add_argument("--no-resume", action="store_true", help="No reanudar desde checkpoint existente")

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
            batch_size=args.batch_size,
            delay=args.delay,
            resume=not args.no_resume,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
