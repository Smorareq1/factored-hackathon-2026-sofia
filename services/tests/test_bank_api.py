"""Tests de integración de la API bancaria (endpoints, permisos, idempotencia, fallas)."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from sofia_services.faults.manager import fault_manager
from sofia_services.main import app
from sofia_services.store import reset_store

client = TestClient(app)


def setup_function() -> None:
    reset_store()
    fault_manager.reset()


def test_auth_full_flow() -> None:
    """Flujo completo de sesión: Documento -> Challenge con OTP -> Verify -> Token -> Session me."""
    # 1. Start session
    resp = client.post("/session", json={"document_number": "MX-DEMO-001"})
    assert resp.status_code == 200
    challenge = resp.json()
    assert "challenge_id" in challenge
    assert "simulated_otp" in challenge
    otp = challenge["simulated_otp"]

    # 2. Verify OTP incorrecto
    bad_resp = client.post("/session/verify", json={"challenge_id": challenge["challenge_id"], "otp": "999999"})
    assert bad_resp.status_code == 401

    # 3. Verify OTP correcto
    ok_resp = client.post("/session/verify", json={"challenge_id": challenge["challenge_id"], "otp": otp})
    assert ok_resp.status_code == 200
    token_data = ok_resp.json()
    token = token_data["access_token"]
    assert token_data["role"] == "customer"

    # 4. GET /session/me
    me_resp = client.get("/session/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["customer_id"] == "C90000001"
    assert me_data["country"] == "MX"


def test_auth_harness_session() -> None:
    """Sesión directa de sandbox para el harness (§9.5)."""
    resp = client.post("/session/test", json={"customer_id": "C90000002"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me_resp = client.get("/session/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["customer_id"] == "C90000002"

    # Cliente inexistente
    bad_resp = client.post("/session/test", json={"customer_id": "C_NON_EXISTENT"})
    assert bad_resp.status_code == 404


def test_transactions_access_control() -> None:
    """POL-1: Un cliente no puede ver ni listar transacciones ajenas."""
    token1 = client.post("/session/test", json={"customer_id": "C90000001"}).json()["access_token"]
    token2 = client.post("/session/test", json={"customer_id": "C90000002"}).json()["access_token"]

    # C90000001 ve sus transacciones
    txs_resp1 = client.get("/transactions", headers={"Authorization": f"Bearer {token1}"})
    assert txs_resp1.status_code == 200
    tx_ids1 = [t["transaction_id"] for t in txs_resp1.json()["items"]]
    assert "TX-MX-0001" in tx_ids1
    assert "TX-CO-0001" not in tx_ids1  # pertenece a C90000002

    # C90000001 consulta TX-MX-0001 -> 200
    tx_resp = client.get("/transactions/TX-MX-0001", headers={"Authorization": f"Bearer {token1}"})
    assert tx_resp.status_code == 200

    # C90000001 intenta consultar TX-CO-0001 (de C90000002) -> 404 sin revelar si existe
    unauth_resp = client.get("/transactions/TX-CO-0001", headers={"Authorization": f"Bearer {token1}"})
    assert unauth_resp.status_code == 404

    # C90000002 sí puede ver TX-CO-0001
    auth2_resp = client.get("/transactions/TX-CO-0001", headers={"Authorization": f"Bearer {token2}"})
    assert auth2_resp.status_code == 200


def test_disputes_create_and_idempotency() -> None:
    """Creación de disputa verificada con elegibilidad, confirmación e idempotencia."""
    token = client.post("/session/test", json={"customer_id": "C90000001"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Chequeo de elegibilidad -> POL-5 (auto)
    elg_resp = client.post("/disputes/eligibility", json={"transaction_id": "TX-MX-0001"}, headers=headers)
    assert elg_resp.status_code == 200
    elg = elg_resp.json()
    assert elg["eligible"] is True
    assert elg["route"] == "auto"
    eligibility_id = elg["eligibility_id"]

    # 2. Creación sin Idempotency-Key -> 422
    body = {
        "transaction_id": "TX-MX-0001",
        "eligibility_id": eligibility_id,
        "customer_claim": "not_recognized",
        "confirmation": {
            "text": "Sí, confirmo la disputa del cargo de Rappi",
            "turn": 3,
            "confirmed_at": datetime.now(UTC).isoformat(),
        },
    }
    no_key_resp = client.post("/disputes", json=body, headers=headers)
    assert no_key_resp.status_code == 422

    # 3. Creación exitosa
    create_headers = {**headers, "Idempotency-Key": "idemp-test-001"}
    create_resp = client.post("/disputes", json=body, headers=create_headers)
    assert create_resp.status_code == 201
    dispute = create_resp.json()
    assert dispute["dispute_id"].startswith("DSP-")
    assert dispute["transaction_id"] == "TX-MX-0001"
    assert dispute["status"] == "open"

    # 4. Llamada idéntica con el mismo Idempotency-Key devuelve el mismo objeto
    idemp_resp = client.post("/disputes", json=body, headers=create_headers)
    assert idemp_resp.status_code == 201
    assert idemp_resp.json()["dispute_id"] == dispute["dispute_id"]

    # 5. Intentar crear otra disputa con el eligibility_id ya consumido -> 409
    dup_body = dict(body)
    dup_resp = client.post("/disputes", json=dup_body, headers={**headers, "Idempotency-Key": "idemp-test-002"})
    assert dup_resp.status_code == 409

    # 6. Consultar disputa creada (VERIFY)
    verify_resp = client.get(f"/disputes/{dispute['dispute_id']}", headers=headers)
    assert verify_resp.status_code == 200
    assert verify_resp.json()["dispute_id"] == dispute["dispute_id"]


def test_handoff_flow() -> None:
    """Recepción de handoff estructurado y feedback del agente."""
    cust_token = client.post("/session/test", json={"customer_id": "C90000001"}).json()["access_token"]
    agent_token = client.post("/session/test", json={"customer_id": "A90000001"}).json()["access_token"]

    draft = {
        "schema_version": "1.0",
        "language": "es",
        "customer_id": "C90000001",
        "authenticated": True,
        "request_summary": "Cliente disputa cargo de 15800 MXN en Liverpool",
        "customer_claim": "wrong_amount",
        "verified_facts": [{"fact": "TX existe", "source": "GET /transactions/TX-MX-0004"}],
        "actions_taken": [{"action": "eligibility_check", "result": "route=human", "verified": True}],
        "open_questions": ["¿Reconoce compras previas en este comercio?"],
        "risk_flags": ["high_amount"],
        "reason_for_handoff": "POL-6",
        "system_version": "proposed",
    }

    # Creación del handoff
    post_resp = client.post(
        "/handoff",
        json=draft,
        headers={"Authorization": f"Bearer {cust_token}", "Idempotency-Key": "ho-idemp-01"},
    )
    assert post_resp.status_code == 201
    receipt = post_resp.json()
    assert receipt["handoff_id"].startswith("HO-")
    handoff_id = receipt["handoff_id"]

    # Agente lista los handoffs
    list_resp = client.get("/handoffs", headers={"Authorization": f"Bearer {agent_token}"})
    assert list_resp.status_code == 200
    assert any(h["handoff_id"] == handoff_id for h in list_resp.json()["items"])

    # Agente envía feedback
    fb_resp = client.post(
        f"/handoffs/{handoff_id}/feedback",
        json={"useful": True, "missing_fields": [], "comment": "Ficha completa"},
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert fb_resp.status_code == 200
    assert fb_resp.json()["useful"] is True


def test_fault_injection_drop_writes() -> None:
    """Inyección de falla drop_writes: responde 201 pero no persiste (prueba de VERIFY)."""
    fault_manager.set_drop_writes(True)
    token = client.post("/session/test", json={"customer_id": "C90000001"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    elg = client.post("/disputes/eligibility", json={"transaction_id": "TX-MX-0001"}, headers=headers).json()
    body = {
        "transaction_id": "TX-MX-0001",
        "eligibility_id": elg["eligibility_id"],
        "customer_claim": "not_recognized",
        "confirmation": {
            "text": "Confirmo",
            "turn": 2,
            "confirmed_at": datetime.now(UTC).isoformat(),
        },
    }
    create_resp = client.post("/disputes", json=body, headers={**headers, "Idempotency-Key": "drop-write-test"})
    assert create_resp.status_code == 201
    dsp_id = create_resp.json()["dispute_id"]

    # Al releer la disputa en el paso VERIFY, no existe (404) -> el agente debe escalar y no afirmar éxito
    get_resp = client.get(f"/disputes/{dsp_id}", headers=headers)
    assert get_resp.status_code == 404


def test_transactions_amount_filter() -> None:
    """Filtro por monto exacto en GET /transactions (§9.2)."""
    token = client.post("/session/test", json={"customer_id": "C90000001"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # TX-MX-0001 tiene monto 349.00 MXN en Rappi
    resp = client.get("/transactions?amount=349.00", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert all(float(t["amount"]) == 349.00 for t in items)

    # Monto inexistente
    resp_empty = client.get("/transactions?amount=999999.99", headers=headers)
    assert resp_empty.status_code == 200
    assert len(resp_empty.json()["items"]) == 0


def test_admin_and_test_endpoints_restricted_in_cloud() -> None:
    """Protege /admin/* y /session/test cuando SOFIA_ENV=cloud salvo con X-Admin-Key."""
    from sofia_services.store import get_store

    store = get_store()
    orig_env = store.settings.SOFIA_ENV
    orig_key = store.settings.ADMIN_API_KEY
    try:
        store.settings.SOFIA_ENV = "cloud"
        store.settings.ADMIN_API_KEY = "bank-admin-secret"

        # 1. /admin/audit sin clave en cloud -> 403
        resp = client.get("/admin/audit")
        assert resp.status_code == 403

        # 2. /session/test sin clave en cloud -> 403
        resp_test = client.post("/session/test", json={"customer_id": "C90000001"})
        assert resp_test.status_code == 403

        # 3. Con clave errónea -> 403
        resp_bad = client.get("/admin/audit", headers={"X-Admin-Key": "wrong-key"})
        assert resp_bad.status_code == 403

        # 4. Con clave correcta -> 200
        resp_ok = client.get("/admin/audit", headers={"X-Admin-Key": "bank-admin-secret"})
        assert resp_ok.status_code == 200

        resp_sess_ok = client.post(
            "/session/test",
            json={"customer_id": "C90000001"},
            headers={"X-Admin-Key": "bank-admin-secret"},
        )
        assert resp_sess_ok.status_code == 200
    finally:
        store.settings.SOFIA_ENV = orig_env
        store.settings.ADMIN_API_KEY = orig_key


def test_latency_fault_injection() -> None:
    """Inyección de latencia vía /admin/faults/latency."""
    import time

    token = client.post("/session/test", json={"customer_id": "C90000001"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Inyectar 0.05 segundos de delay en GET /transactions
    fault_resp = client.post(
        "/admin/faults/latency",
        json={"method": "GET", "path": "/transactions", "delay_s": 0.05, "times": 1},
    )
    assert fault_resp.status_code == 200

    start = time.perf_counter()
    resp = client.get("/transactions", headers=headers)
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    assert elapsed >= 0.04

