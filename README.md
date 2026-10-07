# AI Bug Report Classifier

## Overview

The AI Bug Report Classifier converts messy natural-language bug reports into validated structured information that is useful for software bug triage and engineering operations.

The system will eventually classify and normalize key fields such as:

- category
- severity
- priority
- environment
- issue
- reproduction availability
- confidence
- human-review requirement

## Current status

This project is currently in the schema and contract implementation stage. The structured output contract has been defined and validated, but the LLM integration, provider integration, and evaluation stages have not yet been implemented.

## Planned architecture

The intended architecture is:

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

The repository is intended to evolve into the following structure:

```text
ai-bug-report-classifier/
├── app/
│   ├── main.py
│   ├── schemas.py
│   ├── prompts.py
│   ├── llm_client.py
│   ├── bug_service.py
│   ├── evaluator.py
│   └── review.py
├── data/
│   └── eval_dataset.json
├── tests/
│   ├── test_schema.py
│   ├── test_classifier.py
│   ├── test_review.py
│   ├── test_retry.py
│   └── test_evaluation.py
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

Some of the files above are planned and not yet implemented.

## Testing

The current test command is:

```bash
python -m pytest -q
```

The current schema test suite passes.

This project does not yet claim that future classification, evaluation, or LLM-provider stages are implemented.
