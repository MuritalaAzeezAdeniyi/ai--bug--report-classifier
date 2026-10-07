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

## Future AI-Assisted Tasks

Subsequent AI-assisted tasks will be appended to this log as they are completed.
