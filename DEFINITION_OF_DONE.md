# Definition of Done (brief §13) — owner: OPS

Delivery checklist. Reviewed at integration 2 (10-02) and before submission (10-05). Each item carries its evidence or
what is missing. Status as of 2026-10-04 (develop `3b2f295`).

## Delivery

- [ ] **REQ-01..REQ-19 with linked evidence in the README.** The table exists ([Traceability](README.md#traceability-req-01req-19));
  some rows are still `pending` / `partial` (REQ-02, REQ-06, REQ-17) and close with the full harness run.
- [ ] **DEL-01..DEL-07 ready; DEL-08 prepared in case we reach the Top 5.**
  - [x] DEL-01 Public repo with reproducible setup: [README](README.md#getting-started)
  - [x] DEL-02 Deployed demo: https://frontend-i6dmh3qssa-uc.a.run.app
  - [ ] DEL-03 Slides 4–6 (DS): content in [slides-4-6.md](docs/slides/slides-4-6.md); figures filled; export to PDF pending
  - [ ] DEL-04 Video ≤ 3 min (DS): script in [video-script.md](docs/video-script.md); missing the shots (AG) and the edit
  - [x] DEL-05 Final README (DS edits; OPS already contributed deployment, data, CI, CD, observability, retries/fallbacks
    and path to production); Results placeholders filled 2026-10-05
  - [x] DEL-06 Evaluation report MET-01..06 (DS + SIM): structure in [evaluation-report.md](docs/evaluation-report.md);
    figures filled from the 200-case run (one run per system, Gemini free tier; limits in §10)
  - [ ] DEL-07 Submission email (OPS): draft ready; sent once the video and slides links exist
  - [ ] DEL-08 Live defense script (everyone): [defense-notes.md](docs/defense-notes.md); figures filled
- [ ] **Email sent to hackathon.admin@factored.ai** (OPS, before 2026-10-05).

## Engineering

- [x] **No secrets or customer data in the repo, including git history.** gitleaks over the full history on
  every PR ([ci.yml](.github/workflows/ci.yml)); `data/` and `.env` kept out of git, Cloud Build and the images.
- [ ] **`make setup && make data && make run && make eval` works from scratch.**
  - [x] `make setup`, `make data` (S3 or `make data-fixture`) and `make run`
  - [x] `make eval` runs baseline and proposed (`--versions proposed,baseline` by default); the full run is done: the
    versioned `eval/outputs/results.json` has 200 proposed and 200 baseline cases (SIM + DS)
  - [ ] Tested from a clean clone
- [ ] **Cloud Run demo can be brought up on demand, tested from an external network.** Continuous deployment on every
  merge to `develop` ([deploy.yml](.github/workflows/deploy.yml)).
  - [x] Deployed and tested end to end (OTP login → dispute with Gemini through Vertex AI)
  - [x] Agent connected to the deployed bank-api (2026-10-04). `deploy.sh` uses it by default, so CD no longer
    falls back to the in-process bank
  - [x] bank-api `/admin/*` and `/session/test` closed in the cloud (SIM): 403 unless `X-Admin-Key` = secret
    `admin-api-key`
  - [ ] End-to-end test of the frontend against the deployed bank-api (OPS + AG)
  - [ ] Tested from an external network in the agreed window, with `MIN_INSTANCES=1`

## Evaluation

- [ ] **Report with MET-01..MET-06 by language and case type, with n and limitations** (DS + SIM). The harness must read
  latency and cost with Langfuse's `GET /api/public/v2/observations`: the classic `/api/public/traces` API does not
  exist for new organizations.
- [ ] **Langfuse evaluators validated against a human sample and documented** (DS). Not done: the report states that no LLM-as-judge was used (§9).

## Documentation

- [x] **"Limitations, trade-offs and path to production"**, infra and data part:
  [README](README.md#limitations-and-path-to-production-infra-and-data). The agent, ML and evaluation part is there
  too ([README](README.md#limitations-and-path-to-production-agent-ml-and-evaluation)); it closes with the results.
- [x] **Retries, timeouts and fallbacks documented**, and what stays out of the trace:
  [infra/README.md](infra/README.md#retries-timeouts-and-fallbacks).
- [ ] **Video ≤ 3 minutes** (DS).
