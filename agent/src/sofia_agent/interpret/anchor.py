"""Anclaje de la transacción: de lo que dijo el cliente a UNA transacción real de su cuenta (vía API).

Solo se usan datos devueltos por `GET /transactions`; el filtrado por monto, comercio y duplicados es
determinístico. 0 candidatos → aclarar; 1 → seleccionada; 2..N → aclarar con tarjetas; más → pedir datos.
"""

import difflib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sofia_agent.facts import to_ref, tx_facts
from sofia_agent.purpose import InterpretConfig
from sofia_agent.state import Slots, TxRef, VerifiedFact
from sofia_agent.text import fold, words
from sofia_agent.tools.bank import BankClient
from sofia_contracts.bank_api import Transaction


@dataclass
class AnchorResult:
    selected: TxRef | None = None
    candidates: list[TxRef] = field(default_factory=list)
    clarify_reason: str | None = None
    unverified_tx_id: str | None = None
    facts: list[VerifiedFact] = field(default_factory=list)
    merchant_from_text: str | None = None


def merchant_matches(said: str, actual: str) -> bool:
    a, b = fold(said).strip(), fold(actual).strip()
    if not a:
        return False
    if a in b or b in a:
        return True
    tokens_a = {t for t in words(a) if len(t) >= 4}
    if tokens_a & set(words(b)):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def merchant_mentioned(message: str, merchant: str) -> bool:
    folded_message = fold(message)
    name = fold(merchant)
    if re.search(rf"\b{re.escape(name)}\b", folded_message):
        return True
    significant = [t for t in words(name) if len(t) >= 4]
    return bool(significant) and re.search(rf"\b{re.escape(significant[0])}\b", folded_message) is not None


def _amount_matches(tx: Transaction, slots: Slots, tolerance_pct: float) -> bool:
    assert slots.amount is not None
    tolerance = max(slots.amount * Decimal(str(tolerance_pct)) / 100, Decimal("0.5"))
    if slots.currency == "USD" and tx.currency != "USD":
        return abs(tx.amount_usd - slots.amount) <= tolerance
    return abs(tx.amount - slots.amount) <= tolerance


def _duplicates(items: list[Transaction]) -> list[Transaction]:
    def key(t: Transaction) -> tuple[str, Decimal, date]:
        return t.merchant_name, t.amount, t.transaction_date.date()

    counts = Counter(key(t) for t in items)
    return [t for t in items if counts[key(t)] > 1]


def has_search_filters(slots: Slots) -> bool:
    return any([slots.amount, slots.merchant, slots.date_from, slots.date_to, slots.customer_claim == "duplicate"])


async def anchor_transaction(
    *,
    bank: BankClient,
    slots: Slots,
    message: str,
    today: date,
    config: InterpretConfig,
    turn: int,
    previous_candidates: list[TxRef],
    selection: int | None,
) -> AnchorResult:
    # 1. El cliente eligió una de las opciones listadas: se relee para anclarla con su fuente.
    if selection is not None and previous_candidates:
        chosen = previous_candidates[selection - 1]
        tx = await bank.get_transaction(chosen.transaction_id)
        if tx is None:
            return AnchorResult(clarify_reason="tx_not_found")
        ref = to_ref(tx)
        return AnchorResult(
            selected=ref, facts=tx_facts(ref, source=f"GET /transactions/{ref.transaction_id}", turn=turn)
        )

    # 2. El cliente dio un ID: si la API no lo devuelve, eligibility decide (POL-1, sin revelar si existe).
    if slots.transaction_id:
        tx = await bank.get_transaction(slots.transaction_id)
        if tx is None:
            return AnchorResult(unverified_tx_id=slots.transaction_id)
        ref = to_ref(tx)
        return AnchorResult(
            selected=ref, facts=tx_facts(ref, source=f"GET /transactions/{ref.transaction_id}", turn=turn)
        )

    # 3. Búsqueda por filtros, o se intenta con el comercio mencionado en el texto.
    since = slots.date_from or today - timedelta(days=config.default_lookback_days)
    until = slots.date_to or today
    if not has_search_filters(slots):
        items = await bank.list_transactions(since=since, until=until, limit=100)
        mentioned = [t for t in items if merchant_mentioned(message, t.merchant_name)]
        if not mentioned:
            return AnchorResult(clarify_reason="tx_missing_details")
        items, merchant_from_text = mentioned, mentioned[0].merchant_name
    else:
        items = await bank.list_transactions(since=since, until=until, limit=100)
        merchant_from_text = None
        if slots.merchant:
            items = [t for t in items if merchant_matches(slots.merchant, t.merchant_name)]
        else:
            mentioned = [t for t in items if merchant_mentioned(message, t.merchant_name)]
            if mentioned:
                items, merchant_from_text = mentioned, mentioned[0].merchant_name

    if slots.amount is not None:
        items = [t for t in items if _amount_matches(t, slots, config.amount_tolerance_pct)]
    if slots.customer_claim == "duplicate":
        items = _duplicates(items) or items

    refs = [to_ref(t) for t in items]
    if not refs:
        return AnchorResult(clarify_reason="tx_not_found", merchant_from_text=merchant_from_text)
    if len(refs) == 1:
        return AnchorResult(
            selected=refs[0],
            facts=tx_facts(refs[0], source="GET /transactions", turn=turn),
            merchant_from_text=merchant_from_text,
        )
    if len(refs) <= config.max_candidates_listed:
        return AnchorResult(candidates=refs, clarify_reason="candidates", merchant_from_text=merchant_from_text)
    return AnchorResult(clarify_reason="tx_too_many", merchant_from_text=merchant_from_text)
