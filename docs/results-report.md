# Evaluation Results Report

## Scope

This report covers the deterministic evaluation runner added for Step 15. It does not claim a real LLM evaluation has been executed. The automated suite verifies the runner logic using deterministic fake classifications and synthetic results only.

## Current status

- Synthetic validation: completed via unit tests
- Live LLM evaluation: not run in this implementation
- Dataset in use: `data/eval_dataset.json`

## Automated-test metrics

The automated evaluation runner is tested against known prediction fixtures. These are not model outputs and must not be interpreted as live classification performance.

Supported metrics produced by the runner:

- dataset case count
- attempted cases
- successful classifications
- failed cases
- schema compliance rate
- category accuracy
- severity accuracy
- priority accuracy
- reproduction-availability accuracy
- overall classification accuracy
- human-review routing rate
- human-review routing accuracy when explicit ground-truth review values are supplied
- failure counts by the canonical FailureCategory values

## Real evaluation run

To execute a real model evaluation later, use the runner script from the repository root:

```bash
python scripts/run_evaluation.py --dataset data/eval_dataset.json --output data/evaluation_results.json
```

The runner expects provider configuration via environment variables `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_API_KEY` unless they are overridden on the command line. It writes JSON output for later analysis without printing secrets or full environment configuration.

## Important limitation

No live LLM evaluation metrics are included in this report because no real provider call was made during the implementation step.
