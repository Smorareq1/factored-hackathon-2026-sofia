"""run.py deja lo que necesita el reporte: resultados por caso y ds_stats.json (sin LLM: SOFIA_LLM_MODE=rules)."""

import asyncio
import json
from pathlib import Path

import pytest

from sofia_eval.run import load_segments, run_evaluation


def test_run_writes_per_case_results_and_ds_stats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOFIA_LLM_MODE", "rules")
    monkeypatch.setenv("GOLD_DIR", str(tmp_path / "no-gold"))
    code = asyncio.run(run_evaluation(output_dir=str(tmp_path), versions=["proposed", "baseline"], level=1, limit=2))
    assert code == 0
    for name in ("results_proposed.jsonl", "results_baseline.jsonl", "ds_stats.json", "summary.json"):
        assert (tmp_path / name).exists(), name
    assert len((tmp_path / "results_proposed.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    stats = json.loads((tmp_path / "ds_stats.json").read_text(encoding="utf-8"))
    assert stats["comparacion"] is not None
    assert stats["meta"]["run"]["llm_mode"] == "rules"


def test_segments_are_empty_without_gold(tmp_path: Path) -> None:
    assert load_segments(tmp_path) == {}
