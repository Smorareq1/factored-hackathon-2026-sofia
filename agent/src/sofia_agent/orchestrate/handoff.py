"""Ensamblador determinístico del handoff §9.4. Nunca incluye el transcript ni texto libre del cliente (REQ-05).

Todo sale del estado: hechos verificados con su fuente, acciones con su verificación, flags de la política y
de SENSE, y preguntas abiertas de un catálogo por regla/flag + los datos que faltan.
"""

from sofia_agent.state import AgentState
from sofia_contracts.handoff import HandoffAction, HandoffDraft, HandoffFact

_CLAIM_PHRASE = {
    "not_recognized": "no reconoce",
    "duplicate": "reporta como duplicado",
    "wrong_amount": "reporta monto incorrecto en",
    "not_received": "reporta que no recibió lo pagado en",
    "other": "disputa",
}
_REASON_LABEL = {
    "POL-6": "requiere revisión humana por política (POL-6)",
    "POL-7": "no se pudo identificar la transacción (POL-7)",
    "POL-3": "fuera de la ventana de disputa; el cliente pidió revisión humana",
    "customer_request": "el cliente pidió hablar con una persona",
    "verification_failed": "la disputa no se pudo verificar después de crearla",
    "tool_unavailable": "el sistema no respondió durante la atención",
    "action_rejected": "la API rechazó la acción",
    "kill_switch": "acciones automáticas desactivadas (kill switch)",
    "guard_blocked": "una guarda de GOVERN bloqueó una acción",
}
_QUESTIONS = {
    "fraud_suspected": "¿El cliente aún tiene la tarjeta física en su poder?",
    "high_amount": "¿El cliente reconoce otras transacciones recientes del mismo comercio?",
    "repeat_complainer": "¿Hay disputas previas del cliente relacionadas con este comercio?",
    "prompt_injection_suspected": (
        "Se detectó un posible intento de manipular al asistente: validar identidad y solicitud."
    ),
    "mixed_language": "El cliente mezcló español y portugués: confirmar el idioma preferido.",
    "POL-7": "¿Cuál es la transacción exacta que el cliente quiere disputar (comercio, fecha y monto)?",
    "verification_failed": "Verificar manualmente si la disputa quedó registrada antes de contactar al cliente.",
    "tool_unavailable": "Verificar el estado de la solicitud: el sistema no respondió durante la atención.",
    "action_rejected": "Revisar por qué la API rechazó el registro de la disputa.",
}


def build_handoff(state: AgentState, *, reason: str, trace_id: str | None) -> HandoffDraft:
    session = state.get("session")
    goal = state.get("goal")
    # Solo los hechos de la meta actual: una disputa ya resuelta antes en el hilo no se mezcla.
    since = goal.opened_turn if goal else 0
    facts = [f for f in state.get("verified_facts", []) if f.turn >= since]
    by_key = {f.key: f for f in facts}
    eligibility = state.get("eligibility")
    slots = state.get("slots")
    claim = slots.customer_claim if slots else None
    signals = [s.code for s in state.get("signals", [])]

    if "tx.id" in by_key:
        amount = by_key["tx.amount"]
        summary = (
            f"Cliente {_CLAIM_PHRASE.get(claim or 'other', 'disputa')} un cargo de {amount.value} {amount.currency} "
            f"en {by_key['tx.merchant'].value} del {by_key['tx.date'].value}."
        )
    else:
        summary = f"Cliente solicita atención humana ({goal.type if goal else 'sin intención clara'})."
    summary += f" Motivo de la transferencia: {_REASON_LABEL.get(reason, reason)}."

    actions: list[HandoffAction] = []
    if eligibility is not None:
        actions.append(
            HandoffAction(
                action="eligibility_check",
                result=f"route={eligibility.route} rule={eligibility.rule_id}",
                verified=True,
            )
        )
    actions += [
        HandoffAction(action=a.action, result=a.result, verified=a.verified)
        for a in state.get("actions_taken", [])
        if a.turn >= since
    ]

    risk_flags = list(dict.fromkeys((eligibility.risk_flags if eligibility else []) + signals))
    questions = [_QUESTIONS[k] for k in [*risk_flags, reason] if k in _QUESTIONS]
    if "tx.id" not in by_key and reason != "POL-7" and (goal is not None and goal.type == "dispute_new"):
        questions.append(_QUESTIONS["POL-7"])
    if claim is None and "tx.id" in by_key:
        questions.append("¿Cuál es el motivo de la disputa (no reconoce, duplicado, monto incorrecto, no recibido)?")

    return HandoffDraft(
        language=state.get("language") or "es",
        customer_id=session.customer_id if session else "",
        authenticated=session is not None,
        request_summary=summary,
        customer_claim=claim,
        verified_facts=[HandoffFact(fact=f.fact, source=f.source) for f in facts if f.key != "handoff.id"],
        actions_taken=actions,
        open_questions=list(dict.fromkeys(questions)),
        risk_flags=risk_flags,
        reason_for_handoff=reason,
        system_version=state.get("system_version") or "proposed",
        trace_id=trace_id,
    )
