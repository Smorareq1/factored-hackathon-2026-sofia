"""Automated checks on the router corpus. Run after every corpus change:

    uv run --package sofia-ml python ml/scripts/audit_corpus.py [--review-csv corpus_review.csv]

Model, rule and language-detector predictions are **signals to review**, never ground truth: the labeling guidelines
decide the label (ml/reports/corpus_audit.md). Writes ml/reports/corpus_checks.json (aggregates) and, on request, a
review CSV with one row per example and its flags (flagged rows first).
"""

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from sklearn.model_selection import GroupKFold

from sofia_ml.baseline_rules import predict_rules
from sofia_ml.labeling import CORPUS_PATH, ML_DIR, load_corpus, render, trainable
from sofia_ml.language import detect_language
from sofia_ml.text import words
from sofia_ml.train import fit

# Values that must not appear in the raw text: dataset-formatted ids, contact details, long numbers.
PRIVACY = {
    "dataset_id": re.compile(r"\b(CLI|CMP|TRX|TX|INT|PRD|SUC|AGT)-[A-Z0-9]{6,}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "long_number": re.compile(r"\d{6,}"),
    "case_id_literal": re.compile(r"\bDSP-\d{4}-\d+\b"),
}
PLACEHOLDER = re.compile(r"<[A-Z_]+>")


def model_disagreement(examples, n_splits: int = 5) -> list[tuple[str, float] | None]:
    """Out-of-fold prediction (GroupKFold: a group is never in train and test at the same time)."""
    out: list[tuple[str, float] | None] = [None] * len(examples)
    groups = [e.group_id for e in examples]
    for tr, te in GroupKFold(n_splits=n_splits).split(examples, groups=groups):
        pipe = fit([examples[i] for i in tr])
        texts = [examples[i].text for i in te]
        for i, pred, proba in zip(te, pipe.predict(texts), pipe.predict_proba(texts).max(axis=1), strict=True):
            out[i] = (str(pred), round(float(proba), 2))
    return out


def shortcuts(examples, min_count: int = 5, purity: float = 0.9) -> dict[str, tuple[str, int]]:
    """Words that almost only appear in one class: the model can memorize them instead of learning the intent."""
    by_word: dict[str, Counter] = {}
    for e in examples:
        for w in set(words(e.text)):
            by_word.setdefault(w, Counter())[e.label] += 1
    return {
        w: c.most_common(1)[0]
        for w, c in by_word.items()
        if sum(c.values()) >= min_count and c.most_common(1)[0][1] / sum(c.values()) >= purity
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    parser.add_argument("--review-csv", type=Path, default=None)
    args = parser.parse_args()

    raw = load_corpus(args.corpus, rendered=False)
    rows = [render(e) for e in raw]
    approved_idx = [i for i, e in enumerate(rows) if e.review_status == "approved"]
    approved = [rows[i] for i in approved_idx]
    oof = dict(zip(approved_idx, model_disagreement(approved), strict=True))

    review, flag_counts, confusions = [], Counter(), Counter()
    for i, (src, e) in enumerate(zip(raw, rows, strict=True)):
        flags = []
        if e.review_status != "approved":
            flags.append("adjudicate")
        if i in oof and oof[i][0] != e.label:
            flags.append(f"model:{oof[i][0]}({oof[i][1]})")
            confusions[f"{e.label}->{oof[i][0]}"] += 1
        rule = predict_rules(e.text)
        if rule.confidence > 0.3 and rule.intent != e.label:
            flags.append(f"rules:{rule.intent}")
        lang = detect_language(e.text)
        if lang.decided and lang.language != e.language and e.variation != "code_switch":
            flags.append(f"language:{lang.language}")
        flags += [f"privacy:{name}" for name, rx in PRIVACY.items() if rx.search(src.text)]
        if PLACEHOLDER.search(e.text):
            flags.append("unfilled_placeholder")
        flag_counts.update(f.split(":")[0] for f in flags)
        review.append({
            "group_id": e.group_id, "language": e.language, "label": e.label, "variation": e.variation,
            "review_status": e.review_status, "text": src.text, "flags": "; ".join(flags), "note": e.note or "",
            "label_ok": "", "comment": "",
        })

    report = {
        "rows": len(rows),
        "approved": len(approved),
        "needs_adjudication": len(rows) - len(approved),
        "human_review_required": sum(e.human_review_required for e in rows),
        "labels_approved": dict(Counter(e.label for e in trainable(rows))),
        "by_language": dict(Counter(e.language for e in rows)),
        "by_variation": dict(Counter(e.variation for e in rows)),
        "groups": len({e.group_id for e in rows}),
        "flags": dict(flag_counts),
        "model_confusions_cv": dict(confusions.most_common()),
        "model_cv_accuracy": round(1 - sum(confusions.values()) / len(approved), 3) if approved else None,
        "shortcut_words": {w: list(v) for w, v in shortcuts(approved).items()},
        "undecided_language": sum(not detect_language(e.text).decided for e in rows),
    }
    out = ML_DIR / "reports" / "corpus_checks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.review_csv:
        review.sort(key=lambda r: (r["flags"] == "", r["label"], r["group_id"]))
        with args.review_csv.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(review[0]))
            writer.writeheader()
            writer.writerows(review)
        print("review CSV:", args.review_csv)


if __name__ == "__main__":
    main()
