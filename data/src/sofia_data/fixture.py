"""Fixture sintético y sucio con la forma del LATAM Bank Dataset. Etiquetado `team_generated` (CON-04).

No contiene registros reales: sirve para CI, tests y demo offline sin credenciales de S3. Replica los problemas que
documenta el Data Dictionary: ~2% duplicados, ~5% nulos, huérfanos de FK, evolución de schema y llegadas tardías.
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 20261001
COUNTRIES = {"MX": "MXN", "CO": "COP", "AR": "ARS"}
FX = {"MXN": 0.055, "COP": 0.00025, "ARS": 0.0011, "USD": 1.0}
MERCHANTS = ["OXXO", "Rappi", "Mercado Libre", "Uber", "Netflix", "Éxito", "Coppel", "Farmacia del Ahorro"]
STATUSES = ["Approved", "Approved", "Approved", "Declined", "Pending", "Reversed"]
REASONS = [
    ("Disputas", "Cargo no reconocido en mi tarjeta", "Quiero disputar un cargo que no reconozco de {m}"),
    ("Disputas", "Estado de mi reclamo", "Quiero saber el estado de mi reclamo, el número de caso es DSP-{n}"),
    ("Consultas", "Consulta de movimiento", "Me pueden explicar este movimiento de {m}?"),
    ("Escalamiento", "Solicita supervisor", "Quiero hablar con un supervisor, esto es una queja formal"),
    ("Otros", "Actualización de dirección", "Necesito cambiar mi dirección de correspondencia"),
]
START = datetime(2023, 6, 17)
END = datetime(2026, 6, 17)


def _write(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fieldnames or list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _dirty(rows: list[dict], rng: random.Random, nullable: list[str], dup_rate=0.02, null_rate=0.05) -> list[dict]:
    for r in rows:
        for col in nullable:
            if rng.random() < null_rate:
                r[col] = ""
    dups = [dict(r) for r in rng.sample(rows, max(1, int(len(rows) * dup_rate)))]
    out = rows + dups
    rng.shuffle(out)
    return out


def _date(rng: random.Random, lo: datetime = START, hi: datetime = END) -> datetime:
    return lo + timedelta(seconds=rng.randint(0, int((hi - lo).total_seconds())))


def write_raw(raw_dir: Path, customers: int = 200, transactions: int = 3000) -> None:
    """Escribe el lote inicial en `raw_dir/<tabla>/...csv`. Determinístico."""
    rng = random.Random(SEED)  # noqa: S311 - datos sintéticos, no criptografía
    cust = []
    for i in range(customers):
        country = rng.choice(list(COUNTRIES))
        cust.append(
            {
                "customer_id": f"C{10000000 + i}",
                "document_number": f"{rng.randint(10**7, 10**8 - 1)}",
                "country": country if rng.random() > 0.1 else country.lower(),
                "segment": rng.choice(["Masivo", "Premium"]),
                "customer_status": rng.choice(["Activo", "Activo", "Inactivo"]),
                "detected_accent": country,
            }
        )
    ids = [c["customer_id"] for c in cust]
    _write(raw_dir / "customers" / "customers.csv", _dirty(cust, rng, ["segment", "customer_status"]))

    prods = [
        {
            "product_id": f"P{20000000 + i}",
            "customer_id": rng.choice(ids),
            "product_type": rng.choice(["Tarjeta de crédito", "Tarjeta de débito", "Cuenta de ahorro"]),
            "product_status": "Activo",
        }
        for i in range(customers * 2)
    ]
    _write(raw_dir / "products" / "products.csv", _dirty(prods, rng, ["product_status"]))

    def tx(i: int, when: datetime) -> dict:
        cid = rng.choice(ids)
        cur = COUNTRIES[next(c["country"].upper() for c in cust if c["customer_id"] == cid)]
        cur = "USD" if rng.random() < 0.05 else cur
        amount = round(rng.uniform(5, 2000) / FX[cur] * 0.01, 2)
        return {
            "transaction_id": f"T{30000000 + i}",
            "transaction_date": when.isoformat(sep=" ", timespec="seconds"),
            "customer_id": cid,
            "product_id": rng.choice(prods)["product_id"],
            "transaction_type": "Compra",
            "transaction_category": rng.choice(["Supermercado", "Transporte", "Entretenimiento"]),
            "amount": f"{amount:.2f}",
            "currency": cur,
            "amount_usd": f"{amount * FX[cur]:.2f}",
            "channel": rng.choice(["POS", "Online", "App"]),
            "merchant_name": rng.choice(MERCHANTS),
            "transaction_status": rng.choice(STATUSES),
            "is_fraud": rng.choice(["False"] * 49 + ["True"]),
            "fraud_score": f"{rng.random():.3f}",
        }

    half = transactions // 2
    cutoff = START + (END - START) / 2
    batch1 = [tx(i, _date(rng, START, cutoff)) for i in range(half)]
    # Huérfanos de FK: clientes que no existen en customers
    for r in rng.sample(batch1, 5):
        r["customer_id"] = f"C9{rng.randint(10**6, 10**7 - 1)}"
    _write(
        raw_dir / "transactions" / "date=2024" / "transactions_part1.csv",
        _dirty(batch1, rng, ["merchant_name", "channel", "fraud_score"]),
    )

    # Evolución de schema en el segundo lote: columna renombrada, status en minúsculas, columna nueva
    batch2 = [tx(half + i, _date(rng, cutoff, END)) for i in range(transactions - half)]
    for r in batch2:
        r["merchant"] = r.pop("merchant_name")
        r["transaction_status"] = r["transaction_status"].lower()
        r["device_type"] = rng.choice(["android", "ios", "web"])
    _write(
        raw_dir / "transactions" / "date=2025" / "transactions_part2.csv", _dirty(batch2, rng, ["merchant", "channel"])
    )

    inter, trans, comp = [], [], []
    for i in range(customers * 3):
        cat, reason, template = rng.choice(REASONS)
        iid = f"I{40000000 + i}"
        when = _date(rng)
        cid = rng.choice(ids)
        inter.append(
            {
                "interaction_id": iid,
                "interaction_date": when.isoformat(sep=" ", timespec="seconds"),
                "customer_id": cid,
                "agent_id": f"A{rng.randint(1000, 2199)}",
                "channel": "Teléfono",
                "contact_reason": reason,
                "reason_category": cat,
                "duration_seconds": rng.randint(60, 1800),
                "wait_time_seconds": rng.randint(0, 600),
                "was_resolved": rng.choice(["Sí", "No"]),
                "requires_followup": rng.choice(["true", "false"]),
                "detected_sentiment": rng.choice(["negativo", "neutral", "positivo"]),
                "was_escalated": "true" if cat == "Escalamiento" else "false",
            }
        )
        if rng.random() < 0.7:
            text = template.format(m=rng.choice(MERCHANTS), n=rng.randint(100000, 999999))
            trans.append(
                {
                    "transcript_id": f"R{iid[1:]}",
                    "customer_id": cid,
                    "interaction_id": iid,
                    "full_text": f"Agente: Buen día. Cliente: {text}",
                    "customer_text": text,
                    "detected_language": "es",
                    "detected_intents": reason,
                    "main_topics": cat,
                    "mentioned_entities": "",
                }
            )
        if cat == "Disputas" and rng.random() < 0.8:
            comp.append(
                {
                    "complaint_id": f"Q{50000000 + i}",
                    "creation_date": (when + timedelta(hours=1)).isoformat(sep=" "),
                    "customer_id": cid,
                    "case_type": "Reclamo",
                    "category": "Cargo no reconocido",
                    "subcategory": "Compra",
                    "reception_channel": "Teléfono",
                    "affected_product_id": rng.choice(prods)["product_id"],
                    "origin_interaction_id": iid,
                    "description": "Cliente no reconoce cargo",
                    "claimed_amount": f"{rng.uniform(10, 900):.2f}",
                    "priority": rng.choice(["Alta", "Media", "Baja"]),
                    "status": rng.choice(["Abierto", "Cerrado"]),
                    "sla_breached": rng.choice(["true", "false"]),
                    "resolution_days": rng.randint(1, 30),
                    "compensation_granted": rng.choice(["", "", f"{rng.uniform(5, 300):.2f}"]),
                    "is_repeat_complainer": rng.choice(["true", "false", "false"]),
                }
            )
    _write(
        raw_dir / "call_center_interactions" / "call_center_interactions.csv",
        _dirty(inter, rng, ["detected_sentiment"]),
    )
    _write(raw_dir / "call_transcripts" / "call_transcripts.csv", _dirty(trans, rng, ["main_topics"]))
    _write(raw_dir / "complaints" / "complaints.csv", _dirty(comp, rng, ["priority", "claimed_amount"]))


def write_late_batch(raw_dir: Path, rows: int = 20) -> None:
    """Lote que llega después con fechas antiguas (llegada tardía) y una corrección de un registro existente."""
    rng = random.Random(SEED + 1)  # noqa: S311
    late = []
    for i in range(rows):
        late.append(
            {
                "transaction_id": f"T{39000000 + i}",
                "transaction_date": _date(rng, START, START + timedelta(days=30)).isoformat(sep=" "),
                "customer_id": f"C{10000000 + rng.randint(0, 199)}",
                "product_id": "",
                "transaction_type": "Compra",
                "transaction_category": "Supermercado",
                "amount": "12.50",
                "currency": "USD",
                "amount_usd": "12.50",
                "channel": "POS",
                "merchant_name": "OXXO",
                "transaction_status": "Approved",
                "is_fraud": "False",
                "fraud_score": "0.010",
            }
        )
    _write(raw_dir / "transactions" / "late" / "transactions_late_2023.csv", late)
