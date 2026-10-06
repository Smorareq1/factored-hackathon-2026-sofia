"""Served intent router (§8.6, §9.3): keyword rules first, the trained model for what the rules do not cover.

Out-of-fold on the approved corpus (GroupKFold by family, 256 rows): rules 0.449 accuracy, model 0.645,
hybrid 0.766. The rules are precise when they match (confidence >= 0.65: 0.865 accuracy on 41% of messages);
the model covers the rest. The agent clarifies below its router threshold, set by DS to
`RECOMMENDED_CONFIDENCE_THRESHOLD` (agent/src/sofia_agent/purpose/purpose.yaml): at 0.35 the hybrid passes 60% of
messages with 0.89 accuracy.

The model is trained at startup from the shipped corpus (under a second), so the service needs no binary artifact.
Without a corpus it serves the rules alone. `router_version` records which component answered (REQ-19).
"""

import logging
from collections.abc import Callable
from pathlib import Path

from sofia_contracts.common import Language
from sofia_contracts.router import IntentPrediction
from sofia_ml.baseline_rules import RULES_ROUTER_VERSION, predict_rules
from sofia_ml.labeling import CORPUS_PATH, load_corpus, trainable
from sofia_ml.train import MODEL_VERSION, as_predictor, fit

log = logging.getLogger(__name__)

RULES_MATCH_CONFIDENCE = 0.65  # predict_rules returns >= 0.65 only when at least one rule matched
RECOMMENDED_CONFIDENCE_THRESHOLD = 0.35
HYBRID_ROUTER_VERSION = f"hybrid-0.1[{RULES_ROUTER_VERSION}+{MODEL_VERSION}]"

Predictor = Callable[[str, Language | None], IntentPrediction]


class HybridRouter:
    def __init__(self, model: Predictor | None) -> None:
        self._model = model

    @classmethod
    def from_corpus(cls, path: Path = CORPUS_PATH) -> "HybridRouter":
        examples = trainable(load_corpus(path))
        if not examples:
            log.warning("router: no approved corpus at %s, serving rules only", path)
            return cls(None)
        log.info("router: trained %s on %d approved examples", MODEL_VERSION, len(examples))
        return cls(as_predictor(fit(examples)))

    @property
    def version(self) -> str:
        return HYBRID_ROUTER_VERSION if self._model else RULES_ROUTER_VERSION

    def predict(self, text: str, language_hint: Language | None = None) -> IntentPrediction:
        rules = predict_rules(text, language_hint)
        if self._model is None:
            return rules
        if rules.confidence >= RULES_MATCH_CONFIDENCE:
            return rules.model_copy(update={"router_version": f"{HYBRID_ROUTER_VERSION}/rules"})
        return self._model(text, language_hint).model_copy(update={"router_version": f"{HYBRID_ROUTER_VERSION}/model"})
