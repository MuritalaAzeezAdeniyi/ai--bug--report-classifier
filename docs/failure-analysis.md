# Failure Analysis

## Purpose

This document describes the observed failures in the saved live evaluation and the limits of what can be concluded from them.

## Canonical failure categories

The evaluator and runner use these canonical values:

- `INVALID_SCHEMA`
- `LOW_CONFIDENCE`
- `AMBIGUOUS_REPORT`
- `MISSING_INFORMATION`
- `LLM_TIMEOUT`
- `RATE_LIMITED`
- `PROVIDER_ERROR`

## Observed live-run failures

The saved file `data/evaluation_results_live.json` records 30 attempted cases: one successful classification and 29 failures. All 29 failures are categorized as `RATE_LIMITED`. The recorded diagnostics for these failures are HTTP status 429 and provider error code `RESOURCE_EXHAUSTED`; the adapter identifies the diagnostic cause as `rate_limit_or_quota`.

These observations establish that the provider returned rate-limit/resource-exhaustion responses during this run. They do not establish the precise underlying quota cause. In particular, the available result data does not prove whether the cause was a particular request-rate limit, a project/model quota, billing status, or another provider-side condition. No one cause should be asserted without additional provider-side evidence.

## Impact on evaluation conclusions

Only one of 30 cases produced a successful classification. The saved 1.0 schema-compliance and classification accuracy aggregates reflect that single successful case; they do not describe the full dataset. The other 29 cases failed at the provider request stage and were counted separately, not evaluated as ordinary classification mismatches.

There are not enough successful classifications to assess overall model quality, compare categories reliably, or draw dataset-wide conclusions. The evaluation is incomplete (`evaluation_complete: false`, `incomplete: true`).

## Next diagnostic evidence

Before another live run, inspect the provider's project/model quota and request limits through the provider's authorized console or account diagnostics. The saved responses alone do not identify which limit or account condition caused the 429s. Do not rerun the full evaluation until provider availability is confirmed, to avoid unnecessary requests and quota consumption.
