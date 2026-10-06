"""Merge harness outputs into one `ds_stats.json` (DS).

    # one run split into batches (different sessions, machines or output dirs): one result per case and system
    python -m sofia_eval.merge_runs eval/outputs/batch-1 eval/outputs/batch-2 --output-dir eval/outputs/merged

    # repeated full runs (§6 variability): every run is kept, plus the MET-01/MET-04 range across runs
    python -m sofia_eval.merge_runs eval/outputs/run-1 eval/outputs/run-2 eval/outputs/run-3 --repeated \
        --output-dir eval/outputs/merged

Each input dir holds `results_proposed.jsonl` / `results_baseline.jsonl` as written by `run.py`. A conversation that
failed because of the provider's rate limit (a 429 / RESOURCE_EXHAUSTED in `errors`, or a proposed-system rules
fallback caused by one; see `quota.py`) is a quota event, not a system failure: it is left out and listed in
`meta.merge.rate_limited`. With `--prune`, those lines are also removed from the input files, so `run.py`'s resume runs
those cases again.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from sofia_contracts.eval_case import ConversationResult, EvalCase
from sofia_eval.ds_stats import build_ds_stats, save_ds_stats
from sofia_eval.levels import load_cases_from_dir
from sofia_eval.metrics import calculate_metrics
from sofia_eval.quota import is_rate_limited
from sofia_eval.run import load_segments

log = logging.getLogger("sofia_eval.merge_runs")

VERSIONS = ("proposed", "baseline")

def read_results(path: Path) -> list[ConversationResult]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [ConversationResult.model_validate_json(line) for line in f if line.strip()]


def prune_rate_limited(path: Path) -> int:
    """Rewrite a results file without its rate-limited conversations; returns how many were removed."""
    results = read_results(path)
    kept = [r for r in results if not is_rate_limited(r)]
    if len(kept) != len(results):
        path.write_text("".join(r.model_dump_json() + "\n" for r in kept), encoding="utf-8")
    return len(results) - len(kept)


def collect(dirs: list[Path], version: str, repeated: bool) -> tuple[list[ConversationResult], list[str], list[list]]:
    """Results of one system across input dirs.

    Batches: one result per case (the last dir wins). Repeated runs: all results are kept (ds_stats groups them by
    case for the bootstrap). Also returns the rate-limited case ids and the per-dir results (for variability).
    """
    by_case: dict[str, ConversationResult] = {}
    pooled: list[ConversationResult] = []
    per_dir: list[list[ConversationResult]] = []
    rate_limited: list[str] = []
    for d in dirs:
        usable = []
        for r in read_results(d / f"results_{version}.jsonl"):
            if is_rate_limited(r):
                rate_limited.append(f"{d.name}:{r.case_id}")
                continue
            usable.append(r)
            by_case[r.case_id] = r
        pooled.extend(usable)
        per_dir.append(usable)
    return (pooled if repeated else list(by_case.values())), rate_limited, per_dir


def variability(cases: list[EvalCase], per_dir: list[list[ConversationResult]], names: list[str]) -> dict[str, Any]:
    """MET-01 rate and MET-04 count per run, and their range (report §5.3)."""
    runs = []
    for name, results in zip(names, per_dir, strict=True):
        if not results:
            continue
        s = calculate_metrics(cases, results)
        runs.append({
            "run": name,
            "n": s.total_cases,
            "met01_safe_auto_resolution": s.safe_auto_resolution_rate,
            "met04_unsafe_outcomes": s.unsafe_outcomes_total,
        })
    if not runs:
        return {"runs": []}
    met01 = [r["met01_safe_auto_resolution"] for r in runs]
    met04 = [r["met04_unsafe_outcomes"] for r in runs]
    return {"runs": runs, "met01_range": [min(met01), max(met01)], "met04_range": [min(met04), max(met04)]}


def merge(
    dirs: list[Path],
    output_dir: Path,
    cases_dir: Path = Path("eval/cases"),
    repeated: bool = False,
    prune: bool = False,
    gold_dir: Path = Path("data/gold"),
) -> dict[str, Any]:
    if prune:
        removed = {f"{d.name}/{v}": prune_rate_limited(d / f"results_{v}.jsonl") for d in dirs for v in VERSIONS}
        log.info("pruned rate-limited conversations: %s", {k: n for k, n in removed.items() if n})

    all_cases = {c.case_id: c for c in load_cases_from_dir(cases_dir)}
    merged, rate_limited, per_dir = {}, {}, {}
    for v in VERSIONS:
        merged[v], rate_limited[v], per_dir[v] = collect(dirs, v, repeated)

    if not merged["proposed"]:
        raise SystemExit(f"no proposed results in {[str(d) for d in dirs]}")
    unknown = sorted({r.case_id for r in merged["proposed"]} - set(all_cases))
    cases = [all_cases[cid] for cid in sorted({r.case_id for r in merged["proposed"]} & set(all_cases))]

    segments = load_segments(gold_dir)
    stats = build_ds_stats(cases, merged["proposed"], merged["baseline"] or None, segments=segments or None)
    stats["meta"]["merge"] = {
        "inputs": [str(d) for d in dirs],
        "mode": "repeated_runs" if repeated else "batches",
        "cases_in_catalog": len(all_cases),
        "cases_evaluated": len(cases),
        "missing_cases": sorted(set(all_cases) - {c.case_id for c in cases}),
        "unknown_case_ids": unknown,
        "results": {v: len(merged[v]) for v in VERSIONS},
        "rate_limited": rate_limited,
    }
    if repeated:
        names = [d.name for d in dirs]
        stats["variabilidad"] = {v: variability(cases, per_dir[v], names) for v in VERSIONS if merged[v]}

    output_dir.mkdir(parents=True, exist_ok=True)
    for v in VERSIONS:
        if merged[v]:
            (output_dir / f"results_{v}.jsonl").write_text(
                "".join(r.model_dump_json() + "\n" for r in merged[v]), encoding="utf-8"
            )
    log.info("merged ds_stats: %s", save_ds_stats(stats, output_dir))
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+", type=Path, help="harness output dirs (batches or repeated runs)")
    parser.add_argument("--output-dir", type=Path, default=Path("eval/outputs/merged"))
    parser.add_argument("--cases-dir", type=Path, default=Path("eval/cases"))
    parser.add_argument("--repeated", action="store_true", help="inputs are repeated full runs: keep every run")
    parser.add_argument("--prune", action="store_true", help="remove rate-limited lines from the inputs (re-run them)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    stats = merge(args.dirs, args.output_dir, args.cases_dir, repeated=args.repeated, prune=args.prune)
    meta = stats["meta"]["merge"]
    print(json.dumps({k: meta[k] for k in ("mode", "cases_in_catalog", "cases_evaluated", "results")}, indent=2))
    missing, limited = meta["missing_cases"], sum(len(v) for v in meta["rate_limited"].values())
    if missing or limited:
        print(f"WARNING: {len(missing)} catalog cases without results, {limited} rate-limited conversations left out")


if __name__ == "__main__":
    main()
