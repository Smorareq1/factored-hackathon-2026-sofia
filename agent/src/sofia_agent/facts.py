"""Construcción de `verified_facts`: solo datos devueltos por una tool o una regla, siempre con su fuente.

La frase `fact` está en español porque es la lengua de trabajo del back office (va al handoff §9.4);
lo que ve el cliente se renderiza aparte, en su idioma.
"""

from sofia_agent.state import TxRef, VerifiedFact
from sofia_contracts.bank_api import Dispute, Eligibility, Transaction


def to_ref(tx: Transaction) -> TxRef:
    return TxRef(
        transaction_id=tx.transaction_id,
        date=tx.transaction_date,
        amount=tx.amount,
        currency=tx.currency,
        amount_usd=tx.amount_usd,
        merchant=tx.merchant_name,
        status=tx.transaction_status,
    )


def tx_facts(tx: TxRef, *, source: str, turn: int) -> list[VerifiedFact]:
    day = tx.date.date().isoformat()
    return [
        VerifiedFact(
            key="tx.id",
            kind="id",
            value=tx.transaction_id,
            fact=f"La transacción {tx.transaction_id} existe y pertenece al cliente",
            source=source,
            turn=turn,
        ),
        VerifiedFact(
            key="tx.amount",
            kind="money",
            value=str(tx.amount),
            currency=tx.currency,
            fact=f"Monto {tx.amount} {tx.currency} (≈ {tx.amount_usd} USD)",
            source=source,
            turn=turn,
        ),
        VerifiedFact(
            key="tx.merchant", kind="text", value=tx.merchant, fact=f"Comercio: {tx.merchant}", source=source, turn=turn
        ),
        VerifiedFact(
            key="tx.date", kind="date", value=day, fact=f"Fecha de la transacción: {day}", source=source, turn=turn
        ),
        VerifiedFact(
            key="tx.status",
            kind="tx_status",
            value=tx.status,
            fact=f"Estado de la transacción: {tx.status}",
            source=source,
            turn=turn,
        ),
    ]


def rule_fact(eligibility: Eligibility, *, turn: int) -> list[VerifiedFact]:
    facts = [
        VerifiedFact(
            key="rule.id",
            kind="rule",
            value=eligibility.rule_id,
            fact=f"Política {eligibility.rule_id}: {eligibility.reason} (ruta {eligibility.route})",
            source="POST /disputes/eligibility",
            turn=turn,
        )
    ]
    for flag in eligibility.risk_flags:
        facts.append(
            VerifiedFact(
                key=f"risk.{flag}",
                kind="rule",
                value=flag,
                fact=f"Señal de riesgo de la política: {flag}",
                source=eligibility.rule_id,
                turn=turn,
            )
        )
    if eligibility.existing_dispute_id:
        facts.append(
            VerifiedFact(
                key="existing_case.id",
                kind="id",
                value=eligibility.existing_dispute_id,
                fact=f"Ya existe la disputa abierta {eligibility.existing_dispute_id} para esta transacción",
                source="POST /disputes/eligibility",
                turn=turn,
            )
        )
    return facts


def dispute_facts(dispute: Dispute, *, turn: int) -> list[VerifiedFact]:
    source = f"GET /disputes/{dispute.dispute_id}"
    return [
        VerifiedFact(
            key="case.id",
            kind="id",
            value=dispute.dispute_id,
            fact=f"La disputa {dispute.dispute_id} existe (verificada al releerla)",
            source=source,
            turn=turn,
        ),
        VerifiedFact(
            key="case.status",
            kind="dispute_status",
            value=dispute.status,
            fact=f"Estado de la disputa: {dispute.status}",
            source=source,
            turn=turn,
        ),
    ]


def plain_fact(key: str, value: str, *, fact: str, source: str, turn: int) -> VerifiedFact:
    return VerifiedFact(key=key, kind="id", value=value, fact=fact, source=source, turn=turn)
