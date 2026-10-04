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

- **Transactional** interactions are `{{results/workflow_justification.json:reason_categories[Transaccional].pct}}`%
  of the call center, with an escalation rate of `{{results/workflow_justification.json:reason_categories[Transaccional].p_escalado}}`.
- "Unrecognized charge" + "improper charge" = `{{results/workflow_justification.json:dispute_share_pct}}`% of complaints;
  SLA breached in `{{results/workflow_justification.json:complaint_subcategories[Cargo no reconocido].p_sla_roto}}`.
- We measured the §14 risk instead of assuming it away: complaints **do not link** to their transactions in this dataset
  (the affected product never belongs to the complainant), so a dispute is anchored to the transaction the customer
  identifies in the conversation and the API verifies as theirs (POL-1).
- Policy with stated grounds: window **N = `{{results/policy_calibration.json:N_days.value}}` days** (Mexico's legal
  window for unrecognized charges), threshold **U = `{{results/policy_calibration.json:U_usd.value}}` USD**, fraud score
  ≥ `{{results/policy_calibration.json:fraud_score_threshold.value}}` (minimum expected cost).
- Safe action: **register** the dispute; money never moves (CON-05).

**Single chart:** horizontal bars "Interactions by contact category" with the escalation rate as a label, highlighting
Transactional. Source: `analysis/results/workflow_justification.json` → `reason_categories` (figure in
`analysis/figures/`). Optional small inset: the fraud-threshold cost curve with the minimum at 30, from
`analysis/results/policy_calibration.json` → `fraud_score_threshold.cost_curve` (only if it fits; otherwise it goes in the README).

**Speaker notes (~35 s):**
We did not pick the workflow by taste: we picked it because it is where the dataset has the most connected evidence.
Transactions, complaints and interactions join by keys, so we can measure volume, broken SLAs and escalation of the
same phenomenon. We had an exit criterion written before the EDA: if disputes turned out marginal, we would switch to
card support. It did not fire: `{{results/workflow_justification.json:decision}}`.
We also checked what the data cannot do: complaints do not point to their transactions, so the dispute window could
not be fitted from data. We took it from regulation instead: Mexico gives 90 days to object to an unrecognized charge,
inside the card networks' 120-day chargeback window. The fraud threshold is the point of lowest expected cost: a missed
fraud costs far more than one extra human review.

---

## Slide 5 · Architecture: the LLM understands and writes; the policy decides

**Title:** *7 layers: safety lives outside the prompt*

- **PURPOSE → SENSE → INTERPRET → DECIDE → ORCHESTRATE (act · verify · escalate) → GOVERN → LEARN**, as an explicit
  LangGraph graph; each layer leaves an auditable event (glass box, REQ-19).
- **We audited the labels before training:** `call_transcripts` are `{{results/label_audit.json:transcript_templates[0].plantillas}}`
  balance-inquiry templates spread evenly across categories, and `detected_intents` is always `consulta_general` → the
  dataset **has no valid intent labels**. The router is trained on a team-generated ES/PT corpus (`team_generated`),
  with a group split.
- **Served router = rules first, learned model for the rest**, on the same held-out test (split by paraphrase family,
  no repeated texts, n = 56): macro-F1 0.377 (rules) → 0.641 (model) → **0.728 (hybrid)**; `needs_human` recall
  0.0 → 0.7.
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
expensive error. Below a confidence of `{{ml/reports/router_eval.json:confidence_threshold}}`, Sofía does not guess:
she asks.

---

## Slide 6 · Results: baseline vs Sofía, by language

**Title:** *Measured, not promised: MET-01..06 on the held-out set*

- Same set and same load for both systems: n = `{{eval/outputs/ds_stats.json:desglose.idioma.es.n}}` ES cases and
  `{{eval/outputs/ds_stats.json:desglose.idioma.pt.n}}` PT, `{{PENDIENTE:repeated runs per system}}` repeated runs; 95% CI
  (`{{eval/outputs/ds_stats.json:meta.metodos}}`).
- **Safe automated resolution (MET-01):** `{{eval/outputs/ds_stats.json:baseline.metricas.met01_safe_auto_resolution}}` →
  `{{eval/outputs/ds_stats.json:proposed.metricas.met01_safe_auto_resolution}}`; **unsafe outcomes (MET-04):**
  `{{eval/outputs/ds_stats.json:baseline.metricas.met04_unsafe_outcomes.k}}` → `{{eval/outputs/ds_stats.json:proposed.metricas.met04_unsafe_outcomes.k}}`
  out of `{{eval/outputs/ds_stats.json:proposed.n}}` cases.
- **Escalation (MET-03):** recall `{{eval/outputs/ds_stats.json:proposed.metricas.met03_escalation_recall}}`, precision
  `{{eval/outputs/ds_stats.json:proposed.metricas.met03_escalation_precision}}`, complete handoff fields
  `{{eval/outputs/ds_stats.json:proposed.metricas.met03_handoff_completeness}}`.
- **Cost and latency (MET-05/06):** p95 `{{eval/outputs/ds_stats.json:proposed.metricas.met05_latency_p95_ms.value}}` ms;
  `{{eval/outputs/ds_stats.json:proposed.metricas.met06_cost_per_safe_resolution_usd}}` USD per successful resolution
  (Gemini public price, assumptions in the README).
- **Honest limits:** PT is team-generated (the dataset has no PT); 0 unsafe in n cases ≠ zero risk
  (95% upper bound ≈ `{{eval/outputs/ds_stats.json:proposed.metricas.met04_unsafe_outcomes.rule_of_three_upper}}`); offline results, not production (CON-07).

**Backup table (goes in the DEL-06 report; on the slide only if it fits).** Convention: every `ds_stats.json`
placeholder in this table points to a metric object and is shown as `rate` or `value` [95% CI low–high], n.

| Metric | Baseline ES | Sofía ES | Baseline PT | Sofía PT |
|---|---|---|---|---|
| MET-01 safe auto resolution | `{{eval/outputs/ds_stats.json:desglose.idioma.es.baseline.metricas.met01_safe_auto_resolution}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.es.proposed.metricas.met01_safe_auto_resolution}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.pt.baseline.metricas.met01_safe_auto_resolution}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.pt.proposed.metricas.met01_safe_auto_resolution}}` |
| MET-02 containment | `{{eval/outputs/ds_stats.json:desglose.idioma.es.baseline.metricas.met02_containment}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.es.proposed.metricas.met02_containment}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.pt.baseline.metricas.met02_containment}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.pt.proposed.metricas.met02_containment}}` |
| MET-03 escalation recall | `{{eval/outputs/ds_stats.json:desglose.idioma.es.baseline.metricas.met03_escalation_recall}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.es.proposed.metricas.met03_escalation_recall}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.pt.baseline.metricas.met03_escalation_recall}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.pt.proposed.metricas.met03_escalation_recall}}` |
| MET-04 unsafe (count / n) | `{{eval/outputs/ds_stats.json:desglose.idioma.es.baseline.metricas.met04_unsafe_outcomes}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.es.proposed.metricas.met04_unsafe_outcomes}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.pt.baseline.metricas.met04_unsafe_outcomes}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.pt.proposed.metricas.met04_unsafe_outcomes}}` |
| MET-05 latency p50 / p95 (ms) | `{{eval/outputs/ds_stats.json:desglose.idioma.es.baseline.metricas.met05_latency_p50_ms}}` / `{{eval/outputs/ds_stats.json:desglose.idioma.es.baseline.metricas.met05_latency_p95_ms}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.es.proposed.metricas.met05_latency_p50_ms}}` / `{{eval/outputs/ds_stats.json:desglose.idioma.es.proposed.metricas.met05_latency_p95_ms}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.pt.baseline.metricas.met05_latency_p50_ms}}` / `{{eval/outputs/ds_stats.json:desglose.idioma.pt.baseline.metricas.met05_latency_p95_ms}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.pt.proposed.metricas.met05_latency_p50_ms}}` / `{{eval/outputs/ds_stats.json:desglose.idioma.pt.proposed.metricas.met05_latency_p95_ms}}` |
| MET-06 USD / attempted case | `{{eval/outputs/ds_stats.json:desglose.idioma.es.baseline.metricas.met06_cost_per_case_usd}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.es.proposed.metricas.met06_cost_per_case_usd}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.pt.baseline.metricas.met06_cost_per_case_usd}}` | `{{eval/outputs/ds_stats.json:desglose.idioma.pt.proposed.metricas.met06_cost_per_case_usd}}` |

**Single chart:** dot plot with error bars (95% CI): one row per metric (MET-01..04), two dots per language
(baseline grey, Sofía in color), ES and PT in side-by-side panels. Latency and cost go as text in the bullets, not in
the chart (different scale). Source: `eval/outputs/ds_stats.json` (aggregated by DS from SIM's harness output).
Fairness by segment (REQ-18): `analysis/results/fairness.json`, report only.

**Speaker notes (~40 s):**
Everything we show is offline, on the held-out set, with the same set for the baseline and for Sofía. The baseline is
an LLM with the same tools but no layers: no router, no policy of its own and no verification. We report by language
because it is a requirement, and because Portuguese is our biggest weakness: the dataset has no Portuguese, so we wrote
the PT cases ourselves. Look at the intervals, not just the dots: with `{{eval/outputs/ds_stats.json:proposed.n}}`
cases, zero unsafe outcomes does not mean zero risk; it means the risk is below
`{{eval/outputs/ds_stats.json:proposed.metricas.met04_unsafe_outcomes.rule_of_three_upper}}` with 95% confidence.
And containment is not resolution: we count separately the cases Sofía resolved correctly without a human.

---

## Placeholder keys this file expects

For whoever writes the JSONs. Notation: `a.b` = nested key; `list[X]` = the list element whose first field equals `X`
(e.g. `reason_category = "Transaccional"`); `list[0]` = the first element.

| File | Keys | Status |
|---|---|---|
| `analysis/results/workflow_justification.json` | `reason_categories[...]` (`pct`, `p_escalado`), `complaint_subcategories[...]` (`p_sla_roto`), `decision` | exist in notebook 01 |
| `analysis/results/workflow_justification.json` | `dispute_share_pct` | **to add** (notebook 01 §3) |
| `analysis/results/policy_calibration.json` | `N_days.value`, `U_usd.value`, `fraud_score_threshold.value`, `fraud_score_threshold.cost_curve` | exist (notebook 02) |
| `analysis/results/label_audit.json` | `transcript_templates[0].{filas,plantillas}` | exist |
| `ml/reports/router_eval.json` | `split.n_test`, `confidence_threshold`, `served_version`; per-system figures are copied from `router_eval.md` | exist (`ml/src/sofia_ml/train.py`) |
| `eval/outputs/ds_stats.json` | `proposed.n`, `desglose.idioma.{es,pt}.n`, `meta.metodos`; metric objects `{baseline,proposed}.metricas.<met>` and `desglose.idioma.{es,pt}.{baseline,proposed}.metricas.<met>` (shown as `rate` or `value` [95% CI low–high], n); single fields `.k`, `.value`, `.rule_of_three_upper` (only present when k = 0) | schema of `eval/src/sofia_eval/ds_stats.py` (`build_ds_stats`) |
| Only in `docs/defense-notes.md` | `judge_validation.json`: `evaluators[0].agreement`; `ds_stats.json`: `proposed.metricas.met04_unsafe_outcomes.ci[1]`; `fairness.json`: `summary` | `fairness` **blocked** until the evaluation run |
| `agent/evals/reference.rules.json` · `agent/src/sofia_agent/config.py` | `context."Modelo (cadena)"`; `GEMINI_PRICE_INPUT_PER_MTOK`, `GEMINI_PRICE_OUTPUT_PER_MTOK` | exist (AG's gate: development set, 30 cases, not held-out) |
| No JSON yet | `{{PENDIENTE:…}}`: repeated runs | **pending**: no source; never estimated |
