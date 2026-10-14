# Evaluation Results Report

## Scope

This report separates deterministic automated-test evidence from the saved live-provider evaluation. Synthetic test fixtures are not model-performance results.

## Automated tests

The evaluation-runner tests use deterministic fake classifiers to check metric calculation, per-case association, failure counting, partial-run status, and JSON output. They do not establish real model quality.

## Saved live evaluation

The saved run in `data/evaluation_results_live.json` used the 30 cases in `data/eval_dataset.json` and records:

- Dataset cases: 30
- Cases attempted: 30
- Successful classifications: 1
- Failed cases: 29
- Failure categories: `RATE_LIMITED` for all 29 failures
- Recorded provider diagnostics: HTTP 429, provider code `RESOURCE_EXHAUSTED`
- `evaluation_complete`: `false`
- `incomplete`: `true`

The saved aggregate fields report 1.0 for schema compliance and classification accuracy metrics. These values are based on the one successful classification only; the failed provider requests are recorded separately and do not count as classification mismatches in those aggregates. With just one successful case, these scores are not representative of the 30-case dataset and must not be presented as full-dataset performance.

The saved result demonstrates one successful classification and 29 rate-limited failures. It does not establish overall model quality or a completed evaluation.

## Re-running the evaluation

After confirming provider availability and quota, run the evaluation from the repository root:

```powershell
python -m scripts.run_evaluation --dataset data/eval_dataset.json --output data/evaluation_results_live.json
```

Provider configuration is read from the process environment or the repository-root `.env` file. Review the output's `evaluation_complete` and `incomplete` fields, case counts, and failure categories before interpreting any metrics.
