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

## Step 9 — Classification Prompt Design

- AI tool used: coding agent
- Task: create prompt-building functions for system instructions, developer classification instructions, and untrusted user bug-report input.
- Files created/modified:
  - `app/prompts.py`
  - `tests/test_prompts.py`
  - `AI_USAGE_LOG.md`
- Prompt structure: `build_system_prompt()` defines high-level safety and anti-hallucination constraints; `build_developer_prompt()` defines the output contract and classification rules; `build_user_prompt(bug_report)` inserts the raw bug report as untrusted input while keeping the instructions authoritative.
- Classification rules included: category selection, severity rules, priority rules, environment extraction restrictions, issue normalization, reproduction availability criteria, confidence requirements, and human-review routing rules.
- Anti-hallucination rules included: no invented environment details, no invented reproduction steps, no invented root causes, no invented technical details, and explicit uncertainty preservation when the report is vague or incomplete.
- Tests performed: `python -m pytest -q`
- Exact test result: 62 passed in 0.95s
- No LLM calls were made. These tests are deterministic and do not invoke any provider SDK or network path.
- Result: completed within the prompt-design scope only.

## Step 10 — Bug Classification Service

- AI tool used: coding agent
- Task: build the application service that connects the BugReport schema, prompt module, and provider-agnostic LLMClient into a single classification flow.
- Files created/modified:
  - `app/bug_service.py`
  - `tests/test_bug_service.py`
  - `AI_USAGE_LOG.md`
- Service responsibility: validate raw bug-report input, build system/developer/user prompts from the prompt module, call the provider-agnostic LLMClient, validate the returned structured payload against the existing BugReport schema, and return a validated BugReport.
- Dependency injection: the classifier receives an LLMClient instance rather than constructing provider logic internally, keeping the service provider-independent.
- Prompt integration: the service uses `build_system_prompt()`, `build_developer_prompt()`, and `build_user_prompt()` from `app/prompts.py` and concatenates them into a single request payload for the LLM client while preserving the separation of responsibilities.
- Structured-output validation: invalid or malformed output is rejected with an application-level error instead of being silently repaired or partially accepted.
- Error handling: empty input, invalid structured output, and unexpected client/provider failure are surfaced as clear application-level errors. Retries, fallback, rate-limit handling, and timeout policy are intentionally not implemented in this step.
- Tests performed: `python -m pytest -q`
- Exact test result: 72 passed in 7.22s
- No real LLM calls were made. The service is tested against a deterministic fake client and does not invoke Gemini or OpenAI SDKs.
- Provider-specific SDKs remain outside the service boundary; no direct importer references were added in the bug service code.
- Result: completed within the classification-service scope only.

## Step 11 — Classification Validation & Error Handling

- AI tool used: coding agent
- Task: tighten validation and error handling around the classification service without adding retries, fallback, rate-limit logic, timeout logic, or provider-specific branching.
- Files created/modified:
  - `app/bug_service.py`
  - `tests/test_bug_service.py`
  - `AI_USAGE_LOG.md`
- Validation work performed: kept input validation deterministic and explicit for empty and whitespace-only values, preserved meaningful user input, and delegated structured-output checks to the existing BugReport Pydantic model instead of re-implementing schema rules in the service.
- Error-handling work performed: clarified typed exceptions for invalid input, invalid structured output, and unexpected client failures; ensured validation problems from BugReport become typed invalid-output errors; ensured unexpected injected client exceptions become typed client/classification errors without swallowing context.
- Tests added: coverage for empty input, whitespace input, valid inputs, missing required fields, invalid category/severity/priority/confidence/bool values, invalid-output translation, and secret-sanitized client error messages.
- Tests performed: `python -m pytest -q`
- Exact test result: 72 passed in 6.27s
- No real LLM calls were made. The service continues to use a fake/mock client for deterministic tests only.
- Retries, fallback, rate-limit handling, timeout policy, human-review routing, and confidence thresholds remain out of scope for this step.
- Result: completed within the validation and error-handling scope only.

## Future AI-Assisted Tasks

Subsequent AI-assisted tasks will be appended to this log as they are completed.
