"""§9.1 Tablas gold: OPS produce; SIM, DS y AG consumen.

Una fila de cada tabla gold valida contra su modelo. Los Parquet viven en `data/gold/<tabla>.parquet`
(muestra de 1.000 filas en `data/gold/sample/`) y se regeneran con `make data`.
Las columnas son las mínimas del brief; agregar una columna es compatible, quitar o renombrar requiere avisar.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from sofia_contracts.common import Country, Currency, Language
from sofia_contracts.router import Intent


class GoldCustomer(BaseModel):
    customer_id: str
    country: Country
    segment: str | None = None
    customer_status: str | None = None


class GoldTransaction(BaseModel):
    transaction_id: str
    customer_id: str
    product_id: str | None = None
    transaction_date: datetime
    amount: Decimal
    currency: Currency
    amount_usd: Decimal | None = None
    merchant_name: str | None = None
    transaction_status: str
    is_fraud: bool | None = None
    fraud_score: float | None = None


class GoldDispute(BaseModel):
    """Una fila de `complaints` (PQR) del cliente. No trae transaction_id: se liga por producto + fecha (§14)."""

    complaint_id: str
    customer_id: str
    affected_product_id: str | None = None
    category: str | None = None
    status: str | None = None
    priority: str | None = None
    creation_date: datetime
    claimed_amount: Decimal | None = None
    sla_breached: bool | None = None
    is_repeat_complainer: bool | None = None


class GoldIntentTraining(BaseModel):
    """Texto de cliente con label de intención. `label` es provisional hasta que DS publique su mapeo (§8.6);
    `label_source` conserva el campo crudo que lo originó para que DS pueda re-etiquetar sin re-correr el pipeline."""

    text: str
    label: Intent
    language: Language
    customer_id: str | None = None
    event_date: date | None = None
    source: str
    label_source: str | None = None


GOLD_TABLES: dict[str, type[BaseModel]] = {
    "gold_customers": GoldCustomer,
    "gold_transactions": GoldTransaction,
    "gold_disputes": GoldDispute,
    "gold_intent_training": GoldIntentTraining,
}
