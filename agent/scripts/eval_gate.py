"""Gate de regresión (LEARN): corre el set dev con propuesto y baseline, escribe el reporte y compara.

Uso (dentro del contenedor del agente, desde agent/):
    python scripts/eval_gate.py                       # corre y compara contra evals/reference.<modo>.json
    python scripts/eval_gate.py --accept              # acepta esta corrida como nueva referencia
    python scripts/eval_gate.py --systems proposed    # sin baseline (sin LLM el baseline no corre)
    python scripts/eval_gate.py --only DEV-ES-001 DEV-PT-002

Un prompt o una versión de PURPOSE nuevos se promueven solo si MET-01 no baja y MET-04 no sube. El set es el
**dev** (nunca el held-out de test). Hay una referencia por modo (`rules` y `gemini`): nunca se compara una
corrida con LLM contra una sin LLM. Para corridas reproducibles: GEMINI_FALLBACK_MODELS=none.
Sale con código 1 si el gate falla.
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sofia_agent.config import get_settings
from sofia_agent.evaluation import Evaluation, gate, load_cases, render_report
from sofia_agent.runner import Harness

HERE = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", type=Path, default=HERE / "evals" / "dev_cases.jsonl")
    parser.add_argument("--systems", default="proposed,baseline")
    parser.add_argument("--reference", type=Path, help="por defecto evals/reference.<rules|gemini>.json")
    parser.add_argument("--out", type=Path, default=HERE / "evals" / "reports")
    parser.add_argument("--only", nargs="*", help="case_id a correr (por defecto, todos)")
    parser.add_argument("--accept", action="store_true", help="guarda esta corrida como referencia")
    args = parser.parse_args()

    settings = get_settings()
    mode = "gemini" if settings.use_gemini else "rules"
    reference_path = args.reference or HERE / "evals" / f"reference.{mode}.json"
    cases = load_cases(args.cases)
    if args.only:
        cases = [case for case in cases if case.case_id in set(args.only)]
    async with Harness.open(settings) as harness:
        systems = [s for s in args.systems.split(",") if s == "proposed" or harness.baseline is not None]
        if "baseline" in args.systems and "baseline" not in systems:
            print("baseline omitido: necesita Gemini (SOFIA_LLM_MODE=rules o sin GEMINI_API_KEY)", file=sys.stderr)
        results = await harness.run_many(cases, systems)  # type: ignore[arg-type]
        models = ", ".join(settings.gemini_models) if settings.use_gemini else "rules (sin LLM)"
        context = {
            "Fecha": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "Casos": f"{len(cases)} ({args.cases.name}, origin team_generated)",
            "Sistemas": ", ".join(systems),
            "Modelo (cadena)": models,
            "prompt_version": harness.prompts.version,
            "purpose_version": harness.purpose.purpose_version,
            "Banco": "falso en proceso" if settings.bank_api_url == "fake" else settings.bank_api_url,
            "Precio supuesto": (
                f"USD {settings.gemini_price_in_per_mtok}/M tokens de entrada, "
                f"{settings.gemini_price_out_per_mtok}/M de salida"
            ),
        }
        prompt_version = harness.prompts.version

    evaluation = Evaluation.build(cases, results)
    summary = evaluation.summary()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{stamp}-results.jsonl").write_text(
        "".join(r.model_dump_json() + "\n" for r in results), encoding="utf-8"
    )
    snapshot = {"prompt_version": prompt_version, "created_at": stamp, "context": context, **summary}
    (args.out / f"{stamp}-summary.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report = render_report(evaluation, title="Evaluación del set dev: propuesto vs baseline", context=context)
    (args.out / f"{stamp}-report.md").write_text(report, encoding="utf-8")
    (args.out / "latest-report.md").write_text(report, encoding="utf-8")

    reference = json.loads(reference_path.read_text(encoding="utf-8")) if reference_path.exists() else None
    passed, reasons = gate(summary, reference)
    for system, cuts in summary.items():
        o = cuts["overall"]
        print(
            f"{system:9} n={o['n']} ruta={o['route_accuracy']:.0%} MET-01={o['met01_safe_automated_resolution']:.0%} "
            f"MET-02={o['met02_containment']:.0%} MET-04={o['met04_unsafe_cases']} "
            f"p50={o['met05_latency_p50_ms']}ms costo/caso=${o['met06_cost_per_case_usd'] or 0:.5f}"
        )
    print(f"Reporte: {args.out / 'latest-report.md'}")
    print(("✓ GATE OK: " if passed else "✗ GATE FALLA: ") + "; ".join(reasons))
    if args.accept:
        reference_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Referencia actualizada: {reference_path}")
        return 0
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
