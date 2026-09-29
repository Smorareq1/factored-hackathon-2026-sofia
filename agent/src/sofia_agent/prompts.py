"""Carga de prompts y plantillas desde `agent/prompts/` (fuente de verdad, versionada en el repo).

`prompt_version` = hash de todos los archivos: cualquier cambio de redacción cambia la versión trazada
(§9.6 y MET: variabilidad por versión de prompt).
"""

import hashlib
import re
from functools import lru_cache
from importlib import resources
from pathlib import Path

import yaml
from pydantic import BaseModel

from sofia_contracts.common import Language

_VAR = re.compile(r"\{(\w+)\}")


def fill(text: str, **values: object) -> str:
    """Reemplaza `{nombre}` por su valor; deja intactos los placeholders `{{clave.dato}}`."""
    return _VAR.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text)


class StagePrompt(BaseModel):
    version: str
    system: str
    user: str


class LanguagePack(BaseModel):
    version: str
    templates: dict[str, str]
    quick_replies: dict[str, list[str]]
    option_label: str
    labels: dict[str, dict[str, str] | list[str]]


class BaselinePrompt(BaseModel):
    version: str
    system: str


class PromptBook(BaseModel):
    version: str
    interpret: StagePrompt
    respond: StagePrompt
    packs: dict[Language, LanguagePack]
    baseline: BaselinePrompt

    def template(self, language: Language, situation: str) -> str:
        templates = self.packs[language].templates
        if situation in templates:
            return templates[situation]
        if situation.startswith("escalated_"):
            return templates["escalated_default"]
        return templates["clarify_intent_unclear"]


def prompts_dir() -> Path:
    """En la imagen de runtime los prompts viajan dentro del paquete; en desarrollo, en `agent/prompts`."""
    packaged = resources.files("sofia_agent") / "prompts"
    if packaged.is_dir():
        return Path(str(packaged))
    return Path(__file__).resolve().parents[2] / "prompts"


@lru_cache
def load_prompts(root: Path | None = None) -> PromptBook:
    root = root or prompts_dir()
    files = sorted(p for p in root.rglob("*.yaml"))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())

    def read(relative: str) -> dict:
        return yaml.safe_load((root / relative).read_text(encoding="utf-8"))

    return PromptBook(
        version=f"p-{digest.hexdigest()[:10]}",
        interpret=StagePrompt.model_validate(read("interpret/system.yaml")),
        respond=StagePrompt.model_validate(read("respond/system.yaml")),
        packs={lang: LanguagePack.model_validate(read(f"templates/{lang}.yaml")) for lang in ("es", "pt")},
        baseline=BaselinePrompt.model_validate(read("baseline/system.yaml")),
    )
