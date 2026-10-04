"""Language detector restricted to {es, pt}, deterministic and without heavy dependencies.

v0 = the agent's detector (counting exclusive markers). It is the first candidate to replace with a character n-gram
model once there is data: today it only decides when there is enough evidence.
"""

from dataclasses import dataclass

from sofia_contracts.common import Language
from sofia_ml.text import words

# Words (already without accents) that almost only appear in one of the two languages.
_ES = frozenset(
    """
    si usted ustedes gracias hola estoy quiero tarjeta transaccion transacciones reconozco dos veces ayer
    anteayer antier pasada pasado eso esa ese esos esas tambien ya entonces cobraron cobro cobros cuenta
    dinero monto hice con el los las del al fue tengo necesito cuando donde mucho muchas buenos ahora hoy
    tienda ayuda hablar persona pero cual esto aquel le lo quiero puedes puede hacer llego recibi compra
    cargo cargos senor senora mis tu tus nosotros vos sos queres podes mande muestrame dime prestamo presten
    tiempo cancele olvida
    """.split()
)
_PT = frozenset(
    """
    sim nao voce voces obrigado obrigada ola oi estou quero cartao transacao transacoes reconheco duas
    vezes ontem anteontem passada passado isso essa esse esses essas tambem ja entao cobraram cobranca
    conta dinheiro fiz com do da dos das ao aos foi tenho preciso quando onde muito muitas bom
    agora hoje loja ajuda falar pessoa qual isto aquele lhe minha meu minhas meus seu sua pode fazer
    chegou recebi compra senhor senhora gostaria mostre contestacao atendente um uma uns umas emprestimo
    tempo pela pelo tem estranha cancelei cobrado ignore suas instrucoes
    """.split()
)
# Spelling markers (before removing accents).
_ES_CHARS = ("ñ", "¿", "¡")
_PT_CHARS = ("ã", "õ", "ç", "ê", "ô", "lh", "nh")


@dataclass(frozen=True)
class LanguageGuess:
    language: Language
    confidence: float
    es_score: float
    pt_score: float
    decided: bool  # there was enough evidence
    mixed: bool  # both languages carry real weight


def detect_language(text: str, fallback: Language = "es") -> LanguageGuess:
    tokens = words(text)
    lowered = text.casefold()
    es = sum(1 for t in tokens if t in _ES and t not in _PT) + 2 * sum(lowered.count(c) for c in _ES_CHARS)
    pt = sum(1 for t in tokens if t in _PT and t not in _ES) + 2 * sum(lowered.count(c) for c in _PT_CHARS)
    total = es + pt
    if total < 2 or es == pt:
        return LanguageGuess(fallback, 0.5, es, pt, decided=False, mixed=es >= 2 and pt >= 2)
    language: Language = "es" if es > pt else "pt"
    confidence = round(max(es, pt) / total, 2)
    mixed = min(es, pt) >= 2 and min(es, pt) / total >= 0.2
    return LanguageGuess(language, confidence, es, pt, decided=True, mixed=mixed)
