"""Configuración del agente, leída del entorno (nunca de archivos versionados con secretos, CON-03)."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

FAKE_BANK = "fake"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
# Free tier: cada modelo tiene su propia cuota y su propia disponibilidad (503 "high demand" intermitentes).
DEFAULT_GEMINI_FALLBACKS = "gemini-3.1-flash-lite,gemini-3.6-flash,gemini-3.8-flash"
NO_FALLBACK = "none"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    env: str = Field(default="local", validation_alias="SOFIA_ENV")

    # "fake" = banco en proceso (tools/fake_bank.py) hasta que llegue el stub de SIM.
    bank_api_url: str = Field(default=FAKE_BANK, validation_alias="BANK_API_URL")
    # Vacío = reglas locales por palabras clave (fallback del router de DS).
    router_url: str | None = Field(default=None, validation_alias="ROUTER_URL")
    # Vacío = checkpointer en memoria.
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")

    gemini_api_key: SecretStr | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    # La versión exacta se fija por env y queda en cada traza. Los 2.5 ya no están disponibles (27-sep).
    gemini_model: str = Field(default=DEFAULT_GEMINI_MODEL, validation_alias="GEMINI_MODEL")
    # Se prueban en orden si el principal falla (503/429/timeout). "none" = sin respaldo (eval reproducible).
    gemini_fallback_models: str = Field(default=DEFAULT_GEMINI_FALLBACKS, validation_alias="GEMINI_FALLBACK_MODELS")
    # "minimal" clasifica peor y no lo aceptan todos los modelos; "default" = no se envía (el del modelo).
    gemini_thinking_level: Literal["minimal", "low", "medium", "high", "default"] = Field(
        default="low", validation_alias="GEMINI_THINKING_LEVEL"
    )
    # auto = Gemini si hay API key; rules = solo reglas + plantillas (sin LLM).
    llm_mode: Literal["auto", "gemini", "rules"] = Field(default="auto", validation_alias="SOFIA_LLM_MODE")
    llm_timeout_s: float = Field(default=20.0, validation_alias="SOFIA_LLM_TIMEOUT_S")
    # Tope por modelo dentro de ese presupuesto: un modelo saturado que se cuelga deja tiempo al respaldo.
    llm_attempt_timeout_s: float = Field(default=8.0, validation_alias="SOFIA_LLM_ATTEMPT_TIMEOUT_S")
    # MET-06: supuesto de precio (USD por millón de tokens). Se declara en el reporte; ajustar al precio vigente.
    gemini_price_in_per_mtok: float = Field(default=0.30, validation_alias="GEMINI_PRICE_INPUT_PER_MTOK")
    gemini_price_out_per_mtok: float = Field(default=2.50, validation_alias="GEMINI_PRICE_OUTPUT_PER_MTOK")

    # Kill switch (GOVERN): off = toda acción automática pasa a humano.
    auto_actions: bool = Field(default=True, validation_alias="SOFIA_AUTO_ACTIONS")

    cors_origins: str = Field(default="", validation_alias="CORS_ORIGINS")

    langfuse_host: str | None = Field(default=None, validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL"))
    langfuse_public_key: str | None = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: SecretStr | None = Field(default=None, validation_alias="LANGFUSE_SECRET_KEY")

    @field_validator("auto_actions", mode="before")
    @classmethod
    def _on_off(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in {"on", "off"}:
            return value.strip().lower() == "on"
        return value

    @field_validator(
        "router_url",
        "database_url",
        "gemini_api_key",
        "langfuse_host",
        "langfuse_public_key",
        "langfuse_secret_key",
        mode="before",
    )
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator(
        "bank_api_url",
        "gemini_model",
        "gemini_fallback_models",
        "gemini_thinking_level",
        "gemini_price_in_per_mtok",
        "gemini_price_out_per_mtok",
        "llm_mode",
        mode="before",
    )
    @classmethod
    def _empty_is_default(cls, value: object, info: ValidationInfo) -> object:
        # compose pasa "${VAR:-}" como cadena vacía cuando la variable no está en .env.
        return cls.model_fields[info.field_name].default if value == "" else value

    @property
    def use_gemini(self) -> bool:
        if self.llm_mode == "rules":
            return False
        return self.gemini_api_key is not None

    @property
    def gemini_models(self) -> list[str]:
        """Principal primero; sin duplicados."""
        raw = self.gemini_fallback_models
        fallbacks = [] if raw.strip().lower() == NO_FALLBACK else raw.split(",")
        models: list[str] = []
        for model in [self.gemini_model, *fallbacks]:
            if model.strip() and model.strip() not in models:
                models.append(model.strip())
        return models

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
