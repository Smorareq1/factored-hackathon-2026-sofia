"""merge_runs: batches become one ds_stats.json, rate-limited runs are left out, repeated runs keep variability."""

import asyncio
import json
from pathlib import Path

import pytest

from sofia_eval.merge_runs import merge, read_results
from sofia_eval.run import run_evaluation


def _run(out: Path, level: int) -> None:
    code = asyncio.run(run_evaluation(output_dir=str(out), versions=["proposed", "baseline"], level=level, limit=2))
    assert code == 0


@pytest.fixture
def batches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    monkeypatch.setenv("SOFIA_LLM_MODE", "rules")
    monkeypatch.setenv("GOLD_DIR", str(tmp_path / "no-gold"))
    a, b = tmp_path / "batch-1", tmp_path / "batch-2"
    _run(a, level=1)
    _run(b, level=3)
    return a, b


def _mark_first_rate_limited(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["errors"] = ["turn 1: llm_unavailable:429_resource_exhausted"]
    lines[0] = json.dumps(first)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return first["case_id"]


def test_batches_merge_into_one_ds_stats(batches: tuple[Path, Path], tmp_path: Path) -> None:
    a, b = batches
    stats = merge([a, b], tmp_path / "merged", gold_dir=tmp_path / "no-gold")
    assert stats["proposed"]["n"] == 4  # 2 cases from each batch
    assert stats["meta"]["merge"]["mode"] == "batches"
    assert (tmp_path / "merged" / "ds_stats.json").exists()
    assert len(read_results(tmp_path / "merged" / "results_proposed.jsonl")) == 4


def test_rate_limited_results_are_left_out_and_pruned(batches: tuple[Path, Path], tmp_path: Path) -> None:
    a, b = batches
    limited = _mark_first_rate_limited(a / "results_proposed.jsonl")
    stats = merge([a, b], tmp_path / "merged", gold_dir=tmp_path / "no-gold", prune=True)
    assert stats["meta"]["merge"]["rate_limited"]["proposed"] == []  # pruned before collecting
    assert limited not in {r.case_id for r in read_results(a / "results_proposed.jsonl")}  # resume will re-run it
    assert stats["proposed"]["n"] == 3


def test_repeated_runs_keep_every_run_and_report_variability(batches: tuple[Path, Path], tmp_path: Path) -> None:
    a, _ = batches
    stats = merge([a, a], tmp_path / "merged", gold_dir=tmp_path / "no-gold", repeated=True)
    assert len(read_results(tmp_path / "merged" / "results_proposed.jsonl")) == 4  # 2 cases × 2 runs
    runs = stats["variabilidad"]["proposed"]["runs"]
    assert len(runs) == 2
    assert stats["variabilidad"]["proposed"]["met01_range"][0] <= stats["variabilidad"]["proposed"]["met01_range"][1]
