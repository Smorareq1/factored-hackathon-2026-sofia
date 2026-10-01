"""Lineage y política de freshness / llegadas tardías.

Lineage: cada corrida escribe `data/_state/lineage.jsonl` con qué archivos crudos entraron a bronze, qué tablas
silver y gold salieron, filas por etapa, versión del código y duración. Cualquier fila de gold se rastrea a su
archivo de origen con `_source_file` (bronze) -> mismo registro en silver.

Freshness (política):
- El dataset publicado termina el 2026-06-17 y Factored no lo actualiza durante el hackathon; el pipeline está
  pensado para correr a diario (`make data`) y es incremental: solo ingiere archivos nuevos o re-publicados.
- Una tabla está **fresca** si su última ingesta tiene menos de `FRESHNESS_SLA_HOURS`; si no, el reporte la marca
  `stale` (no bloquea: el dataset es estático).
- **Llegada tardía**: registro ingerido en esta corrida cuya fecha de evento es anterior al watermark (máxima fecha
  de evento ya publicada) de la corrida previa. Se aceptan y se incorporan (silver se recalcula completo y el
  dedup por llave conserva la versión más reciente); se cuentan en el reporte para auditar su volumen.
"""

import json
import os
import subprocess
from datetime import UTC, datetime

import duckdb

from sofia_data.contracts import CONTRACTS
from sofia_data.settings import Settings, scan

FRESHNESS_SLA_HOURS = 24


def code_version() -> str:
    if sha := os.environ.get("GIT_SHA"):
        return sha
    try:
        return subprocess.run(  # noqa: S603 - comando fijo, sin input externo
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _watermarks_path(settings: Settings):
    return settings.state / "watermarks.json"


def late_arrivals(settings: Settings, run_id: str) -> dict[str, int]:
    """Cuenta registros de esta corrida con fecha de evento <= watermark previo de su tabla."""
    path = _watermarks_path(settings)
    previous: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}
    con = duckdb.connect()
    late = {}
    for name, contract in CONTRACTS.items():
        files = list((settings.bronze / name).rglob("*.parquet"))
        if not contract.event_date or name not in previous or not files:
            continue
        glob = settings.bronze / name / "**" / "*.parquet"
        cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {scan(glob)}").fetchall()}
        if contract.event_date not in cols:
            continue
        late[name] = con.execute(
            f"""SELECT count(*) FROM {scan(glob)}
                WHERE _run_id = ? AND TRY_CAST({contract.event_date} AS TIMESTAMP) <= TIMESTAMP '{previous[name]}'""",
            [run_id],
        ).fetchone()[0]
    con.close()
    return late


def update_watermarks(settings: Settings, silver_report: dict) -> dict[str, str]:
    path = _watermarks_path(settings)
    marks: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}
    for name, q in silver_report.items():
        if q.event_date_max:
            marks[name] = max(marks.get(name, q.event_date_max), q.event_date_max)
    settings.state.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(marks, indent=2, sort_keys=True))
    return marks


def freshness(settings: Settings, now: datetime | None = None) -> dict[str, dict]:
    now = now or datetime.now(UTC)
    out = {}
    con = duckdb.connect()
    for name in CONTRACTS:
        if not (settings.bronze / name).exists() or not list((settings.bronze / name).rglob("*.parquet")):
            continue
        glob = settings.bronze / name / "**" / "*.parquet"
        last = con.execute(f"SELECT max(_ingested_at) FROM {scan(glob)}").fetchone()[0]
        # _ingested_at se guarda como TIMESTAMP en UTC (sin zona) para no depender de pytz
        age_h = (now.replace(tzinfo=None) - last).total_seconds() / 3600 if last else None
        out[name] = {
            "last_ingested_at": str(last),
            "age_hours": round(age_h, 2) if age_h is not None else None,
            "status": "fresh" if age_h is not None and age_h <= FRESHNESS_SLA_HOURS else "stale",
        }
    con.close()
    return out


def record_run(settings: Settings, entry: dict) -> None:
    settings.state.mkdir(parents=True, exist_ok=True)
    with (settings.state / "lineage.jsonl").open("a") as f:
        f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
