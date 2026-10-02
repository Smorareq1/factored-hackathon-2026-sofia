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
    FRAUD_SCORE_THRESHOLD: float = 0.8

    # Tiempos de vida (TTL)
    SESSION_TTL_MINUTES: int = 30
    ELIGIBILITY_TTL_MINUTES: int = 15
    CHALLENGE_TTL_MINUTES: int = 5


def get_settings() -> Settings:
    return Settings()
