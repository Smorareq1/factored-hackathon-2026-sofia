"""Hybrid router: rules answer when they match, the trained model answers the rest, rules alone without a corpus."""

from sofia_ml.baseline_rules import RULES_ROUTER_VERSION
from sofia_ml.labeling import LabeledExample
from sofia_ml.router import HYBRID_ROUTER_VERSION, HybridRouter
from sofia_ml.train import as_predictor, fit

TRAIN = [
    LabeledExample(text=t, label=label, language=lang, group_id=f"{label}-{i}", origin="team_generated", source="test")
    for label, rows in {
        "dispute_new": [("algo raro en mi cuenta del super", "es"), ("algo estranho na minha conta", "pt")],
        "transaction_inquiry": [("cuanto fue lo de ayer en el super", "es"), ("quanto foi o de ontem", "pt")],
        "dispute_status": [("y lo que reclame el lunes en que va", "es"), ("e o que reclamei segunda", "pt")],
        "out_of_scope": [("quiero cambiar de plan de celular", "es"), ("quero mudar meu plano", "pt")],
        "needs_human": [("me urge alguien ya", "es"), ("preciso de alguem agora", "pt")],
    }.items()
    for i, (t, lang) in enumerate(rows)
]


def test_rules_answer_when_they_match() -> None:
    router = HybridRouter(as_predictor(fit(TRAIN)))
    prediction = router.predict("No reconozco un cargo de Rappi")
    assert prediction.intent == "dispute_new"
    assert prediction.router_version == f"{HYBRID_ROUTER_VERSION}/rules"


def test_model_answers_what_rules_do_not_cover() -> None:
    router = HybridRouter(as_predictor(fit(TRAIN)))
    prediction = router.predict("algo raro en mi cuenta del super otra vez")
    assert prediction.router_version == f"{HYBRID_ROUTER_VERSION}/model"
    assert 0 <= prediction.confidence <= 1


def test_without_corpus_serves_rules_only(tmp_path) -> None:
    router = HybridRouter.from_corpus(tmp_path / "missing.jsonl")
    assert router.version == RULES_ROUTER_VERSION
    assert router.predict("Quiero ver mis últimos movimientos").router_version == RULES_ROUTER_VERSION
