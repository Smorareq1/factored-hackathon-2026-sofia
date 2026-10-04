"""Labels del router (§8.6): de dónde salen los ejemplos etiquetados y cómo se audita su ruido.

Hallazgo de la auditoría (analysis/notebooks/04_label_audit.ipynb): `call_transcripts.customer_text` son 42 plantillas
de consulta de saldo repartidas igual entre las 6 `reason_category`, y `detected_intents` es siempre
`consulta_general`. El dataset no trae una señal de intención válida, así que el corpus de entrenamiento es
**team_generated** (CON-02) en `ml/data/intent_corpus.jsonl`; `gold_intent_training` se carga solo para auditar.

Cada ejemplo lleva `group_id`: el cliente en datos del dataset, la familia de paráfrasis en el corpus del equipo.
El split agrupa por ahí para que ninguna paráfrasis de un mismo mensaje quede a ambos lados (split.py).

Reglas de etiquetado (ml/reports/corpus_audit.md): el label es la **intención** del cliente; la política decide
después si escala (POL-6). Una fila con `review_status=needs_adjudication` no entra al entrenamiento hasta que un
humano la resuelva. Montos, comercios e ids de caso se guardan como placeholders (`<AMOUNT>`, `<MERCHANT>`,
`<CASE_ID>`) y se rellenan con un generador sintético determinístico al cargar: ningún valor viene del dataset.
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
MANUAL_LABELS_PATH = ML_DIR / "labels" / "manual_labels.csv"


ReviewStatus = Literal["approved", "needs_adjudication"]
VARIATIONS = (
    "original", "contrastive", "typo", "no_accents", "short", "colloquial", "code_switch",
    "prompt_injection", "surrounding_text", "vague",
)


class LabeledExample(BaseModel):
    text: str
    label: Intent
    language: Language  # idioma dominante; los code_switch mezclan ES/PT
    group_id: str
    event_date: date | None = None
    origin: Origin
    source: str
    variation: str = "original"
    review_status: ReviewStatus = "approved"
    human_review_required: bool = False  # CON-02: texto generado o modificado por LLM pendiente de revisión humana
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
    """Rellena placeholders con valores sintéticos; misma fila → mismos valores (semilla = hash de la fila)."""
    if "<" not in example.text:
        return example
    rng = random.Random(f"{example.group_id}|{example.text}")  # noqa: S311 (datos sintéticos reproducibles)
    text = example.text
    for placeholder, values in _FILL[example.language].items():
        while placeholder in text:
            text = text.replace(placeholder, rng.choice(values), 1)
    while "<CASE_ID>" in text:
        text = text.replace("<CASE_ID>", f"DSP-2026-{rng.randrange(1, 9999):04d}", 1)
    return example.model_copy(update={"text": text})


def sample_id(text: str) -> str:
    """Id estable del texto: la muestra manual se versiona por id, sin copiar textos del dataset al repo (CON-03)."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:12]


def load_corpus(path: Path = CORPUS_PATH, rendered: bool = True) -> list[LabeledExample]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        rows = [LabeledExample.model_validate_json(line) for line in f if line.strip()]
    return [render(r) for r in rows] if rendered else rows


def trainable(examples: list[LabeledExample]) -> list[LabeledExample]:
    """Solo filas aprobadas: las que esperan adjudicación no multiplican errores de anotación."""
    return [e for e in examples if e.review_status == "approved"]


def load_gold(gold_dir: Path) -> list[LabeledExample]:
    """`gold_intent_training` con su label provisional de OPS. Solo para auditar ruido, no para entrenar."""
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
    """Muestra estratificada por (label, idioma) para etiquetar a mano; textos repetidos cuentan una vez."""
    unique = {sample_id(e.text): e for e in examples}
    strata: dict[tuple[str, str], list[LabeledExample]] = defaultdict(list)
    for e in unique.values():
        strata[(e.label, e.language)].append(e)
    rng = random.Random(seed)  # noqa: S311 (muestreo reproducible, no criptografía)
    for bucket in strata.values():
        rng.shuffle(bucket)
    picked: list[LabeledExample] = []
    while len(picked) < n and any(strata.values()):
        for key in sorted(strata):
            if strata[key] and len(picked) < n:
                picked.append(strata[key].pop())
    return picked


def write_manual_template(examples: list[LabeledExample], path: Path = MANUAL_LABELS_PATH) -> None:
    """CSV para etiquetar: `label_manual` vacío. El texto va solo si es team_generated (CON-03)."""
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
    """Acuerdo label del dataset vs label manual: mide el ruido de las etiquetas (§8.6)."""
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
