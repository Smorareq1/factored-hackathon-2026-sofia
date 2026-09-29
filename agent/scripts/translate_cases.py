"""Traduce casos §9.5 de español a portugués con Gemini, con los IDs enmascarados.

Uso (dentro del contenedor del agente, desde agent/):
    python scripts/translate_cases.py evals/dev_cases.jsonl --out evals/dev_cases_pt.jsonl
    python scripts/translate_cases.py evals/dev_cases.jsonl --dry-run   # muestra lo que saldría, sin llamar

Solo traduce los casos en español. Los generados quedan `origin: team_generated` y con sufijo `-pt`; se revisan
a mano antes de usarlos en el reporte (§8.5).
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from sofia_agent.config import get_settings
from sofia_agent.evaluation import load_cases
from sofia_agent.llm import MIN_SERVER_DEADLINE_S, failure_reason
from sofia_agent.translate import (
    SYSTEM_PROMPT,
    Translation,
    TranslationError,
    check_translation,
    mask_ids,
    translated_case,
    unmask_ids,
)


async def translate(masked: list[str], models: list[tuple[str, object]], timeout_s: float) -> list[str]:
    payload = json.dumps({"turns": masked}, ensure_ascii=False)
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=payload)]
    last = "no_model"
    for name, runnable in models:
        try:
            result = await asyncio.wait_for(runnable.ainvoke(messages), timeout=timeout_s)  # type: ignore[attr-defined]
        except Exception as exc:  # 503/429/timeout → siguiente modelo de la cadena
            last = f"{name}:{failure_reason(exc)}"
            continue
        return result.turns
    raise TranslationError(f"ningún modelo respondió ({last})")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--out", type=Path, help="JSONL de salida (por defecto: <entrada>_pt.jsonl)")
    parser.add_argument("--dry-run", action="store_true", help="solo muestra el texto enmascarado")
    args = parser.parse_args()

    spanish = [case for case in load_cases(args.cases) if case.language == "es"]
    if args.dry_run:
        for case in spanish:
            masked, ids = mask_ids(case.turns)
            print(
                json.dumps({"case_id": case.case_id, "turns": masked, "ids_kept_local": len(ids)}, ensure_ascii=False)
            )
        return 0

    settings = get_settings()
    if settings.gemini_api_key is None:
        print("Falta GEMINI_API_KEY", file=sys.stderr)
        return 2
    from langchain_google_genai import ChatGoogleGenerativeAI

    models = [
        (
            name,
            ChatGoogleGenerativeAI(
                model=name,
                google_api_key=settings.gemini_api_key.get_secret_value(),
                temperature=0,
                max_retries=0,
                timeout=max(settings.llm_timeout_s, MIN_SERVER_DEADLINE_S),
            ).with_structured_output(Translation, method="json_schema"),
        )
        for name in settings.gemini_models
    ]
    out = args.out or args.cases.with_name(f"{args.cases.stem}_pt.jsonl")
    written, skipped = 0, 0
    with out.open("w", encoding="utf-8") as handle:
        for case in spanish:
            masked, ids = mask_ids(case.turns)
            try:
                translated = await translate(masked, models, settings.llm_timeout_s)
                check_translation(masked, translated)
                result = translated_case(case, unmask_ids(translated, ids))
            except TranslationError as exc:
                skipped += 1
                print(f"✗ {case.case_id}: {exc}", file=sys.stderr)
                continue
            handle.write(result.model_dump_json(exclude_defaults=True) + "\n")
            written += 1
            print(f"✓ {result.case_id}: {result.turns[0][:70]}")
    print(f"{written} casos traducidos → {out} ({skipped} descartados). Revisar a mano antes de usarlos.")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
