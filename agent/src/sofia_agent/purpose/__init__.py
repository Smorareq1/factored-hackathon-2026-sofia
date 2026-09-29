"""PURPOSE: carga purpose.yaml (misión, alcance, persona, límites) y la meta de cada conversación."""

import hashlib
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from sofia_contracts.router import Intent

PURPOSE_FILE = Path(__file__).with_name("purpose.yaml")


class Persona(BaseModel):
    name: str
    languages: list[str]
    tone: str
    voseo_countries: list[str] = []


class Limits(BaseModel):
    max_clarifications: int
    max_tool_retries: int
    max_llm_calls_per_turn: int
    tool_timeout_s: float
    max_message_chars: int


class InterpretConfig(BaseModel):
    router_confidence_threshold: float
    default_lookback_days: int
    max_candidates_listed: int
    amount_tolerance_pct: float


class Purpose(BaseModel):
    version: str
    mission: str
    persona: Persona
    in_scope_intents: list[Intent]
    out_of_scope_policy: str
    limits: Limits
    interpret: InterpretConfig
    # semver + hash corto del archivo: cualquier cambio al YAML cambia la versión trazada.
    purpose_version: str = ""


@lru_cache
def load_purpose(path: Path = PURPOSE_FILE) -> Purpose:
    raw = path.read_bytes()
    purpose = Purpose.model_validate(yaml.safe_load(raw))
    purpose.purpose_version = f"{purpose.version}+{hashlib.sha256(raw).hexdigest()[:8]}"
    return purpose
