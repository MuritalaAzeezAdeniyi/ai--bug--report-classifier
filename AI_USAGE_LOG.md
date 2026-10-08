# AI Usage Log

This project uses AI coding assistance during development. Each bounded task is reviewed by the developer before approval, and generated changes are tested and inspected before they are considered complete. This log will be updated after each significant AI-assisted development task.

## Step 1 — Specification and Acceptance Plan

- AI tool used: coding agent
- Task: create project specification and acceptance plan
- Files created:
  - `docs/specification.md`
  - `docs/acceptance-plan.md`
- Human review: reviewed and approved
- Result: completed

## Step 2 — Agent Repository Instructions

- AI tool used: coding agent
- Task: create `AGENTS.md`
- File created: `AGENTS.md`
- Human review: reviewed and approved
- Result: completed

## Step 3 — Structured Output Contract

- AI tool used: coding agent
- Task: implement Pydantic BugReport schema and validation tests
- Files created/modified:
  - `app/schemas.py`
  - `tests/test_schema.py`
- Test result: 11 tests passed
- Human review: reviewed and approved
- Notable issue discovered: normal Pydantic boolean coercion could accept string boolean values, so `StrictBool` was used.
- Result: completed

## Step 4 — Foundation Files

- AI tool used: coding agent
- Task: verify and create the required project foundation files
- Files created/confirmed:
  - `README.md`
  - `AI_USAGE_LOG.md`
  - `requirements.txt`
  - `.env.example`
  - `AGENTS.md`
- Human review: reviewed and approved
- Result: completed

## Step 5 — Evaluation Dataset

- AI tool used: coding agent
- Task: create initial evaluation dataset and dataset validation tests
- Dataset: 30 cases
- Files created:
  - `data/eval_dataset.json`
  - `tests/test_eval_dataset.py`
- Validation tests executed: `python -m pytest -q`
- Test result: passed
- Human review status: AI-drafted and pending human review
- Result: completed

## Step 6 — Evaluation Quality Rules

- AI tool used: coding agent
- Task: implement the deterministic evaluation module and evaluation unit tests
- Files created/modified:
  - `app/evaluator.py`
  - `tests/test_evaluation.py`
  - `AI_USAGE_LOG.md`
- What was implemented: deterministic evaluation for schema compliance, exact classification accuracy, dataset aggregation, overall classification accuracy, optional human-review routing accuracy when explicit review values are supplied, and failure-category counting.
- Why the evaluator exists: to compare predicted BugReport output against the approved ground-truth dataset without inventing confidence or review decisions from the dataset.
- Metrics defined: schema_compliance, category_accuracy, severity_accuracy, priority_accuracy, reproduction_accuracy, overall_classification_accuracy, human_review_routing_accuracy when supplied, and failure_counts support for INVALID_SCHEMA, LOW_CONFIDENCE, AMBIGUOUS_REPORT, MISSING_INFORMATION, LLM_TIMEOUT, RATE_LIMITED, and PROVIDER_ERROR.
- Validation tests executed: `python -m pytest -q`
- Exact test result: 33 passed in 0.55s
- Human review status: not applicable to the dataset; review routing is evaluated only when explicit expected review values are supplied by the caller.
- No LLM/provider integration was added.
- The evaluation dataset was not modified.
- Result: completed

## Future AI-Assisted Tasks

Subsequent AI-assisted tasks will be appended to this log as they are completed.
