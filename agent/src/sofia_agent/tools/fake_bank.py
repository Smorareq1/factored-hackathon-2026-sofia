"""Banco falso en proceso: implementa la propuesta de AG para §9.2 con estado en memoria.

Sirve para los tests y para desarrollar el agente y el frontend hasta que SIM publique su stub
(`BANK_API_URL=fake`). NO es el servicio de SIM: la política real (POL-1..POL-7) vive en `services/`.
Aquí se replica de forma mínima, con N y U provisionales hasta que DS los calibre (D2).

Datos: clientes y transacciones inventados por el equipo (origin: team_generated, CON-02);
los IDs usan el prefijo C9… para no chocar con el dataset.
"""

import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response

from sofia_contracts.bank_api import (
    DemoCustomer,
    Dispute,
    DisputeCreate,
    DisputeList,
    Eligibility,
    EligibilityRequest,
    HandoffList,
    HandoffReceipt,
    HarnessSessionRequest,
    SessionChallenge,
    SessionInfo,
    SessionStart,
    SessionToken,
    SessionVerify,
    Transaction,
    TransactionList,
)
from sofia_contracts.common import Country
from sofia_contracts.handoff import Handoff, HandoffDraft, HandoffFeedback, HandoffFeedbackRecord

DISPUTE_WINDOW_DAYS = 90  # N provisional (DS calibra el D2)
AMOUNT_THRESHOLD_USD = Decimal("500")  # U provisional (DS calibra el D2)
FRAUD_SCORE_THRESHOLD = 0.8
SESSION_TTL = timedelta(minutes=30)
ELIGIBILITY_TTL = timedelta(minutes=15)
USD_RATE = {"MXN": Decimal("18.5"), "COP": Decimal("4000"), "ARS": Decimal("1000"), "USD": Decimal("1")}


@dataclass
class _Customer:
    customer_id: str
    document_number: str
    country: Country
    label: str
    repeat_complainer: bool = False
    role: str = "customer"


@dataclass
class _Tx:
    tx: Transaction
    customer_id: str
    is_fraud: bool = False
    fraud_score: float = 0.05


@dataclass
class _Session:
    customer_id: str
    role: str
    country: Country | None
    expires_at: datetime


@dataclass
class FakeBankState:
    clock: Callable[[], datetime]
    customers: dict[str, _Customer] = field(default_factory=dict)
    txs: dict[str, _Tx] = field(default_factory=dict)
    challenges: dict[str, tuple[str, str, datetime]] = field(default_factory=dict)
    sessions: dict[str, _Session] = field(default_factory=dict)
    eligibilities: dict[str, tuple[str, str, datetime]] = field(default_factory=dict)
    disputes: dict[str, Dispute] = field(default_factory=dict)
    handoffs: dict[str, Handoff] = field(default_factory=dict)
    feedback: dict[str, HandoffFeedbackRecord] = field(default_factory=dict)
    idempotency: dict[str, object] = field(default_factory=dict)
    audit: list[dict[str, object]] = field(default_factory=list)
    # Inyección de fallas para tests: "POST /disputes" -> cola de status HTTP a devolver.
    faults: dict[str, list[int]] = field(default_factory=dict)
    # Simula un POST /disputes que "responde ok" pero no persiste (para probar VERIFY).
    drop_dispute_writes: bool = False
    _seq: int = 0

    @property
    def now(self) -> datetime:
        return self.clock()

    def next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self.now.year}-{self._seq:06d}"

    def expire_sessions(self) -> None:
        for s in self.sessions.values():
            s.expires_at = self.now - timedelta(seconds=1)


def _tx(
    tx_id: str, days_ago: int, amount: str, currency: str, merchant: str, status: str, now: datetime
) -> Transaction:
    value = Decimal(amount)
    return Transaction(
        transaction_id=tx_id,
        transaction_date=(now - timedelta(days=days_ago)).replace(hour=13, minute=20, second=0, microsecond=0),
        amount=value,
        currency=currency,
        amount_usd=(value / USD_RATE[currency]).quantize(Decimal("0.01")),
        merchant_name=merchant,
        transaction_status=status,
        channel="card_present" if merchant in {"OXXO", "Éxito"} else "online",
        transaction_type="purchase",
    )


def seed(state: FakeBankState) -> None:
    """Clientes demo que cubren los 3 caminos y los 3 países (propuesta #6)."""
    now = state.now
    for c in [
        _Customer("C90000001", "MX-DEMO-001", "MX", "Ana · MX · auto, aclaración y denegaciones"),
        _Customer("C90000002", "CO-DEMO-002", "CO", "Bruno · CO · monto alto (POL-6)"),
        _Customer("C90000003", "AR-DEMO-003", "AR", "Carla · AR · reincidente (POL-6)", repeat_complainer=True),
        _Customer("C90000004", "AR-DEMO-004", "AR", "João · AR · habla portugués"),
        _Customer("A90000001", "AGENTE-DEMO", "MX", "Agente humano · consola", role="agent"),
    ]:
        state.customers[c.customer_id] = c

    rows = [
        # cliente, id, días atrás, monto, moneda, comercio, estado, fraude, score
        ("C90000001", "TX-MX-0001", 2, "349.00", "MXN", "Rappi", "Approved", False, 0.04),
        ("C90000001", "TX-MX-0002", 5, "189.50", "MXN", "Cinépolis", "Approved", False, 0.03),
        ("C90000001", "TX-MX-0003", 5, "189.50", "MXN", "Cinépolis", "Approved", False, 0.05),
        ("C90000001", "TX-MX-0004", 10, "15800.00", "MXN", "Liverpool", "Approved", False, 0.10),
        ("C90000001", "TX-MX-0005", 12, "520.00", "MXN", "OXXO", "Declined", False, 0.02),
        ("C90000001", "TX-MX-0006", 150, "899.00", "MXN", "Amazon MX", "Approved", False, 0.03),
        ("C90000001", "TX-MX-0007", 20, "1250.00", "MXN", "Walmart", "Approved", False, 0.06),
        ("C90000001", "TX-MX-0008", 3, "2100.00", "MXN", "Uber", "Approved", True, 0.91),
        ("C90000001", "TX-MX-0009", 1, "89.00", "MXN", "Spotify", "Approved", False, 0.01),
        ("C90000002", "TX-CO-0001", 4, "85000", "COP", "Éxito", "Approved", False, 0.04),
        ("C90000002", "TX-CO-0002", 6, "3200000", "COP", "Falabella", "Approved", False, 0.20),
        ("C90000003", "TX-AR-0001", 3, "25000", "ARS", "Mercado Libre", "Approved", False, 0.05),
        ("C90000004", "TX-AR-0101", 2, "18500", "ARS", "Mercado Libre", "Approved", False, 0.03),
        ("C90000004", "TX-AR-0102", 7, "920000", "ARS", "Frávega", "Approved", False, 0.15),
        ("C90000004", "TX-AR-0103", 4, "4500", "ARS", "Netflix", "Approved", False, 0.02),
        ("C90000004", "TX-AR-0104", 4, "4500", "ARS", "Netflix", "Approved", False, 0.02),
    ]
    for customer_id, tx_id, days, amount, currency, merchant, status, fraud, score in rows:
        state.txs[tx_id] = _Tx(_tx(tx_id, days, amount, currency, merchant, status, now), customer_id, fraud, score)

    # POL-4: disputa ya abierta sobre TX-MX-0007.
    existing = Dispute(
        dispute_id="DSP-2026-000900",
        transaction_id="TX-MX-0007",
        customer_id="C90000001",
        status="open",
        customer_claim="not_received",
        created_at=now - timedelta(days=15),
    )
    state.disputes[existing.dispute_id] = existing


def create_fake_bank(now: datetime | None = None) -> tuple[FastAPI, FakeBankState]:
    state = FakeBankState(clock=(lambda: now) if now else (lambda: datetime.now(UTC)))
    seed(state)
    app = FastAPI(title="Banco falso (propuesta AG §9.2)", version="0.1.0")

    def inject_faults(method: str, path: str) -> None:
        queue = state.faults.get(f"{method} {path}")
        if queue:
            raise HTTPException(status_code=queue.pop(0), detail="fault_injected")

    def auth(authorization: Annotated[str | None, Header()] = None) -> _Session:
        token = (authorization or "").removeprefix("Bearer ").strip()
        session = state.sessions.get(token)
        if session is None or session.expires_at <= state.now:
            raise HTTPException(status_code=401, detail="session_invalid_or_expired")
        return session

    def customer_session(session: Annotated[_Session, Depends(auth)]) -> _Session:
        if session.role != "customer":
            raise HTTPException(status_code=403, detail="customer_role_required")
        return session

    Customer = Annotated[_Session, Depends(customer_session)]

    @app.get("/demo/customers")
    def demo_customers() -> list[DemoCustomer]:
        return [
            DemoCustomer(document_number=c.document_number, label=c.label, country=c.country, role=c.role)
            for c in state.customers.values()
        ]

    @app.post("/session")
    def start_session(body: SessionStart) -> SessionChallenge:
        customer = next((c for c in state.customers.values() if c.document_number == body.document_number), None)
        challenge_id = secrets.token_urlsafe(12)
        otp = f"{secrets.randbelow(10**6):06d}"
        expires = state.now + timedelta(minutes=5)
        # Mismo shape exista o no el documento: no se revela quién es cliente.
        if customer is not None:
            state.challenges[challenge_id] = (customer.customer_id, otp, expires)
        return SessionChallenge(challenge_id=challenge_id, expires_at=expires, simulated_otp=otp)

    @app.post("/session/verify")
    def verify_session(body: SessionVerify) -> SessionToken:
        entry = state.challenges.pop(body.challenge_id, None)
        if entry is None or entry[1] != body.otp or entry[2] <= state.now:
            raise HTTPException(status_code=401, detail="otp_invalid")
        customer = state.customers[entry[0]]
        token = secrets.token_urlsafe(24)
        expires = state.now + SESSION_TTL
        state.sessions[token] = _Session(customer.customer_id, customer.role, customer.country, expires)
        return SessionToken(access_token=token, expires_at=expires, role=customer.role)

    @app.post("/session/test")
    def harness_session(body: HarnessSessionRequest) -> SessionToken:
        """Solo sandbox: el harness abre la sesión del `session_customer_id` del caso sin OTP."""
        customer = state.customers.get(body.customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="not_found")
        token = secrets.token_urlsafe(24)
        expires = state.now + SESSION_TTL
        state.sessions[token] = _Session(customer.customer_id, customer.role, customer.country, expires)
        return SessionToken(access_token=token, expires_at=expires, role=customer.role)

    @app.get("/session/me")
    def session_me(session: Annotated[_Session, Depends(auth)]) -> SessionInfo:
        inject_faults("GET", "/session/me")
        return SessionInfo(
            customer_id=session.customer_id, role=session.role, country=session.country, expires_at=session.expires_at
        )

    @app.get("/transactions")
    def list_transactions(
        session: Customer,
        since: date | None = None,
        until: date | None = None,
        merchant: str | None = None,
        limit: Annotated[int, Query(le=200)] = 50,
    ) -> TransactionList:
        inject_faults("GET", "/transactions")
        items = [t.tx for t in state.txs.values() if t.customer_id == session.customer_id]
        if since:
            items = [t for t in items if t.transaction_date.date() >= since]
        if until:
            items = [t for t in items if t.transaction_date.date() <= until]
        if merchant:
            items = [t for t in items if merchant.casefold() in t.merchant_name.casefold()]
        items.sort(key=lambda t: t.transaction_date, reverse=True)
        return TransactionList(items=items[:limit])

    @app.get("/transactions/{transaction_id}")
    def get_transaction(transaction_id: str, session: Customer) -> Transaction:
        inject_faults("GET", "/transactions/{id}")
        row = state.txs.get(transaction_id)
        if row is None or row.customer_id != session.customer_id:
            state.audit.append({"event": "tx_access_denied", "customer_id": session.customer_id, "tx": transaction_id})
            raise HTTPException(status_code=404, detail="not_found")
        return row.tx

    @app.post("/disputes/eligibility")
    def eligibility(body: EligibilityRequest, session: Customer) -> Eligibility:
        inject_faults("POST", "/disputes/eligibility")
        result = _evaluate_policy(state, session.customer_id, body.transaction_id)
        state.audit.append({"event": "eligibility", "customer_id": session.customer_id, "rule": result.rule_id})
        return result

    @app.post("/disputes")
    def create_dispute(
        body: DisputeCreate,
        session: Customer,
        response: Response,
        idempotency_key: Annotated[str | None, Header()] = None,
    ) -> Dispute:
        inject_faults("POST", "/disputes")
        if not idempotency_key:
            raise HTTPException(status_code=422, detail="idempotency_key_required")
        cached = state.idempotency.get(f"dispute:{idempotency_key}")
        if isinstance(cached, Dispute):
            return cached
        entry = state.eligibilities.get(body.eligibility_id)
        if entry is None or entry[0] != session.customer_id or entry[1] != body.transaction_id:
            raise HTTPException(status_code=409, detail="eligibility_not_found")
        if entry[2] <= state.now:
            raise HTTPException(status_code=409, detail="eligibility_expired")
        if not body.confirmation.text.strip():
            raise HTTPException(status_code=422, detail="confirmation_required")
        dispute = Dispute(
            dispute_id=state.next_id("DSP"),
            transaction_id=body.transaction_id,
            customer_id=session.customer_id,
            status="open",
            customer_claim=body.customer_claim,
            created_at=state.now,
        )
        state.eligibilities.pop(body.eligibility_id)
        state.idempotency[f"dispute:{idempotency_key}"] = dispute
        if not state.drop_dispute_writes:
            state.disputes[dispute.dispute_id] = dispute
        state.audit.append({"event": "dispute_created", "customer_id": session.customer_id, "id": dispute.dispute_id})
        response.status_code = 201
        return dispute

    @app.get("/disputes")
    def list_disputes(session: Customer, status: str | None = None) -> DisputeList:
        inject_faults("GET", "/disputes")
        items = [d for d in state.disputes.values() if d.customer_id == session.customer_id]
        if status:
            items = [d for d in items if d.status == status]
        return DisputeList(items=sorted(items, key=lambda d: d.created_at, reverse=True))

    @app.get("/disputes/{dispute_id}")
    def get_dispute(dispute_id: str, session: Customer) -> Dispute:
        inject_faults("GET", "/disputes/{id}")
        dispute = state.disputes.get(dispute_id)
        if dispute is None or dispute.customer_id != session.customer_id:
            raise HTTPException(status_code=404, detail="not_found")
        return dispute

    @app.post("/handoff")
    def create_handoff(
        body: HandoffDraft,
        session: Customer,
        response: Response,
        idempotency_key: Annotated[str | None, Header()] = None,
    ) -> HandoffReceipt:
        inject_faults("POST", "/handoff")
        if body.customer_id != session.customer_id:
            raise HTTPException(status_code=403, detail="customer_mismatch")
        key = f"handoff:{idempotency_key}" if idempotency_key else None
        cached = state.idempotency.get(key) if key else None
        if isinstance(cached, HandoffReceipt):
            return cached
        handoff = Handoff(**body.model_dump(), handoff_id=state.next_id("HO"), created_at=state.now)
        receipt = HandoffReceipt(handoff_id=handoff.handoff_id, created_at=handoff.created_at)
        if key:
            state.idempotency[key] = receipt
        state.handoffs[handoff.handoff_id] = handoff
        response.status_code = 201
        return receipt

    @app.get("/handoffs/{handoff_id}")
    def get_handoff(handoff_id: str, session: Annotated[_Session, Depends(auth)]) -> Handoff:
        inject_faults("GET", "/handoffs/{id}")
        handoff = state.handoffs.get(handoff_id)
        if handoff is None or (session.role != "agent" and handoff.customer_id != session.customer_id):
            raise HTTPException(status_code=404, detail="not_found")
        return handoff

    @app.get("/handoffs")
    def list_handoffs(session: Annotated[_Session, Depends(auth)]) -> HandoffList:
        if session.role != "agent":
            raise HTTPException(status_code=403, detail="agent_role_required")
        return HandoffList(items=sorted(state.handoffs.values(), key=lambda h: h.created_at, reverse=True))

    def agent_session(session: Annotated[_Session, Depends(auth)]) -> _Session:
        if session.role != "agent":
            raise HTTPException(status_code=403, detail="agent_role_required")
        return session

    @app.post("/handoffs/{handoff_id}/feedback")
    def give_feedback(
        handoff_id: str, body: HandoffFeedback, session: Annotated[_Session, Depends(agent_session)]
    ) -> HandoffFeedbackRecord:
        if handoff_id not in state.handoffs:
            raise HTTPException(status_code=404, detail="not_found")
        record = HandoffFeedbackRecord(
            **body.model_dump(), handoff_id=handoff_id, reviewer_id=session.customer_id, submitted_at=state.now
        )
        state.feedback[handoff_id] = record
        return record

    @app.get("/handoffs/{handoff_id}/feedback")
    def read_feedback(handoff_id: str, _: Annotated[_Session, Depends(agent_session)]) -> HandoffFeedbackRecord:
        record = state.feedback.get(handoff_id)
        if record is None:
            raise HTTPException(status_code=404, detail="not_found")
        return record

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "fake-bank"}

    return app, state


def _evaluate_policy(state: FakeBankState, customer_id: str, transaction_id: str) -> Eligibility:
    """Réplica mínima del motor de SIM, en el orden POL-1 → POL-4 → POL-2 → POL-3 → POL-6 → POL-5."""
    row = state.txs.get(transaction_id)
    if row is None or row.customer_id != customer_id:
        return Eligibility(eligible=False, rule_id="POL-1", reason="transaction_not_accessible", route="deny")
    existing = next(
        (
            d
            for d in state.disputes.values()
            if d.transaction_id == transaction_id and d.status in {"open", "in_review"}
        ),
        None,
    )
    if existing:
        return Eligibility(
            eligible=False,
            rule_id="POL-4",
            reason="dispute_already_open",
            route="deny",
            existing_dispute_id=existing.dispute_id,
        )
    tx = row.tx
    if tx.transaction_status != "Approved":
        return Eligibility(eligible=False, rule_id="POL-2", reason="status_not_disputable", route="deny")
    if tx.transaction_date < state.now - timedelta(days=DISPUTE_WINDOW_DAYS):
        return Eligibility(eligible=False, rule_id="POL-3", reason="outside_dispute_window", route="deny")
    flags = []
    if tx.amount_usd > AMOUNT_THRESHOLD_USD:
        flags.append("high_amount")
    if row.is_fraud or row.fraud_score >= FRAUD_SCORE_THRESHOLD:
        flags.append("fraud_suspected")
    if state.customers[customer_id].repeat_complainer:
        flags.append("repeat_complainer")
    if flags:
        return Eligibility(
            eligible=True, rule_id="POL-6", reason="requires_human_review", route="human", risk_flags=flags
        )
    eligibility_id = f"ELG-{secrets.token_hex(6)}"
    expires = state.now + ELIGIBILITY_TTL
    state.eligibilities[eligibility_id] = (customer_id, transaction_id, expires)
    return Eligibility(
        eligible=True,
        rule_id="POL-5",
        reason="low_amount_no_risk",
        route="auto",
        eligibility_id=eligibility_id,
        expires_at=expires,
    )


_default: tuple[FastAPI, FakeBankState] | None = None


def default_fake_bank() -> tuple[FastAPI, FakeBankState]:
    """Instancia compartida del proceso (modo `BANK_API_URL=fake`)."""
    global _default
    if _default is None:
        _default = create_fake_bank()
    return _default
