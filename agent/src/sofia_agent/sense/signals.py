"""Señales de riesgo del turno. Son señales, no bloqueos: la defensa real está en la API de SIM (REQ-10).

Se registran, se muestran en la caja de cristal y se suman a `risk_flags` del handoff; si además se piden
datos de otro cliente, DECIDE deniega (POL-1).
"""

import re

from sofia_agent.state import RiskSignal
from sofia_agent.text import fold

_INJECTION = [
    re.compile(p)
    for p in (
        # ES
        r"\b(ignora|olvida|omite|salta\w*) (tus|las|todas|sus|esas|estas)( \w+)? "
        r"(instrucciones|reglas|politicas|restricciones)",
        r"\bsoy (del|de el|un|una)? ?(banco|empleado|empleada|agente|administrador\w*|gerente|supervisor\w*"
        r"|desarrollador\w*|auditor\w*)\b",
        r"\b(modo|mode) (desarrollador|developer|admin\w*|dios|god|debug)\b",
        r"\b(prompt|instrucciones|mensaje) del sistema\b",
        r"\b(actua|comportate|responde) como\b",
        r"\bahora (eres|sos)\b",
        r"\bsin (restricciones|reglas|filtros)\b",
        # PT
        r"\b(ignore|esqueca|desconsidere) (suas|as|todas|essas|estas)( \w+)? (instrucoes|regras|politicas|restricoes)",
        r"\bsou (do|da|um|uma)? ?(banco|funcionari\w*|gerente|administrador\w*|atendente|supervisor\w*"
        r"|desenvolvedor\w*)\b",
        r"\bprompt do sistema\b",
        r"\b(aja|atue|responda) como\b",
        r"\bagora voce e\b",
        r"\bsem (restricoes|regras|filtros)\b",
        # EN (mezcla frecuente en ataques)
        r"\bignore (all|your|previous|the)( \w+)? (instructions|rules)",
        r"\bsystem prompt\b",
        r"\byou are now\b",
        r"\b(developer mode|jailbreak|dan mode)\b",
    )
]
_OTHER_CUSTOMER = re.compile(r"\b(otro cliente|otra cuenta|outro cliente|outra conta|another customer)\b")
_CUSTOMER_ID = re.compile(r"\b[CA]\d{8}\b", re.IGNORECASE)


def detect_signals(text: str, *, session_customer_id: str | None, normalize_flags: list[str]) -> list[RiskSignal]:
    folded = fold(text)
    signals = [RiskSignal(code=flag) for flag in normalize_flags]
    injection = next((rx.search(folded) for rx in _INJECTION if rx.search(folded)), None)
    if injection:
        signals.append(RiskSignal(code="prompt_injection_suspected", evidence=injection.group(0)[:60]))
    foreign_ids = {m.upper() for m in _CUSTOMER_ID.findall(text)} - {(session_customer_id or "").upper()}
    if foreign_ids:
        signals.append(RiskSignal(code="foreign_customer_id", evidence=f"{len(foreign_ids)} id(s)"))
    elif _OTHER_CUSTOMER.search(folded):
        signals.append(RiskSignal(code="other_customer_reference"))
    return signals
