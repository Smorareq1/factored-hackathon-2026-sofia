"""Ensamblador determinístico del handoff §9.4. Nunca incluye el transcript ni texto libre del cliente (REQ-05).

Todo sale del estado: hechos verificados con su fuente, acciones con su verificación, flags de la política y
de SENSE, y preguntas abiertas de un catálogo por regla/flag + los datos que faltan.

`request_summary` y `open_questions` salen en el idioma de la conversación (`es` o `pt`). Los hechos
verificados siguen en español: es la lengua de trabajo del back office.
"""

from sofia_agent.state import AgentState
from sofia_contracts.common import Language
from sofia_contracts.handoff import HandoffAction, HandoffDraft, HandoffFact

_CLAIM = {
    "es": {
        "not_recognized": "no reconoce",
        "duplicate": "reporta como duplicado",
        "wrong_amount": "reporta monto incorrecto en",
        "not_received": "reporta que no recibió lo pagado en",
        "other": "disputa",
    },
    "pt": {
        "not_recognized": "não reconhece",
        "duplicate": "informa como duplicada",
        "wrong_amount": "informa valor incorreto em",
        "not_received": "informa que não recebeu o que pagou em",
        "other": "contesta",
    },
}
_REASON = {
    "es": {
        "POL-6": "requiere revisión humana por política (POL-6)",
        "POL-7": "no se pudo identificar la transacción (POL-7)",
        "POL-3": "fuera de la ventana de disputa; el cliente pidió revisión humana",
        "customer_request": "el cliente pidió hablar con una persona",
        "verification_failed": "la disputa no se pudo verificar después de crearla",
        "tool_unavailable": "el sistema no respondió durante la atención",
        "action_rejected": "la API rechazó la acción",
        "kill_switch": "acciones automáticas desactivadas (kill switch)",
        "guard_blocked": "una guarda de GOVERN bloqueó una acción",
    },
    "pt": {
        "POL-6": "requer revisão humana por política (POL-6)",
        "POL-7": "não foi possível identificar a transação (POL-7)",
        "POL-3": "fora da janela de contestação; o cliente pediu revisão humana",
        "customer_request": "o cliente pediu para falar com uma pessoa",
        "verification_failed": "a contestação não pôde ser verificada depois de criada",
        "tool_unavailable": "o sistema não respondeu durante o atendimento",
        "action_rejected": "a API rejeitou a ação",
        "kill_switch": "ações automáticas desativadas (kill switch)",
        "guard_blocked": "uma guarda de GOVERN bloqueou uma ação",
    },
}
_QUESTION = {
    "es": {
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
        "missing_claim": "¿Cuál es el motivo de la disputa (no reconoce, duplicado, monto incorrecto, no recibido)?",
    },
    "pt": {
        "fraud_suspected": "O cliente ainda está com o cartão físico?",
        "high_amount": "O cliente reconhece outras transações recentes do mesmo estabelecimento?",
        "repeat_complainer": "Há contestações anteriores do cliente relacionadas a este estabelecimento?",
        "prompt_injection_suspected": (
            "Foi detectada uma possível tentativa de manipular o assistente: validar identidade e solicitação."
        ),
        "mixed_language": "O cliente misturou espanhol e português: confirmar o idioma preferido.",
        "POL-7": "Qual é a transação exata que o cliente quer contestar (estabelecimento, data e valor)?",
        "verification_failed": "Verificar manualmente se a contestação ficou registrada antes de contatar o cliente.",
        "tool_unavailable": "Verificar o estado da solicitação: o sistema não respondeu durante o atendimento.",
        "action_rejected": "Revisar por que a API rejeitou o registro da contestação.",
        "missing_claim": (
            "Qual é o motivo da contestação (não reconhece, duplicada, valor incorreto, não recebido)?"
        ),
    },
}
_SUMMARY = {
    "es": {
        "tx": "Cliente {claim} un cargo de {amount} {currency} en {merchant} del {date}.",
        "no_tx": "Cliente solicita atención humana ({goal}).",
        "no_goal": "sin intención clara",
        "reason": " Motivo de la transferencia: {reason}.",
    },
    "pt": {
        "tx": "Cliente {claim} uma cobrança de {amount} {currency} em {merchant} de {date}.",
        "no_tx": "Cliente solicita atendimento humano ({goal}).",
        "no_goal": "sem intenção clara",
        "reason": " Motivo da transferência: {reason}.",
    },
}


def _language(state: AgentState) -> Language:
    return "pt" if state.get("language") == "pt" else "es"


def build_handoff(state: AgentState, *, reason: str, trace_id: str | None) -> HandoffDraft:
    language = _language(state)
    claim_phrase = _CLAIM[language]
    reason_label = _REASON[language]
    questions_for = _QUESTION[language]
    summary_for = _SUMMARY[language]

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
        summary = summary_for["tx"].format(
            claim=claim_phrase.get(claim or "other", claim_phrase["other"]),
            amount=amount.value,
            currency=amount.currency,
            merchant=by_key["tx.merchant"].value,
            date=by_key["tx.date"].value,
        )
    else:
        summary = summary_for["no_tx"].format(goal=goal.type if goal else summary_for["no_goal"])
    summary += summary_for["reason"].format(reason=reason_label.get(reason, reason))

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
    questions = [questions_for[k] for k in [*risk_flags, reason] if k in questions_for]
    if "tx.id" not in by_key and reason != "POL-7" and (goal is not None and goal.type == "dispute_new"):
        questions.append(questions_for["POL-7"])
    if claim is None and "tx.id" in by_key:
        questions.append(questions_for["missing_claim"])

    return HandoffDraft(
        language=language,
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
