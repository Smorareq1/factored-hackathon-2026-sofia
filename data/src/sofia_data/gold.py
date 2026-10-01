"""silver -> gold: tablas de §9.1 (gold_customers, gold_transactions, gold_disputes, gold_intent_training).

Salidas:
- `data/gold/<tabla>.parquet`: tabla completa.
- `data/gold/sample/<tabla>.parquet`: muestra determinística de ≤1.000 filas por tabla, coherente por cliente
  (los clientes de la muestra son los dueños de las transacciones muestreadas), para stubs y tests de SIM/DS/AG.
"""

import logging

import duckdb

from sofia_data.settings import Settings

log = logging.getLogger(__name__)

SAMPLE_ROWS = 1000

# Mapeo PROVISIONAL de razón de contacto -> intención del router (§8.6). DS es dueño del mapeo final
# (ml/src/sofia_ml/labeling.py); `label_source` conserva el texto crudo para re-etiquetar sin re-correr.
# Orden importa: la primera regla que matchea gana.
_LABEL_RULES: tuple[tuple[str, str], ...] = (
    ("needs_human", r"supervisor|queja formal|abogad|legal|amenaz|escala"),
    ("dispute_status", r"estado.*(disputa|reclamo|caso|queja)|seguimiento|n[uú]mero de caso"),
    ("dispute_new", r"disput|desconoc|no reconoc|fraude|cargo.*(indebido|no autorizado|duplicado)|contracargo|reclamo"),
    ("transaction_inquiry", r"transacci|movimiento|compra|cargo|pago|transferencia|consulta de saldo|extracto"),
)


def _label_case(expr: str) -> str:
    whens = " ".join(f"WHEN regexp_matches({expr}, '{pattern}') THEN '{label}'" for label, pattern in _LABEL_RULES)
    return f"CASE {whens} ELSE 'out_of_scope' END"


def _silver(settings: Settings, table: str) -> str:
    return f"read_parquet('{settings.silver / (table + '.parquet')}')"


def _has(settings: Settings, *tables: str) -> bool:
    return all((settings.silver / f"{t}.parquet").exists() for t in tables)


GOLD_SQL = {
    "gold_customers": (
        ("customers",),
        """SELECT customer_id, country, segment, customer_status
           FROM {customers} WHERE country IN ('MX', 'CO', 'AR')""",
    ),
    "gold_transactions": (
        ("transactions",),
        """SELECT transaction_id, customer_id, product_id, transaction_date, amount, currency, amount_usd,
                  merchant_name, transaction_status, is_fraud, fraud_score
           FROM {transactions}
           WHERE currency IN ('MXN', 'COP', 'ARS', 'USD')
             AND transaction_status IN ('Approved', 'Declined', 'Pending', 'Reversed')""",
    ),
    "gold_disputes": (
        ("complaints",),
        """SELECT complaint_id, customer_id, affected_product_id, category, status, priority, creation_date,
                  claimed_amount, sla_breached, is_repeat_complainer
           FROM {complaints}""",
    ),
    "gold_intent_training": (
        ("call_transcripts", "call_center_interactions"),
        """WITH t AS (
             SELECT coalesce(nullif(trim(tr.customer_text), ''), tr.full_text) AS text,
                    CASE WHEN lower(coalesce(tr.detected_language, 'es')) SIMILAR TO '(pt|por|portugu).*' THEN 'pt'
                         WHEN lower(coalesce(tr.detected_language, 'es')) SIMILAR TO '(es|spa|espa).*' THEN 'es'
                    END AS language,
                    coalesce(tr.customer_id, i.customer_id) AS customer_id,
                    CAST(i.interaction_date AS DATE) AS event_date,
                    concat_ws(' | ', i.reason_category, i.contact_reason, tr.detected_intents) AS label_source
             FROM {call_transcripts} tr
             LEFT JOIN {call_center_interactions} i USING (interaction_id)
           )
           SELECT text, {label} AS label, language, customer_id, event_date,
                  'call_transcripts' AS source, label_source
           FROM t WHERE text IS NOT NULL AND language IS NOT NULL""",
    ),
}


def silver_to_gold(settings: Settings) -> dict[str, int]:
    settings.gold.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    counts = {}
    for name, (deps, sql) in GOLD_SQL.items():
        if not _has(settings, *deps):
            log.warning("gold: %s omitida, falta silver de %s", name, deps)
            continue
        label = _label_case("lower(label_source || ' ' || text)")
        query = sql.format(**{d: _silver(settings, d) for d in deps}, label=label)
        out = settings.gold / f"{name}.parquet"
        con.execute(f"COPY ({query}) TO '{out}' (FORMAT parquet)")
        counts[name] = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
        log.info("silver -> gold: %s (%d filas)", name, counts[name])
    con.close()
    write_sample(settings)
    return counts


def write_sample(settings: Settings, n: int = SAMPLE_ROWS) -> dict[str, int]:
    """Muestra determinística (orden por hash de la llave), coherente por cliente."""
    out_dir = settings.gold / "sample"
    out_dir.mkdir(parents=True, exist_ok=True)
    g = {t: f"read_parquet('{settings.gold / (t + '.parquet')}')" for t in GOLD_SQL}
    present = {t for t in GOLD_SQL if (settings.gold / f"{t}.parquet").exists()}
    con = duckdb.connect()
    queries = {}
    if "gold_transactions" in present:
        queries["gold_transactions"] = f"SELECT * FROM {g['gold_transactions']} ORDER BY hash(transaction_id) LIMIT {n}"
        con.execute(f"CREATE TEMP TABLE sample_tx AS {queries['gold_transactions']}")
        sample_customers = "(SELECT DISTINCT customer_id FROM sample_tx)"
    else:
        sample_customers = None
    if "gold_customers" in present:
        where = f"WHERE customer_id IN {sample_customers}" if sample_customers else ""
        queries["gold_customers"] = f"SELECT * FROM {g['gold_customers']} {where} ORDER BY hash(customer_id) LIMIT {n}"
    if "gold_disputes" in present:
        where = f"WHERE customer_id IN {sample_customers}" if sample_customers else ""
        queries["gold_disputes"] = f"SELECT * FROM {g['gold_disputes']} {where} ORDER BY hash(complaint_id) LIMIT {n}"
    if "gold_intent_training" in present:
        queries["gold_intent_training"] = f"SELECT * FROM {g['gold_intent_training']} ORDER BY hash(text) LIMIT {n}"
    counts = {}
    for name, query in queries.items():
        out = out_dir / f"{name}.parquet"
        con.execute(f"COPY ({query}) TO '{out}' (FORMAT parquet)")
        counts[name] = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    con.close()
    log.info("gold sample: %s", counts)
    return counts
