"""Evaluación del router (§8.6): macro-F1, recall de needs_human (el error más caro), matriz de confusión,
desglose por idioma; reglas (baseline) vs modelo entrenado sobre el mismo test held-out.

Los reportes son agregados (sin textos) y se versionan en `ml/reports/` como evidencia de REQ-13.
"""

import json
from collections.abc import Callable
from pathlib import Path

from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score

from sofia_contracts.common import Language
from sofia_contracts.router import IntentPrediction
from sofia_ml.labeling import INTENTS, ML_DIR, LabeledExample

REPORTS_DIR = ML_DIR / "reports"
Predictor = Callable[[str, Language | None], IntentPrediction]


def score(y_true: list[str], y_pred: list[str]) -> dict:
    labels = list(INTENTS)
    return {
        "n": len(y_true),
        "accuracy": round(accuracy_score(y_true, y_pred), 3),
        "macro_f1": round(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0), 3),
        "needs_human_recall": round(
            recall_score(y_true, y_pred, labels=["needs_human"], average="macro", zero_division=0), 3
        ),
        "f1_per_class": {
            label: round(v, 3)
            for label, v in zip(
                labels, f1_score(y_true, y_pred, labels=labels, average=None, zero_division=0), strict=True
            )
        },
        "confusion": {"labels": labels, "matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist()},
    }


def evaluate(test: list[LabeledExample], predict: Predictor, use_language_hint: bool = False) -> dict:
    preds = [predict(e.text, e.language if use_language_hint else None) for e in test]
    y_true = [e.label for e in test]
    y_pred = [p.intent for p in preds]
    result = score(y_true, y_pred)
    hits = sum(p.language == e.language for p, e in zip(preds, test, strict=True))
    result["language_accuracy"] = round(hits / len(test), 3)
    result["by_language"] = {
        lang: score([t for t, e in zip(y_true, test, strict=True) if e.language == lang],
                    [p for p, e in zip(y_pred, test, strict=True) if e.language == lang])
        for lang in sorted({e.language for e in test})
    }
    return result


def compare(test: list[LabeledExample], predictors: dict[str, Predictor], split_info: dict | None = None) -> dict:
    return {"split": split_info or {}, "systems": {name: evaluate(test, fn) for name, fn in predictors.items()}}


def write_report(report: dict, name: str = "router_eval", out_dir: Path = REPORTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = out_dir / f"{name}.md"
    md.write_text(to_markdown(report), encoding="utf-8")
    return md


def to_markdown(report: dict) -> str:
    lines = [
        "# Router: baseline vs proposed (REQ-13)",
        "",
        f"Split: `{json.dumps(report['split'], ensure_ascii=False)}`",
        "",
        f"Served: `{report.get('served_version', '-')}` · "
        f"agent clarifies below `{report.get('confidence_threshold', '-')}`",
        "",
        "| System | n | macro-F1 | needs_human recall | accuracy | language acc. | macro-F1 ES | macro-F1 PT |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, r in report["systems"].items():
        by = r["by_language"]
        es = by.get("es", {}).get("macro_f1", "—")
        pt = by.get("pt", {}).get("macro_f1", "—")
        lines.append(
            f"| {name} | {r['n']} | {r['macro_f1']} | {r['needs_human_recall']} | {r['accuracy']} "
            f"| {r['language_accuracy']} | {es} | {pt} |"
        )
    return "\n".join(lines) + "\n"
