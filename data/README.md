# data/ — owner: OPS

Repeatable pipeline for the LATAM Bank Dataset (REQ-12): **S3 → raw → bronze → silver → gold**, with schema contracts,
quality checks, lineage and a freshness policy. DuckDB does the heavy lifting; everything is stored as Parquet.

```bash
make data           # S3 if .env has AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / S3_BUCKET; otherwise it uses data/raw
make data-fixture   # same pipeline over synthetic data (team_generated) in data/fixture/, no S3
```

Without Docker, from data already in `data/raw`: `uv run --package sofia-data python -m sofia_data.pipeline --source local`
(reads only `data/raw`, never touches S3).

No data is versioned (CON-03): `data/raw`, `bronze`, `silver`, `gold`, `_state` and `fixture` are in `.gitignore`.

## Stages

| Stage | What it does | Output |
|---|---|---|
| S3 → raw | Mirrors only the objects of the tables in use (§7); downloads again if the ETag changed | `raw/<S3 key>` |
| raw → bronze | Faithful copy (everything as text) + `_source_file`, `_ingested_at`, `_run_id`. Each file is ingested **once** | `bronze/<table>/ingest_date=YYYY-MM-DD/*.parquet` |
| bronze → silver | Per-table contract ([contracts.py](src/sofia_data/contracts.py)): normalized names + aliases, types with `TRY_CAST`, canonical categoricals, dedup by key (the most recent and complete wins), quarantine of null required fields and FK orphans | `silver/<table>.parquet`, `silver/_quarantine/<table>.parquet` (with `_reason`) |
| silver → gold | §9.1 tables validated against [`sofia_contracts.gold`](../contracts/src/sofia_contracts/gold.py) | `gold/<table>.parquet` + `gold/sample/` (≤1,000 rows, consistent per customer) |

Silver and gold are fully recomputed from bronze on every run: re-running is idempotent.

## Quality

- **Blocking** (exit 1, the report is still written): >10% duplicates, >10% in quarantine, gold that breaks the contract.
- **Warnings**: contract columns missing in the source, values that do not cast, optional columns >50% null.
- Report per run in `_state/reports/<run_id>.json` (`latest.json` = the last one): rows per stage, duplicates,
  quarantine by reason, null rate per column, renamed / new / missing columns, date range.

## Schema evolution

Bronze is read with `union_by_name`, so files with new or missing columns coexist. In silver, a known rename
(`merchant` → `merchant_name`) is declared in the contract's `aliases` and combined with `coalesce`; columns the
contract does not know are kept and reported in `unexpected_columns`.

## Lineage and freshness

- `_state/lineage.jsonl`: one line per run with the input files, the bronze Parquet written, rows in silver and gold,
  the code version (`git rev-parse` or `GIT_SHA`) and whether it passed the checks. Every silver row keeps
  `_source_file` and `_run_id`.
- **Freshness**: a table is `fresh` if its last ingestion is < 24 h old; otherwise `stale`. It does not block because
  the published dataset is static (it ends on 2026-06-17); the pipeline is designed to run daily and is incremental.
- **Late arrivals**: records ingested in the run with an event date ≤ the previous run's watermark
  (`_state/watermarks.json`). They are accepted and incorporated; they are counted in the report's `late_arrivals`.

## Intent labels

`gold_intent_training.label` uses a **provisional** keyword mapping over `reason_category`, `contact_reason` and
`detected_intents` ([gold.py](src/sofia_data/gold.py)); `label_source` keeps the raw text. DS audited these labels and
they are not usable for intents (see findings below), so the router is trained on a team-generated corpus instead
([ml/reports/corpus_audit.md](../ml/reports/corpus_audit.md)).

## Findings from the first real run (2026-10-01)

- Bucket: `data/<table>/year=/month=/day=/<table>_YYYYMMDD.csv` (1,097 days) + `data/customers.csv`, `products.csv`;
  there is also a `data_backup_20260831/` that is ignored (`S3_PREFIX=data/`). First run ~23 min (mostly download);
  re-running without new files ~30 s.
- Rows in gold: 150,000 customers, 4,425,008 transactions, 67,095 complaints, 171,321 intent texts. A second, local
  run on Windows (2026-10-04) produced identical counts.
- This version has no duplicates by key, no null keys and no FK orphans; the dirt is in optional columns:
  `merchant_name` 77% null, `amount_usd` 57%, `claimed_amount` 68%, `complaints.origin_interaction_id` 100%.
  `amount_usd` is empty on every USD transaction (they are already in USD), which explains most of its nulls.
- `call_transcripts.detected_intents` is almost always `consulta_general` and the texts are templates: the provisional
  label comes out almost entirely `out_of_scope` / `transaction_inquiry`.
- Complaints do not link to their transactions: the affected product never belongs to the complainant.
- There are no MXN transactions: Mexico operates in USD in this dataset.
