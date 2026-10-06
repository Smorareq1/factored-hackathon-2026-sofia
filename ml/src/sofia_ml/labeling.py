"""Router labels (§8.6): where the labeled examples come from and how their noise is audited.

Audit finding (analysis/notebooks/04_label_audit.ipynb): `call_transcripts.customer_text` holds 42 balance-inquiry
templates spread evenly across the 6 `reason_category` values, and `detected_intents` is always `consulta_general`.
The dataset has no valid intent signal, so the training corpus is **team_generated** (CON-02) in
`ml/data/intent_corpus.jsonl`; `gold_intent_training` is loaded only for auditing.

Each example carries a `group_id`: the customer for dataset rows, the paraphrase family in the team corpus. The split
groups by it so no paraphrase of the same message ends up on both sides (split.py).

Labeling rules (ml/reports/corpus_audit.md): the label is the customer's **intent**; the policy decides afterwards
whether to escalate (POL-6). A row with `review_status=needs_adjudication` stays out of training until a human
resolves it. Amounts, merchants and case ids are stored as placeholders (`<AMOUNT>`, `<MERCHANT>`, `<CASE_ID>`) and
filled by a deterministic synthetic generator at load time: no value comes from the dataset.
"""

import csv
import hashlib
import json
import os
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel

from sofia_contracts.common import Language
from sofia_contracts.eval_case import Origin
from sofia_contracts.router import Intent

INTENTS: tuple[Intent, ...] = get_args(Intent)
ML_DIR = Path(os.getenv("ML_DIR", Path(__file__).resolve().parents[2]))
CORPUS_PATH = ML_DIR / "data" / "intent_corpus.jsonl"
if not CORPUS_PATH.exists():  # installed wheel (Cloud Run): the corpus ships inside the package
    CORPUS_PATH = Path(__file__).parent / "data" / "intent_corpus.jsonl"
MANUAL_LABELS_PATH = ML_DIR / "labels" / "manual_labels.csv"


ReviewStatus = Literal["approved", "needs_adjudication"]
VARIATIONS = (
    "original", "contrastive", "typo", "no_accents", "short", "colloquial", "code_switch",
    "prompt_injection", "surrounding_text", "vague",
)


class LabeledExample(BaseModel):
    text: str
    label: Intent
    language: Language  # dominant language; code_switch rows mix ES/PT
    group_id: str
    event_date: date | None = None
    origin: Origin
    source: str
    variation: str = "original"
    review_status: ReviewStatus = "approved"
    human_review_required: bool = False  # CON-02: LLM-generated or LLM-modified text awaiting human review
    note: str | None = None


_FILL: dict[str, dict[str, tuple[str, ...]]] = {
    "es": {
        "<AMOUNT>": ("45 dólares", "$1.250", "300 pesos", "US$ 89,90", "120 dólares", "5.000 pesos", "$18.000"),
        "<MERCHANT>": ("Netflix", "Uber", "Mercado Libre", "Rappi", "Oxxo", "Falabella", "Spotify", "Despegar"),
    },
    "pt": {
        "<AMOUNT>": ("45 dólares", "R$ 1.250", "R$ 89,90", "300 reais", "120 dólares", "R$ 5.000", "R$ 18,50"),
        "<MERCHANT>": ("Netflix", "Uber", "Mercado Livre", "iFood", "Renner", "Spotify", "Magalu", "99"),
    },
}


def render(example: LabeledExample) -> LabeledExample:
    """Fills placeholders with synthetic values; same row → same values (seed = the row's hash)."""
    if "<" not in example.text:
        return example
    rng = random.Random(f"{example.group_id}|{example.text}")  # noqa: S311 (reproducible synthetic data)
    text = example.text
    for placeholder, values in _FILL[example.language].items():
        while placeholder in text:
            text = text.replace(placeholder, rng.choice(values), 1)
    while "<CASE_ID>" in text:
        text = text.replace("<CASE_ID>", f"DSP-2026-{rng.randrange(1, 9999):04d}", 1)
    return example.model_copy(update={"text": text})


def sample_id(text: str) -> str:
    """Stable text id: the manual sample is versioned by id, without copying dataset text into the repo (CON-03)."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:12]


def load_corpus(path: Path = CORPUS_PATH, rendered: bool = True) -> list[LabeledExample]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        rows = [LabeledExample.model_validate_json(line) for line in f if line.strip()]
    return [render(r) for r in rows] if rendered else rows


def trainable(examples: list[LabeledExample]) -> list[LabeledExample]:
    """Approved rows only: rows awaiting adjudication must not multiply annotation errors."""
    return [e for e in examples if e.review_status == "approved"]


def load_gold(gold_dir: Path) -> list[LabeledExample]:
    """`gold_intent_training` with OPS's provisional label. Only for auditing noise, not for training."""
    import polars as pl

    path = gold_dir / "gold_intent_training.parquet"
    if not path.exists():
        return []
    rows = pl.read_parquet(path).iter_rows(named=True)
    return [
        LabeledExample(
            text=r["text"],
            label=r["label"],
            language=r["language"],
            group_id=r["customer_id"] or sample_id(r["text"]),
            event_date=r["event_date"],
            origin="synthetic",
            source=r["source"],
        )
        for r in rows
    ]


def sample_for_manual(examples: list[LabeledExample], n: int = 200, seed: int = 42) -> list[LabeledExample]:
    """Sample stratified by (label, language) for manual labeling; repeated texts count once."""
    unique = {sample_id(e.text): e for e in examples}
    strata: dict[tuple[str, str], list[LabeledExample]] = defaultdict(list)
    for e in unique.values():
        strata[(e.label, e.language)].append(e)
    rng = random.Random(seed)  # noqa: S311 (reproducible sampling, not cryptography)
    for bucket in strata.values():
        rng.shuffle(bucket)
    picked: list[LabeledExample] = []
    while len(picked) < n and any(strata.values()):
        for key in sorted(strata):
            if strata[key] and len(picked) < n:
                picked.append(strata[key].pop())
    return picked


def write_manual_template(examples: list[LabeledExample], path: Path = MANUAL_LABELS_PATH) -> None:
    """CSV for labeling: empty `label_manual`. The text is included only for team_generated rows (CON-03)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sample_id", "language", "label_dataset", "label_manual", "annotator", "text"])
        for e in examples:
            text = e.text if e.origin == "team_generated" else ""
            w.writerow([sample_id(e.text), e.language, e.label, "", "", text])


def load_manual_labels(path: Path = MANUAL_LABELS_PATH) -> dict[str, Intent]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {r["sample_id"]: r["label_manual"] for r in csv.DictReader(f) if r["label_manual"] in INTENTS}


def label_agreement(examples: list[LabeledExample], manual: dict[str, Intent]) -> dict:
    """Dataset label vs manual label agreement: measures label noise (§8.6)."""
    pairs = [(e.label, manual[sid]) for e in examples if (sid := sample_id(e.text)) in manual]
    if not pairs:
        return {"n": 0, "agreement": None, "confusions": {}}
    confusions = Counter(f"{d}->{m}" for d, m in pairs if d != m)
    return {
        "n": len(pairs),
        "agreement": round(sum(d == m for d, m in pairs) / len(pairs), 3),
        "confusions": dict(confusions.most_common()),
    }


def write_corpus(examples: list[LabeledExample], path: Path = CORPUS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for e in examples:
            f.write(json.dumps(e.model_dump(mode="json"), ensure_ascii=False) + "\n")
