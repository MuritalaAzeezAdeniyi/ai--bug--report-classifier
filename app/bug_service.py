from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.evaluator import FailureCategory
from app.llm_client import LLMRateLimitError, LLMTimeoutError, ProviderRequestError
from app.prompts import build_developer_prompt, build_system_prompt, build_user_prompt
from app.schemas import BugReport


class ClassificationServiceError(RuntimeError):
    """Base error for classification service failures."""

    def __init__(self, message: str, *, category: FailureCategory = FailureCategory.PROVIDER_ERROR):
        super().__init__(message)
        self.category = category


class EmptyBugReportError(ClassificationServiceError):
    """Raised when the input report is missing or empty."""

    def __init__(self, message: str):
        super().__init__(message, category=FailureCategory.MISSING_INFORMATION)


class InvalidStructuredOutputError(ClassificationServiceError):
    """Raised when the LLM returns structured data that cannot be validated."""

    def __init__(self, message: str):
        super().__init__(message, category=FailureCategory.INVALID_SCHEMA)


class ClientFailureError(ClassificationServiceError):
    """Raised when the underlying LLM client fails unexpectedly."""

    def __init__(self, message: str, *, category: FailureCategory = FailureCategory.PROVIDER_ERROR):
        super().__init__(message, category=category)


class TransientClientError(ClientFailureError):
    """Raised when an LLM client error is transient and retryable."""

    def __init__(self, message: str):
        super().__init__(message, category=FailureCategory.PROVIDER_ERROR)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 4.0
    sleep_fn: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must be non-negative.")
        if self.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds must be non-negative.")

    def delay_for_attempt(self, attempt_number: int) -> float:
        if attempt_number < 1:
            raise ValueError("attempt_number must be at least 1.")
        if attempt_number == 1:
            return min(self.base_delay_seconds, self.max_delay_seconds)
        exp = 2 ** (attempt_number - 2)
        return min(self.base_delay_seconds * exp, self.max_delay_seconds)


@dataclass(frozen=True)
class HumanReviewPolicy:
    """Deterministic escalation rules for bug reports that should be reviewed by a human."""

    confidence_threshold: float = 0.75

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0 inclusive.")

    def should_require_human_review(self, report: BugReport) -> bool:
        if report.requires_human_review:
            return True
        if report.confidence < self.confidence_threshold:
            return True
        if not report.reproduction_available:
            return True
        return False


class BugReportClassifier:
    """Classifies a raw bug report into a validated BugReport instance."""

    def __init__(self, llm_client: Any, retry_policy: RetryPolicy | None = None, review_policy: HumanReviewPolicy | None = None):
        if llm_client is None:
            raise ValueError("llm_client must not be None.")
        self._llm_client = llm_client
        self._retry_policy = retry_policy or RetryPolicy()
        self._review_policy = review_policy or HumanReviewPolicy()

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

        for attempt_number in range(1, self._retry_policy.max_attempts + 1):
            try:
                structured_response = self._llm_client.generate(
                    combined_prompt,
                    response_format="json_object",
                )
            except (LLMTimeoutError, LLMRateLimitError, TransientClientError) as exc:
                if attempt_number >= self._retry_policy.max_attempts:
                    raise self._wrap_client_failure(exc, attempt_number) from exc
                delay = self._retry_policy.delay_for_attempt(attempt_number)
                self._retry_policy.sleep_fn(delay)
                continue
            except ProviderRequestError as exc:
                raise self._wrap_client_failure(exc, attempt_number) from exc
            except Exception as exc:
                raise self._wrap_client_failure(exc, attempt_number) from exc

            try:
                report = self._validate_response(structured_response)
                return self._apply_review_policy(report)
            except InvalidStructuredOutputError:
                raise

    @staticmethod
    def _infer_failure_category(exc: BaseException) -> FailureCategory:
        if isinstance(exc, InvalidStructuredOutputError):
            return FailureCategory.INVALID_SCHEMA
        if isinstance(exc, LLMTimeoutError):
            return FailureCategory.LLM_TIMEOUT
        if isinstance(exc, LLMRateLimitError):
            return FailureCategory.RATE_LIMITED
        if isinstance(exc, ProviderRequestError):
            return FailureCategory.PROVIDER_ERROR

        if isinstance(exc, ClassificationServiceError):
            category = getattr(exc, "category", None)
            if isinstance(category, FailureCategory):
                return category
        return FailureCategory.PROVIDER_ERROR

    @staticmethod
    def _wrap_client_failure(exc: BaseException, attempt_number: int) -> ClientFailureError:
        message = str(exc).strip() or exc.__class__.__name__
        safe_message = BugReportClassifier._sanitize_error_text(message)
        category = BugReportClassifier._infer_failure_category(exc)
        if attempt_number > 1:
            return ClientFailureError(f"LLM client failed after {attempt_number} attempts: {safe_message}", category=category)
        return ClientFailureError(f"LLM client failed: {safe_message}", category=category)

    @staticmethod
    def _sanitize_error_text(message: str) -> str:
        redacted = message
        for key_name in ("api_key", "apikey", "token", "secret", "authorization", "password"):
            redacted = re.sub(
                rf"(?i)(?:\b{key_name}\b\s*[:=]\s*)[^\s,;\]]+",
                "[REDACTED]",
                redacted,
            )
        return redacted

    def _apply_review_policy(self, report: BugReport) -> BugReport:
        review_required = self._review_policy.should_require_human_review(report)
        return report.model_copy(update={"requires_human_review": review_required})

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
            raise InvalidStructuredOutputError(
                "LLM structured output did not match the BugReport schema."
            ) from exc
