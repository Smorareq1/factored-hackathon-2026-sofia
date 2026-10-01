"""Rutas y configuración del pipeline. Todo sale de variables de entorno; los secretos nunca se loguean (CON-03)."""

import os
from dataclasses import dataclass
from pathlib import Path


def scan(glob: Path | str) -> str:
    """Lectura de Parquet tolerante a evolución de schema; sin columnas derivadas de carpetas `clave=valor`."""
    return f"read_parquet('{glob}', union_by_name=true, hive_partitioning=false)"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    s3_bucket: str | None
    s3_prefix: str
    aws_region: str

    @property
    def raw(self) -> Path:
        return self.data_dir / "raw"

    @property
    def bronze(self) -> Path:
        return self.data_dir / "bronze"

    @property
    def silver(self) -> Path:
        return self.data_dir / "silver"

    @property
    def quarantine(self) -> Path:
        return self.data_dir / "silver" / "_quarantine"

    @property
    def gold(self) -> Path:
        return self.data_dir / "gold"

    @property
    def state(self) -> Path:
        """Estado entre corridas: archivos ya ingeridos, watermarks y reportes."""
        return self.data_dir / "_state"

    @property
    def has_s3_credentials(self) -> bool:
        return bool(self.s3_bucket and os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"))

    @classmethod
    def from_env(cls, data_dir: Path | None = None) -> "Settings":
        return cls(
            data_dir=Path(data_dir or os.environ.get("DATA_DIR", "data")).resolve(),
            s3_bucket=os.environ.get("S3_BUCKET") or None,
            s3_prefix=os.environ.get("S3_PREFIX", "data/"),  # el bucket también trae data_backup_*/
            aws_region=os.environ.get("AWS_REGION", "us-east-2"),
        )
