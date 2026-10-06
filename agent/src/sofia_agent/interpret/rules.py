"""Extracción determinística ES/PT: IDs, montos, fechas, tipo de reclamo, confirmación y selección.

Es el fallback cuando Gemini no está disponible (circuit breaker, REQ-16) y la fuente principal para lo que
debe ser exacto: la confirmación explícita nunca depende del LLM (el LLM solo desempata).
"""

import re
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field

from sofia_agent.text import fold

Confirmation = Literal["yes", "no", "ambiguous", "none"]
Claim = Literal["not_recognized", "duplicate", "wrong_amount", "not_received", "other"]


class SlotExtraction(BaseModel):
    """Salida estructurada de INTERPRET (la misma forma para Gemini y para las reglas)."""

    transaction_id: str | None = Field(default=None, description="ID de transacción tal cual lo escribió el cliente")
    amount: float | None = Field(default=None, description="Monto mencionado por el cliente, sin moneda")
    currency: Literal["MXN", "COP", "ARS", "USD"] | None = None
    merchant: str | None = Field(default=None, description="Nombre del comercio mencionado")
    date_from: str | None = Field(default=None, description="Inicio del rango de fechas, YYYY-MM-DD")
    date_to: str | None = Field(default=None, description="Fin del rango de fechas, YYYY-MM-DD")
    customer_claim: Claim | None = None
    dispute_id: str | None = Field(default=None, description="Número de caso de disputa, si lo menciona")
    confirmation: Literal["yes", "no", "none"] = "none"
    wants_human: bool = False
    selection: int | None = Field(default=None, description="Número de opción elegida de una lista previa")


# ───────────────────────── IDs ─────────────────────────
_TX_ID = re.compile(r"\b(TX-[A-Z]{2}-\d{4}|TX\d{6,}|TRX-?\d{6,})\b", re.IGNORECASE)
_DISPUTE_ID = re.compile(r"\b(DSP-\d{4}-\d{6})\b", re.IGNORECASE)

# ───────────────────────── montos ─────────────────────────
_CURRENCY_WORDS = {
    "mxn": "MXN",
    "cop": "COP",
    "ars": "ARS",
    "usd": "USD",
    "us$": "USD",
    "dolares": "USD",
    "dolar": "USD",
}
_AMOUNT = re.compile(
    r"(?:(?P<pre>us\$|\$|mxn|cop|ars|usd)\s?(?P<n1>\d[\d.,]*)(?P<mil1>\s?mil\b)?)"
    r"|(?:(?P<n2>\d[\d.,]*)(?P<mil2>\s?mil)?\s?(?P<post>pesos|mxn|cop|ars|usd|dolares|dolar)\b)"
)


def parse_number(raw: str) -> Decimal | None:
    raw = raw.strip(".,")
    if "," in raw and "." in raw:
        decimal_sep = "," if raw.rfind(",") > raw.rfind(".") else "."
        thousands = "." if decimal_sep == "," else ","
        raw = raw.replace(thousands, "").replace(decimal_sep, ".")
    elif "," in raw or "." in raw:
        sep = "," if "," in raw else "."
        parts = raw.split(sep)
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            raw = parts[0] + "." + parts[1]
        else:
            raw = raw.replace(sep, "")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def extract_amount(folded: str) -> tuple[Decimal | None, str | None]:
    match = _AMOUNT.search(folded)
    if not match:
        return None, None
    number = parse_number(match.group("n1") or match.group("n2") or "")
    if number is None:
        return None, None
    if match.group("mil1") or match.group("mil2"):
        number *= 1000
    marker = match.group("pre") or match.group("post") or ""
    return number, _CURRENCY_WORDS.get(marker)


# ───────────────────────── fechas ─────────────────────────
_MONTHS = {
    **dict.fromkeys(["enero", "janeiro"], 1),
    **dict.fromkeys(["febrero", "fevereiro"], 2),
    **dict.fromkeys(["marzo", "marco"], 3),
    "abril": 4,
    **dict.fromkeys(["mayo", "maio"], 5),
    **dict.fromkeys(["junio", "junho"], 6),
    **dict.fromkeys(["julio", "julho"], 7),
    "agosto": 8,
    **dict.fromkeys(["septiembre", "setiembre", "setembro"], 9),
    **dict.fromkeys(["octubre", "outubro"], 10),
    **dict.fromkeys(["noviembre", "novembro"], 11),
    **dict.fromkeys(["diciembre", "dezembro"], 12),
}
_WEEKDAYS = {
    **dict.fromkeys(["lunes", "segunda-feira"], 0),
    **dict.fromkeys(["martes", "terca", "terca-feira"], 1),
    **dict.fromkeys(["miercoles", "quarta", "quarta-feira"], 2),
    **dict.fromkeys(["jueves", "quinta", "quinta-feira"], 3),
    **dict.fromkeys(["viernes", "sexta", "sexta-feira"], 4),
    "sabado": 5,
    "domingo": 6,
}
_DAY_MONTH = re.compile(r"\b(\d{1,2}) de (" + "|".join(_MONTHS) + r")(?: de (\d{4}))?\b")
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
_MONTH_ONLY = re.compile(r"\b(?:en|em|de|del|do|no) (" + "|".join(_MONTHS) + r")\b")
_DAYS_AGO = re.compile(r"\b(?:hace|ha|faz) (\d{1,2}) dias?\b")
_WEEKDAY = re.compile(r"\b(?:el|la|na|no|en|ese|esse|este|o|a|pasado|passado)? ?(" + "|".join(_WEEKDAYS) + r")\b")


def _past(day: date, today: date) -> date:
    return day if day <= today else day.replace(year=day.year - 1)


def extract_dates(folded: str, today: date) -> tuple[date | None, date | None]:
    if re.search(r"\b(hoy|hoje)\b", folded):
        return today, today
    if re.search(r"\b(anteayer|antier|anteontem)\b", folded):
        day = today - timedelta(days=2)
        return day, day
    if re.search(r"\b(ayer|ontem)\b", folded):
        day = today - timedelta(days=1)
        return day, day
    if m := _DAYS_AGO.search(folded):
        day = today - timedelta(days=int(m.group(1)))
        return day - timedelta(days=1), day + timedelta(days=1)
    if m := _DAY_MONTH.search(folded):
        year = int(m.group(3)) if m.group(3) else today.year
        try:
            day = date(year, _MONTHS[m.group(2)], int(m.group(1)))
        except ValueError:
            return None, None
        day = day if m.group(3) else _past(day, today)
        return day, day
    if m := _NUMERIC_DATE.search(folded):
        year = int(m.group(3)) if m.group(3) else today.year
        year = year + 2000 if year < 100 else year
        try:
            day = date(year, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None, None
        day = day if m.group(3) else _past(day, today)
        return day, day
    if re.search(r"\bsemana (pasada|passada)\b", folded):
        return today - timedelta(days=14), today - timedelta(days=1)
    if re.search(r"\b(esta|essa|nesta) semana\b", folded):
        return today - timedelta(days=today.weekday()), today
    if re.search(r"\b(mes pasado|mes passado)\b", folded):
        last_prev = today.replace(day=1) - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    if re.search(r"\b(este|esse|neste) mes\b", folded):
        return today.replace(day=1), today
    if m := _MONTH_ONLY.search(folded):
        first = _past(date(today.year, _MONTHS[m.group(1)], 1), today)
        return first, min(first.replace(day=monthrange(first.year, first.month)[1]), today)
    if m := _WEEKDAY.search(folded):
        delta = (today.weekday() - _WEEKDAYS[m.group(1)]) % 7 or 7
        day = today - timedelta(days=delta)
        return day, day
    return None, None


# ───────────────────────── reclamo ─────────────────────────
_CLAIMS: list[tuple[Claim, re.Pattern[str]]] = [
    ("duplicate", re.compile(r"\b(dos veces|2 veces|doble|duplicad\w*|duas vezes|em dobro|repetid\w*)\b")),
    (
        "not_received",
        re.compile(r"\b(no (me )?llego|no recibi|nunca llego|nao chegou|nao recebi|nunca chegou|no me entregaron)\b"),
    ),
    (
        "wrong_amount",
        re.compile(r"\b(de mas|cobraron mas|monto (incorrecto|equivocado|distinto)|valor (errado|incorreto)|a mais)\b"),
    ),
    (
        "not_recognized",
        re.compile(
            r"\b(no (la |lo )?reconozco|desconozco|no (hice|realice|autorice)|nao reconheco"
            r"|nao (fiz|realizei|autorizei)|no fui yo|nao fui eu|fraude|me robaron|clonaron)\b"
        ),
    ),
]


def extract_claim(folded: str) -> Claim | None:
    return next((claim for claim, rx in _CLAIMS if rx.search(folded)), None)


# ───────────────────────── confirmación y selección ─────────────────────────
_YES_HEAD = (
    r"(si|sim|claro|correcto|exacto|dale|de acuerdo|isso|certo|ok|okay|confirmo|confirmado|adelante|pode|va|sale)"
)
_YES_TAIL = (
    r"(si|sim|confirmo|por favor|claro|adelante|dale|pode seguir|que si|que sim|esa|essa|esa misma|essa mesma"
    r"|registrala|registre|obrigad[oa]|gracias|hacelo|hazlo)"
)
_YES = re.compile(rf"^{_YES_HEAD}( {_YES_TAIL})*$")
_NO = re.compile(
    r"^(no|nao|mejor no|melhor nao|nop|negativo|cancela\w*)"
    r"( (gracias|obrigad[oa]|por favor|todavia no|ainda nao|cancela\w*))*$"
)
_YES_START = re.compile(rf"^{_YES_HEAD}\b")
_NO_START = re.compile(r"^(no|nao)\b")
# "Sí, confirmo la disputa de este cargo" también es consentimiento explícito: empieza afirmando y lo que sigue solo
# repite la acción. Cualquier negación, condición o cambio de objeto lo deja ambiguo y se vuelve a preguntar.
_RESTATES_ACTION = re.compile(
    r"\b(confirm\w*|registr\w*|disput\w*|contest\w*|reclam\w*|abr\w*|abertura|adelante|proced\w*|segu\w*|pode|dale"
    r"|hacelo|hazlo|crea\w*|cria\w*|levant\w*)\b"
)
_HEDGE = re.compile(
    r"\b(no|nao|pero|mas|sino|senao|aunque|embora|solo si|so se|otra|otro|outra|outro|cambi\w*|mud\w*|espera\w*"
    r"|momento|todavia|ainda|duda|duvida|antes|ignora\w*|olvida\w*|esquec\w*)\b"
)
# "cargo no reconocido" describe el cargo, no niega la confirmación.
_DESCRIPTIVE_NEGATION = re.compile(r"\b(no|nao) (reconoc\w*|reconhec\w*|autoriz\w*)\b")


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]", " ", fold(text))).strip()


def read_confirmation(text: str) -> Confirmation:
    compact = _compact(text)
    if _YES.match(compact):
        return "yes"
    if _NO.match(compact):
        return "no"
    if (
        _YES_START.match(compact)
        and "?" not in text
        and _RESTATES_ACTION.search(compact)
        and not _HEDGE.search(_DESCRIPTIVE_NEGATION.sub(" ", compact))
    ):
        return "yes"
    if _YES_START.match(compact) or _NO_START.match(compact):
        return "ambiguous"  # "sí, pero…", "no sé": se vuelve a preguntar
    return "none"


_ORDINALS = {
    **dict.fromkeys(["primera", "primero", "primeira", "primeiro", "1ra", "1ro", "1a"], 1),
    **dict.fromkeys(["segunda", "segundo", "2da", "2do"], 2),
    **dict.fromkeys(["tercera", "tercero", "terceira", "terceiro", "3ra", "3ro"], 3),
}
_OPTION_NUMBER = re.compile(r"\b(?:opcion|opcao|numero|nro|#)\s*(\d)\b")
_BARE_NUMBER = re.compile(r"^(?:la |a |o |el )?(\d)$")


def read_selection(text: str, n_options: int) -> int | None:
    if n_options <= 0:
        return None
    compact = _compact(text)
    choice: int | None = None
    if m := _OPTION_NUMBER.search(compact) or _BARE_NUMBER.match(compact):
        choice = int(m.group(1))
    elif re.search(r"\b(ultima|ultimo)\b", compact):
        choice = n_options
    else:
        choice = next((n for word, n in _ORDINALS.items() if re.search(rf"\b{word}\b", compact)), None)
    return choice if choice and 1 <= choice <= n_options else None


# ───────────────────────── extracción completa ─────────────────────────
def rules_extract(text: str, today: date, *, n_options: int = 0, wants_human: bool = False) -> SlotExtraction:
    folded = fold(text)
    amount, currency = extract_amount(folded)
    date_from, date_to = extract_dates(folded, today)
    tx = _TX_ID.search(text)
    dispute = _DISPUTE_ID.search(text)
    confirmation = read_confirmation(text)
    return SlotExtraction(
        transaction_id=tx.group(1).upper() if tx else None,
        amount=float(amount) if amount is not None else None,
        currency=currency,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        customer_claim=extract_claim(folded),
        dispute_id=dispute.group(1).upper() if dispute else None,
        confirmation=confirmation if confirmation in ("yes", "no") else "none",
        wants_human=wants_human,
        selection=read_selection(text, n_options),
    )
