"""Entrenamiento del router con split sin leakage y comparación contra el baseline de reglas (§8.6, §8.7).

    python -m sofia_ml.train                      # corpus del equipo (ml/data/intent_corpus.jsonl)
    python -m sofia_ml.train --holdout-days 90    # temporal + grupo, si todos los ejemplos traen fecha

Candidato v1: TF-IDF de n-gramas de caracteres + regresión logística (segundo baseline del brief, robusto a
tildes y a ES/PT). El artefacto va a MODEL_DIR (gitignored); el reporte agregado a ml/reports/ (versionado).
"""

import argparse
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from sofia_contracts.common import Language
from sofia_contracts.router import IntentPrediction
from sofia_ml.baseline_rules import RULES_ROUTER_VERSION, predict_rules
from sofia_ml.evaluate import compare, write_report
from sofia_ml.labeling import CORPUS_PATH, ML_DIR, LabeledExample, load_corpus, trainable
from sofia_ml.language import detect_language
from sofia_ml.split import group_split
from sofia_ml.text import fold

log = logging.getLogger(__name__)

MODEL_VERSION = "tfidf-lr-0.1"
MODEL_DIR = Path(os.getenv("MODEL_DIR", ML_DIR / "artifacts"))


def build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(preprocessor=fold, analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])


def fit(train: list[LabeledExample]) -> Pipeline:
    pipe = build_pipeline()
    pipe.fit([e.text for e in train], [e.label for e in train])
    return pipe


def as_predictor(pipe: Pipeline, version: str = MODEL_VERSION):
    def predict(text: str, language_hint: Language | None = None) -> IntentPrediction:
        proba = pipe.predict_proba([text])[0]
        best = int(proba.argmax())
        language = detect_language(text, fallback=language_hint or "es")
        return IntentPrediction(
            intent=pipe.classes_[best],
            confidence=round(float(proba[best]), 3),
            language=language.language,
            language_confidence=language.confidence,
            router_version=version,
        )

    return predict


def save(pipe: Pipeline, split_info: dict, out_dir: Path = MODEL_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, out_dir / "router.joblib")
    meta = {"router_version": MODEL_VERSION, "trained_at": datetime.now(UTC).isoformat(), "split": split_info}
    (out_dir / "router_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--holdout-days", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    corpus = load_corpus(args.corpus)
    examples = trainable(corpus)
    if not examples:
        raise SystemExit(f"corpus vacío o sin filas aprobadas: {args.corpus}")
    log.info("corpus: %d filas, %d aprobadas (el resto espera adjudicación)", len(corpus), len(examples))
    split = group_split(examples, args.test_size, args.holdout_days, args.seed)
    log.info("split %s: %s", split.strategy, split.info)

    from sofia_ml.router import HYBRID_ROUTER_VERSION, RECOMMENDED_CONFIDENCE_THRESHOLD, HybridRouter

    pipe = fit(split.train)
    report = compare(
        split.test,
        {
            RULES_ROUTER_VERSION: predict_rules,
            MODEL_VERSION: as_predictor(pipe),
            HYBRID_ROUTER_VERSION: HybridRouter(as_predictor(pipe)).predict,
        },
        split_info={"strategy": split.strategy, **split.info},
    )
    report["served_version"] = HYBRID_ROUTER_VERSION
    report["confidence_threshold"] = RECOMMENDED_CONFIDENCE_THRESHOLD
    log.info("reporte: %s", write_report(report))
    save(fit(examples), split.info)  # el modelo servido usa todo el corpus; las métricas son las del held-out
    log.info("modelo en %s", MODEL_DIR)


if __name__ == "__main__":
    main()
