"""Renderer determinístico: reemplaza placeholders por valores de `verified_facts`, con formato por locale."""

import re
from datetime import date
from decimal import Decimal

from sofia_agent.govern.guards import PLACEHOLDER
from sofia_agent.prompts import LanguagePack, fill
from sofia_agent.state import DisputeRef, TxRef, VerifiedFact
from sofia_contracts.common import Language
from sofia_contracts.events import CandidateCard, CaseCard, TransactionCard

_ZERO_DECIMAL = {"COP", "ARS"}


def _group(integer: int, sep: str) -> str:
    return f"{integer:,}".replace(",", sep)


def format_money(amount: Decimal, currency: str, language: Language) -> str:
    """es: MXN/USD con coma de miles (es-MX); COP/ARS con punto de miles (es-CO/es-AR). pt: pt-BR."""
    decimals = 0 if currency in _ZERO_DECIMAL and amount == amount.to_integral_value() else 2
    quantized = amount.quantize(Decimal(1) if decimals == 0 else Decimal("0.01"))
    integer, _, fraction = f"{quantized:f}".partition(".")
    comma_thousands = language == "es" and currency in {"MXN", "USD"}
    thousands, decimal_sep = (",", ".") if comma_thousands else (".", ",")
    number = _group(int(integer), thousands) + (decimal_sep + fraction if decimals else "")
    if language == "pt":
        return f"{currency} {number}"
    return f"US${number}" if currency == "USD" else f"${number} {currency}"


def format_date(value: date, pack: LanguagePack) -> str:
    months = pack.labels["months"]
    return f"{value.day} de {months[value.month - 1]} de {value.year}"


def format_fact(fact: VerifiedFact, language: Language, pack: LanguagePack) -> str:
    if fact.kind == "money":
        return format_money(Decimal(fact.value), fact.currency or "", language)
    if fact.kind == "date":
        return format_date(date.fromisoformat(fact.value), pack)
    if fact.kind == "tx_status":
        return pack.labels["tx_status"].get(fact.value, fact.value)
    if fact.kind == "dispute_status":
        return pack.labels["dispute_status"].get(fact.value, fact.value)
    return fact.value


def render(text: str, facts: dict[str, VerifiedFact], language: Language, pack: LanguagePack) -> str:
    """Los placeholders sin hecho verificado no deberían existir (el grounding check lo impide)."""

    def value(match: re.Match[str]) -> str:
        fact = facts.get(match.group(1))
        return format_fact(fact, language, pack) if fact else match.group(0)

    return PLACEHOLDER.sub(value, text)


def transaction_card(tx: TxRef, language: Language, pack: LanguagePack) -> TransactionCard:
    return TransactionCard(
        transaction_id=tx.transaction_id,
        date=format_date(tx.date.date(), pack),
        merchant=tx.merchant,
        amount=tx.amount,
        currency=tx.currency,
        amount_display=format_money(tx.amount, tx.currency, language),
    )


def candidate_cards(candidates: list[TxRef], language: Language, pack: LanguagePack) -> list[CandidateCard]:
    return [
        CandidateCard(option=i, **transaction_card(tx, language, pack).model_dump())
        for i, tx in enumerate(candidates, start=1)
    ]


def case_card(facts: dict[str, VerifiedFact], pack: LanguagePack, *, verified: bool) -> CaseCard | None:
    """Tarjeta del caso solo si el número y el estado salieron de la API (hechos verificados)."""
    case_id, status = facts.get("case.id"), facts.get("case.status")
    if case_id is None or status is None:
        return None
    return CaseCard(
        dispute_id=case_id.value,
        status=status.value,
        status_display=pack.labels["dispute_status"].get(status.value, status.value),
        verified=verified,
    )


def candidates_block(cards: list[CandidateCard], pack: LanguagePack) -> str:
    """Versión en texto de las tarjetas (el harness solo ve texto)."""
    lines = [f"{fill(pack.option_label, n=c.option)}: {c.date} · {c.merchant} · {c.amount_display}" for c in cards]
    return "\n".join(lines)


def disputes_block(disputes: list[DisputeRef], pack: LanguagePack) -> str:
    labels = pack.labels["dispute_status"]
    return "\n".join(f"• {d.dispute_id} · {labels.get(d.status, d.status)}" for d in disputes)
