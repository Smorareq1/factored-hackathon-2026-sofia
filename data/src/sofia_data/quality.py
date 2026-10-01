"""Checks de calidad y reporte por corrida.

- Umbrales por tabla: si una corrida los rompe, el pipeline termina con error (no se publica gold dudoso en silencio).
- Validación de gold contra los modelos Pydantic de `sofia_contracts.gold` sobre una muestra de filas.
- Reporte JSON en `data/_state/reports/<run_id>.json` y `latest.json`.
"""

import json
import logging
from dataclasses import dataclass

import duckdb
from pydantic import ValidationError

from sofia_contracts.gold import GOLD_TABLES
from sofia_data.settings import Settings
from sofia_data.silver import TableQuality

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Thresholds:
    # El dataset trae ~2% duplicados, ~5% nulos y "pocos" huérfanos: los umbrales dejan margen pero detectan un
    # archivo corrupto o un cambio de schema que vacíe una columna.
    max_duplicate_rate: float = 0.10
    max_quarantine_rate: float = 0.10
    max_required_null_rate: float = 0.0  # en silver, después de cuarentena
    max_column_null_rate: float = 0.50


DEFAULT_THRESHOLDS = Thresholds()


def check_silver(report: dict[str, TableQuality], t: Thresholds = DEFAULT_THRESHOLDS) -> list[str]:
    failures = []
    for name, q in report.items():
        if not q.bronze_rows:
            failures.append(f"{name}: bronze vacío")
            continue
        if q.duplicates_removed / q.bronze_rows > t.max_duplicate_rate:
            failures.append(f"{name}: {q.duplicates_removed / q.bronze_rows:.1%} duplicados")
        quarantined = sum(q.quarantined.values())
        if quarantined / q.bronze_rows > t.max_quarantine_rate:
            failures.append(f"{name}: {quarantined / q.bronze_rows:.1%} en cuarentena {q.quarantined}")
    return failures


def silver_warnings(report: dict[str, TableQuality], t: Thresholds = DEFAULT_THRESHOLDS) -> list[str]:
    """No bloquean: columnas opcionales muy vacías o ausentes y valores que no castean (posible drift)."""
    warnings = []
    for name, q in report.items():
        warnings += [f"{name}.{c}: columna ausente en el origen" for c in q.missing_columns]
        warnings += [f"{name}.{c}: {n} valores no castean al tipo del contrato" for c, n in q.cast_failures.items()]
        warnings += [
            f"{name}.{c}: {rate:.0%} nulos"
            for c, rate in q.null_rate.items()
            if c not in q.missing_columns and rate > t.max_column_null_rate
        ]
    return warnings


def validate_gold(settings: Settings, rows: int = 500) -> dict[str, dict]:
    """Valida filas de cada tabla gold contra su contrato. Devuelve filas validadas y errores por tabla."""
    con = duckdb.connect()
    result = {}
    for name, model in GOLD_TABLES.items():
        path = settings.gold / f"{name}.parquet"
        if not path.exists():
            continue
        cols = list(model.model_fields)
        actual = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()]
        missing = [c for c in cols if c not in actual]
        errors = []
        if not missing:
            cur = con.execute(f"SELECT {', '.join(cols)} FROM read_parquet('{path}') LIMIT {rows}")
            for values in cur.fetchall():
                try:
                    model.model_validate(dict(zip(cols, values, strict=True)))
                except ValidationError as e:
                    errors.append(e.errors()[0]["loc"][0] if e.errors() else "?")
        result[name] = {
            "missing_columns": missing,
            "rows_checked": rows,
            "invalid_rows": len(errors),
            "invalid_fields": sorted(set(map(str, errors))),
        }
    con.close()
    return result


def check_gold(validation: dict[str, dict]) -> list[str]:
    failures = []
    for name, v in validation.items():
        if v["missing_columns"]:
            failures.append(f"{name}: faltan columnas del contrato {v['missing_columns']}")
        if v["invalid_rows"]:
            failures.append(f"{name}: {v['invalid_rows']} filas no cumplen el contrato ({v['invalid_fields']})")
    return failures


def write_report(settings: Settings, run_id: str, report: dict) -> None:
    out = settings.state / "reports"
    out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, default=str, ensure_ascii=False)
    (out / f"{run_id}.json").write_text(text)
    (out / "latest.json").write_text(text)
