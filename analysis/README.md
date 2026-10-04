# analysis/ — owner: DS

EDA, workflow justification (REQ-02), business baseline, N/U/fraud calibration and fairness. Notebooks in
`notebooks/`, aggregate results in `results/` (versioned evidence that the README, the report and the slides cite),
figures in `figures/`.

| Notebook | Question | Output |
|---|---|---|
| `01_workflow_justification` | Is dispute intake the workflow with the most evidence? Can complaints be linked to transactions? | `results/workflow_justification.json` |
| `02_policy_calibration` | N (dispute window), U (amount threshold) and the fraud-score threshold, with regulation and a cost curve | `results/policy_calibration.json` |
| `03_business_baseline` | Historical call-center FCR, escalation, duration and CSAT (a projection, never a measured gain, CON-07) | `results/business_baseline.json` |
| `04_label_audit` | Does the dataset carry valid intent labels? (No: 42 templates, one detected intent) | `results/label_audit.json` |
| `05_fairness` | Metrics by language and customer segment, from the evaluation run (REQ-18) | `results/fairness.json` |

`notebooks/common.py` gives every notebook the same DuckDB views (silver if it exists, otherwise `data/raw`, plus gold)
and `save_result()`, which only stores aggregates: never customer rows (CON-03).

## Running

The official stack is Docker (`make notebook` → JupyterLab on http://localhost:8888). Without Docker:

```bash
uv run --package sofia-analysis jupyter lab --notebook-dir analysis/notebooks
# headless, e.g. to regenerate a result file:
uv run --package sofia-analysis jupyter nbconvert --to notebook --execute --output-dir /tmp analysis/notebooks/02_policy_calibration.ipynb
```

The notebooks need the data locally. To build it without putting credentials in `.env`, sync the raw files with your
own AWS CLI profile into `data/raw/` and run the pipeline on them (`--source local` never touches S3):

```bash
aws s3 sync s3://<BUCKET>/data/transactions/ data/raw/transactions/ --profile <PROFILE>
uv run --package sofia-data python -m sofia_data.pipeline --source local
```

## Filling the docs

`fill_placeholders.py` resolves the `{{file:key}}` placeholders in the README and `docs/` from the result files:

```bash
uv run --package sofia-analysis python analysis/fill_placeholders.py           # check what resolves
uv run --package sofia-analysis python analysis/fill_placeholders.py --write   # replace in place
```

Run `--write` only after the real evaluation run: the versioned `eval/outputs/ds_stats.json` comes from a 5-case,
rules-mode run.
