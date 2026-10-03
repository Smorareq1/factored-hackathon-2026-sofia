"""Utilidades compartidas por los notebooks de analysis/ (DS). Se importa con `from common import *`.

- Rutas del repo sin rutas absolutas (funciona local, en conda y en Docker con DATA_DIR=/app/data).
- `connect()`: DuckDB con una vista por tabla; lee gold/silver si existe, si no los CSV de data/raw.
- `save_result()`: guarda **agregados** (nunca filas de clientes, CON-03) en analysis/results/<nombre>.json,
  que es la evidencia versionada que citan el README, el reporte y las slides.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import duckdb

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "contracts").is_dir())
DATA = Path(os.getenv("DATA_DIR", ROOT / "data"))
RAW, SILVER, GOLD = DATA / "raw", DATA / "silver", DATA / "gold"
RESULTS = ROOT / "analysis" / "results"
FIGURES = ROOT / "analysis" / "figures"

TABLES = (
    "customers", "transactions", "products", "complaints", "call_center_interactions",
    "call_transcripts", "satisfaction_surveys", "service_agents", "daily_exchange_rates",
)


def _source(table: str) -> str | None:
    if (SILVER / f"{table}.parquet").exists():
        return f"read_parquet('{(SILVER / f'{table}.parquet').as_posix()}')"
    if (RAW / f"{table}.csv").exists():
        return f"read_csv('{(RAW / f'{table}.csv').as_posix()}')"
    if (RAW / table).is_dir():
        return f"read_csv('{(RAW / table).as_posix()}/**/*.csv', hive_partitioning=true, union_by_name=true)"
    return None


def connect() -> duckdb.DuckDBPyConnection:
    """Una vista por tabla disponible (silver > raw) y por tabla gold. Imprime qué se cargó y de dónde."""
    con = duckdb.connect()
    for t in TABLES:
        if src := _source(t):
            con.sql(f"CREATE VIEW {t} AS SELECT * FROM {src}")  # noqa: S608 (rutas locales, sin input externo)
            print(f"  {t:28s} <- {src.split('(')[0]}")
        else:
            print(f"  {t:28s} (no disponible: correr `make data` o bajar de S3)")
    for g in sorted(GOLD.glob("gold_*.parquet")):
        con.sql(f"CREATE VIEW {g.stem} AS SELECT * FROM read_parquet('{g.as_posix()}')")  # noqa: S608
        print(f"  {g.stem:28s} <- gold")
    return con


def show(con: duckdb.DuckDBPyConnection, title: str, sql: str, n: int = 40):
    print(f"\n== {title}")
    df = con.sql(sql).pl()
    print(df.head(n))
    return df


def save_result(name: str, payload: dict) -> Path:
    """Agregados versionados. `payload` no debe tener ids ni textos de clientes."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{name}.json"
    body = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), **payload}
    out.write_text(json.dumps(body, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return out


def save_fig(fig, name: str) -> Path:
    FIGURES.mkdir(parents=True, exist_ok=True)
    out = FIGURES / f"{name}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    return out
