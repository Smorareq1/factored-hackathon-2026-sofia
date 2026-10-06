"""Rutas de consulta de transacciones con control estricto de permisos (POL-1, REQ-10)."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from sofia_contracts.bank_api import Transaction, TransactionList
from sofia_services.audit.logger import audit_trail
from sofia_services.auth.service import require_customer
from sofia_services.faults.manager import fault_manager
from sofia_services.store import BankStore, SessionRecord, get_store

router = APIRouter(tags=["transactions"])


@router.get("/transactions")
def list_transactions(
    session: Annotated[SessionRecord, Depends(require_customer)],
    store: Annotated[BankStore, Depends(get_store)],
    since: date | None = None,
    until: date | None = None,
    merchant: str | None = None,
    amount: Decimal | None = None,
    limit: Annotated[int, Query(le=200)] = 50,
) -> TransactionList:
    fault_manager.check_endpoint("GET", "/transactions")

    # Filtra transacciones que pertenecen EXCLUSIVAMENTE al cliente autenticado
    items = [r.tx for r in store.transactions.values() if r.customer_id == session.customer_id]

    if since:
        items = [t for t in items if t.transaction_date.date() >= since]
    if until:
        items = [t for t in items if t.transaction_date.date() <= until]
    if merchant:
        items = [t for t in items if merchant.casefold() in t.merchant_name.casefold()]
    if amount is not None:
        items = [t for t in items if abs(t.amount - amount) < Decimal("0.01")]

    items.sort(key=lambda t: t.transaction_date, reverse=True)
    return TransactionList(items=items[:limit])


@router.get("/transactions/{transaction_id}")
def get_transaction(
    transaction_id: str,
    session: Annotated[SessionRecord, Depends(require_customer)],
    store: Annotated[BankStore, Depends(get_store)],
) -> Transaction:
    fault_manager.check_endpoint("GET", f"/transactions/{transaction_id}")

    row = store.transactions.get(transaction_id)
    # POL-1: Si no existe o no pertenece al cliente, devuelve 404 idéntico sin revelar si existe
    if row is None or row.customer_id != session.customer_id:
        audit_trail.record(
            "tx_access_denied",
            customer_id=session.customer_id,
            rule_id="POL-1",
            transaction_id=transaction_id,
        )
        raise HTTPException(status_code=404, detail="not_found")

    return row.tx
