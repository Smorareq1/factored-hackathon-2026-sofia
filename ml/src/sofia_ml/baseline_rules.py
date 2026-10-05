"""Keyword baseline; it was also the router published on D1 (v0 of the HTTP service) and is now the rules half
of the served hybrid (`sofia_ml.router`).

The rules started as a copy of the agent's fallback (`sofia_agent.tools.router`), so behavior did not change when
moving from the local fallback to the service. They evolve separately: the agent's stay as a safety net (REQ-16) and
these are the bar the trained model has to beat. The patterns are Spanish and Portuguese on purpose: they match what
customers write.

`router_version` says what predicted: `rules-ds-0.2` here, `rules-local-0.2` if the agent fell back to its own rules.
"""

import re

from sofia_contracts.common import Language
from sofia_contracts.router import Intent, IntentPrediction
from sofia_ml.language import detect_language
from sofia_ml.text import fold

RULES_ROUTER_VERSION = "rules-ds-0.2"

_RULES: dict[Intent, list[str]] = {
    "needs_human": [
        # Any conjugation of the verb (comunícame, pásame, me pasas, transfiéreme), not just the infinitive.
        r"\b(habla\w*|comunica\w*|pasa\w*|transfier\w*|transferir\w*|deriva\w*) (con|a) (un|una|el|la)? ?"
        r"(agente|persona|humano|asesor\w*|ejecutiv\w*|operador\w*)",
        r"\b(agente|persona) (humano|humana|real)\b",
        r"\b(quiero|necesito) (un|una|a un|a una) (humano|persona|asesor\w*|agente)\b",
        r"\bfalar com (um|uma|o|a)? ?(atendente|pessoa|humano|agente|gerente)",
        r"\b(transfer\w*|pass\w*|encaminh\w*) (para|com) (um|uma|o|a)? ?(atendente|pessoa|humano|agente|gerente)",
        r"\b(quero|preciso de) (um|uma) (humano|pessoa|atendente|agente)\b",
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
        r"\bno reconocid[oa]s?\b",
        r"\bme (cobraron|hicieron un cargo|descontaron)",
        r"\b(cobro|cargo|cobranza)s? (doble|duplicad\w*|dos veces|indebid\w*|raro|extran\w*|desconocid\w*|de mas)",
        r"\b(dos|2) veces\b",
        r"\b(disputar|disputo|reclamar|objetar|impugnar|impugno)\b",
        r"\babrir (una )?(disputa|reclamacion|aclaracion)",
        r"\bno (hice|realice|autorice) (esa|esta|ese|este)",
        r"\bno (me )?llego\b|\bno recibi\b",
        r"\bnao reconheco\b",
        # PT counterparts of the ES rules above (REQ-18 parity): desconozco, abrir una disputa, no reconocido.
        r"\bdesconheco\b",
        r"\babrir (uma )?(disputa|contestacao|reclamacao)",
        r"\bnao reconhecid[oa]s?\b",
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
# If several classes match, the most expensive one to get wrong wins (needs_human first, §8.6).
_PRIORITY: tuple[Intent, ...] = ("needs_human", "dispute_status", "dispute_new", "out_of_scope", "transaction_inquiry")


def predict_rules(text: str, language_hint: Language | None = None) -> IntentPrediction:
    folded = fold(text)
    hits = {intent: sum(1 for rx in rxs if rx.search(folded)) for intent, rxs in _COMPILED.items()}
    language = detect_language(text, fallback=language_hint or "es")
    matched = [i for i in _PRIORITY if hits[i] > 0]
    if not matched:
        # No rule matched: out_of_scope with low confidence, so the agent clarifies instead of abstaining.
        return IntentPrediction(
            intent="out_of_scope",
            confidence=0.3,
            language=language.language,
            language_confidence=language.confidence,
            router_version=RULES_ROUTER_VERSION,
        )
    intent = matched[0]
    confidence = min(0.95, 0.65 + 0.1 * hits[intent])
    return IntentPrediction(
        intent=intent,
        confidence=round(confidence, 2),
        language=language.language,
        language_confidence=language.confidence,
        router_version=RULES_ROUTER_VERSION,
    )
