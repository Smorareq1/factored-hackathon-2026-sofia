"""El pipeline completo sobre el fixture sintético: contratos, calidad, idempotencia, llegadas tardías y muestra."""

import json

import duckdb
import pytest

from sofia_contracts.gold import GOLD_TABLES
from sofia_data import fixture
from sofia_data.ingest import table_for_key
from sofia_data.pipeline import run
from sofia_data.settings import Settings


@pytest.fixture(scope="module")
def first_run(tmp_path_factory):
    settings = Settings.from_env(tmp_path_factory.mktemp("data"))
    return settings, run(settings, source="fixture")


def _gold(settings, table: str) -> str:
    return f"read_parquet('{settings.gold / (table + '.parquet')}')"


def _count(path) -> int:
    return duckdb.sql(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]


def test_run_passes_quality_checks(first_run):
    _, report = first_run
    assert report["ok"], report["failures"]


def test_gold_tables_match_contract(first_run):
    settings, report = first_run
    for name, model in GOLD_TABLES.items():
        path = settings.gold / f"{name}.parquet"
        cols = [r[0] for r in duckdb.sql(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()]
        assert cols == list(model.model_fields), name
        assert report["gold_contract"][name]["invalid_rows"] == 0


def test_dedup_removes_duplicates_and_keys_are_unique(first_run):
    settings, report = first_run
    assert report["silver"]["transactions"]["duplicates_removed"] > 0
    dupes = duckdb.sql(
        f"SELECT count(*) - count(DISTINCT transaction_id) FROM {_gold(settings, 'gold_transactions')}"
    ).fetchone()[0]
    assert dupes == 0


def test_fk_orphans_go_to_quarantine(first_run):
    settings, report = first_run
    assert report["silver"]["transactions"]["quarantined"] == {"fk_orphan:customer_id": 5}
    assert _count(settings.quarantine / "transactions.parquet") == 5


def test_schema_evolution_is_absorbed(first_run):
    settings, report = first_run
    tx = report["silver"]["transactions"]
    assert tx["renamed_columns"] == {"merchant": "merchant_name"}
    assert tx["unexpected_columns"] == ["device_type"]
    # el lote 2 traía status en minúsculas y otra columna de comercio: ambos quedan normalizados en gold
    statuses = {
        r[0]
        for r in duckdb.sql(
            f"SELECT DISTINCT transaction_status FROM read_parquet('{settings.gold}/gold_transactions.parquet')"
        ).fetchall()
    }
    assert statuses <= {"Approved", "Declined", "Pending", "Reversed"}
    merchant_null = duckdb.sql(
        f"SELECT avg(CAST(merchant_name IS NULL AS DOUBLE)) FROM {_gold(settings, 'gold_transactions')}"
    ).fetchone()[0]
    assert merchant_null < 0.15


def test_sample_is_capped_and_consistent(first_run):
    settings, _ = first_run
    sample = settings.gold / "sample"
    assert _count(sample / "gold_transactions.parquet") == 1000
    orphans = duckdb.sql(
        f"""SELECT count(*) FROM read_parquet('{sample}/gold_transactions.parquet') t
            WHERE t.customer_id NOT IN (SELECT customer_id FROM read_parquet('{sample}/gold_customers.parquet'))"""
    ).fetchone()[0]
    assert orphans == 0


def test_intent_labels_are_router_classes(first_run):
    settings, _ = first_run
    labels = {
        r[0]
        for r in duckdb.sql(
            f"SELECT DISTINCT label FROM read_parquet('{settings.gold}/gold_intent_training.parquet')"
        ).fetchall()
    }
    assert labels == {"dispute_new", "dispute_status", "transaction_inquiry", "out_of_scope", "needs_human"}


def test_rerun_is_incremental_and_counts_late_arrivals(tmp_path):
    settings = Settings.from_env(tmp_path)
    first = run(settings, source="fixture")
    again = run(settings, source="local")
    assert again["bronze_files"] == []  # nada nuevo: no se re-ingiere
    assert again["gold"] == first["gold"]

    fixture.write_late_batch(settings.raw)
    late = run(settings, source="local")
    assert late["ok"], late["failures"]
    assert [f["source"] for f in late["bronze_files"]] == ["transactions/late/transactions_late_2023.csv"]
    assert late["late_arrivals"]["transactions"] == 20
    assert late["gold"]["gold_transactions"] == first["gold"]["gold_transactions"] + 20
    lineage = [json.loads(line) for line in (settings.state / "lineage.jsonl").read_text().splitlines()]
    assert len(lineage) == 3


@pytest.mark.parametrize(
    ("key", "table"),
    [
        ("transactions/date=2024/part-1.csv", "transactions"),
        ("raw/call_center_interactions_2025.parquet", "call_center_interactions"),
        ("call_transcripts/x.csv", "call_transcripts"),
        ("digital_events/x.csv", None),
    ],
)
def test_table_for_key(key, table):
    assert table_for_key(key) == table
