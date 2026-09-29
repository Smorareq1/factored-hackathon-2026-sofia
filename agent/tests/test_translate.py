"""Traducción de casos: los IDs nunca salen hacia Gemini y una traducción rota no se guarda."""

import pytest

from sofia_agent.translate import TranslationError, check_translation, mask_ids, translated_case, unmask_ids
from sofia_contracts.eval_case import EvalCase


def test_ids_are_masked_consistently_and_restored():
    turns = ["Soy C90000001 y no reconozco TX-MX-0001", "¿Y el caso DSP-2026-000900 de TX-MX-0001?"]
    masked, ids = mask_ids(turns)
    assert masked == ["Soy ⟦0⟧ y no reconozco ⟦1⟧", "¿Y el caso ⟦2⟧ de ⟦1⟧?"]
    assert ids == ["C90000001", "TX-MX-0001", "DSP-2026-000900"]
    translated = ["Sou ⟦0⟧ e não reconheço ⟦1⟧", "E o caso ⟦2⟧ de ⟦1⟧?"]
    check_translation(masked, translated)
    assert unmask_ids(translated, ids) == [
        "Sou C90000001 e não reconheço TX-MX-0001",
        "E o caso DSP-2026-000900 de TX-MX-0001?",
    ]


@pytest.mark.parametrize(
    "translated",
    [
        ["Sou ⟦0⟧ e não reconheço"],  # se perdió un marcador
        ["Sou ⟦0⟧ e não reconheço ⟦1⟧", "extra"],  # cambió la cantidad de turnos
    ],
)
def test_broken_translations_are_rejected(translated):
    masked, _ = mask_ids(["Soy C90000001 y no reconozco TX-MX-0001"])
    with pytest.raises(TranslationError):
        check_translation(masked, translated)


def test_translated_case_is_labeled():
    case = EvalCase(
        case_id="DEV-ES-001",
        language="es",
        type="normal",
        level=1,
        session_customer_id="C90000001",
        turns=["No reconozco un cargo"],
        expected_route="auto",
        origin="team_generated",
    )
    pt = translated_case(case, ["Não reconheço uma cobrança"])
    assert (pt.case_id, pt.language, pt.origin) == ("DEV-ES-001-pt", "pt", "team_generated")
    assert "respond_wrong_language" in pt.must_not and pt.expected_route == "auto"
