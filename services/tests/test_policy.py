"""Tests exhaustivos del motor de política POL-1..POL-7 (REQ-10)."""

import pytest

from sofia_services.policy.engine import evaluate_dispute_policy
from sofia_services.store import reset_store


def setup_function() -> None:
    reset_store()


def test_pol1_transaction_not_accessible() -> None:
    """POL-1: Si la transacción no existe o pertenece a otro cliente, deniega sin revelar."""
    # TX-CO-0001 pertenece a C90000002, no a C90000001
    result = evaluate_dispute_policy("C90000001", "TX-CO-0001")
    assert not result.eligible
    assert result.rule_id == "POL-1"
    assert result.route == "deny"
    assert result.reason == "transaction_not_accessible"

    # Transacción inexistente
    result_none = evaluate_dispute_policy("C90000001", "TX-NON-EXISTENT")
    assert not result_none.eligible
    assert result_none.rule_id == "POL-1"
    assert result_none.route == "deny"


def test_pol4_dispute_already_open() -> None:
    """POL-4: Ya existe disputa abierta para esa transacción."""
    # TX-MX-0007 ya tiene disputa abierta (DSP-2026-000900)
    result = evaluate_dispute_policy("C90000001", "TX-MX-0007")
    assert not result.eligible
    assert result.rule_id == "POL-4"
    assert result.route == "deny"
    assert result.reason == "dispute_already_open"
    assert result.existing_dispute_id == "DSP-2026-000900"


def test_pol2_status_not_disputable() -> None:
    """POL-2: Transacción con estado distinto de Approved (p. ej. Declined)."""
    # TX-MX-0005 tiene estado Declined
    result = evaluate_dispute_policy("C90000001", "TX-MX-0005")
    assert not result.eligible
    assert result.rule_id == "POL-2"
    assert result.route == "deny"
    assert result.reason == "status_not_disputable"


def test_pol3_outside_dispute_window() -> None:
    """POL-3: Transacción con más de N días (p. ej. 150 días)."""
    # TX-MX-0006 tiene 150 días de antigüedad
    result = evaluate_dispute_policy("C90000001", "TX-MX-0006")
    assert not result.eligible
    assert result.rule_id == "POL-3"
    assert result.route == "deny"
    assert result.reason == "outside_dispute_window"


def test_pol6_high_amount() -> None:
    """POL-6: Monto supera el umbral U (500 USD)."""
    # TX-MX-0004 es de 15,800 MXN (~854 USD)
    result = evaluate_dispute_policy("C90000001", "TX-MX-0004")
    assert result.eligible
    assert result.rule_id == "POL-6"
    assert result.route == "human"
    assert "high_amount" in result.risk_flags


def test_pol6_fraud_suspected() -> None:
    """POL-6: Sospecha de fraude (score >= 0.30 o is_fraud=True)."""
    # TX-MX-0008 tiene fraud_score 0.91 y is_fraud=True
    result = evaluate_dispute_policy("C90000001", "TX-MX-0008")
    assert result.eligible
    assert result.rule_id == "POL-6"
    assert result.route == "human"
    assert "fraud_suspected" in result.risk_flags


def test_pol6_repeat_complainer() -> None:
    """POL-6: Cliente marcado como reincidente."""
    # C90000003 (Carla) es repeat_complainer=True
    # TX-AR-0001 es de monto bajo (25,000 ARS ~ 25 USD), aprobada y reciente
    result = evaluate_dispute_policy("C90000003", "TX-AR-0001")
    assert result.eligible
    assert result.rule_id == "POL-6"
    assert result.route == "human"
    assert "repeat_complainer" in result.risk_flags


def test_pol5_low_amount_no_risk() -> None:
    """POL-5: Transacción reciente, aprobada, bajo monto y sin riesgo -> Auto elegible."""
    # TX-MX-0001 es de 349 MXN (~18.86 USD), Approved, 2 días atrás, sin fraude
    result = evaluate_dispute_policy("C90000001", "TX-MX-0001")
    assert result.eligible
    assert result.rule_id == "POL-5"
    assert result.route == "auto"
    assert result.reason == "low_amount_no_risk"
    assert result.eligibility_id is not None
    assert result.eligibility_id.startswith("ELG-")
    assert result.expires_at is not None


def test_pol6_fraud_score_alone_routes_to_human() -> None:
    """POL-6 por score, sin is_fraud: 0.30 escala, 0.20 (el máximo de la semilla) no."""
    store = reset_store()
    store.transactions["TX-MX-0001"].fraud_score = 0.35
    result = evaluate_dispute_policy("C90000001", "TX-MX-0001", store=store)
    assert result.route == "human"
    assert "fraud_suspected" in result.risk_flags

    store.transactions["TX-MX-0001"].fraud_score = 0.20
    assert "fraud_suspected" not in evaluate_dispute_policy("C90000001", "TX-MX-0001", store=store).risk_flags


def test_gold_fraud_score_is_converted_from_0_100_scale() -> None:
    """gold siempre viene en 0–100: 30 → 0.30 (escala), 0.5 → 0.005 (no escala), sin score → 0.05."""
    from sofia_services.store import gold_fraud_score

    assert gold_fraud_score(30) == pytest.approx(0.30)
    assert gold_fraud_score(0.5) == pytest.approx(0.005)
    assert gold_fraud_score(99.99) == pytest.approx(0.9999)
    assert gold_fraud_score(None) == 0.05
