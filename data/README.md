# data/ — dueño: OPS

Pipeline repetible del LATAM Bank Dataset (REQ-12): **S3 → raw → bronze → silver → gold**, con contratos de
schema, checks de calidad, lineage y política de freshness. DuckDB hace el trabajo pesado; todo queda en Parquet.

```bash
make data           # S3 si .env tiene AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / S3_BUCKET; si no, usa data/raw
make data-fixture   # mismo pipeline sobre datos sintéticos (team_generated) en data/fixture/, sin S3
```

Ningún dato se versiona (CON-03): `data/raw`, `bronze`, `silver`, `gold`, `_state` y `fixture` están en `.gitignore`.

## Etapas

| Etapa | Qué hace | Salida |
|---|---|---|
| S3 → raw | Espeja solo los objetos de las tablas usadas (§7); re-descarga si cambió el ETag | `raw/<llave S3>` |
| raw → bronze | Copia fiel (todo como texto) + `_source_file`, `_ingested_at`, `_run_id`. Cada archivo entra **una vez** | `bronze/<tabla>/ingest_date=YYYY-MM-DD/*.parquet` |
| bronze → silver | Contrato por tabla ([contracts.py](src/sofia_data/contracts.py)): nombres normalizados + alias, tipos con `TRY_CAST`, categóricos canónicos, dedup por llave (gana lo más reciente y completo), cuarentena de obligatorios nulos y huérfanos de FK | `silver/<tabla>.parquet`, `silver/_quarantine/<tabla>.parquet` (con `_reason`) |
| silver → gold | Tablas de §9.1 validadas contra [`sofia_contracts.gold`](../contracts/src/sofia_contracts/gold.py) | `gold/<tabla>.parquet` + `gold/sample/` (≤1.000 filas, coherente por cliente) |

Silver y gold se recalculan completos desde bronze en cada corrida: re-correr es idempotente.

## Calidad

- **Bloquean** (exit 1, el reporte se escribe igual): >10% duplicados, >10% en cuarentena, gold que no cumple el contrato.
- **Avisan**: columnas del contrato ausentes en el origen, valores que no castean, columnas opcionales >50% nulas.
- Reporte por corrida en `_state/reports/<run_id>.json` (`latest.json` = última): filas por etapa, duplicados,
  cuarentena por motivo, tasa de nulos por columna, columnas renombradas / nuevas / faltantes, rango de fechas.

## Evolución de schema

Bronze se lee con `union_by_name`, así que archivos con columnas nuevas o faltantes conviven. En silver, un renombre
conocido (`merchant` → `merchant_name`) se declara en `aliases` del contrato y se combina con `coalesce`;
las columnas que el contrato no conoce se conservan y se reportan en `unexpected_columns`.

## Lineage y freshness

- `_state/lineage.jsonl`: una línea por corrida con archivos de entrada, Parquet de bronze escritos, filas en silver
  y gold, versión del código (`git rev-parse` o `GIT_SHA`) y si pasó los checks. Cada fila de silver conserva
  `_source_file` y `_run_id`.
- **Freshness**: una tabla está `fresh` si su última ingesta tiene < 24 h; si no, `stale`. No bloquea porque el
  dataset publicado es estático (termina el 2026-06-17); el pipeline está pensado para correr a diario y es incremental.
- **Llegadas tardías**: registros ingeridos en la corrida con fecha de evento ≤ watermark de la corrida anterior
  (`_state/watermarks.json`). Se aceptan e incorporan; se cuentan en `late_arrivals` del reporte.

## Labels de intención

`gold_intent_training.label` usa un mapeo **provisional** por palabras clave sobre `reason_category`, `contact_reason`
y `detected_intents` ([gold.py](src/sofia_data/gold.py)). DS es dueño del mapeo final (§8.6); `label_source` guarda el
texto crudo para re-etiquetar sin re-correr el pipeline.

## Pendientes conocidos

- La estructura real del bucket (formato y particiones) se confirma en la primera corrida con credenciales;
  `table_for_key` reconoce la tabla por carpeta o prefijo del archivo.
- `call_center_interactions.interaction_date` es un nombre supuesto: si el origen usa otro, agregarlo a `aliases`.
