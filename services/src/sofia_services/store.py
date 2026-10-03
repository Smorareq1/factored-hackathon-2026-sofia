"""Capa de datos y almacenamiento en memoria / DuckDB para bank-api (SIM).

Lee Parquet de GOLD_DIR si existen, y mantiene un seed determinístico de clientes demo
para asegurar que los tests, el harness y la demo funcionen sin dependencias externas.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sofia_contracts.bank_api import (
    Dispute,
    Role,
    Transaction,
    TransactionStatus,
)
from sofia_contracts.common import Country, Currency
from sofia_contracts.handoff import Handoff, HandoffFeedbackRecord
from sofia_services.settings import Settings, get_settings

logger = logging.getLogger("sofia_services.store")

USD_RATE: dict[str, Decimal] = {
    "MXN": Decimal("18.5"),
    "COP": Decimal("4000"),
    "ARS": Decimal("1000"),
    "USD": Decimal("1"),
}


@dataclass
class CustomerRecord:
    customer_id: str
    document_number: str
    country: Country
    label: str
    repeat_complainer: bool = False
    role: Role = "customer"


@dataclass
class TransactionRecord:
    tx: Transaction
    customer_id: str
    is_fraud: bool = False
    fraud_score: float = 0.05


@dataclass
class SessionRecord:
    customer_id: str
    role: Role
    country: Country | None
    expires_at: datetime


class BankStore:
    def __init__(
        self,
        settings: Settings | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._clock = clock or (lambda: datetime.now(UTC))
        self.customers: dict[str, CustomerRecord] = {}
        self.customers_by_doc: dict[str, CustomerRecord] = {}
        self.transactions: dict[str, TransactionRecord] = {}
        self.disputes: dict[str, Dispute] = {}
        self.handoffs: dict[str, Handoff] = {}
        self.feedback: dict[str, HandoffFeedbackRecord] = {}
        self.challenges: dict[str, tuple[str, str, datetime]] = {}  # challenge_id -> (customer_id, otp, expires_at)
        self.sessions: dict[str, SessionRecord] = {}  # token -> SessionRecord
        self.eligibilities: dict[str, tuple[str, str, datetime]] = {}  # eligibility_id -> (cid, tx_id, expires_at)
        self.idempotency: dict[str, Any] = {}
        self._seq: int = 0

        self.seed_demo_data()
        self.load_gold_parquet_if_available()

    @property
    def now(self) -> datetime:
        return self._clock()

    def next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self.now.year}-{self._seq:06d}"

    def seed_demo_data(self) -> None:
        """Clientes demo y transacciones base compatibles con el brief y fake_bank."""
        now = self.now
        demo_custs = [
            CustomerRecord("C90000001", "MX-DEMO-001", "MX", "Ana · MX · auto, aclaración y denegaciones"),
            CustomerRecord("C90000002", "CO-DEMO-002", "CO", "Bruno · CO · monto alto (POL-6)"),
            CustomerRecord(
                "C90000003", "AR-DEMO-003", "AR", "Carla · AR · reincidente (POL-6)", repeat_complainer=True
            ),
            CustomerRecord("C90000004", "AR-DEMO-004", "AR", "João · AR · habla portugués"),
            CustomerRecord("A90000001", "AGENTE-DEMO", "MX", "Agente humano · consola", role="agent"),
        ]
        for c in demo_custs:
            self.customers[c.customer_id] = c
            self.customers_by_doc[c.document_number] = c

        def make_tx(
            tx_id: str, days_ago: int, amount: str, currency: Currency, merchant: str, status: TransactionStatus
        ) -> Transaction:
            val = Decimal(amount)
            tx_date = (now - timedelta(days=days_ago)).replace(hour=13, minute=20, second=0, microsecond=0)
            usd_val = (val / USD_RATE[currency]).quantize(Decimal("0.01"))
            return Transaction(
                transaction_id=tx_id,
                transaction_date=tx_date,
                amount=val,
                currency=currency,
                amount_usd=usd_val,
                merchant_name=merchant,
                transaction_status=status,
                channel="card_present" if merchant in {"OXXO", "Éxito"} else "online",
                transaction_type="purchase",
            )

        rows: list[tuple[str, str, int, str, Currency, str, TransactionStatus, bool, float]] = [
            ("C90000001", "TX-MX-0001", 2, "349.00", "MXN", "Rappi", "Approved", False, 0.04),
            ("C90000001", "TX-MX-0002", 5, "189.50", "MXN", "Cinépolis", "Approved", False, 0.03),
            ("C90000001", "TX-MX-0003", 5, "189.50", "MXN", "Cinépolis", "Approved", False, 0.05),
            ("C90000001", "TX-MX-0004", 10, "15800.00", "MXN", "Liverpool", "Approved", False, 0.10),
            ("C90000001", "TX-MX-0005", 12, "520.00", "MXN", "OXXO", "Declined", False, 0.02),
            ("C90000001", "TX-MX-0006", 150, "899.00", "MXN", "Amazon MX", "Approved", False, 0.03),
            ("C90000001", "TX-MX-0007", 20, "1250.00", "MXN", "Walmart", "Approved", False, 0.06),
            ("C90000001", "TX-MX-0008", 3, "2100.00", "MXN", "Uber", "Approved", True, 0.91),
            ("C90000001", "TX-MX-0009", 1, "89.00", "MXN", "Spotify", "Approved", False, 0.01),
            ("C90000002", "TX-CO-0001", 4, "85000", "COP", "Éxito", "Approved", False, 0.04),
            ("C90000002", "TX-CO-0002", 6, "3200000", "COP", "Falabella", "Approved", False, 0.20),
            ("C90000003", "TX-AR-0001", 3, "25000", "ARS", "Mercado Libre", "Approved", False, 0.05),
            ("C90000004", "TX-AR-0101", 2, "18500", "ARS", "Mercado Libre", "Approved", False, 0.03),
            ("C90000004", "TX-AR-0102", 7, "920000", "ARS", "Frávega", "Approved", False, 0.15),
            ("C90000004", "TX-AR-0103", 4, "4500", "ARS", "Netflix", "Approved", False, 0.02),
            ("C90000004", "TX-AR-0104", 4, "4500", "ARS", "Netflix", "Approved", False, 0.02),
        ]
        for cid, tx_id, days, amt, curr, merch, st, fraud, score in rows:
            self.transactions[tx_id] = TransactionRecord(
                tx=make_tx(tx_id, days, amt, curr, merch, st),
                customer_id=cid,
                is_fraud=fraud,
                fraud_score=score,
            )

        # POL-4: disputa ya abierta sobre TX-MX-0007
        existing_dsp = Dispute(
            dispute_id="DSP-2026-000900",
            transaction_id="TX-MX-0007",
            customer_id="C90000001",
            status="open",
            customer_claim="not_received",
            created_at=now - timedelta(days=15),
        )
        self.disputes[existing_dsp.dispute_id] = existing_dsp

    def load_gold_parquet_if_available(self) -> None:
        """Carga tablas gold vía DuckDB si están presentes en GOLD_DIR."""
        gold_dir = Path(self.settings.GOLD_DIR)
        cust_pq = gold_dir / "gold_customers.parquet"
        tx_pq = gold_dir / "gold_transactions.parquet"
        dsp_pq = gold_dir / "gold_disputes.parquet"

        if not (cust_pq.exists() and tx_pq.exists()):
            return

        try:
            import duckdb

            con = duckdb.connect()
            # Cargar clientes reales (CLI-...)
            cust_rows = con.execute(
                "SELECT customer_id, country, segment, customer_status FROM read_parquet(?)",
                [str(cust_pq)],
            ).fetchall()
            for cid, country, seg, _status in cust_rows:
                if cid not in self.customers:
                    c_record = CustomerRecord(
                        customer_id=str(cid),
                        document_number=str(cid),
                        country=str(country).upper(),  # type: ignore
                        label=f"{cid} · {country} · {seg or ''}",
                        repeat_complainer=False,
                    )
                    self.customers[c_record.customer_id] = c_record
                    self.customers_by_doc[c_record.document_number] = c_record

            # Cargar disputas existentes para reincidentes y POL-4
            if dsp_pq.exists():
                dsp_rows = con.execute(
                    """
                    SELECT complaint_id, customer_id, affected_product_id, status,
                           creation_date, is_repeat_complainer
                    FROM read_parquet(?)
                    """,
                    [str(dsp_pq)],
                ).fetchall()
                for _comp_id, cid, _prod_id, _st, _c_date, repeat in dsp_rows:
                    if cid in self.customers and repeat:
                        self.customers[cid].repeat_complainer = True

            # Cargar transacciones reales
            tx_rows = con.execute(
                """
                SELECT transaction_id, customer_id, product_id, transaction_date, amount,
                       currency, amount_usd, merchant_name, transaction_status, is_fraud, fraud_score
                FROM read_parquet(?)
                """,
                [str(tx_pq)],
            ).fetchall()
            for tid, cid, _pid, tdate, amt, curr, amt_usd, merch, tstatus, is_fraud, score in tx_rows:
                if tid not in self.transactions:
                    parsed_curr = str(curr).upper()
                    if parsed_curr not in ("MXN", "COP", "ARS", "USD"):
                        parsed_curr = "USD"
                    parsed_usd = Decimal(str(amt_usd)) if amt_usd is not None else Decimal(str(amt))
                    tx_obj = Transaction(
                        transaction_id=str(tid),
                        transaction_date=tdate if isinstance(tdate, datetime) else datetime.fromisoformat(str(tdate)),
                        amount=Decimal(str(amt)),
                        currency=parsed_curr,  # type: ignore
                        amount_usd=parsed_usd,
                        merchant_name=str(merch) if merch else "Comercio",
                        transaction_status=str(tstatus),  # type: ignore
                        channel="online",
                        transaction_type="purchase",
                    )
                    self.transactions[tx_obj.transaction_id] = TransactionRecord(
                        tx=tx_obj,
                        customer_id=str(cid),
                        is_fraud=bool(is_fraud) if is_fraud is not None else False,
                        fraud_score=float(score) if score is not None else 0.05,
                    )
        except Exception as exc:
            logger.warning("No se pudieron cargar archivos parquet de GOLD_DIR: %s", exc)

    def expire_all_sessions(self) -> None:
        """Invalida todas las sesiones activas (para testing de expiración)."""
        for s in self.sessions.values():
            s.expires_at = self.now - timedelta(seconds=1)


_store_instance: BankStore | None = None


def get_store() -> BankStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = BankStore()
    return _store_instance


def reset_store() -> BankStore:
    global _store_instance
    _store_instance = BankStore()
    return _store_instance
