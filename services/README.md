# SIM: simulated bank API and evaluation services (services/)

Simulated banking service for the transaction-dispute intake workflow (**Transaction-Dispute Intake**, REQ-01): financial policy governance (POL-1..POL-7, REQ-10), trusted authentication with session + OTP (REQ-11), auditable logging (REQ-19) and controlled fault injection (REQ-15, REQ-16).

---

## 1. Architecture and responsibilities

SIM owns the financial backend (`sofia-services`). Everything involving business truth, policy validation and persistence of transactions/disputes lives in this service and **not in the LLM**:

- **Authentication and session (§9.2, REQ-11)**: issues challenges with a simulated OTP for the demo, verifies the OTP and issues session tokens with a 30-minute TTL.
- **Permission control (§9.2, POL-1, REQ-10)**: transaction queries (`/transactions`) return only the authenticated customer's transactions. If a customer tries to read someone else's transaction, an identical `404 Not Found` is returned so third-party data is not revealed.
- **Deterministic policy engine (POL-1..POL-6, REQ-10)**: checks dispute eligibility (`POST /disputes/eligibility`) by evaluating deterministic rules over historical data.
- **Idempotent dispute registration (§9.2, REQ-09)**: `POST /disputes` requires an `Idempotency-Key` header, a valid `eligibility_id` and explicit proof of confirmation (`ConfirmationProof`).
- **Simulation and harness (REQ-15, REQ-16)**: admin endpoints under `/admin/*` for HTTP fault injection, forced session expiry, silent write failures (`drop_writes`) and latency/timeout injection.

---

## 2. API endpoints (§9.2)

| Method | Endpoint | Role / Auth | Purpose |
|---|---|---|---|
| `GET` | `/health` | Public | Service healthcheck |
| `GET` | `/demo/customers` | Public | Lists synthetic customers for the demo frontend selector |
| `POST` | `/session` | Public | Starts a session with a document number; issues a challenge + OTP |
| `POST` | `/session/verify` | Public | Validates the OTP and returns a Bearer session token |
| `POST` | `/session/test` | Protected / Sandbox | Opens a session directly for a `session_customer_id` in the harness |
| `GET` | `/session/me` | Customer / Agent | Authenticated customer's information |
| `GET` | `/transactions` | Customer | Lists the customer's transactions with filters (`since`, `until`, `merchant`, `amount`, `limit`) |
| `GET` | `/transactions/{id}` | Customer | Transaction detail (POL-1: 404 if it belongs to someone else) |
| `POST` | `/disputes/eligibility` | Customer | Evaluates policies POL-1..POL-6 and issues an `eligibility_id` |
| `POST` | `/disputes` | Customer | Registers the dispute (requires `Idempotency-Key` and `ConfirmationProof`) |
| `GET` | `/disputes` | Customer | Lists the authenticated customer's disputes |
| `GET` | `/disputes/{id}` | Customer | Dispute detail |
| `POST` | `/handoff` | Customer / Agent | Registers a structured handoff card to a human |
| `GET` | `/handoffs` | Agent | Lists pending handoffs for the human console |
| `POST` | `/handoffs/{id}/feedback` | Agent | Sends feedback on how useful the received handoff was |
| `POST` | `/admin/faults/http` | Admin / Sandbox | Injects an HTTP error code for a method/route |
| `POST` | `/admin/faults/latency` | Admin / Sandbox | Injects controlled latency to simulate timeouts |
| `POST` | `/admin/faults/drop-writes` | Admin / Sandbox | Simulates a successful response without persisting (silent failure) |
| `POST` | `/admin/faults/expire-sessions`| Admin / Sandbox | Expires every active session |
| `POST` | `/admin/faults/reset` | Admin / Sandbox | Clears every injected fault |
| `GET` | `/admin/audit` | Admin / Sandbox | Audit event log |
| `POST` | `/admin/reset-store` | Admin / Sandbox | Resets the store state and the faults |

---

## 3. Security and protection in the cloud

To prevent abuse or unauthorized tampering in the public Google Cloud Run deployment:

1. **Environment gating (`SOFIA_ENV`)**:
   - When `SOFIA_ENV=cloud` (or `production`), the `/admin/*` routes and `POST /session/test` are blocked by default with `403 Forbidden`.
   - To reach them in cloud environments from evaluation or admin tools, the `X-Admin-Key` header must carry the value of `ADMIN_API_KEY`.
2. **Local environment**:
   - In local development (`SOFIA_ENV=local` or `test`), the admin and sandbox endpoints are open, to make running the harness and the automated tests easy.

---

## 4. Calibrated banking policy (§8.3)

The policy parameters were analyzed by the Data Science owner (`analysis/notebooks/02_policy_calibration.ipynb` → `analysis/results/policy_calibration.json`):

- **$N$ (dispute window)**: **90 days**. It cannot be calibrated from the data (the dataset does not link disputes to their transactions); it follows Mexico's 90-calendar-day window to object to unrecognized charges, within Visa/Mastercard's 120-day chargeback window.
- **$U$ (amount threshold)**: **500.00 USD**. Approved purchases top out near 500 USD (p95 475), so almost every purchase dispute can be automated, while large claims (23% of claimed amounts) go to specialized human review (POL-6).
- **Fraud threshold**: **0.30** on the policy's 0–1 scale (= 30 on gold's 0–100 `fraud_score`, which the store converts when loading gold). It is the minimum expected cost with a missed fraud costing 40–50× an extra review: recall 0.69, precision 0.80, 0.08% of transactions sent to review.

---

## 5. Level 5 fault injection (REQ-15, REQ-16)

The fault manager (`FaultManager`) puts the agent through stress tests and adverse scenarios without compromising system stability:

1. **HTTP error (`POST /admin/faults/http`)**:
   - Simulates dependency outages (e.g. `500 Internal Server Error` or `503 Service Unavailable` repeated $k$ times).
2. **Session expiry (`POST /admin/faults/expire-sessions`)**:
   - Invalidates the active tokens to check that the agent moves to the `reauth` route and asks to re-authenticate without losing the conversation context.
3. **Persistence failure / drop writes (`POST /admin/faults/drop-writes`)**:
   - `POST /disputes` returns a simulated `201 Created` but skips persisting in memory/database. It checks that the agent's `VERIFY` node detects the omission and escalates to a human with the corresponding alert instead of claiming a false success to the customer (REQ-09, MET-04).
4. **Latency and timeouts (`POST /admin/faults/latency`)**:
   - Adds a `delay_s`-second delay to the chosen endpoint. It checks that the bank client (`BankClient`) respects the time limit (`tool_timeout_s`), retries with exponential backoff and, after the last attempt, escalates cleanly to a human.

---

## 6. Contract deviations and architecture decisions

The S.O.F.I.A. implementation adopted four justified architecture decisions:

### 1. POL-7 is handled in the conversational agent, not in SIM's policy engine
- **Rationale**: POL-1 to POL-6 evaluate deterministic financial rules over transactions and customers (account status, amounts, age, duplicate claims and fraud risk). POL-7, instead, sets the limit of clarification turns (at most 2 attempts before escalating to a human). The clarification count and the dialogue's ambiguity belong to the conversational graph's state (`agent/`), so they are controlled in the agent's orchestration layer, not in the bank API.

### 2. Eligibility identifier (`eligibility_id`) + `ConfirmationProof` instead of a separate `confirmation_id`
- **Rationale**: The preliminary specification had a `confirmation_id` issued by the bank. In the final design, creating the dispute (`POST /disputes`) requires the `eligibility_id` (which guarantees the transaction was checked against the policy beforehand and is within its 15-minute TTL) plus a `ConfirmationProof` object (which carries the customer's explicit confirmation text and the turn's timestamp). This removes a redundant intermediate call while keeping the strict guarantee of confirmation before any mutation (REQ-09).

### 3. In-memory audit log (`InMemoryAuditTrail`) for the hackathon sandbox
- **Rationale**: During the hackathon, the audit log (`audit_trail`) runs in memory for maximum speed in unit tests and direct inspection through `GET /admin/audit`. In a production banking design, this log is shipped asynchronously to an append-only table in PostgreSQL/BigQuery or Cloud Logging with immutable WORM retention and cryptographic signatures.

### 4. MET-05 and MET-06 computed from local timers and token counters
- **Rationale**: MET-05 (latency) and MET-06 (cost) are measured in the evaluation harness by accumulating `time.perf_counter()` deltas per turn and summing the input and output tokens reported by the LLM responses multiplied by the configured public prices (`GEMINI_PRICE_INPUT_PER_MTOK` and `GEMINI_PRICE_OUTPUT_PER_MTOK`). This keeps offline evaluations (`make eval`) strictly reproducible without depending on the network or on Langfuse's external analytics API quotas.
