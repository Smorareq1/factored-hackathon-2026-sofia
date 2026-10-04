"""Labels, split sin leakage, métricas y entrenamiento del router (REQ-13). Datos sintéticos en memoria."""

from datetime import date, timedelta

import pytest

from sofia_ml.baseline_rules import predict_rules
from sofia_ml.evaluate import compare, score, to_markdown
from sofia_ml.labeling import (
    INTENTS,
    LabeledExample,
    label_agreement,
    load_manual_labels,
    sample_for_manual,
    sample_id,
    write_manual_template,
)
from sofia_ml.split import Split, assert_no_leakage, group_split
from sofia_ml.train import as_predictor, fit

SEEDS = {
    "dispute_new": ("No reconozco un cargo de {m}", "Não reconheço a cobrança da {m}"),
    "dispute_status": ("¿Cómo va mi disputa de {m}?", "Qual o status da minha contestação da {m}?"),
    "transaction_inquiry": ("Quiero ver mis compras en {m}", "Quais compras eu fiz na {m}?"),
    "out_of_scope": ("Necesito un préstamo, vi publicidad de {m}", "Quero um empréstimo, vi anúncio da {m}"),
    "needs_human": ("Quiero hablar con un agente por lo de {m}", "Quero falar com um atendente sobre a {m}"),
}
MERCHANTS = ["Rappi", "Éxito", "Oxxo", "Mercado Libre", "Falabella", "Uber", "Netflix", "Spotify"]


def corpus(dated: bool = False) -> list[LabeledExample]:
    out = []
    for label, (es, pt) in SEEDS.items():
        for i, m in enumerate(MERCHANTS):
            for lang, tpl in (("es", es), ("pt", pt)):
                out.append(
                    LabeledExample(
                        text=tpl.format(m=m),
                        label=label,
                        language=lang,
                        group_id=f"{label}-{i}",
                        event_date=date(2026, 1, 1) + timedelta(days=20 * i) if dated else None,
                        origin="team_generated",
                        source="test",
                    )
                )
    return out


def test_group_split_keeps_groups_apart():
    split = group_split(corpus(), test_size=0.3)
    assert split.strategy == "group"
    assert split.train and split.test
    assert not {e.group_id for e in split.train} & {e.group_id for e in split.test}


def test_temporal_split_tests_on_latest_dates():
    split = group_split(corpus(dated=True), holdout_days=50)
    assert split.strategy == "temporal+group"
    assert min(e.event_date for e in split.test) > max(e.event_date for e in split.train)


def test_leakage_is_rejected():
    e = corpus()[0]
    with pytest.raises(ValueError, match="leakage"):
        assert_no_leakage(Split(train=[e], test=[e], strategy="manual"))


def test_score_needs_human_recall_and_confusion_shape():
    r = score(["needs_human", "needs_human", "dispute_new"], ["needs_human", "out_of_scope", "dispute_new"])
    assert r["needs_human_recall"] == 0.5
    assert len(r["confusion"]["matrix"]) == len(INTENTS)


def test_model_vs_rules_report_has_both_languages():
    split = group_split(corpus(), test_size=0.3)
    report = compare(split.test, {"rules": predict_rules, "model": as_predictor(fit(split.train))}, split.info)
    for system in report["systems"].values():
        assert set(system["by_language"]) == {"es", "pt"}
        assert 0 <= system["macro_f1"] <= 1
    assert "| model |" in to_markdown(report)


def test_manual_sample_is_stratified_and_roundtrips(tmp_path):
    examples = corpus()
    picked = sample_for_manual(examples, n=20)
    assert len(picked) == 20
    assert len({(e.label, e.language) for e in picked}) == len(INTENTS) * 2

    path = tmp_path / "manual.csv"
    write_manual_template(picked, path)
    text = path.read_text(encoding="utf-8").replace(",dispute_new,,", ",dispute_new,needs_human,", 1)
    path.write_text(text, encoding="utf-8")
    manual = load_manual_labels(path)
    assert list(manual.values()) == ["needs_human"]
    agreement = label_agreement(examples, manual)
    assert agreement["agreement"] == 0.0
    assert sample_id(" a ") == sample_id("a")


def test_placeholders_render_deterministically_per_language():
    from sofia_ml.labeling import render

    row = LabeledExample(text="No reconozco <AMOUNT> en <MERCHANT>, caso <CASE_ID>", label="dispute_new",
                         language="es", group_id="g", origin="team_generated", source="test")
    a, b = render(row), render(row)
    assert a.text == b.text
    assert "<" not in a.text and "DSP-2026-" in a.text


def test_rows_awaiting_adjudication_are_not_trained_on():
    from sofia_ml.labeling import trainable

    rows = corpus()[:2]
    rows[1] = rows[1].model_copy(update={"review_status": "needs_adjudication"})
    assert trainable(rows) == rows[:1]


def test_shipped_corpus_is_valid_and_leak_free():
    from sofia_ml.labeling import load_corpus

    rows = load_corpus()
    if not rows:
        pytest.skip("sin corpus")
    assert all("<" not in e.text for e in rows)
    assert len({e.text for e in rows}) == len(rows)
    group_split(trainable_rows := [e for e in rows if e.review_status == "approved"], test_size=0.2)
    assert {e.label for e in trainable_rows} == set(INTENTS)
