"""Tests del contrato §9.3 y del comportamiento v0 (reglas). Son la red de seguridad que el modelo entrenado
tiene que seguir cumpliendo: cambia `router_version`, no la forma de la respuesta."""

import pytest
from fastapi.testclient import TestClient

from sofia_contracts.router import IN_SCOPE_INTENTS, IntentPrediction
from sofia_ml.baseline_rules import RULES_ROUTER_VERSION, predict_rules
from sofia_ml.serve import app

client = TestClient(app)

CASES = [
    # (texto, intención esperada, idioma esperado)
    ("No reconozco un cargo de Rappi", "dispute_new", "es"),
    ("Me cobraron dos veces en Éxito", "dispute_new", "es"),
    ("Não reconheço essa cobrança da loja", "dispute_new", "pt"),
    ("Fui cobrado duas vezes no mercado", "dispute_new", "pt"),
    ("¿Cómo va mi disputa DSP-2026-14?", "dispute_status", "es"),
    ("Qual o status da minha contestação?", "dispute_status", "pt"),
    ("Quiero ver mis últimos movimientos", "transaction_inquiry", "es"),
    ("Quais compras eu fiz ontem?", "transaction_inquiry", "pt"),
    ("Quiero hablar con un agente humano", "needs_human", "es"),
    ("Quero falar com um atendente", "needs_human", "pt"),
    ("Necesito un préstamo para mi negocio", "out_of_scope", "es"),
    ("Quero fazer um empréstimo", "out_of_scope", "pt"),
]


# Fallos conocidos de las reglas v0 (strict: si alguien las mejora, este test avisa y se mueve a CASES).
# Son exactamente lo que el modelo entrenado tiene que resolver; ver docs/evaluation-report.md cuando exista.
KNOWN_MISSES = [
    # DEV-ES-002 del set dev: "no hice" sin demostrativo y "reclamarlo" (clítico) no matchean ninguna regla.
    ("Hay un cobro de Spotify que no hice, quiero reclamarlo", "dispute_new"),
    # "foram" entre el interrogativo y el sustantivo rompe la regla de transaction_inquiry.
    ("Quais foram as minhas compras de ontem?", "transaction_inquiry"),
]


_XFAIL = pytest.mark.xfail(strict=True)


@pytest.mark.parametrize(("text", "intent"), [pytest.param(*case, marks=_XFAIL) for case in KNOWN_MISSES])
def test_rules_known_misses(text: str, intent: str) -> None:
    assert predict_rules(text).intent == intent


@pytest.mark.parametrize(("text", "intent", "language"), CASES)
def test_predict_rules(text: str, intent: str, language: str) -> None:
    prediction = predict_rules(text)
    assert prediction.intent == intent
    assert prediction.language == language


def test_needs_human_wins_over_other_intents() -> None:
    # Regla de costo (§8.6): si el cliente pide una persona, se respeta aunque también describa una disputa.
    prediction = predict_rules("No reconozco un cargo y quiero hablar con un agente humano")
    assert prediction.intent == "needs_human"


def test_unknown_text_is_low_confidence() -> None:
    prediction = predict_rules("asdf qwerty")
    assert prediction.intent == "out_of_scope"
    assert prediction.confidence < 0.55  # umbral de purpose.yaml: el agente debe aclarar, no abstenerse


def test_language_hint_is_the_fallback_when_there_is_no_evidence() -> None:
    assert predict_rules("ok", language_hint="pt").language == "pt"
    assert predict_rules("ok", language_hint="es").language == "es"


def test_predict_endpoint_matches_contract() -> None:
    response = client.post("/predict", json={"text": "No reconozco un cargo de Rappi", "language_hint": "es"})
    assert response.status_code == 200
    body = response.json()
    prediction = IntentPrediction.model_validate(body)  # valida tipos y rangos del contrato
    assert prediction.intent in IN_SCOPE_INTENTS
    assert prediction.router_version == RULES_ROUTER_VERSION
    assert prediction.language_confidence is not None


def test_predict_endpoint_without_language_hint() -> None:
    response = client.post("/predict", json={"text": "Quero contestar uma cobrança"})
    assert response.status_code == 200
    assert response.json()["language"] == "pt"


@pytest.mark.parametrize("payload", [{}, {"text": 123}, {"text": "hola", "language_hint": "en"}])
def test_predict_endpoint_rejects_invalid_requests(payload: dict) -> None:
    assert client.post("/predict", json=payload).status_code == 422
