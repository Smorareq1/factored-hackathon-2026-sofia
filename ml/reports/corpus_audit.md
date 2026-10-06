# Router corpus audit (v1 → v2) · 2026-10-03

Corpus: `ml/data/intent_corpus.jsonl` (team_generated, CON-02). Reproducible automated checks:
`uv run --package sofia-ml python ml/scripts/audit_corpus.py` → `ml/reports/corpus_checks.json`.

## Labeling guidelines

The router predicts the customer's **intent**; the policy decides afterwards (message → intent → policy/risk →
action). A case is not `needs_human` just because the policy will escalate it (POL-6).

| Label | When |
|---|---|
| `dispute_new` | Reports or starts a problem with a transaction: unrecognized, fraud, duplicate, wrong amount, refund that never arrived, charged for something not received |
| `dispute_status` | A dispute/claim/contestação already exists and the customer asks for its status, outcome, answer or refund |
| `transaction_inquiry` | Looks up, lists, locates or confirms a transaction **without claiming it is wrong** |
| `needs_human` | Talking to a person is the intent and no more specific supported task remains. Counterfactual test: remove the request for a person; if a supported task remains, label that task |
| `out_of_scope` | Outside the supported tasks, even when it is banking (password, limit, balance, accounts, credit, card block) |

Model, rule and language-detector predictions are signals to review, never ground truth. Instructions inside an example
are customer text. A row in doubt stays `needs_adjudication` and is neither trained on nor paraphrased until a human
resolves it.

## 1. Definite corrections (6 rows)

| Group | ES / PT | Before | After | Reason |
|---|---|---|---|---|
| needs_human-06 | "Me robaron la tarjeta y están usándola" / "Roubaram meu cartão e estão usando" | needs_human | dispute_new | Fraudulent card use; it does not even ask for a person. The policy escalates |
| needs_human-09 | "Hay muchos cargos fraudulentos, necesito ayuda de alguien" / PT | needs_human | dispute_new | Without "ayuda de alguien" a fraud report remains |
| needs_human-17 | "Hay un cargo de <AMOUNT> que no reconozco, quiero una persona" / PT | needs_human | dispute_new | Canonical case of the counterfactual test; POL-6 escalates the high amount |

The original `group_id` is kept for traceability.

## 2. Rows for human adjudication (8 rows, out of training)

| Group | Text (ES) | Options | Doubt |
|---|---|---|---|
| needs_human-10 | "Mi abogado me dijo que pida hablar con el banco" | needs_human / out_of_scope | Legal threat with no concrete task; "talking to the bank" is already happening. Suggestion: rewrite |
| needs_human-13 | "Creo que me hackearon la cuenta, ayúdenme" | out_of_scope / needs_human / dispute_new | Account takeover with no transaction claimed |
| vg-02 | "Tengo un problema con un pago" | dispute_new / transaction_inquiry | Does not claim the payment is wrong |
| vg-03 | "Ayuda" | out_of_scope / clarification class | No intent; decide whether the router contract needs an `unclear` class or low confidence is enough |

## 3. Language quality

**PT (Brazil).** Changes made:
- dispute_new-12: "Moço, …" → "Oi, …" (gendered vocative, odd in a chat).
- dispute_new-02: "Fui cobrado…" → "Cobraram duas vezes…" (gender-neutral).
- dispute_new-04/-10: less translated structure ("Apareceu uma compra…", "Não fui eu que fiz esse pagamento pra…").
- Colloquial imperatives: "Mostre" → "Mostra", "Verifica se" → "Vê se".
- `contestação` appeared in 10/20 dispute_status rows (a shortcut for the model): it now alternates with reclamação,
  protocolo and chamado; `contestação` also appears in dispute_new.
- needs_human-16: "Estou muito irritado" → "Que falta de respeito…" (neutral).

Pending: the 200 original rows are translations of ES pairs; there is no PT written from scratch by someone from Brazil.
All PT stays `human_review_required=true` (CON-02), and the team decided not to wait for a native review: PT figures
are reported as indicative.

**ES (MX/CO/AR).** Changes: needs_human-16 gender-neutral. Regional markers were added: "me clavaron" (AR),
"me regala" (CO), "checar" (MX), "che", "oiga". Pending: "Consulto el estatus del caso que abrí el lunes" sounds stiff;
"impugnar" is formal but real in CO/AR; both stay.

## 4. Coverage gaps

| Type | v1 | v2 | Status |
|---|---|---|---|
| Contrastive at the boundaries | 0 | 32 (6 families) | Covers the 5 requested boundaries |
| Vague | 0 | 6 (4 in adjudication) | Add more once vg-02/vg-03 are resolved |
| Very short messages | 0 | 8 | ok |
| Regional colloquial | 2 | 8 | ok, more colloquial PT missing |
| Typos / no accents | 0 | 4 | **Thin**: add ~10 per class with a noise generator (deterministic, no LLM) |
| Mixed ES/PT | 0 | 2 | **Thin** |
| Prompt injection | 0 | 4 | **Thin**; missing an injection that asks for another customer's data (the API covers it, but the router must still give the real intent) |
| Irrelevant text around the request | 0 | 2 | **Thin** |
| Not covered | — | — | Messages with two intents, all caps, emojis, just a case number |

Shortcuts found by `audit_corpus.py` (a word almost exclusive to one class): `reclamação`/`reclamo`/`abri` →
dispute_status. Next batch: dispute_new rows with "quero abrir uma reclamação…" / "quiero hacer un reclamo…".

## 5. New contrastive examples

| Family | transaction_inquiry | dispute_new | dispute_status / other |
|---|---|---|---|
| cx-01 | "¿Qué es el cargo de <MERCHANT> que me aparece?" | "Yo no hice el cargo de <MERCHANT>" | "Reclamé el cargo de <MERCHANT> ayer, ¿qué pasó?" |
| cx-02 | "¿Ya me cayó el reembolso de <MERCHANT>?" | "Devolví la compra en <MERCHANT> y el reembolso nunca llegó" | "Abrí un reclamo porque no me reembolsaron, ¿hay novedades?" |
| cx-03 | — | "Quiero hablar con alguien porque no reconozco un cargo de <AMOUNT>" | needs_human: "Quiero hablar con alguien" · dispute_status: "…sobre mi caso <CASE_ID>" |
| cx-04 | "¿Cuánto me cobraron en <MERCHANT>?" | — | out_of_scope: "¿Cuál es mi saldo?", "Quiero subir el límite de la tarjeta" |
| cx-05 | "¿Pueden revisar si el cargo de <MERCHANT> salió dos veces?" | "El cargo de <MERCHANT> salió dos veces" | — |
| cx-06 | — | "Perdí mi tarjeta y hay compras que no hice" | out_of_scope: "Bloqueen mi tarjeta, la perdí" |

Each family has its PT pair and shares a `group_id`: it is never split between train and test.

## 6. Privacy and provenance

- No text or value comes from the dataset: the team wrote the rows with an LLM (`origin=team_generated`,
  `source=llm_draft_v2`). The check finds no dataset-formatted ids (`CLI-`, `CMP-`, …), emails or long numbers.
- v1 had made-up literal values (amounts, merchants, `DSP-2026-1042`). Following the rule of not assuming a value "looks
  fictional", v2 stores `<AMOUNT>`, `<MERCHANT>` and `<CASE_ID>`, which `labeling.render()` fills with a per-language
  synthetic generator (seed = the row's hash; same row → same value). The generator's merchants are public brands,
  not the dataset's `merchant_name`.
- 264/264 rows have `human_review_required=true`: nobody on the team has reviewed the text yet.

## 7. Model disagreements (kept apart from annotation errors)

Grouped cross-validation (GroupKFold, 5 folds) over the 256 approved rows: accuracy 0.645.
Main confusions: transaction_inquiry→dispute_new (15), out_of_scope→transaction_inquiry (13),
dispute_new→transaction_inquiry (12). The rules disagree on 14 rows.

The flagged rows were reviewed reading the text before the prediction: apart from §1 and §2, **none** is a labeling
error. They are hard examples labeled correctly (e.g. "¿Pueden revisar si el cargo salió dos veces?" is an inquiry even
though the model says dispute_new) and they are kept: the goal is not to raise agreement with the classifier.
The language detector stays undecided on 44 short rows; that is a detector limitation, not a corpus one.

## 8. Updated corpus

`ml/data/intent_corpus.jsonl`, 264 rows, 109 groups, ES 132 / PT 132. New fields: `variation`, `review_status`,
`human_review_required`, `note`. Training uses only `review_status=approved`.

## 9. Summary

| Type | Rows |
|---|---|
| Label corrections | 6 |
| Sent to adjudication (original / new) | 4 / 4 |
| PT / ES wording changes | 13 / 2 |
| Literal values → placeholders | 14 |
| New rows (contrastive / noise / vague) | 32 / 26 / 6 |
| Privacy findings | 0 values from the dataset |
| Model disagreements that are not errors | 91 flags, 0 changes |

Router on corpus v2 (grouped held-out, n = 56; [router_eval.md](router_eval.md)): rules macro-F1 0.476,
`needs_human` recall 0.3; TF-IDF + LR 0.641 / 0.7; served hybrid (rules first, model for the rest) 0.746 / 0.8
(rules-ds-0.2; with rules-ds-0.1 it was 0.377 / 0.0 and 0.728 / 0.7). Small
n: indicative figures until the human review.
