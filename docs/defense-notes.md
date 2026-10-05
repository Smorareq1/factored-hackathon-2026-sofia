# Defense notes (DEL-08) · Top 5, 2026-10-16

Likely jury questions with a short answer (≤ 30 s spoken) and the evidence to show if they push back. The figures are
`{{...}}` placeholders filled from the versioned JSONs before the defense; if a figure does not exist, answer without
it and say it was not measured.

**The message we repeat:** *the LLM understands and writes; the API decides. We measured against a baseline under the
same load, we report by language with n and intervals, and we say what we do not know.*

---

## 1. Data and choice of workflow

**Why disputes and not cards or payments?**
Because that is where the dataset has the most connected evidence: `transactions`, `complaints` and
`call_center_interactions` join by keys and let us measure volume, broken SLAs and escalation of the same phenomenon.
Disputes are `36.5`% of complaints. We wrote an exit criterion
before the EDA (if they were marginal, we would switch to card support) and it did not fire.
*Evidence:* `analysis/notebooks/01_workflow_justification.ipynb`, `analysis/results/workflow_justification.json`.

**`complaints` has no `transaction_id`. How do you link a complaint to a transaction?**
We tested it instead of assuming it, and in this dataset you cannot: the affected product never belongs to the
customer who complained (0 of 16,257), and claimed amounts match the customer's own transactions at chance level
(37 of 6,987). The conversation does not need that historical link: the customer points to the transaction and Sofía
finds it in their own records, which the API verifies as theirs (POL-1).
*Evidence:* `analysis/notebooks/02_policy_calibration.ipynb` §1, `analysis/results/policy_calibration.json`.

**Where do N and U come from?**
N = `90` days. Since the data cannot calibrate it (no dispute links to its
transaction), we took it from regulation: Mexico gives 90 calendar days to object to an unrecognized charge, inside
Visa/Mastercard's 120-day chargeback window. Argentina is stricter (30 days from the statement), so per-country windows
are a production step. U = `500` USD: no regulation sets an amount;
purchases in the data top out near 500 USD, so almost every purchase dispute is automated while 23% of claimed amounts
go to a human. The fraud threshold, 30 on the 0–100 score, is the point of minimum expected cost. The policy is
synthetic and labeled as team-defined (CON-02): a real bank would put its own rules in the same place.

## 2. Learned component (router)

**Where do the router's labels come from? (very likely question)**
Not from the dataset: we audited it before training and the labels are unusable. `call_transcripts` has only
`42` **balance-inquiry** templates
(`171,321` rows), spread evenly across contact categories, and
`detected_intents` is always `consulta_general`. The text has nothing to do with the category: a model trained there
would learn noise, or memorize templates and give a high, empty number.
So we trained the router on a team-generated ES/PT corpus, labeled `team_generated` (CON-02), with a group split, and
we present the label audit as the REQ-13 evidence ("valid labels"). It is a declared limitation: the router is not
validated on real customer text.
*Evidence:* `analysis/notebooks/04_label_audit.ipynb`, `ml/reports/corpus_audit.md`.

**How did you avoid leakage in the router split?**
Three layers. (1) Group split: in the team corpus, the group is the paraphrase family (all variants of one sentence
land on the same side); in dataset data, the customer. (2) Temporal when there are dates: test = the last days, and
groups that appear in test are removed from train. (3) An `assert` that fails if a group **or an identical text** is on
both sides. Test size: `56`.
*Evidence:* `ml/src/sofia_ml/split.py` (`assert_no_leakage`), `ml/reports/router_eval.json`.

**Follow-up: if you wrote the corpus yourselves, isn't it easy?**
It is a real risk: whoever writes train and test shares a style. We mitigated it with the paraphrase-family split and
measured it per language (macro-F1 PT 0.778 for the served hybrid). But the router's number is optimistic compared
with real customers, and we say so; the next step is labeling real messages in shadow mode.

**Why macro-F1 and `needs_human` recall?**
Macro-F1 because the classes are imbalanced and `out_of_scope` or `needs_human` matter as much as the majority class.
`needs_human` recall because letting through a case that should go to a human is the most expensive error; an
unnecessary one costs an agent a few minutes. Result on the held-out test: 0.3 (rules) → 0.7 (learned model) → 0.8 (served
hybrid); macro-F1 0.476 → 0.746.

**Why rules plus a model, instead of just the model?**
Because it measured better. The keyword rules are precise when they match (0.868 accuracy on 45% of messages) and the
model covers what they miss; out-of-fold on the 256 approved rows, rules 0.484, model 0.645, hybrid 0.766.
`router_version` records which part answered each message.

**What if the router gets it wrong?**
It decides nothing sensitive. Below the confidence threshold (`0.35`)
Sofía asks; and even if it misclassifies, the API decides eligibility and permissions again. The worst case of a router
error is one extra question or a handoff, not an improper action.

## 3. Architecture and safety

**Why is the policy outside the prompt?**
Because a prompt is a suggestion and a rule in the API is a fact. If eligibility lived in the prompt, a customer could
negotiate it ("ignore your rules"). In Sofía, the API only returns transactions of the `customer_id` bound to the token,
answers 404 if the transaction belongs to someone else (without revealing it exists, POL-1) and requires an explicit
confirmation before registering. The LLM has no tool that lets it skip that. A test proves it with an injection prompt
(REQ-10).

**Why 7 layers? Isn't that over-engineering?**
Each layer answers a requirement and leaves an auditable event: PURPOSE (versioned scope and limits), SENSE (language,
normalization), INTERPRET (router + slots), DECIDE (policy), ORCHESTRATE (act, verify, escalate), GOVERN (per-node tool
allowlist, grounding, output guard), LEARN (regression gate). That way every decision is explainable with records, not
with chain-of-thought (REQ-19). The baseline is exactly the opposite (one LLM with the same tools) and the difference is
measured.

**How do you know the action happened?**
After creating the dispute, Sofía reads it back with `GET /disputes/{id}`. She only reports the case number if the
read-back confirms it; if the tool fails, she retries a bounded number of times and, if it keeps failing, claims nothing
and escalates (REQ-09, REQ-16).

**What does the human see in the handoff?**
A JSON card: verified facts with their source, actions taken, open questions, risk flags and the rule that triggered the
handoff. Never the transcript (REQ-05). Beyond brief §9.4, the card carries `schema_version`, `customer_claim`,
`system_version` (set by the agent) and `created_at` (set by SIM when storing). The summary and the open questions are in
the conversation's language; the verified facts, in Spanish. Field completeness is measured (MET-03:
`0.6042 [0.4808–0.7292], n = 36`).

## 4. Evaluation and statistics

**You report zero (or few) unsafe outcomes. With that n, what does it mean?**
Little, and we say so. With `200` cases and
`0` unsafe outcomes, the 95% upper bound is
`0.0188` (with zero events, rule of three: ≈ 3/n).
Zero in a small sample is not zero risk. What is strong is the structural evidence: the tests showing that the API
denies unauthorized actions do not depend on sample size.

**How did you build the intervals?**
`proporciones: Wilson CI; rule of three (3/n) when there are 0 events, continuas: percentile bootstrap resampling cases (calculate_metrics per replicate), diferencia_proporciones: Newcombe (Wilson) CI; exact Fisher if an expected count < 5, otherwise z, diferencia_continuas: bootstrap of the difference (paired by case_id when possible), desglose: cells with n < 10 are marked 'insufficient n'`. The principle: we resample cases, not turns (the turns of one
conversation are not independent), per language. Each system was run once, so the LLM's run-to-run variability was not measured and the intervals only reflect case sampling. Baseline and Sofía run on the **same** cases, so the difference can be compared case by case.
*(Confirm against the actual method in `ds_stats.json` before the defense.)*

**High containment is not good if the system does not resolve.**
Agreed: that is why MET-01 (**correct** automated resolution over in-scope cases) and MET-02 (containment) are reported
separately, together with the % of cases where automation was attempted.

**Did you use LLM-as-judge?**
Metrics MET-01..05 are deterministic (route, tool calls, leaks, verification). We did not run an LLM-as-judge: no Langfuse evaluator was validated against a human sample, so none of our numbers uses one. Text quality (tone, clarity) is therefore not evaluated, and we say so in the report.

**Are there disparities by language or segment? (REQ-18)**
We report the language cut with its n: `ES and PT match on safety (0 unsafe in 100 cases each) and are inconclusive on automation and escalation recall; the one gap that holds is handoff completeness (PT lower). The segment cut could not be run`. The customer-segment cut could not be computed, because the evaluation's seed customers are not in the gold data. Where a cell is small we do not conclude; the
report says so.

## 5. Portuguese

**The dataset is all Spanish. How good is your Portuguese?**
It is our biggest limitation and we declare it. The PT cases and the PT half of the router corpus are team-generated
with an LLM and labeled `team_generated` (CON-02); they were **not** reviewed by a native speaker. The harness catalog is
balanced (100 ES and 100 PT). The translation script masks identifiers before translating. The language fixes we did
make to the router corpus are listed in `ml/reports/corpus_audit.md`. The agent's development set (23 ES, 7 PT) only
feeds the gate and is not this sample.
Known risk: LLM-written PT is "cleaner" than a real Brazilian customer's (less slang, fewer typos), so the PT result is
probably optimistic. In production: a real PT set labeled by native speakers before opening the channel.

**And Spanish and Portuguese mixed in one message?**
It is an adversarial case in the set (level 4). SENSE detects the language per turn and Sofía answers in the customer's
language; if the intent is unclear, she asks.

## 6. Cost and latency

**What assumptions does the cost per case carry?**
Real tokens measured on every call × Gemini's public per-token price on the run date
(`rules (sin LLM)`, `0.3`
USD per million input tokens, `2.5` per million output
tokens). It does not include infrastructure (Cloud Run scales to zero) or the human agent's cost in handoffs. The cost
per successful resolution is reported as "not defined" if there are no successes (MET-06).

**Why is Sofía slower/more expensive than the baseline (if she is)?**
Because she verifies: she reads the dispute back after creating it and consults the policy. It is a deliberate cost:
p95 `11,415` ms against
`5,199` ms for the baseline. Also, Sofía does not
send tool data to the LLM to decide; the baseline does.

**How much would it save the bank?**
We do not present it as measured savings. Against the historical business baseline (call-center FCR, escalation,
duration, `analysis/results/business_baseline.json`) we only show a **projection**, labeled as such (CON-07).

## 7. Path to production

**What is missing for production?** (in priority order)
1. **Real PT data** and an evaluation run with real customers in shadow mode, without acting.
2. **Persistence:** checkpointer on managed Postgres (today the conversation lives in memory, 1 instance) and a
   persistent audit log.
3. **Network and auth:** router and bank-api internal (VPC / IAM invoker), only the frontend exposed; authentication with
   the bank's real IdP instead of the simulated OTP.
4. **The bank's policy:** replace the synthetic POL-1..7 with the real ones, with business owners and versioning;
   per-country dispute windows.
5. **Operations:** separate staging/prod with rollback, a scheduled pipeline with a freshness SLA that blocks gold,
   router drift monitoring and retraining with the labels the agent console produces (LEARN).
6. **Continuous evaluation:** the regression gate (MET-01 does not drop, MET-04 does not rise) on every prompt or model
   change.

**What would you do differently with more time?**
A larger held-out set for narrower intervals, broader human labeling for the router and a PT evaluation with native
speakers.

---

## Live demo plan

- The day before: `MIN_INSTANCES=1` (OPS) to avoid the cold start; test from an external network.
- Script: the same as the video (ES happy path → PT → handoff → Langfuse), with `MX-DEMO-001`; keep `CO-DEMO-002` as
  backup.
- If Gemini fails live: the turn continues with rules and templates (fallback, REQ-16). Show it as a strength.
- Final backup: the recorded video and screenshots of the Langfuse trace.
