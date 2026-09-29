"""Cliente del router de intención de DS (§9.3) con fallback local por palabras clave.

El router real vive en `ml/` (servicio HTTP, propuesta #13). Si `ROUTER_URL` no está configurado o el
servicio falla, el agente usa estas reglas ES/PT para no quedarse sin entender (REQ-16, fallback seguro).
Las reglas son también un baseline de componente razonable mientras DS entrena el suyo.
"""

import re
from dataclasses import dataclass

import httpx

from sofia_agent import tracing
from sofia_agent.sense.language import detect_language
from sofia_agent.text import fold
from sofia_contracts.common import Language
from sofia_contracts.router import Intent, IntentPrediction, RouterRequest

LOCAL_ROUTER_VERSION = "rules-local-0.1"

_RULES: dict[Intent, list[str]] = {
    "needs_human": [
        r"\b(hablar|comunicar\w*|pasar\w*|transferir\w*) (con|a) (un|una|el|la)? ?"
        r"(agente|persona|humano|asesor\w*|ejecutiv\w*|operador\w*)",
        r"\b(agente|persona) (humano|humana|real)\b",
        r"\bquiero (un|una) (humano|persona|asesor\w*)\b",
        r"\bfalar com (um|uma|o|a)? ?(atendente|pessoa|humano|agente|gerente)",
        r"\b(atendente|atendimento) humano\b",
        r"\bpessoa real\b",
    ],
    "dispute_status": [
        r"\b(estado|estatus|status|seguimiento) de (mi|mis|la|el) (disputa|reclamo|caso|queja|aclaracion)",
        r"\bcomo va (mi|el|la) (disputa|reclamo|caso|queja)",
        r"\b(status|andamento|situacao) d[aoe] (minha|meu|a|o) (disputa|contestacao|reclamacao|caso)",
        r"\bcomo (esta|anda) (minha|meu|a|o) (disputa|contestacao|reclamacao|caso)",
        r"\bdsp-\d{4}-\d+",
        r"\b(numero|nro|no\.?) de caso\b",
    ],
    "dispute_new": [
        r"\bno (la |lo |las |los )?reconozco\b",
        r"\bdesconozco\b",
        r"\bme (cobraron|hicieron un cargo|descontaron)",
        r"\b(cobro|cargo|cobranza)s? (doble|duplicad\w*|dos veces|indebid\w*|raro|extran\w*|desconocid\w*|de mas)",
        r"\b(dos|2) veces\b",
        r"\b(disputar|reclamar|objetar|impugnar)\b",
        r"\babrir (una )?(disputa|reclamacion|aclaracion)",
        r"\bno (hice|realice|autorice) (esa|esta|ese|este)",
        r"\bno (me )?llego\b|\bno recibi\b",
        r"\bnao reconheco\b",
        r"\b(me )?cobraram\b",
        r"\bcobranca (duplicada|em dobro|indevida|errada|estranha|desconhecida)",
        r"\bduas vezes\b",
        r"\b(contestar|disputar|reclamar de)\b",
        r"\bnao (fiz|realizei|autorizei) (essa|esta|esse|este)",
        r"\bnao (chegou|recebi)\b",
    ],
    "transaction_inquiry": [
        r"\b(ver|mostrar|muestrame|consultar|revisar) (mis|las|los|mi|la|el) "
        r"(compras|transacciones|movimientos|cargos|consumos)",
        r"\b(ultimos|ultimas) (movimientos|compras|transacciones|cargos)",
        r"\bcuanto (gaste|pague)\b",
        r"\b(quais|ver|mostrar|consultar|mostre) (as |os |minhas |meus )?(compras|transacoes|movimentacoes|gastos)",
        r"\bextrato\b",
        r"\bdetalle de (la|una|mi) (compra|transaccion)",
    ],
    "out_of_scope": [
        r"\b(prestamo|credito|hipoteca|inversion\w*|invertir|seguro de vida|cdt|plazo fijo)\b",
        r"\b(emprestimo|financiamento|investiment\w*|consorcio)\b",
        r"\b(prest(ar|en|e|a|ame|enme|arme)|emprest(ar|a|e|em|am)|financ(iar|ien|iamiento))\b",
        r"\bcambiar (mi |la |el )?(direccion|correo|telefono|contrasena|clave|nip|pin)",
        r"\b(mudar|alterar|trocar) (meu |minha |o |a )?(endereco|email|telefone|senha)",
        r"\babrir (una |uma )?(cuenta|conta)\b",
        r"\b(clima|chiste|receta|piada|futbol|futebol)\b",
    ],
}
_COMPILED = {intent: [re.compile(p) for p in patterns] for intent, patterns in _RULES.items()}
# Si varias clases coinciden, gana la más cara de equivocar (needs_human primero, §8.6).
_PRIORITY: tuple[Intent, ...] = ("needs_human", "dispute_status", "dispute_new", "out_of_scope", "transaction_inquiry")


def mentions_human(text: str) -> bool:
    """El cliente pide una persona: se respeta siempre, con o sin router (REQ-05)."""
    folded = fold(text)
    return any(rx.search(folded) for rx in _COMPILED["needs_human"])


def predict_local(text: str, language_hint: Language | None = None) -> IntentPrediction:
    folded = fold(text)
    hits = {intent: sum(1 for rx in rxs if rx.search(folded)) for intent, rxs in _COMPILED.items()}
    language = detect_language(text, fallback=language_hint or "es")
    matched = [i for i in _PRIORITY if hits[i] > 0]
    if not matched:
        return IntentPrediction(
            intent="out_of_scope",
            confidence=0.3,
            language=language.language,
            language_confidence=language.confidence,
            router_version=LOCAL_ROUTER_VERSION,
        )
    intent = matched[0]
    confidence = min(0.95, 0.65 + 0.1 * hits[intent])
    return IntentPrediction(
        intent=intent,
        confidence=round(confidence, 2),
        language=language.language,
        language_confidence=language.confidence,
        router_version=LOCAL_ROUTER_VERSION,
    )


@dataclass
class RouterResult:
    prediction: IntentPrediction
    fallback_reason: str | None = None


class RouterClient:
    def __init__(self, http: httpx.AsyncClient | None) -> None:
        self._http = http

    async def predict(self, text: str, language_hint: Language | None) -> RouterResult:
        with tracing.observe("router.predict", as_type="tool") as span:
            result = await self._predict(text, language_hint)
            tracing.update(
                span,
                output=result.prediction.model_dump(mode="json"),
                metadata={"fallback": result.fallback_reason or ""},
                level="WARNING" if result.fallback_reason and self._http is not None else "DEFAULT",
            )
        return result

    async def _predict(self, text: str, language_hint: Language | None) -> RouterResult:
        if self._http is None:
            return RouterResult(predict_local(text, language_hint), "router_not_configured")
        try:
            response = await self._http.post(
                "/predict", json=RouterRequest(text=text, language_hint=language_hint).model_dump()
            )
            response.raise_for_status()
            return RouterResult(IntentPrediction.model_validate(response.json()))
        except (httpx.HTTPError, ValueError) as exc:
            return RouterResult(predict_local(text, language_hint), f"router_error:{type(exc).__name__}")
