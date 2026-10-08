import inspect

import pytest

import app.bug_service as bug_service
from app.bug_service import (
    BugReportClassifier,
    ClientFailureError,
    EmptyBugReportError,
    InvalidStructuredOutputError,
)
from app.prompts import build_developer_prompt, build_system_prompt, build_user_prompt
from app.schemas import BugReport


class FakeLLMClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate(self, prompt: str, *, response_format: str | None = None, **kwargs):
        self.calls.append({"prompt": prompt, "response_format": response_format, "kwargs": kwargs})
        if self.error is not None:
            raise self.error
        return self.response


def test_valid_bug_report_produces_valid_bugreport():
    payload = {
        "category": "API",
        "severity": "High",
        "priority": "P1",
        "environment": "Production",
        "issue": "API requests fail after the token expires",
        "reproduction_available": True,
        "confidence": 0.87,
        "requires_human_review": False,
    }
    classifier = BugReportClassifier(FakeLLMClient(payload))

    result = classifier.classify("API requests fail after the token expires on production")

    assert isinstance(result, BugReport)
    assert result.category == "API"
    assert result.severity == "High"
    assert result.priority == "P1"


def test_correct_prompts_are_passed_to_the_llm_client():
    payload = {
        "category": "UI",
        "severity": "Medium",
        "priority": "P2",
        "environment": None,
        "issue": "Button is hidden on mobile layout",
        "reproduction_available": True,
        "confidence": 0.72,
        "requires_human_review": False,
    }
    fake_llm = FakeLLMClient(payload)
    classifier = BugReportClassifier(fake_llm)

    classifier.classify("Login button is hidden on mobile layout")

    assert fake_llm.calls
    prompt = fake_llm.calls[0]["prompt"]
    assert build_system_prompt() in prompt
    assert build_developer_prompt() in prompt
    assert build_user_prompt("Login button is hidden on mobile layout") in prompt
    assert fake_llm.calls[0]["response_format"] == "json_object"


def test_provider_independent_llm_client_interface_is_used():
    fake_llm = FakeLLMClient({
        "category": "Security",
        "severity": "Critical",
        "priority": "P0",
        "environment": "Production",
        "issue": "User can access admin endpoint without role check",
        "reproduction_available": True,
        "confidence": 0.95,
        "requires_human_review": True,
    })

    classifier = BugReportClassifier(fake_llm)
    result = classifier.classify("Admin endpoint is reachable without role check")

    assert isinstance(result, BugReport)
    assert fake_llm.calls[0]["kwargs"] == {}


def test_invalid_structured_output_is_rejected():
    classifier = BugReportClassifier(FakeLLMClient({"category": "not-real"}))

    with pytest.raises(InvalidStructuredOutputError):
        classifier.classify("Something is broken")


def test_empty_input_is_rejected():
    classifier = BugReportClassifier(FakeLLMClient())

    with pytest.raises(EmptyBugReportError):
        classifier.classify("")


def test_whitespace_input_is_rejected():
    classifier = BugReportClassifier(FakeLLMClient())

    with pytest.raises(EmptyBugReportError):
        classifier.classify("   \n\t ")


def test_llm_client_errors_are_translated_appropriately():
    classifier = BugReportClassifier(FakeLLMClient(error=RuntimeError("provider exploded")))

    with pytest.raises(ClientFailureError, match="LLM client failed"):
        classifier.classify("A request fails")


def test_provider_specific_sdks_are_not_imported_by_bug_service():
    source = inspect.getsource(bug_service)
    assert "google" not in source.lower()
    assert "openai" not in source.lower()


def test_llm_response_string_json_is_validated():
    fake_llm = FakeLLMClient(
        '{"category": "Database", "severity": "Medium", "priority": "P2", "environment": "Database", "issue": "Query timeout on large table", "reproduction_available": true, "confidence": 0.8, "requires_human_review": false}'
    )
    classifier = BugReportClassifier(fake_llm)

    result = classifier.classify("Query times out on a large table")

    assert isinstance(result, BugReport)
    assert result.category == "Database"


def test_bug_report_contains_supplied_bug_report_in_user_prompt():
    bug_report = "Users cannot save settings after upgrading to iOS 17"
    fake_llm = FakeLLMClient({
        "category": "UI",
        "severity": "Medium",
        "priority": "P2",
        "environment": "iOS",
        "issue": "Users cannot save settings after upgrading to iOS 17",
        "reproduction_available": True,
        "confidence": 0.71,
        "requires_human_review": False,
    })
    classifier = BugReportClassifier(fake_llm)

    classifier.classify(bug_report)

    assert bug_report in fake_llm.calls[0]["prompt"]
