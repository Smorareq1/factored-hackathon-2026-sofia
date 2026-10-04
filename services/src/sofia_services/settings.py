"""Configuración del servicio bancario simulado (SIM)."""

from decimal import Decimal
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SOFIA_ENV: str = "local"
    GOLD_DIR: Path = Path("data/gold")
    DATABASE_URL: str = "postgresql://sofia:sofia@postgres:5432/sofia_bank"
    CORS_ORIGINS: str = "http://localhost:3000"

    # Calibración de política (§8.3): N (ventana días) y U (monto umbral USD)
    DISPUTE_WINDOW_DAYS: int = 90
    AMOUNT_THRESHOLD_USD: Decimal = Decimal("500.00")
    # Escala interna 0–1. En gold `fraud_score` va de 0 a 100 y store.py lo normaliza al cargar.
    # 0.30 (= 30 en gold) minimiza el costo esperado con fraude perdido ≈ 40–50× una revisión de más:
    # recall 0.69, precisión 0.80, 0.08% de transacciones a revisión (analysis/notebooks/02_policy_calibration).
    FRAUD_SCORE_THRESHOLD: float = 0.30

    # Tiempos de vida (TTL)
    SESSION_TTL_MINUTES: int = 30
    ELIGIBILITY_TTL_MINUTES: int = 15
    CHALLENGE_TTL_MINUTES: int = 5


def get_settings() -> Settings:
    return Settings()
