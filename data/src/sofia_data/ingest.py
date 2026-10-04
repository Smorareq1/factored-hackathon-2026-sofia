"""S3 raw -> bronze: copia fiel, particionada por fecha, con metadatos de ingesta.

1. `sync_raw`: espeja los objetos del bucket a `data/raw/` (solo los que cambiaron: llave + ETag).
2. `raw_to_bronze`: cada archivo crudo nuevo se escribe una sola vez en
   `data/bronze/<tabla>/ingest_date=YYYY-MM-DD/<archivo>.parquet`, todo como texto (copia fiel, sin tipar)
   más `_source_file`, `_ingested_at` y `_run_id`. Re-correr no duplica: el estado vive en `_state/ingested.json`.
"""

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from sofia_data.contracts import CONTRACTS
from sofia_data.settings import Settings

log = logging.getLogger(__name__)

DOWNLOAD_WORKERS = 16
RAW_SUFFIXES = (".csv", ".csv.gz", ".parquet", ".json", ".jsonl", ".ndjson")


@dataclass(frozen=True)
class RawFile:
    path: Path
    table: str
    fingerprint: str  # ETag de S3 o hash local: detecta archivos re-publicados


def table_for_key(key: str, tables: tuple[str, ...] = tuple(CONTRACTS)) -> str | None:
    """Ubica la tabla por segmento de ruta (`transactions/2024/part-1.csv`) o prefijo del archivo
    (`transactions_2024.csv`). Gana el nombre más largo para no confundir `call_center_interactions`."""
    segments = [s.lower() for s in Path(key).parts]
    for table in sorted(tables, key=len, reverse=True):
        for seg in segments:
            stem = seg.split(".")[0]
            if stem == table or stem.startswith(f"{table}_") or stem.startswith(f"{table}-"):
                return table
    return None


def sync_raw(settings: Settings, tables: tuple[str, ...] = tuple(CONTRACTS)) -> int:
    """Descarga desde S3 los objetos nuevos o modificados de las tablas pedidas. Devuelve cuántos bajó."""
    import boto3
    from botocore.config import Config

    s3 = boto3.client("s3", region_name=settings.aws_region, config=Config(max_pool_connections=DOWNLOAD_WORKERS))
    manifest_path = settings.state / "s3_manifest.json"
    manifest: dict[str, str] = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    pending: list[tuple[str, str, int]] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=settings.s3_bucket, Prefix=settings.s3_prefix):
        for obj in page.get("Contents", []):
            key, etag = obj["Key"], obj["ETag"].strip('"')
            if not key.lower().endswith(RAW_SUFFIXES) or table_for_key(key, tables) is None:
                continue
            if manifest.get(key) == etag and (settings.raw / key).exists():
                continue
            pending.append((key, etag, obj["Size"]))
    log.info("s3 -> raw: %d objetos por bajar (%.1f MB)", len(pending), sum(p[2] for p in pending) / 1e6)

    def fetch(item: tuple[str, str, int]) -> tuple[str, str]:
        key, etag, _ = item
        target = settings.raw / key
        target.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(settings.s3_bucket, key, str(target))
        return key, etag

    settings.state.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        for i, (key, etag) in enumerate(pool.map(fetch, pending), 1):
            manifest[key] = etag
            if i % 500 == 0 or i == len(pending):
                log.info("s3 -> raw: %d/%d", i, len(pending))
                manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return len(pending)


def _fingerprint(path: Path) -> str:
    st = path.stat()
    return hashlib.sha1(f"{path.name}:{st.st_size}:{st.st_mtime_ns}".encode(), usedforsecurity=False).hexdigest()


def list_raw(settings: Settings, tables: tuple[str, ...] = tuple(CONTRACTS)) -> list[RawFile]:
    files = []
    for path in sorted(settings.raw.rglob("*")):
        if not path.is_file() or not path.name.lower().endswith(RAW_SUFFIXES):
            continue
        table = table_for_key(str(path.relative_to(settings.raw)), tables)
        if table:
            files.append(RawFile(path, table, _fingerprint(path)))
    return files


def _reader(path: Path) -> str:
    name, p = path.name.lower(), str(path).replace("'", "''")
    if name.endswith(".parquet"):
        return f"read_parquet('{p}', hive_partitioning=false)"
    if name.endswith((".json", ".jsonl", ".ndjson")):
        return f"read_json_auto('{p}')"
    # all_varchar: bronze no interpreta tipos; silver los valida contra el contrato.
    return f"read_csv('{p}', all_varchar=true, header=true, hive_partitioning=false)"


def raw_to_bronze(settings: Settings, run_id: str, tables: tuple[str, ...] = tuple(CONTRACTS)) -> list[dict]:
    """Escribe en bronze los archivos crudos que no se han ingerido. Devuelve el detalle por archivo para lineage."""
    state_path = settings.state / "ingested.json"
    ingested: dict[str, str] = json.loads(state_path.read_text()) if state_path.exists() else {}
    now = datetime.now(UTC)
    written = []
    con = duckdb.connect()
    for raw in list_raw(settings, tables):
        rel = raw.path.relative_to(settings.raw).as_posix()  # mismas llaves y nombres en Windows y Linux
        if ingested.get(rel) == raw.fingerprint:
            continue
        out_dir = settings.bronze / raw.table / f"ingest_date={now:%Y-%m-%d}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / (rel.replace("/", "__").split(".")[0] + f"__{raw.fingerprint[:8]}.parquet")
        src = rel.replace("'", "''")
        rows = con.execute(
            f"""COPY (
                  SELECT CAST(COLUMNS(*) AS VARCHAR),
                         '{src}' AS _source_file,
                         TIMESTAMP '{now:%Y-%m-%d %H:%M:%S.%f}' AS _ingested_at,  -- UTC
                         '{run_id}' AS _run_id
                  FROM {_reader(raw.path)}
                ) TO '{out}' (FORMAT parquet)"""
        ).fetchone()
        n = rows[0] if rows else 0
        log.info("raw -> bronze: %s -> %s (%d filas)", rel, raw.table, n)
        ingested[rel] = raw.fingerprint
        bronze_path = out.relative_to(settings.data_dir).as_posix()
        written.append({"table": raw.table, "source": rel, "bronze": bronze_path, "rows": n})
    con.close()
    settings.state.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(ingested, indent=2, sort_keys=True))
    return written
