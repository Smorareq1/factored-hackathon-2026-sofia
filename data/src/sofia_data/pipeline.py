"""Punto de entrada de make data: S3 -> bronze -> silver -> gold.

    python -m sofia_data.pipeline                 # S3 si hay credenciales en .env; si no, lo que haya en data/raw
    python -m sofia_data.pipeline --source fixture # datos sintéticos (team_generated) en data/fixture/, sin S3
    python -m sofia_data.pipeline --source local   # solo data/raw, sin tocar S3
    python -m sofia_data.pipeline --tables transactions customers

Sale con código 1 si algún check de calidad o de contrato falla (el reporte queda escrito igual).
"""

import argparse
import logging
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sofia_data import fixture, gold, ingest, lineage, quality, silver
from sofia_data.contracts import CONTRACTS
from sofia_data.settings import Settings

log = logging.getLogger("sofia_data")


def run(settings: Settings, source: str = "auto", tables: tuple[str, ...] = tuple(CONTRACTS)) -> dict:
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    started = time.monotonic()
    log.info("corrida %s · data_dir=%s · source=%s", run_id, settings.data_dir, source)

    if source == "auto":
        source = "s3" if settings.has_s3_credentials else "local"
        if source == "local":
            log.warning("sin credenciales de S3 en el entorno: se usa lo que haya en %s", settings.raw)
    if source == "s3":
        downloaded = ingest.sync_raw(settings, tables)
        log.info("s3 -> raw: %d archivos nuevos o modificados", downloaded)
    elif source == "fixture":
        fixture.write_raw(settings.raw)

    bronze_files = ingest.raw_to_bronze(settings, run_id, tables)
    late = lineage.late_arrivals(settings, run_id)
    silver_report = silver.bronze_to_silver(settings, tables)
    if not silver_report:
        log.error("no hay datos en bronze: configure S3 en .env o use --source fixture")
        return {"run_id": run_id, "ok": False, "failures": ["sin datos"]}
    gold_counts = gold.silver_to_gold(settings)
    validation = quality.validate_gold(settings)
    failures = quality.check_silver(silver_report) + quality.check_gold(validation)
    warnings = quality.silver_warnings(silver_report)
    watermarks = lineage.update_watermarks(settings, silver_report)

    report = {
        "run_id": run_id,
        "ok": not failures,
        "failures": failures,
        "warnings": warnings,
        "source": source,
        "code_version": lineage.code_version(),
        "duration_s": round(time.monotonic() - started, 2),
        "bronze_files": bronze_files,
        "late_arrivals": late,
        "silver": {k: v.to_dict() for k, v in silver_report.items()},
        "gold": gold_counts,
        "gold_contract": validation,
        "watermarks": watermarks,
        "freshness": lineage.freshness(settings),
    }
    quality.write_report(settings, run_id, report)
    lineage.record_run(
        settings,
        {
            "run_id": run_id,
            "at": datetime.now(UTC).isoformat(),
            "code_version": report["code_version"],
            "inputs": [f["source"] for f in bronze_files],
            "bronze": {f["bronze"]: f["rows"] for f in bronze_files},
            "silver": {k: v.silver_rows for k, v in silver_report.items()},
            "gold": gold_counts,
            "ok": report["ok"],
        },
    )
    for w in warnings:
        log.warning("aviso de calidad: %s", w)
    for f in failures:
        log.error("check fallido: %s", f)
    log.info(
        "corrida %s %s en %.1fs · gold %s",
        run_id,
        "OK" if not failures else "CON FALLAS",
        report["duration_s"],
        gold_counts,
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["auto", "s3", "local", "fixture"], default="auto")
    parser.add_argument("--tables", nargs="*", choices=list(CONTRACTS), default=list(CONTRACTS))
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env(args.data_dir)
    if args.source == "fixture" and args.data_dir is None:
        # El fixture nunca se mezcla con los datos reales: vive en su propio árbol raw/bronze/silver/gold.
        settings = Settings.from_env(settings.data_dir / "fixture")
    report = run(settings, args.source, tuple(args.tables))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
