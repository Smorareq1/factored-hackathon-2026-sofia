"""Organización y catálogo de casos de evaluación por niveles de dificultad (§8.8, §9.5, §11 SIM).

Niveles:
- Nivel 1: Normal (30%) - resoluciones automatizadas policy-compliant (POL-5, monto bajo, aprobado).
- Nivel 2: Ambiguo (20%) - faltan datos (comercio, fecha), clarificación requerida.
- Nivel 3: Requiere humano (20%) - monto alto (> U), sospecha de fraude, cliente reincidente (POL-6).
- Nivel 4: Fuera de alcance y Adversarial (15%) - prompt injection, acceso a datos ajenos, productos no soportados.
- Nivel 5: Fallas de sistema (15%) - tool 500, sesión expirada, falla de persistencia (drop_writes).
"""

import json
from pathlib import Path

from sofia_contracts.common import Language
from sofia_contracts.eval_case import EvalCase
from sofia_eval.generator import generate_benchmark_cases

BENCHMARK_CASES: list[EvalCase] = generate_benchmark_cases()


def get_benchmark_cases(
    language: Language | None = None,
    level: int | None = None,
) -> list[EvalCase]:
    cases = list(BENCHMARK_CASES)
    if language:
        cases = [c for c in cases if c.language == language]
    if level:
        cases = [c for c in cases if c.level == level]
    return cases


def save_benchmark_cases(base_dir: Path | str) -> None:
    """Exporta los casos a eval/cases/es/ y eval/cases/pt/ en formato JSONL."""
    base_path = Path(base_dir)
    es_dir = base_path / "es"
    pt_dir = base_path / "pt"
    es_dir.mkdir(parents=True, exist_ok=True)
    pt_dir.mkdir(parents=True, exist_ok=True)

    es_cases = [c for c in BENCHMARK_CASES if c.language == "es"]
    pt_cases = [c for c in BENCHMARK_CASES if c.language == "pt"]

    with (es_dir / "cases.jsonl").open("w", encoding="utf-8") as f:
        for c in es_cases:
            f.write(c.model_dump_json() + "\n")

    with (pt_dir / "cases.jsonl").open("w", encoding="utf-8") as f:
        for c in pt_cases:
            f.write(c.model_dump_json() + "\n")


def load_cases_from_dir(base_dir: Path | str) -> list[EvalCase]:
    base_path = Path(base_dir)
    cases: list[EvalCase] = []
    for jsonl_file in base_path.glob("**/*.jsonl"):
        with jsonl_file.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    cases.append(EvalCase.model_validate(json.loads(line)))
    return cases or list(BENCHMARK_CASES)
