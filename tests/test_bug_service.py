import inspect

import pytest

import app.bug_service as bug_service
from app.bug_service import (
    BugReportClassifier,
    ClientFailureError,
    EmptyBugReportError,
    InvalidStructuredOutputError,
    RetryPolicy,
    TransientClientError,
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


def valid_payload():
    return {
        "category": "API",
        "severity": "High",
        "priority": "P1",
        "environment": "Production",
        "issue": "API requests fail after the token expires",
        "reproduction_available": True,
        "confidence": 0.87,
        "requires_human_review": False,
    }


def test_valid_bug_report_produces_valid_bugreport():
    payload = valid_payload()
    classifier = BugReportClassifier(FakeLLMClient(payload))

    result = classifier.classify("API requests fail after the token expires on production")

    assert isinstance(result, BugReport)
    assert result.category == "API"
    assert result.severity == "High"
    assert result.priority == "P1"


def test_transient_error_retries_and_succeeds():
    fake_llm = FakeLLMClient(response=valid_payload(), error=TransientClientError("temporary issue"))
    sleep_calls = []
    policy = RetryPolicy(max_attempts=2, base_delay_seconds=0.25, max_delay_seconds=2.0, sleep_fn=sleep_calls.append)
    classifier = BugReportClassifier(fake_llm, retry_policy=policy)

    first_call = FakeLLMClient(response=valid_payload(), error=TransientClientError("temporary issue"))
    first_call.generate = lambda *args, **kwargs: (_ for _ in ()).throw(TransientClientError("temporary issue"))

    fake_llm.calls = []
    fake_llm.error = TransientClientError("temporary issue")
    fake_llm.response = None

    class RetrySequenceClient:
        def __init__(self):
            self.calls = 0

        def generate(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise TransientClientError("temporary issue")
            return valid_payload()

    classifier = BugReportClassifier(RetrySequenceClient(), retry_policy=policy)
    result = classifier.classify("Temporary issue then success")

    assert isinstance(result, BugReport)
    assert result.category == "API"
    assert sleep_calls == [0.25]


def test_retry_policy_retries_up_to_max_attempts():
    attempts = {"count": 0}

    class FailAlwaysClient:
        def generate(self, *args, **kwargs):
            attempts["count"] += 1
            raise TransientClientError("still failing")

    sleep_calls = []
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=0.5, max_delay_seconds=2.0, sleep_fn=lambda delay: sleep_calls.append(delay))
    classifier = BugReportClassifier(FailAlwaysClient(), retry_policy=policy)

    with pytest.raises(ClientFailureError):
        classifier.classify("This keeps failing")

    assert attempts["count"] == 3
    assert sleep_calls == [0.5, 0.5]


def test_invalid_structured_output_is_not_retried():
    class BrokenClient:
        def generate(self, *args, **kwargs):
            return {"category": "not-real"}

    policy = RetryPolicy(max_attempts=4, base_delay_seconds=0.5, max_delay_seconds=2.0, sleep_fn=lambda delay: (_ for _ in ()).throw(AssertionError("sleep must not be called")))
    classifier = BugReportClassifier(BrokenClient(), retry_policy=policy)

    with pytest.raises(InvalidStructuredOutputError):
        classifier.classify("Bad schema")


def test_empty_input_is_not_retried():
    sleep_calls = []
    policy = RetryPolicy(max_attempts=4, base_delay_seconds=0.5, max_delay_seconds=2.0, sleep_fn=lambda delay: sleep_calls.append(delay))
    classifier = BugReportClassifier(FakeLLMClient(), retry_policy=policy)

    with pytest.raises(EmptyBugReportError):
        classifier.classify("")

    assert sleep_calls == []


def test_backoff_sequence_uses_exponential_growth():
    delays = []
    policy = RetryPolicy(max_attempts=5, base_delay_seconds=0.25, max_delay_seconds=1.0, sleep_fn=lambda delay: delays.append(delay))

    assert policy.delay_for_attempt(1) == 0.25
    assert policy.delay_for_attempt(2) == 0.25
    assert policy.delay_for_attempt(3) == 0.5
    assert policy.delay_for_attempt(4) == 1.0
    assert policy.delay_for_attempt(5) == 1.0


def test_client_failure_with_secret_is_sanitized_in_retry_error():
    class SecretFailingClient:
        def generate(self, *args, **kwargs):
            raise TransientClientError("temporary failure with api_key=abc123 and token=xyz987")

    policy = RetryPolicy(max_attempts=2, base_delay_seconds=0.1, max_delay_seconds=0.5, sleep_fn=lambda delay: None)
    classifier = BugReportClassifier(SecretFailingClient(), retry_policy=policy)

    with pytest.raises(ClientFailureError) as excinfo:
        classifier.classify("Secret failure")

    text = str(excinfo.value)
    assert "abc123" not in text
    assert "xyz987" not in text
    assert "api_key" not in text.lower()
    assert "token" not in text.lower()


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


def test_missing_required_field_is_rejected():
    payload = valid_payload()
    payload.pop("issue")
    classifier = BugReportClassifier(FakeLLMClient(payload))

    with pytest.raises(InvalidStructuredOutputError):
        classifier.classify("Missing issue field")


def test_invalid_category_rejected():
    payload = valid_payload()
    payload["category"] = "not-a-valid-category"
    classifier = BugReportClassifier(FakeLLMClient(payload))

    with pytest.raises(InvalidStructuredOutputError):
        classifier.classify("Bad category")


def test_invalid_severity_rejected():
    payload = valid_payload()
    payload["severity"] = "Urgent"
    classifier = BugReportClassifier(FakeLLMClient(payload))

    with pytest.raises(InvalidStructuredOutputError):
        classifier.classify("Bad severity")


def test_invalid_priority_rejected():
    payload = valid_payload()
    payload["priority"] = "P99"
    classifier = BugReportClassifier(FakeLLMClient(payload))

    with pytest.raises(InvalidStructuredOutputError):
        classifier.classify("Bad priority")


def test_invalid_confidence_rejected():
    payload = valid_payload()
    payload["confidence"] = 1.5
    classifier = BugReportClassifier(FakeLLMClient(payload))

    with pytest.raises(InvalidStructuredOutputError):
        classifier.classify("Bad confidence")


def test_invalid_boolean_rejected():
    payload = valid_payload()
    payload["requires_human_review"] = "yes"
    classifier = BugReportClassifier(FakeLLMClient(payload))

    with pytest.raises(InvalidStructuredOutputError):
        classifier.classify("Bad bool")


def test_empty_input_is_rejected():
    classifier = BugReportClassifier(FakeLLMClient())

    with pytest.raises(EmptyBugReportError):
        classifier.classify("")


def test_whitespace_input_is_rejected():
    classifier = BugReportClassifier(FakeLLMClient())

    with pytest.raises(EmptyBugReportError):
        classifier.classify("   \n\t ")


def test_llm_client_errors_are_translated_appropriately():
    classifier = BugReportClassifier(FakeLLMClient(error=RuntimeError("provider exploded with secret=abc123")))

    with pytest.raises(ClientFailureError, match="LLM client failed") as excinfo:
        classifier.classify("A request fails")

    assert "abc123" not in str(excinfo.value)
    assert "secret" not in str(excinfo.value).lower()


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
