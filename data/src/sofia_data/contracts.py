"""Contratos de schema de silver (REQ-12): tipos, llave primaria, obligatorios, FKs y alias por evolución de schema.

Solo se procesan las tablas que usa la solución (§7). Cada columna del contrato sale tipada en silver;
las columnas que el contrato no conoce se reportan como drift y se conservan tal cual.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ForeignKey:
    column: str
    ref_table: str
    ref_column: str


@dataclass(frozen=True)
class TableContract:
    name: str
    columns: dict[str, str]  # columna -> tipo DuckDB
    primary_key: str
    required: tuple[str, ...]
    event_date: str | None = None  # columna para freshness, llegadas tardías y partición
    foreign_keys: tuple[ForeignKey, ...] = ()
    # Nombres alternativos vistos en versiones viejas o nuevas del schema -> nombre del contrato
    aliases: dict[str, str] = field(default_factory=dict)
    # Valores categóricos que se normalizan sin importar mayúsculas: columna -> valores canónicos
    enums: dict[str, tuple[str, ...]] = field(default_factory=dict)


CUSTOMERS = TableContract(
    name="customers",
    columns={
        "customer_id": "VARCHAR",
        "document_number": "VARCHAR",
        "country": "VARCHAR",
        "segment": "VARCHAR",
        "customer_status": "VARCHAR",
        "detected_accent": "VARCHAR",
    },
    primary_key="customer_id",
    required=("customer_id", "country"),
    aliases={"client_id": "customer_id", "pais": "country", "status": "customer_status"},
    enums={"country": ("MX", "CO", "AR")},
)

PRODUCTS = TableContract(
    name="products",
    columns={
        "product_id": "VARCHAR",
        "customer_id": "VARCHAR",
        "product_type": "VARCHAR",
        "product_status": "VARCHAR",
    },
    primary_key="product_id",
    required=("product_id", "customer_id"),
    foreign_keys=(ForeignKey("customer_id", "customers", "customer_id"),),
)

TRANSACTIONS = TableContract(
    name="transactions",
    columns={
        "transaction_id": "VARCHAR",
        "transaction_date": "TIMESTAMP",
        "customer_id": "VARCHAR",
        "product_id": "VARCHAR",
        "transaction_type": "VARCHAR",
        "transaction_category": "VARCHAR",
        "amount": "DECIMAL(18,2)",
        "currency": "VARCHAR",
        "amount_usd": "DECIMAL(18,2)",
        "channel": "VARCHAR",
        "merchant_name": "VARCHAR",
        "transaction_status": "VARCHAR",
        "is_fraud": "BOOLEAN",
        "fraud_score": "DOUBLE",
    },
    primary_key="transaction_id",
    required=("transaction_id", "customer_id", "transaction_date", "amount", "currency", "transaction_status"),
    event_date="transaction_date",
    foreign_keys=(ForeignKey("customer_id", "customers", "customer_id"),),
    aliases={"merchant": "merchant_name", "status": "transaction_status"},
    enums={
        "transaction_status": ("Approved", "Declined", "Pending", "Reversed"),
        "currency": ("MXN", "COP", "ARS", "USD"),
    },
)

COMPLAINTS = TableContract(
    name="complaints",
    columns={
        "complaint_id": "VARCHAR",
        "creation_date": "TIMESTAMP",
        "customer_id": "VARCHAR",
        "case_type": "VARCHAR",
        "category": "VARCHAR",
        "subcategory": "VARCHAR",
        "reception_channel": "VARCHAR",
        "affected_product_id": "VARCHAR",
        "origin_interaction_id": "VARCHAR",
        "description": "VARCHAR",
        "claimed_amount": "DECIMAL(18,2)",
        "priority": "VARCHAR",
        "status": "VARCHAR",
        "sla_breached": "BOOLEAN",
        "resolution_days": "INTEGER",
        "compensation_granted": "BOOLEAN",
        "is_repeat_complainer": "BOOLEAN",
    },
    primary_key="complaint_id",
    required=("complaint_id", "customer_id", "creation_date"),
    event_date="creation_date",
    foreign_keys=(ForeignKey("customer_id", "customers", "customer_id"),),
)

CALL_CENTER_INTERACTIONS = TableContract(
    name="call_center_interactions",
    columns={
        "interaction_id": "VARCHAR",
        "interaction_date": "TIMESTAMP",
        "customer_id": "VARCHAR",
        "agent_id": "VARCHAR",
        "channel": "VARCHAR",
        "contact_reason": "VARCHAR",
        "reason_category": "VARCHAR",
        "duration_seconds": "INTEGER",
        "wait_time_seconds": "INTEGER",
        "was_resolved": "BOOLEAN",
        "requires_followup": "BOOLEAN",
        "detected_sentiment": "VARCHAR",
        "was_escalated": "BOOLEAN",
    },
    primary_key="interaction_id",
    required=("interaction_id", "customer_id"),
    event_date="interaction_date",
    foreign_keys=(ForeignKey("customer_id", "customers", "customer_id"),),
)

CALL_TRANSCRIPTS = TableContract(
    name="call_transcripts",
    columns={
        "interaction_id": "VARCHAR",
        "full_text": "VARCHAR",
        "customer_text": "VARCHAR",
        "detected_language": "VARCHAR",
        "detected_intents": "VARCHAR",
        "main_topics": "VARCHAR",
        "mentioned_entities": "VARCHAR",
    },
    primary_key="interaction_id",
    required=("interaction_id",),
    foreign_keys=(ForeignKey("interaction_id", "call_center_interactions", "interaction_id"),),
)

# Orden de procesamiento: las tablas referenciadas por FK van primero.
CONTRACTS: dict[str, TableContract] = {
    c.name: c for c in (CUSTOMERS, PRODUCTS, TRANSACTIONS, COMPLAINTS, CALL_CENTER_INTERACTIONS, CALL_TRANSCRIPTS)
}
