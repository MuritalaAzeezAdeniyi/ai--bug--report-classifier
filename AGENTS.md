# AGENTS.md

## 1. PROJECT OVERVIEW

This repository contains an AI Bug Report Classifier that converts unstructured software bug reports into validated structured outputs.

The system will eventually support:

- classification
- structured output
- Pydantic validation
- confidence scoring
- reproduction detection
- human-review routing
- retries
- failure categorization
- evaluation
- failure analysis
- AI tracing/logging

The project is intended to help teams turn noisy, inconsistent bug reports into a consistent and auditable triage workflow without assuming the input is complete or reliable.

## 2. DEVELOPMENT PRINCIPLES

All coding agents working in this repository must follow these principles:

- specification-first development
- small, bounded implementation tasks
- test-driven or test-supported development
- explicit acceptance criteria
- minimal changes per task
- inspect existing code before modifying it
- never implement unrelated features
- do not rewrite working code unnecessarily
- do not make large architectural changes without clear justification

Before changing code, confirm the relevant specification, tests, and repository context. If the request goes beyond the current task, stop and clarify the scope.

## 3. AI AGENT WORKFLOW

Agents must follow this workflow for each task:

Understand requirement
→ inspect repository
→ identify relevant files
→ make a small change
→ run appropriate tests
→ inspect the diff
→ report what changed
→ identify remaining risks

Agents must not silently make large architectural changes. If a task appears to require a larger refactor, first explain the reason and the expected impact before proceeding.

## 4. STRUCTURED OUTPUT CONTRACT

The structured output defined in docs/specification.md is the application's contract.

Agents must not casually add, remove, or rename fields. Any schema change must:

- have a clear reason
- update the specification
- update tests
- update evaluation data if necessary
- be explicitly reported to the user

If an implementation change affects the output contract, it must be validated against the acceptance criteria and the specification before it is considered complete.

## 5. LLM RULES

LLM-related work must follow these rules:

- no API keys in source code
- secrets must come from environment variables
- provider-specific implementation should be isolated
- model output must be validated
- never blindly trust model-generated JSON
- malformed model output must be handled explicitly
- avoid inventing information that is not present in the bug report
- do not assume model output is correct simply because it is structured or parseable

The system should treat model output as untrusted until validation and policy checks pass.

## 6. HUMAN REVIEW

Uncertain outputs should not simply be treated as correct.

Human review may be triggered by signals such as:

- low confidence
- ambiguous report
- insufficient information
- missing reproduction information

The exact thresholds should remain configurable and should be validated through evaluation. Agents must not hardcode final thresholds without evidence from the evaluation process.

## 7. FAILURE HANDLING

Agents must preserve the project's failure taxonomy.

Use controlled failure categories rather than generic errors where appropriate.

Expected categories include:

- INVALID_SCHEMA
- LOW_CONFIDENCE
- AMBIGUOUS_REPORT
- MISSING_INFORMATION
- LLM_TIMEOUT
- RATE_LIMITED
- PROVIDER_ERROR

Do not hide failures or silently convert errors into successful results. Failures must remain visible and attributable to a specific cause when possible.

## 8. EVALUATION PRINCIPLES

Evaluation is a first-class part of the project.

Agents must not claim that the system works based only on a few manual examples.

Changes affecting classification behavior should be evaluated against the representative evaluation dataset when available.

Do not invent evaluation metrics or results. If a metric is not yet implemented or measured, say so explicitly rather than implying success.

## 9. TESTING

Future implementation should include tests for important behavior. At minimum, tests should cover:

- schema validation
- valid structured outputs
- invalid structured outputs
- classification behavior
- confidence handling
- human-review routing
- reproduction detection
- retry behavior
- failure handling
- evaluation logic

Tests should focus on real behavior and should be written to verify behavior that matters to the user or to the acceptance criteria, not production-only implementation details.

## 10. SECURITY AND PRIVACY

Agents must follow these security and privacy requirements:

- no committed secrets
- .env files must not be committed
- use .env.example for configuration documentation
- do not log API keys
- avoid unnecessary logging of complete user input
- use non-sensitive evaluation data
- validate external or model-generated data before using it
- do not expose sensitive credentials or confidential application data in logs or traces

## 11. DOCUMENTATION

Implementation changes must keep relevant documentation up to date.

Important documentation includes:

- README.md
- docs/specification.md
- docs/acceptance-plan.md
- docs/results-report.md
- docs/failure-analysis.md
- AI_USAGE_LOG.md

If a code change affects behavior, configuration, workflow, or evaluation, the relevant documentation must be updated in the same task when necessary.

## 12. GIT PRACTICES

Agents must follow these git practices:

- small, focused commits
- descriptive commit messages
- do not commit secrets
- do not commit generated temporary files
- inspect the git diff before committing

Avoid broad, noisy changes that mix unrelated work into one commit.

## 13. DEFINITION OF DONE

A task is not considered complete merely because code was written.

A task should normally include:

- implementation
- relevant tests
- passing tests
- acceptance criteria checked
- diff reviewed
- documentation updated when necessary
- risks/limitations reported

If a task cannot fully satisfy these conditions, the agent must report the actual status honestly and clearly.

## General repository guidance

- Keep changes scoped to the requested task.
- Prefer existing patterns and conventions already present in the repository.
- When uncertain, read the existing files and specification before making changes.
- Do not assume the repository is empty; inspect first.
- Do not add speculative features outside the approved scope.
