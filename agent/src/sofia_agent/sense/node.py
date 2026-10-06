"""Nodos de SENSE: percibir el turno (sesión, normalización, idioma, señales) y reauth."""

from typing import Any

from sofia_agent.deps import Deps
from sofia_agent.govern.decorator import governed
from sofia_agent.govern.trail import Trail
from sofia_agent.sense.language import detect_language
from sofia_agent.sense.normalize import normalize_message
from sofia_agent.sense.signals import detect_signals
from sofia_agent.state import AgentState, ChatTurn, RiskSignal, Versions
from sofia_agent.tools.bank import SessionExpiredError


@governed("SENSE", "sense")
async def sense(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    turn = state["turn"]
    # 1. Sesión: el customer_id sale SIEMPRE del token (vía SIM), nunca del texto (REQ-11).
    session = await deps.bank.session_me()
    if session.role != "customer":
        raise SessionExpiredError("role")
    trail.emit("session_valid", expires_in_s=int((session.expires_at - deps.now()).total_seconds()))

    # 2. Normalización.
    message, flags = normalize_message(state["message"], deps.purpose.limits.max_message_chars)
    if flags:
        trail.emit("message_normalized", "warn", flags=flags)

    # 3. Idioma por turno, con cascada si el mensaje es corto o ambiguo.
    guess = detect_language(message)
    if guess.decided:
        language, confidence, source = guess.language, guess.confidence, "detector"
    elif state.get("language"):
        language, confidence, source = state["language"], 0.5, "previous_turn"
    elif guess.pt_score != guess.es_score:
        # Poca evidencia pero de un solo lado ("Me transfere para um humano"): gana al selector de la UI, que
        # llega siempre (por defecto "es") y no distingue una elección del cliente de su valor inicial.
        language, confidence, source = ("pt" if guess.pt_score > guess.es_score else "es"), 0.5, "detector_weak"
    elif state.get("language_hint"):
        language, confidence, source = state["language_hint"], 0.5, "ui_hint"
    else:
        language, confidence, source = "es", 0.5, "default"
    trail.emit("language_detected", lang=language, conf=confidence, source=source, mixed=guess.mixed)

    # 4. Señales de riesgo (se registran; no bloquean por sí solas).
    signals = detect_signals(message, session_customer_id=session.customer_id, normalize_flags=flags)
    if guess.mixed:
        signals.append(RiskSignal(code="mixed_language"))
    for signal in signals:
        trail.emit("risk_signal", "warn", signal=signal.code)

    return {
        "session": session,
        "owner_customer_id": state.get("owner_customer_id") or session.customer_id,
        "message": message,
        "language": language,
        "language_confidence": confidence,
        "signals": signals,
        "messages": [ChatTurn(role="customer", text=message, turn=turn)],
        "versions": Versions(
            purpose=deps.purpose.purpose_version,
            prompts=deps.prompts.version,
            model=deps.llm.model_name,
            router=(state.get("versions") or Versions(purpose="", prompts="", model="")).router,
        ),
    }


@governed("SENSE", "reauth")
async def reauth(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    trail.emit("reauth_required", "warn")
    return {"route": "reauth", "situation": "reauth", "pending_confirmation": False}
