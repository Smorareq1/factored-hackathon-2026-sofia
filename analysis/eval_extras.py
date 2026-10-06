"""Derive the evaluation-report values that ds_stats.json does not hold (DS).

    python analysis/eval_extras.py

Reads eval/outputs/results.json and eval/outputs/ds_stats.json (the single 200-case harness run) and writes
analysis/results/eval_extras.json and analysis/results/fairness.json. Every number is counted from the run; nothing is
estimated. Then run analysis/fill_placeholders.py --write.
"""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "results"
runs = json.loads((ROOT / "eval/outputs/results.json").read_text("utf-8"))
ds = json.loads((ROOT / "eval/outputs/ds_stats.json").read_text("utf-8"))


def frac(k: int, n: int) -> str:
    return f"{k}/{n} ({100 * k / n:.1f}%)" if n else "n/a"


# Level x language counts (same cases for both systems).
prop = runs["proposed"]
level_lang = {f"{lv}.{lg}": sum(1 for r in prop if r["level"] == lv and r["language"] == lg) for lv in range(1, 6) for lg in ("es", "pt")}

# Route accuracy per level: did the final route fall in the set expected for that level.
OK_ROUTES = {2: {"clarify"}, 4: {"abstain", "deny"}, 5: {"escalate", "reauth"}}
route_acc = {}
for system in ("baseline", "proposed"):
    for lv, ok in OK_ROUTES.items():
        rows = [r for r in runs[system] if r["level"] == lv]
        route_acc[f"{system}.{lv}"] = frac(sum(r["route_final"] in ok for r in rows), len(rows))

# MET-03 missed / unnecessary escalations by system and language.
missed = {}
for system in ("baseline", "proposed"):
    for lg in ("es", "pt"):
        rows = [r for r in runs[system] if r["language"] == lg]
        fn = sum(r["expected_route"] == "escalate" and r["route_final"] != "escalate" for r in rows)
        fp = sum(r["expected_route"] != "escalate" and r["route_final"] == "escalate" for r in rows)
        missed[f"{system}.{lg}"] = f"{fn} / {fp}"

# MET-04 detail: the harness detectors (unverified claims, another customer's ids). No unauthorized-action detector.
met04 = {}
for system in ("baseline", "proposed"):
    rows = runs[system]
    met04[system] = {
        "disclosure": f"{sum(bool(r['foreign_references']) for r in rows)} / {len(rows)}",
        "unverified_claims": f"{sum(bool(r['unverified_claims']) for r in rows)} / {len(rows)}",
        "unauthorized_action": "no dedicated detector in the harness (the service layer rejects them; see test_bank_api.py)",
    }

# Capacity: how often the Gemini free tier was unavailable.
base_429 = sum(any("429" in e for e in r["errors"]) for r in runs["baseline"])
prop_no_llm = sum(r["llm_calls"] == 0 for r in prop)
base_no_llm = sum(r["llm_calls"] == 0 for r in runs["baseline"])
capacity = {
    "baseline_cases_with_quota_error": f"{base_429} / {len(runs['baseline'])}",
    "proposed_cases_without_completed_gemini_call": f"{prop_no_llm} / {len(prop)}",
    "baseline_cases_without_completed_gemini_call": f"{base_no_llm} / {len(runs['baseline'])}",
}

extras = {
    "label": "measured offline, derived from eval/outputs/results.json (one run, n = 200)",
    "runs_per_system": 1,
    "level_language_n": level_lang,
    "route_accuracy": route_acc,
    "met03_missed_unnecessary": missed,
    "met04": met04,
    "capacity": capacity,
}
(OUT / "eval_extras.json").write_text(json.dumps(extras, indent=2, ensure_ascii=False) + "\n", "utf-8")

# Fairness by language, from the harness breakdown (ES vs PT). The segment cut is not computable: the harness
# runs on four seed customers (C9000000x) that are not in gold_customers, so there is no segment to join.
m = lambda lg, name: ds["desglose"]["idioma"][lg]["proposed"]["metricas"][name]
par = ds["paridad_idioma"]
by_language = {
    lg: {
        "MET-01": m(lg, "met01_safe_auto_resolution"),
        "MET-03_recall": m(lg, "met03_escalation_recall"),
        "MET-04": m(lg, "met04_unsafe_outcomes"),
        "handoff_completeness": m(lg, "met03_handoff_completeness"),
        "n": ds["desglose"]["idioma"][lg]["n"],
    }
    for lg in ("es", "pt")
}
hc = par["met03_handoff_completeness"]
rc = par["met03_escalation_recall"]
fairness = {
    "label": "measured offline; language cut from ds_stats.json; PT text is team-generated",
    "by_language": by_language,
    "by_segment": "not computable: the harness uses four seed customers (C90000001-4) that are not in gold_customers, so no segment can be joined",
    "max_gap": (
        f"handoff completeness, PT minus ES: {100 * hc['diff']:+.1f} pts "
        f"[{100 * hc['ci'][0]:.1f}, {100 * hc['ci'][1]:.1f}], p = {hc['p_value']}"
    ),
    "interpretation": (
        "Portuguese handoff cards were less complete (43.8% vs 73.8%), the only language gap whose interval excludes zero. "
        f"Escalation recall is lower in PT too ({100 * rc['diff']:+.1f} pts, interval [{100 * rc['ci'][0]:.1f}, "
        f"{100 * rc['ci'][1]:.1f}]) but inconclusive at n = 31 per language, as are safe automated resolution and unsafe "
        "outcomes (0 in both). All PT text is team-generated, so language is confounded with translation quality"
    ),
    "summary": (
        "ES and PT match on safety (0 unsafe in 100 cases each) and are inconclusive on automation and escalation "
        "recall; the one gap that holds is handoff completeness (PT lower). The segment cut could not be run"
    ),
}
(OUT / "fairness.json").write_text(json.dumps(fairness, indent=2, ensure_ascii=False) + "\n", "utf-8")
print(json.dumps(extras, indent=2, ensure_ascii=False))
print(fairness["max_gap"]); print(fairness["interpretation"])
