# AI Bug Report Classifier

## Overview

The AI Bug Report Classifier converts messy natural-language bug reports into validated structured information that is useful for software bug triage and engineering operations.

The system classifies and normalizes key fields such as:

- category
- severity
- priority
- environment
- issue
- reproduction availability
- confidence
- human-review requirement

## Current status

Implemented functionality includes a Pydantic-validated classification service, prompt construction, Gemini and OpenAI provider adapters, deterministic human-review routing, a dataset evaluation runner, and a single-report CLI that prints validated JSON. These features are covered by automated tests using fakes and mocks.

Live-provider behavior remains only partially verified. The saved evaluation is incomplete: 1 of 30 cases succeeded and 29 failed with Gemini HTTP 429 `RESOURCE_EXHAUSTED`. This does not establish full-dataset classification quality; see `data/evaluation_results_live.json`, `docs/results-report.md`, and `docs/failure-analysis.md`.

## Implemented classification flow

The implemented classification flow is:

```text
Input Bug Report
       |
       v
LLM Classification
       |
       v
Structured Pydantic Output
       |
       +----> Validation
       |
       +----> Human Review Routing
       |
       v
Evaluation
       |
       v
Results / Failure Analysis
```

## Project structure

```text
ai-bug-report-classifier/
├── app/
│   ├── schemas.py
│   ├── prompts.py
│   ├── llm_client.py
│   ├── bug_service.py
│   ├── evaluator.py
│   └── __init__.py
├── scripts/
│   ├── classify_bug.py
│   ├── run_evaluation.py
│   └── __init__.py
├── data/
│   └── eval_dataset.json
├── tests/
│   ├── test_schema.py
│   ├── test_bug_service.py
│   ├── test_classify_bug_cli.py
│   ├── test_evaluation.py
│   ├── test_evaluation_runner.py
│   ├── test_eval_dataset.py
│   ├── test_llm_client.py
│   └── test_prompts.py
├── docs/
│   ├── specification.md
│   ├── acceptance-plan.md
│   ├── results-report.md
│   └── failure-analysis.md
├── AGENTS.md
├── README.md
├── AI_USAGE_LOG.md
├── requirements.txt
└── .env.example
```

## Usage

Run one report from the repository root:

```powershell
python -m scripts.classify_bug "Login keeps loading after I enter the correct password on Android"
```

Or read a report from any existing UTF-8 text file:

```powershell
python -m scripts.classify_bug --file .\path\to\your_report.txt
```

The CLI uses the configured provider through the existing classifier service and prints the complete validated `BugReport` as formatted JSON. The evaluation runner loads repository-root `.env` configuration using the same environment-loading helper:

```powershell
python -m scripts.run_evaluation --dataset data/eval_dataset.json --output data/evaluation_results.json
```

Configure `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_API_KEY` in the process environment or repository-root `.env` before making a live request. CLI errors are reported without printing provider credentials or stack traces.

## Demo

[Watch the Demo Recording](https://www.loom.com/share/ed983ea446664cc5976f5f9e651605be
)

## Testing

Run the deterministic test suite with:

```powershell
python -m pytest -q
```

Provider and CLI tests use mocked clients; they do not make live API calls. The CLI is implemented and mocked-tested, but successful live single-report behavior has not been verified. Live evaluation performance remains incomplete because of the recorded Gemini rate-limit failures.
