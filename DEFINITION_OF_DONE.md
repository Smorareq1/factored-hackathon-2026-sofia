# Definition of Done (brief §13) — owner: OPS

Delivery checklist. Reviewed at integration 2 (10-02) and before submission (10-05). Each item carries its evidence or
what is missing. Final status at submission, 2026-10-06 (develop `cbf3248`).

## Delivery

- [ ] **REQ-01..REQ-19 with linked evidence in the README.** The table exists ([Traceability](README.md#traceability-req-01req-19));
  rows still marked `partial` / `pending` (REQ-02, REQ-06, REQ-13..15, REQ-17, REQ-18) are declared as such on purpose.
- [ ] **DEL-01..DEL-07 ready; DEL-08 prepared in case we reach the Top 5.**
  - [x] DEL-01 Public repo with reproducible setup: [README](README.md#getting-started)
  - [x] DEL-02 Deployed demo: https://frontend-i6dmh3qssa-uc.a.run.app
  - [ ] DEL-03 Slides 4–6 (DS): content in [slides-4-6.md](docs/slides/slides-4-6.md); missing the `{{…}}` figures and the export
  - [ ] DEL-04 Video ≤ 3 min (DS): script in [video-script.md](docs/video-script.md); missing the shots (AG) and the edit
  - [ ] DEL-05 Final README (DS edits; OPS already contributed deployment, data, CI, CD, observability, retries/fallbacks
    and path to production); missing the `{{…}}` placeholders in Results
  - [ ] DEL-06 Evaluation report MET-01..06 (DS + SIM): structure in [evaluation-report.md](docs/evaluation-report.md);
    missing the figures from the baseline vs proposed run
  - [ ] DEL-07 Submission email (OPS): draft ready; sent once the video and slides links exist
  - [ ] DEL-08 Live defense script (everyone): [defense-notes.md](docs/defense-notes.md); missing the figures
- [ ] **Email sent to hackathon.admin@factored.ai** (OPS, before 2026-10-05).

## Engineering

- [x] **No secrets or customer data in the repo, including git history.** gitleaks over the full history on
  every PR ([ci.yml](.github/workflows/ci.yml)); `data/` and `.env` kept out of git, Cloud Build and the images.
- [ ] **`make setup && make data && make run && make eval` works from scratch.**
  - [x] `make setup`, `make data` (S3 or `make data-fixture`) and `make run`
  - [x] `make eval` runs baseline and proposed (`--versions proposed,baseline` by default); full 200-case run for both
    versions versioned in `eval/outputs/` (04a459e). Needs `GEMINI_API_KEY` in `.env`: without it the proposed system
    runs on rules only and the baseline is unavailable
  - [x] Tested from a clean clone (2026-10-04): `make setup`, `make data` (S3, ~13 min), `make run` (4 services healthy)
    and `make eval` (runs end to end; without a Gemini key it runs without LLM)
- [ ] **Cloud Run demo can be brought up on demand, tested from an external network.** Continuous deployment on every
  merge to `develop` ([deploy.yml](.github/workflows/deploy.yml)).
  - [x] Deployed and tested end to end (OTP login → dispute with Gemini through Vertex AI)
  - [x] Agent connected to the deployed bank-api (2026-10-04). `deploy.sh` uses it by default, so CD no longer
    falls back to the in-process bank
  - [x] bank-api `/admin/*` and `/session/test` closed in the cloud (SIM): 403 unless `X-Admin-Key` = secret
    `admin-api-key`
  - [ ] End-to-end test of the frontend against the deployed bank-api (OPS + AG)
  - [x] `MIN_INSTANCES=1` on all 4 services for the judging window (2026-10-06); back to 0 afterwards

## Evaluation

- [ ] **Report with MET-01..MET-06 by language and case type, with n and limitations** (DS + SIM). The harness must read
  latency and cost with Langfuse's `GET /api/public/v2/observations`: the classic `/api/public/traces` API does not
  exist for new organizations.
- [ ] **Langfuse evaluators validated against a human sample and documented** (DS).

## Documentation

- [x] **"Limitations, trade-offs and path to production"**, infra and data part:
  [README](README.md#limitations-and-path-to-production-infra-and-data). The agent, ML and evaluation part is there
  too ([README](README.md#limitations-and-path-to-production-agent-ml-and-evaluation)); it closes with the results.
- [x] **Retries, timeouts and fallbacks documented**, and what stays out of the trace:
  [infra/README.md](infra/README.md#retries-timeouts-and-fallbacks).
- [ ] **Video ≤ 3 minutes** (DS).
