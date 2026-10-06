"""Motor de política determinístico para evaluación de elegibilidad de disputas (POL-1..POL-7).

Garantiza REQ-10: la autorización y la elegibilidad viven FUERA DEL PROMPT.
El agente solo recibe la ruta y los códigos estables de regla.
"""

import secrets
from datetime import timedelta

from sofia_contracts.bank_api import Eligibility
from sofia_services.audit.logger import audit_trail
from sofia_services.store import BankStore, get_store


def evaluate_dispute_policy(
    customer_id: str,
    transaction_id: str,
    store: BankStore | None = None,
) -> Eligibility:
    """Evalúa las reglas POL-1 a POL-7 en orden determinístico y estricto.

    Orden de evaluación:
    1. POL-1: Pertenencia de la transacción al cliente autenticado.
    2. POL-4: Duplicidad (disputa ya existente en estado open o in_review).
    3. POL-2: Estado de la transacción (debe ser Approved).
    4. POL-3: Ventana temporal (máx N días, por defecto 90).
    5. POL-6: Riesgo elevado (monto > U USD, sospecha de fraude o cliente reincidente) -> Escala a humano.
    6. POL-5: Monto bajo sin señales de riesgo -> Elegible para resolución automática.
    """
    store = store or get_store()
    now = store.now
    settings = store.settings

    # POL-1: La transacción no pertenece al cliente o no existe
    row = store.transactions.get(transaction_id)
    if row is None or row.customer_id != customer_id:
        audit_trail.record(
            "tx_access_denied",
            customer_id=customer_id,
            rule_id="POL-1",
            transaction_id=transaction_id,
        )
        return Eligibility(
            eligible=False,
            rule_id="POL-1",
            reason="transaction_not_accessible",
            route="deny",
        )

    # POL-4: Ya existe disputa abierta para esa transacción
    existing = next(
        (
            d
            for d in store.disputes.values()
            if d.transaction_id == transaction_id and d.status in {"open", "in_review"}
        ),
        None,
    )
    if existing is not None:
        audit_trail.record(
            "eligibility_evaluated",
            customer_id=customer_id,
            rule_id="POL-4",
            transaction_id=transaction_id,
            existing_dispute_id=existing.dispute_id,
        )
        return Eligibility(
            eligible=False,
            rule_id="POL-4",
            reason="dispute_already_open",
            route="deny",
            existing_dispute_id=existing.dispute_id,
        )

    tx = row.tx

    # POL-2: Estado distinto de Approved o ya reversada
    if tx.transaction_status != "Approved":
        audit_trail.record(
            "eligibility_evaluated",
            customer_id=customer_id,
            rule_id="POL-2",
            transaction_id=transaction_id,
            status=tx.transaction_status,
        )
        return Eligibility(
            eligible=False,
            rule_id="POL-2",
            reason="status_not_disputable",
            route="deny",
        )

    # POL-3: Fuera de la ventana de disputa (N días)
    window = timedelta(days=settings.DISPUTE_WINDOW_DAYS)
    if tx.transaction_date < (now - window):
        audit_trail.record(
            "eligibility_evaluated",
            customer_id=customer_id,
            rule_id="POL-3",
            transaction_id=transaction_id,
            tx_date=tx.transaction_date.isoformat(),
        )
        return Eligibility(
            eligible=False,
            rule_id="POL-3",
            reason="outside_dispute_window",
            route="deny",
        )

    # POL-6: Riesgo elevado (monto > U USD, fraude o reincidencia) -> Humano
    flags: list[str] = []
    if tx.amount_usd > settings.AMOUNT_THRESHOLD_USD:
        flags.append("high_amount")
    if row.is_fraud or row.fraud_score >= settings.FRAUD_SCORE_THRESHOLD:
        flags.append("fraud_suspected")

    customer = store.customers.get(customer_id)
    if customer and customer.repeat_complainer:
        flags.append("repeat_complainer")

    if flags:
        audit_trail.record(
            "eligibility_evaluated",
            customer_id=customer_id,
            rule_id="POL-6",
            transaction_id=transaction_id,
            risk_flags=flags,
            route="human",
        )
        return Eligibility(
            eligible=True,
            rule_id="POL-6",
            reason="requires_human_review",
            route="human",
            risk_flags=flags,
        )

    # POL-5: Elegible para resolución automática (monto <= U y sin riesgo)
    eligibility_id = f"ELG-{secrets.token_hex(6)}"
    expires_at = now + timedelta(minutes=settings.ELIGIBILITY_TTL_MINUTES)
    store.eligibilities[eligibility_id] = (customer_id, transaction_id, expires_at)

    audit_trail.record(
        "eligibility_evaluated",
        customer_id=customer_id,
        rule_id="POL-5",
        transaction_id=transaction_id,
        eligibility_id=eligibility_id,
        route="auto",
    )
    return Eligibility(
        eligible=True,
        rule_id="POL-5",
        reason="low_amount_no_risk",
        route="auto",
        eligibility_id=eligibility_id,
        expires_at=expires_at,
    )
