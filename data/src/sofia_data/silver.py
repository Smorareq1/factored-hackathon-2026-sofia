"""bronze -> silver: contratos de schema, dedup (~2%), nulos (~5%), huérfanos de FK, evolución de schema.

Silver se recalcula completo desde bronze en cada corrida (idempotente). Por tabla:
1. Une todos los Parquet de bronze por nombre (`union_by_name`): columnas nuevas o faltantes no rompen la lectura.
2. Normaliza nombres (snake_case + alias del contrato) y tipa con TRY_CAST; lo que no castea queda nulo y se cuenta.
3. Normaliza categóricos (`approved` -> `Approved`).
4. Dedup por llave primaria: gana la versión ingerida más reciente y, a igualdad, la más completa.
5. Cuarentena (`silver/_quarantine/<tabla>.parquet`, con `_reason`): llave o campo obligatorio nulo, huérfano de FK.
"""

import logging
import re
from dataclasses import asdict, dataclass, field

import duckdb

from sofia_data.contracts import CONTRACTS, TableContract
from sofia_data.settings import Settings, scan

log = logging.getLogger(__name__)

META_COLUMNS = ("_source_file", "_ingested_at", "_run_id")


@dataclass
class TableQuality:
    table: str
    bronze_rows: int = 0
    duplicates_removed: int = 0
    quarantined: dict[str, int] = field(default_factory=dict)
    silver_rows: int = 0
    null_rate: dict[str, float] = field(default_factory=dict)
    cast_failures: dict[str, int] = field(default_factory=dict)
    missing_columns: list[str] = field(default_factory=list)
    unexpected_columns: list[str] = field(default_factory=list)
    renamed_columns: dict[str, str] = field(default_factory=dict)
    event_date_min: str | None = None
    event_date_max: str | None = None
    # Filas cuyo process_date llega más de 1 día después de la fecha del evento (llegada tardía en el origen)
    late_in_source: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_name(name: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", name.strip().lower()).strip("_")


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _bool_expr(col: str) -> str:
    v = f"lower(trim({col}))"
    return (
        f"CASE WHEN {v} IN ('true','t','1','si','sí','yes','y') THEN TRUE "
        f"WHEN {v} IN ('false','f','0','no','n') THEN FALSE ELSE NULL END"
    )


def _typed(col: str, dtype: str, contract: TableContract, name: str) -> str:
    raw = f"NULLIF(trim(CAST({col} AS VARCHAR)), '')"
    if dtype == "BOOLEAN":
        return _bool_expr(raw)
    if name in contract.enums:
        values = {v.lower(): v for v in contract.enums[name]} | contract.value_aliases.get(name, {})
        cases = " ".join(f"WHEN lower({raw}) = '{k}' THEN '{v}'" for k, v in values.items())
        return f"CASE {cases} ELSE {raw} END"
    if dtype == "INTEGER":
        # "250.0" -> 250
        return f"CAST(round(TRY_CAST({raw} AS DOUBLE)) AS INTEGER)"
    if dtype == "VARCHAR":
        return raw
    if dtype.startswith("DECIMAL") or dtype == "DOUBLE":
        # Montos con separador de miles o símbolo de moneda: "1,234.50", "$ 99"
        return f"TRY_CAST(regexp_replace({raw}, '[^0-9.\\-eE]', '', 'g') AS {dtype})"
    return f"TRY_CAST({raw} AS {dtype})"


def build_table(con: duckdb.DuckDBPyConnection, settings: Settings, contract: TableContract) -> TableQuality | None:
    bronze_glob = settings.bronze / contract.name / "**" / "*.parquet"
    if not any((settings.bronze / contract.name).rglob("*.parquet")):
        log.warning("silver: %s sin datos en bronze, se omite", contract.name)
        return None
    q = TableQuality(contract.name)
    con.execute(f"CREATE OR REPLACE TEMP VIEW bronze_raw AS SELECT * FROM {scan(bronze_glob)}")
    source_cols = [r[0] for r in con.execute("DESCRIBE bronze_raw").fetchall()]

    # Evolución de schema: varias columnas de origen pueden mapear a la misma del contrato (renombre entre versiones).
    mapped: dict[str, list[str]] = {}
    for src in source_cols:
        if src in META_COLUMNS:
            continue
        norm = normalize_name(src)
        target = contract.aliases.get(norm, norm)
        mapped.setdefault(target, []).append(src)
        if target != norm or norm != src:
            q.renamed_columns[src] = target

    select = []
    for name, dtype in contract.columns.items():
        sources = mapped.get(name)
        if not sources:
            q.missing_columns.append(name)
            select.append(f"CAST(NULL AS {dtype}) AS {_q(name)}")
            continue
        merged = _q(sources[0]) if len(sources) == 1 else "coalesce(" + ", ".join(_q(s) for s in sources) + ")"
        select.append(f"{_typed(merged, dtype, contract, name)} AS {_q(name)}")
        # Valores presentes en bronze que no pasaron el cast
        if dtype not in ("VARCHAR",) and name not in contract.enums:
            fails = con.execute(
                f"SELECT count(*) FROM bronze_raw WHERE NULLIF(trim(CAST({merged} AS VARCHAR)), '') IS NOT NULL "
                f"AND ({_typed(merged, dtype, contract, name)}) IS NULL"
            ).fetchone()[0]
            if fails:
                q.cast_failures[name] = fails
    extras = [s for t, srcs in mapped.items() if t not in contract.columns for s in srcs]
    q.unexpected_columns = sorted(extras)
    select += [_q(s) for s in extras]
    select += [_q(m) for m in META_COLUMNS if m in source_cols]

    con.execute(f"CREATE OR REPLACE TEMP TABLE typed AS SELECT {', '.join(select)} FROM bronze_raw")
    q.bronze_rows = con.execute("SELECT count(*) FROM typed").fetchone()[0]

    # Cuarentena por llave/obligatorios nulos
    req_null = " OR ".join(f"{_q(c)} IS NULL" for c in contract.required)
    con.execute(
        f"CREATE OR REPLACE TEMP TABLE quarantine AS SELECT *, 'required_null' AS _reason FROM typed WHERE {req_null}"
    )
    con.execute(f"DELETE FROM typed WHERE {req_null}")

    # Dedup por PK: versión más reciente y, a igualdad, la más completa
    completeness = " + ".join(f"CAST({_q(c)} IS NOT NULL AS INTEGER)" for c in contract.columns)
    order = "_ingested_at DESC NULLS LAST, " if "_ingested_at" in source_cols else ""
    before = con.execute("SELECT count(*) FROM typed").fetchone()[0]
    con.execute(
        f"""CREATE OR REPLACE TEMP TABLE deduped AS SELECT * FROM typed
            QUALIFY row_number() OVER (PARTITION BY {_q(contract.primary_key)}
                                       ORDER BY {order}({completeness}) DESC) = 1"""
    )
    q.duplicates_removed = before - con.execute("SELECT count(*) FROM deduped").fetchone()[0]

    # Huérfanos de FK contra silver ya construido (CONTRACTS está en orden de dependencia)
    for fk in contract.foreign_keys:
        ref = settings.silver / f"{fk.ref_table}.parquet"
        if not ref.exists():
            continue
        cond = (
            f"{_q(fk.column)} IS NOT NULL AND {_q(fk.column)} NOT IN "
            f"(SELECT {_q(fk.ref_column)} FROM read_parquet('{ref}'))"
        )
        con.execute(f"INSERT INTO quarantine SELECT *, 'fk_orphan:{fk.column}' FROM deduped WHERE {cond}")
        con.execute(f"DELETE FROM deduped WHERE {cond}")

    for reason, n in con.execute("SELECT _reason, count(*) FROM quarantine GROUP BY 1 ORDER BY 1").fetchall():
        q.quarantined[reason] = n
    q.silver_rows = con.execute("SELECT count(*) FROM deduped").fetchone()[0]
    if q.silver_rows:
        nulls = ", ".join(f"avg(CAST({_q(c)} IS NULL AS DOUBLE)) AS {_q(c)}" for c in contract.columns)
        row = con.execute(f"SELECT {nulls} FROM deduped").fetchone()
        q.null_rate = {c: round(v, 4) for c, v in zip(contract.columns, row, strict=True)}
    if contract.event_date and q.silver_rows:
        col = _q(contract.event_date)
        lo, hi = con.execute(f"SELECT min({col}), max({col}) FROM deduped").fetchone()
        q.event_date_min, q.event_date_max = (str(lo) if lo else None), (str(hi) if hi else None)
    if contract.event_date and contract.process_date and q.silver_rows:
        ev, pr = _q(contract.event_date), _q(contract.process_date)
        q.late_in_source = con.execute(
            f"SELECT count(*) FROM deduped WHERE {pr} > CAST({ev} AS DATE) + INTERVAL 1 DAY"
        ).fetchone()[0]

    settings.silver.mkdir(parents=True, exist_ok=True)
    settings.quarantine.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY deduped TO '{settings.silver / (contract.name + '.parquet')}' (FORMAT parquet)")
    con.execute(f"COPY quarantine TO '{settings.quarantine / (contract.name + '.parquet')}' (FORMAT parquet)")
    log.info(
        "bronze -> silver: %s %d -> %d (dups %d, cuarentena %s)",
        contract.name,
        q.bronze_rows,
        q.silver_rows,
        q.duplicates_removed,
        q.quarantined,
    )
    return q


def bronze_to_silver(settings: Settings, tables: tuple[str, ...] = tuple(CONTRACTS)) -> dict[str, TableQuality]:
    con = duckdb.connect()
    report = {}
    for name, contract in CONTRACTS.items():
        if name in tables and (q := build_table(con, settings, contract)):
            report[name] = q
    con.close()
    return report
