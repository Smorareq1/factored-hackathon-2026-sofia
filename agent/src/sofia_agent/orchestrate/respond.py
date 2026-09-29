"""respond: placeholders → render → grounding check → fallback a plantilla (01-arquitectura).

1. Se arma la ficha de hechos SIN valores (claves y descripciones) para la situación del turno.
2. Gemini redacta usando solo placeholders; nunca ve montos, IDs, fechas ni comercios reales (CON-03).
3. Grounding check sobre el borrador; si falla, plantilla determinística + evento `grounding_fallback`.
4. El renderer llena los placeholders con `verified_facts` y la guardia de salida revisa el texto final.
"""

from dataclasses import dataclass
from typing import Any

from sofia_agent.deps import Deps
from sofia_agent.govern.decorator import governed
from sofia_agent.govern.guards import grounding_check, output_guard
from sofia_agent.govern.trail import Trail
from sofia_agent.llm import DraftRequest, LLMUnavailableError
from sofia_agent.orchestrate.render import (
    candidate_cards,
    candidates_block,
    case_card,
    disputes_block,
    render,
    transaction_card,
)
from sofia_agent.state import AgentState, ChatTurn
from sofia_contracts.events import AgentMessage

_TX = ("tx.amount", "tx.merchant", "tx.date")
KEY_DESCRIPTIONS = {
    "tx.amount": "monto de la transacción",
    "tx.merchant": "comercio de la transacción",
    "tx.date": "fecha de la transacción",
    "tx.status": "estado de la transacción",
    "case.id": "número de caso de la disputa",
    "case.status": "estado de la disputa",
    "existing_case.id": "número de caso de la disputa ya abierta",
    "handoff.id": "número de referencia de la transferencia",
}


_SUBJECT_SITUATIONS = frozenset(
    {"confirm_request", "confirm_again", "dispute_created", "inquiry_one", "deny_POL-2", "deny_POL-3", "deny_POL-4"}
)


@dataclass(frozen=True)
class Situation:
    description: str
    keys: tuple[str, ...] = ()
    required: tuple[str, ...] = ()


SITUATIONS: dict[str, Situation] = {
    "greeting": Situation("saludo inicial; presentarse y decir en qué puede ayudar"),
    "clarify_intent_unclear": Situation("no se entendió qué necesita; ofrecer las tres opciones"),
    "clarify_tx_missing_details": Situation(
        "faltan datos para encontrar la transacción; pedir comercio, fecha o monto"
    ),
    "clarify_tx_not_found": Situation("no hay transacciones que coincidan; pedir que confirme los datos"),
    "clarify_tx_too_many": Situation("hay demasiadas transacciones posibles; pedir un dato más"),
    "clarify_candidates": Situation("hay varias transacciones posibles; pedir que elija una de la lista"),
    "clarify_selection": Situation("no se entendió qué opción eligió; pedir el número"),
    "confirm_request": Situation(
        "la transacción es elegible; pedir confirmación explícita para registrar la disputa", _TX, _TX[:2]
    ),
    "confirm_again": Situation("la confirmación no fue clara; volver a pedirla de forma explícita", _TX, _TX[:2]),
    "dispute_created": Situation(
        "la disputa se registró y se verificó; dar el número de caso", ("case.id", *_TX), ("case.id",)
    ),
    "dispute_cancelled": Situation("el cliente no confirmó; no se registró nada"),
    "deny_POL-1": Situation("la transacción no está entre las del cliente; no revelar si existe"),
    "deny_POL-2": Situation("la transacción no se puede disputar por su estado", ("tx.merchant", "tx.status")),
    "deny_POL-3": Situation("fuera del plazo de disputa; ofrecer un agente humano", _TX),
    "deny_POL-4": Situation(
        "ya existe una disputa abierta para esa transacción; dar su número",
        ("existing_case.id",),
        ("existing_case.id",),
    ),
    "deny_other_customer": Situation("pidió datos de otro cliente; negarse con amabilidad"),
    "escalate_failed": Situation("no se pudo transferir por un problema técnico; pedir que intente más tarde"),
    "abstain": Situation("el pedido está fuera del alcance; ofrecer un agente humano"),
    "human_declined": Situation("el cliente no quiso un humano; cerrar con amabilidad"),
    "status_none": Situation("el cliente no tiene disputas abiertas"),
    "status_one": Situation("informar el estado de su disputa", ("case.id", "case.status"), ("case.id", "case.status")),
    "status_list": Situation("introducir la lista de sus disputas (la lista la agrega el sistema)"),
    "inquiry_one": Situation("informar los datos de la transacción", (*_TX, "tx.status"), _TX),
    "inquiry_list": Situation("introducir la lista de transacciones recientes (la agrega el sistema)"),
    "inquiry_none": Situation("no hay transacciones que coincidan"),
    "reauth": Situation("la sesión expiró; pedir que vuelva a iniciar sesión"),
}
_ESCALATED = Situation(
    "se transfirió a un agente humano con el resumen del caso; dar el número de referencia",
    ("handoff.id",),
    ("handoff.id",),
)


def situation_spec(situation: str) -> Situation:
    if situation.startswith("escalated_"):
        return _ESCALATED
    return SITUATIONS.get(situation, SITUATIONS["clarify_intent_unclear"])


@governed("ORCHESTRATE", "respond")
async def respond(state: AgentState, deps: Deps, trail: Trail) -> dict[str, Any]:
    language = state.get("language") or state.get("language_hint") or "es"
    pack = deps.prompts.packs[language]
    route = state.get("route")
    situation = state.get("situation") or ("reauth" if route == "reauth" else "clarify_intent_unclear")
    spec = situation_spec(situation)
    session = state.get("session")
    facts = {f.key: f for f in state.get("verified_facts", [])}
    allowed = {k for k in spec.keys if k in facts}
    required = set(spec.required)
    if missing := required - allowed:
        # Nunca debería pasar: la situación exige un hecho que no se verificó. No se inventa: se escala el texto.
        trail.emit("missing_verified_fact", "error", layer="GOVERN", keys=sorted(missing))
        situation, spec, allowed, required = "escalate_failed", situation_spec("escalate_failed"), set(), set()

    reference = deps.prompts.template(language, situation)
    text, source = reference, "template"
    llm_calls = state.get("llm_calls", 0)
    if llm_calls < deps.purpose.limits.max_llm_calls_per_turn and situation != "reauth":
        try:
            draft = await deps.llm.draft(
                DraftRequest(
                    situation=situation,
                    situation_description=spec.description,
                    language=language,
                    # El voseo es del español rioplatense: un cliente de AR que escribe en portugués no lo lleva.
                    voseo=language == "es"
                    and bool(session and session.country in deps.purpose.persona.voseo_countries),
                    message=state.get("message", ""),
                    placeholders={k: KEY_DESCRIPTIONS[k] for k in sorted(allowed)},
                    required=sorted(required),
                    reference=reference,
                )
            )
            llm_calls += 1
            check = grounding_check(draft, allowed=allowed, required=required, language=language)
            if check.ok:
                text, source = draft, "llm"
                trail.emit("grounding_passed", layer="GOVERN")
            else:
                trail.emit("grounding_fallback", "warn", layer="GOVERN", reason=check.reason, detail=check.detail)
        except LLMUnavailableError as exc:
            trail.emit("llm_fallback", "warn", layer="GOVERN", reason=str(exc))

    candidates = state.get("candidates") or []
    cards = candidate_cards(candidates, language, pack) if situation in ("clarify_candidates", "inquiry_list") else []

    def compose(body: str) -> str:
        rendered = render(body, facts, language, pack)
        if cards:
            rendered += "\n" + candidates_block(cards, pack)
        if situation == "status_list":
            rendered += "\n" + disputes_block(state.get("disputes_listed", []), pack)
        return rendered

    final = compose(text)
    guard = output_guard(final, session_customer_id=session.customer_id if session else None)
    if not guard.ok:
        trail.emit("output_blocked", "error", layer="GOVERN", reason=guard.reason)
        final, source = compose(reference), "template"

    quick_replies: list[str] = []
    if state.get("pending_confirmation") and situation in ("confirm_request", "confirm_again"):
        quick_replies = pack.quick_replies["confirm"]
    elif state.get("offered_human"):
        quick_replies = pack.quick_replies["human"]

    trail.emit("response_ready", source=source, situation=situation, llm_calls=llm_calls)
    goal = state.get("goal")
    trail.emit(
        "goal_status",
        layer="PURPOSE",
        goal=goal.type if goal else None,
        goal_status=goal.status if goal else None,
        purpose_version=deps.purpose.purpose_version,
    )
    # Los mismos datos que ya están en el texto, en estructura para la UI (tarjetas; el harness lee `text`).
    selected = state.get("selected_tx")
    subject = transaction_card(selected, language, pack) if selected and situation in _SUBJECT_SITUATIONS else None
    dispute = state.get("dispute")
    case = (
        case_card(facts, pack, verified=situation == "status_one" or bool(dispute and dispute.verified))
        if situation in ("dispute_created", "status_one")
        else None
    )
    message = AgentMessage(
        text=final,
        language=language,
        route=route,
        quick_replies=quick_replies,
        candidates=cards,
        subject=subject,
        case=case,
    )
    return {
        "response": message,
        "situation": situation,
        "llm_calls": llm_calls,
        "messages": [ChatTurn(role="agent", text=final, turn=state.get("turn", 0))],
    }
