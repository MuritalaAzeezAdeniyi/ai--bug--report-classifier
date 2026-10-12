# Failure Analysis

## Purpose

This document records the failure taxonomy and execution behavior used by the evaluation runner. It is intentionally limited to the repository’s existing failure categories and deterministic evaluation logic.

## Canonical failure categories

The evaluator and runner use the existing values from `FailureCategory`:

- INVALID_SCHEMA
- LOW_CONFIDENCE
- AMBIGUOUS_REPORT
- MISSING_INFORMATION
- LLM_TIMEOUT
- RATE_LIMITED
- PROVIDER_ERROR

## Failure handling in the runner

The evaluation runner distinguishes between:

- successful classifications
- provider or API failures
- schema/validation failures
- failed dataset cases that are counted as failures rather than correct classifications

A failed case is recorded with its dataset ID, dataset index, failure category, and error message when available. These are included in the JSON output so they are visible to review instead of being collapsed into a successful result.

## Provider diagnostics

Provider request errors retain only bounded structured diagnostics: provider exception class name, numeric HTTP status when supplied, recognized provider error codes, and a conservative cause label. Recognized causes include authentication, rate-limit/quota, timeout, and explicit model-not-found errors. The adapter does not include raw SDK exception text, request payloads, response bodies, headers, or environment values in the surfaced message. If structured attributes do not establish a cause, the diagnostic label is `unknown`.

These diagnostics do not change the canonical failure categories or retry policy: timeout and rate-limit/quota errors retain their existing typed categories and retry behavior; other provider errors remain `PROVIDER_ERROR`.

## Current evidence

This implementation has been verified with deterministic synthetic tests. Actual model-side failures remain pending until a real evaluation run occurs under a configured LLM provider.

## Limitation

No real LLM output or live failure analysis is claimed in this document. The diagnostic changes were verified with mocked exceptions; the reported live evaluation failures were not rerun. A live model run must be performed separately with the configured environment.
