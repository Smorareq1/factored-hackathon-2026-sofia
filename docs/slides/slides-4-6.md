# Slides 4–6 (DS) · DEL-03

A 4–6 slide deck (DEL-03: problem, solution, architecture, results, limitations). DS owns slides 4–6; slides 1–3
(problem, chosen workflow, demo) are built by the team. Each slide: title, at most 5 bullets, **a single chart** (with
the JSON it comes from) and speaker notes. The slides are in English; the demo itself speaks Spanish and Portuguese.

> **Figures rule:** no figure is typed by hand. Each number is a `{{file:key}}` placeholder replaced with the value from
> the versioned JSON right before exporting the deck. If a JSON lacks the key, the bullet is rewritten without the
> figure; it is never estimated. Simulated and projected results are labeled as such (CON-07). Exception: the router
> figures (slide 5) are copied from the generated `ml/reports/router_eval.md`.

---

## Slide 4 · The data chose the workflow

**Title:** *Transaction disputes: high volume, broken SLAs and a safe action*

- **Transactional** interactions are `35`%
  of the call center, with an escalation rate of `0.099`.
- "Unrecognized charge" + "improper charge" = `36.5`% of complaints;
  SLA breached in `0.204`.
- We measured the §14 risk instead of assuming it away: complaints **do not link** to their transactions in this dataset
  (the affected product never belongs to the complainant), so a dispute is anchored to the transaction the customer
  identifies in the conversation and the API verifies as theirs (POL-1).
- Policy with stated grounds: window **N = `90` days** (Mexico's legal
  window for unrecognized charges), threshold **U = `500` USD**, fraud score
  ≥ `30` (minimum expected cost).
- Safe action: **register** the dispute; money never moves (CON-05).

**Single chart:** horizontal bars "Interactions by contact category" with the escalation rate as a label, highlighting
Transactional. Source: `analysis/results/workflow_justification.json` → `reason_categories` (figure in
`analysis/figures/`). Optional small inset: the fraud-threshold cost curve with the minimum at 30, from
`analysis/results/policy_calibration.json` → `fraud_score_threshold.cost_curve` (only if it fits; otherwise it goes in the README).

**Speaker notes (~35 s):**
We did not pick the workflow by taste: we picked it because it is where the dataset has the most connected evidence.
Transactions, complaints and interactions join by keys, so we can measure volume, broken SLAs and escalation of the
same phenomenon. We had an exit criterion written before the EDA: if disputes turned out marginal, we would switch to
card support. It did not fire: `Keep dispute intake: disputes are 36.5% of complaints (24,491 of 67,095); SLA breached in 20.2%, first response p50 37 h, resolution p50 15 days. Intake moves no money (CON-05). Exit criterion (disputes marginal) not met.`.
We also checked what the data cannot do: complaints do not point to their transactions, so the dispute window could
not be fitted from data. We took it from regulation instead: Mexico gives 90 days to object to an unrecognized charge,
inside the card networks' 120-day chargeback window. The fraud threshold is the point of lowest expected cost: a missed
fraud costs far more than one extra human review.

---

## Slide 5 · Architecture: the LLM understands and writes; the policy decides

**Title:** *7 layers: safety lives outside the prompt*

- **PURPOSE → SENSE → INTERPRET → DECIDE → ORCHESTRATE (act · verify · escalate) → GOVERN → LEARN**, as an explicit
  LangGraph graph; each layer leaves an auditable event (glass box, REQ-19).
- **We audited the labels before training:** `call_transcripts` are `42`
  balance-inquiry templates spread evenly across categories, and `detected_intents` is always `consulta_general` → the
  dataset **has no valid intent labels**. The router is trained on a team-generated ES/PT corpus (`team_generated`),
  with a group split.
- **Served router = rules first, learned model for the rest**, on the same held-out test (split by paraphrase family,
  no repeated texts, n = 56): macro-F1 0.476 (rules) → 0.641 (model) → **0.746 (hybrid)**; `needs_human` recall
  0.3 → 0.8.
- **Policy POL-1..7 in the API (FastAPI)**, not in the prompt: permissions by the token's `customer_id`, deterministic
  eligibility, explicit confirmation before acting and a re-read to verify (REQ-09/10).
- Gemini only extracts slots and writes (if it fails, rules and templates, REQ-16); everything traced in **Langfuse**:
  1 trace per conversation, 1 span per layer and per tool call → real latency and cost.

**Single chart:** diagram of the 7 layers (left) against the API's deterministic layer (right), with a dashed red
"trust boundary" line between them. Below, a 3-row router mini-table (rules vs model vs hybrid: macro-F1, `needs_human`
recall, n). Diagram source: brief §8.4 + `agent/README.md`; mini-table source: `ml/reports/router_eval.md`.

**Speaker notes (~40 s):**
The most important architecture decision is where the LLM is NOT. Gemini understands what the customer says and writes
the reply; it never decides who can see what, or whether a dispute is eligible. The API decides that, with the session
token and rules POL-1 to POL-7. That is why a malicious prompt cannot get around the policy: there is nothing to
persuade, the rule is not in the text. The learned component is the intent router, and before training it we audited
the labels: the dataset's transcripts are balance-inquiry templates spread evenly across categories, and the detected
intent is always the same. Training on that would have produced a high, empty number. So we trained on a team-generated
ES/PT corpus, labeled as such, and used the audit as evidence (REQ-13). The served router uses the keyword rules when
they match and the model for everything else: it beats both on the same test, split by group so there is no leakage.
The metric we care about most is `needs_human` recall: letting through a case that should go to a human is the most
expensive error. Below a confidence of `0.35`, Sofía does not guess:
she asks.

---

## Slide 6 · Results: baseline vs Sofía, by language

**Title:** *Measured, not promised: MET-01..06 on the held-out set*

- Same set and same load for both systems: n = `100` ES cases and
  `100` PT, one run per system; 95% CI
  (`proporciones: Wilson CI; rule of three (3/n) when there are 0 events, continuas: percentile bootstrap resampling cases (calculate_metrics per replicate), diferencia_proporciones: Newcombe (Wilson) CI; exact Fisher if an expected count < 5, otherwise z, diferencia_continuas: bootstrap of the difference (paired by case_id when possible), desglose: cells with n < 10 are marked 'insufficient n'`).
- **Safe automated resolution (MET-01):** `13.3% [6.9%–24.2%], n = 60` →
  `5.0% [1.7%–13.7%], n = 60`; **unsafe outcomes (MET-04):**
  `0` → `0`
  out of `200` cases.
- **Escalation (MET-03):** recall `58.1% [45.7%–69.5%], n = 62`, precision
  `100.0% [90.4%–100.0%], n = 36`, complete handoff fields
  `0.6042 [0.4808–0.7292], n = 36`.
- **Cost and latency (MET-05/06):** p95 `11,415` ms;
  `0.02489 [0.01054–0.07966], n = 3` USD per successful resolution
  (Gemini public price, assumptions in the README).
- **Honest limits:** PT is team-generated (the dataset has no PT); 0 unsafe in n cases ≠ zero risk
  (95% upper bound ≈ `0.015`); offline results, not production (CON-07).

**Backup table (goes in the DEL-06 report; on the slide only if it fits).** Convention: every `ds_stats.json`
placeholder in this table points to a metric object and is shown as `rate` or `value` [95% CI low–high], n.

| Metric | Baseline ES | Sofía ES | Baseline PT | Sofía PT |
|---|---|---|---|---|
| MET-01 safe auto resolution | `20.0% [9.5%–37.3%], n = 30` | `6.7% [1.8%–21.3%], n = 30` | `6.7% [1.8%–21.3%], n = 30` | `3.3% [0.6%–16.7%], n = 30` |
| MET-02 containment | `95.0% [88.8%–97.9%], n = 100` | `80.0% [71.1%–86.7%], n = 100` | `100.0% [96.3%–100.0%], n = 100` | `84.0% [75.6%–89.9%], n = 100` |
| MET-03 escalation recall | `16.1% [7.1%–32.6%], n = 31` | `64.5% [46.9%–78.9%], n = 31` | `0.0% [0.0%–11.0%], n = 31` | `51.6% [34.8%–68.0%], n = 31` |
| MET-04 unsafe (count / n) | `0.0% [0.0%–3.7%], n = 100` | `0.0% [0.0%–3.7%], n = 100` | `0.0% [0.0%–3.7%], n = 100` | `0.0% [0.0%–3.7%], n = 100` |
| MET-05 latency p50 / p95 (ms) | `516 [503–704], n = 100` / `8,105 [4,184–17,702], n = 100` | `221 [207–238], n = 100` / `13,102 [5,652–17,102], n = 100` | `952 [514–982], n = 100` / `3,240 [1,450–5,199], n = 100` | `212 [199–222], n = 100` / `10,194 [4,044–13,549], n = 100` |
| MET-06 USD / attempted case | `0.000545 [0.000326–0.000791], n = 100` | `0.00033 [0.000226–0.000444], n = 100` | `0.000354 [0.000227–0.000511], n = 100` | `0.000417 [0.000276–0.000535], n = 100` |

**Single chart:** dot plot with error bars (95% CI): one row per metric (MET-01..04), two dots per language
(baseline grey, Sofía in color), ES and PT in side-by-side panels. Latency and cost go as text in the bullets, not in
the chart (different scale). Source: `eval/outputs/ds_stats.json` (aggregated by DS from SIM's harness output).
Fairness by segment (REQ-18): `analysis/results/fairness.json`, report only.

**Speaker notes (~40 s):**
Everything we show is offline, on the held-out set, with the same set for the baseline and for Sofía. The baseline is
an LLM with the same tools but no layers: no router, no policy of its own and no verification. We report by language
because it is a requirement, and because Portuguese is our biggest weakness: the dataset has no Portuguese, so we wrote
the PT cases ourselves. Look at the intervals, not just the dots: with `200`
cases, zero unsafe outcomes does not mean zero risk; it means the risk is below
`0.015` with 95% confidence.
And containment is not resolution: we count separately the cases Sofía resolved correctly without a human.

---

## Placeholder keys this file expects

For whoever writes the JSONs. Notation: `a.b` = nested key; `list[X]` = the list element whose first field equals `X`
(e.g. `reason_category = "Transaccional"`); `list[0]` = the first element.

| File | Keys | Status |
|---|---|---|
| `analysis/results/workflow_justification.json` | `reason_categories[...]` (`pct`, `p_escalado`), `complaint_subcategories[...]` (`p_sla_roto`), `decision` | exist in notebook 01 |
| `analysis/results/workflow_justification.json` | `dispute_share_pct`, `operational_constraints`, `decision` | exist (notebook 01 §6–7) |
| `analysis/results/policy_calibration.json` | `N_days.value`, `U_usd.value`, `fraud_score_threshold.value`, `fraud_score_threshold.cost_curve` | exist (notebook 02) |
| `analysis/results/label_audit.json` | `transcript_templates[0].{filas,plantillas}` | exist |
| `ml/reports/router_eval.json` | `split.n_test`, `confidence_threshold`, `served_version`; per-system figures are copied from `router_eval.md` | exist (`ml/src/sofia_ml/train.py`) |
| `eval/outputs/ds_stats.json` | `proposed.n`, `desglose.idioma.{es,pt}.n`, `meta.metodos`; metric objects `{baseline,proposed}.metricas.<met>` and `desglose.idioma.{es,pt}.{baseline,proposed}.metricas.<met>` (shown as `rate` or `value` [95% CI low–high], n); single fields `.k`, `.value`, `.rule_of_three_upper` (only present when k = 0) | schema of `eval/src/sofia_eval/ds_stats.py` (`build_ds_stats`) |
| Only in `docs/defense-notes.md` | `ds_stats.json`: `proposed.metricas.met04_unsafe_outcomes.ci[1]`; `fairness.json`: `summary` | `fairness.json` from `analysis/eval_extras.py` |
| `agent/evals/reference.rules.json` · `agent/src/sofia_agent/config.py` | `context."Modelo (cadena)"`; `GEMINI_PRICE_INPUT_PER_MTOK`, `GEMINI_PRICE_OUTPUT_PER_MTOK` | exist (AG's gate: development set, 30 cases, not held-out) |
