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

## Step 7 — LLM Client Abstraction

- AI tool used: coding agent
- Task: create the provider-agnostic LLM client abstraction and validation tests
- Files created/modified:
  - `app/llm_client.py`
  - `tests/test_llm_client.py`
  - `AI_USAGE_LOG.md`
- What was implemented: a lightweight `LLMClient` abstraction with environment-driven configuration, provider validation, and explicit configuration errors for missing values and unsupported providers.
- Configuration approach: environment variables `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_API_KEY` are validated at construction time without hardcoded secrets.
- Provider abstraction approach: the public interface is intentionally provider-independent and suitable for later structured JSON/Pydantic output handling, without vendor-specific SDK calls.
- Tests performed: `python -m pytest -q`
- Exact test result: 33 passed in 0.32s
- No real provider calls were made.
- No API keys or secrets were committed.
- Retry, fallback, rate-limit, timeout, and provider-network logic were intentionally not implemented in this step.
- Result: completed

## Step 8 — Multi-Provider LLM Integration

- AI tool used: coding agent
- Task: implement provider adapters for Gemini and OpenAI behind the existing provider-agnostic LLM client abstraction.
- Files created/modified:
  - `app/llm_client.py`
  - `tests/test_llm_client.py`
  - `requirements.txt`
  - `.env.example`
  - `AI_USAGE_LOG.md`
- Multi-provider architecture: `LLMClient` now delegates to provider adapters (`GeminiProvider` and `OpenAIProvider`) behind a common interface so the classifier and business logic do not depend on provider-specific branching.
- Provider selection: configured through `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_API_KEY`; the same application code works with either provider by configuration alone.
- Structured output: both adapters normalize provider responses into provider-independent Python objects suitable for later Pydantic validation without bundling any bug-classification logic into the provider layer.
- Error handling: missing config, unsupported provider, provider initialization failure, and provider request failure are translated into application-level client errors without exposing API keys in exception text.
- Tests performed: `python -m pytest -q`
- Exact test result: 49 passed in 7.73s
- No real API calls were made. All provider tests use mocked SDK responses and exceptions.
- No API keys or secrets were committed or embedded in source/test files.
- Unimplemented in this bounded step: retries, exponential backoff, rate-limit handling, model fallback, timeout policy, streaming, and token-budget management.
- Result: completed within the provider-integration scope only.

## Future AI-Assisted Tasks

Subsequent AI-assisted tasks will be appended to this log as they are completed.
