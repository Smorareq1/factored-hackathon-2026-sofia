"""Servicio HTTP: login por OTP (proxy), chat por SSE, propiedad del hilo y consola."""

import json

import httpx
import pytest

from sofia_agent.api.main import app
from sofia_agent.api.runtime import open_runtime
from sofia_agent.config import Settings


@pytest.fixture
async def client():
    settings = Settings(SOFIA_LLM_MODE="rules", BANK_API_URL="fake")
    async with open_runtime(settings) as runtime:
        app.state.runtime = runtime
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://agent") as http:
            yield http


async def login(client: httpx.AsyncClient, document: str) -> dict[str, str]:
    challenge = (await client.post("/v1/session", json={"document_number": document})).json()
    verify = {"challenge_id": challenge["challenge_id"], "otp": challenge["simulated_otp"]}
    token = (await client.post("/v1/session/verify", json=verify)).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events, name = [], None
    for line in body.replace("\r\n", "\n").split("\n"):
        if line.startswith("event:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and name:
            events.append((name, json.loads(line.split(":", 1)[1].strip())))
            name = None
    return events


async def chat(client, headers, thread_id: str, message: str) -> list[tuple[str, dict]]:
    response = await client.post("/v1/chat", headers=headers, json={"thread_id": thread_id, "message": message})
    assert response.status_code == 200
    return parse_sse(response.text)


async def test_wrong_otp_is_rejected(client):
    challenge = (await client.post("/v1/session", json={"document_number": "MX-DEMO-001"})).json()
    response = await client.post(
        "/v1/session/verify", json={"challenge_id": challenge["challenge_id"], "otp": "000000"}
    )
    assert response.status_code == 401


async def test_chat_streams_layer_events_then_message_and_done(client):
    headers = await login(client, "MX-DEMO-001")
    events = await chat(client, headers, "thread-api-0001", "No reconozco el cargo de Rappi")
    names = [name for name, _ in events]
    assert names[0] == "layer" and names[-2:] == ["message", "done"]
    layers = [data["layer"] for name, data in events if name == "layer"]
    assert layers.index("SENSE") < layers.index("INTERPRET") < layers.index("DECIDE") < layers.index("ORCHESTRATE")
    message = next(data for name, data in events if name == "message")
    assert message["quick_replies"] == ["Sí, confirmo", "No"]

    events = await chat(client, headers, "thread-api-0001", "Sí, confirmo")
    done = next(data for name, data in events if name == "done")
    assert done["route"] == "auto" and done["goal_status"] == "resolved" and done["turn"] == 2


async def test_escalation_streams_the_handoff(client):
    headers = await login(client, "CO-DEMO-002")
    events = await chat(client, headers, "thread-api-0002", "No reconozco el cargo de Falabella")
    handoff = next(data for name, data in events if name == "handoff")
    assert handoff["reason_for_handoff"] == "POL-6"

    agent = await login(client, "AGENTE-DEMO")
    queue = (await client.get("/v1/console/handoffs", headers=agent)).json()["items"]
    assert handoff["handoff_id"] in [h["handoff_id"] for h in queue]
    # Un cliente no puede leer la cola de la consola.
    assert (await client.get("/v1/console/handoffs", headers=headers)).status_code == 403


async def test_thread_belongs_to_its_customer(client):
    ana = await login(client, "MX-DEMO-001")
    bruno = await login(client, "CO-DEMO-002")
    await chat(client, ana, "thread-api-0003", "No reconozco el cargo de Rappi")

    assert (await client.get("/v1/threads/thread-api-0003", headers=bruno)).status_code == 403
    response = await client.post("/v1/chat", headers=bruno, json={"thread_id": "thread-api-0003", "message": "hola"})
    assert response.status_code == 403

    history = (await client.get("/v1/threads/thread-api-0003", headers=ana)).json()
    assert [m["role"] for m in history["messages"]] == ["customer", "agent"]


async def test_chat_without_valid_session_does_not_touch_the_thread(client):
    events = await chat(client, {"Authorization": "Bearer invalido"}, "thread-api-0004", "hola")
    assert events == [("error", {"code": "session_expired", "message": "reauth"})]


async def test_console_feedback_is_stored_for_agents_only(client):
    customer = await login(client, "CO-DEMO-002")
    events = await chat(client, customer, "thread-api-0003", "No reconozco el cargo de Falabella")
    handoff_id = next(data for name, data in events if name == "handoff")["handoff_id"]
    agent = await login(client, "AGENTE-DEMO")
    url = f"/v1/console/handoffs/{handoff_id}/feedback"
    feedback = {"useful": False, "missing_fields": ["open_questions"], "comment": "Faltó el canal de la compra"}

    assert (await client.get(url, headers=agent)).status_code == 404  # todavía sin feedback
    record = (await client.post(url, headers=agent, json=feedback)).json()
    assert record["handoff_id"] == handoff_id and record["reviewer_id"] == "A90000001"
    assert record["useful"] is False and record["missing_fields"] == ["open_questions"]
    assert (await client.get(url, headers=agent)).json() == record

    assert (await client.post(url, headers=customer, json=feedback)).status_code == 403
    missing = "/v1/console/handoffs/HO-2026-999999/feedback"
    assert (await client.post(missing, headers=agent, json=feedback)).status_code == 404


async def test_baseline_needs_an_llm(client):
    assert (await client.get("/v1/meta")).json()["baseline_available"] is False
    headers = await login(client, "MX-DEMO-001")
    body = {"thread_id": "thread-api-base", "message": "Hola", "system_version": "baseline"}
    events = parse_sse((await client.post("/v1/chat", headers=headers, json=body)).text)
    assert events == [("error", {"code": "baseline_unavailable", "message": "El baseline necesita Gemini."})]
