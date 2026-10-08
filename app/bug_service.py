from __future__ import annotations

import json
from typing import Any

from app.prompts import build_developer_prompt, build_system_prompt, build_user_prompt
from app.schemas import BugReport


class ClassificationServiceError(RuntimeError):
    """Base error for classification service failures."""


class EmptyBugReportError(ClassificationServiceError):
    """Raised when the input report is missing or empty."""


class InvalidStructuredOutputError(ClassificationServiceError):
    """Raised when the LLM returns structured data that cannot be validated."""


class ClientFailureError(ClassificationServiceError):
    """Raised when the underlying LLM client fails unexpectedly."""


class BugReportClassifier:
    """Classifies a raw bug report into a validated BugReport instance."""

    def __init__(self, llm_client: Any):
        if llm_client is None:
            raise ValueError("llm_client must not be None.")
        self._llm_client = llm_client

    def classify(self, bug_report: str) -> BugReport:
        if not isinstance(bug_report, str) or not bug_report.strip():
            raise EmptyBugReportError("bug_report must be a non-empty string.")

        system_prompt = build_system_prompt()
        developer_prompt = build_developer_prompt()
        user_prompt = build_user_prompt(bug_report)
        combined_prompt = (
            "System instructions:\n"
            f"{system_prompt}\n\n"
            "Developer instructions:\n"
            f"{developer_prompt}\n\n"
            f"{user_prompt}"
        )

        try:
            structured_response = self._llm_client.generate(
                combined_prompt,
                response_format="json_object",
            )
        except Exception as exc:
            raise ClientFailureError("LLM client failed to classify the bug report.") from exc

        return self._validate_response(structured_response)

    @staticmethod
    def _validate_response(payload: Any) -> BugReport:
        if payload is None:
            raise InvalidStructuredOutputError("LLM returned no structured output.")

        if isinstance(payload, BugReport):
            return payload

        if isinstance(payload, str):
            payload = payload.strip()
            if not payload:
                raise InvalidStructuredOutputError("LLM returned empty structured output.")
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise InvalidStructuredOutputError("LLM structured output is not valid JSON.") from exc

        try:
            return BugReport.model_validate(payload)
        except Exception as exc:
            raise InvalidStructuredOutputError("LLM structured output did not match the BugReport schema.") from exc
