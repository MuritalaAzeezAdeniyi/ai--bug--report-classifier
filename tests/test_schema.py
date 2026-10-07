import pytest
from pydantic import ValidationError

from app.schemas import BugReport


VALID_BUG_REPORT = {
    "category": "Authentication",
    "severity": "High",
    "priority": "P1",
    "environment": "Production / Web / Chrome on Windows 11",
    "issue": "Users cannot sign in with valid SSO credentials.",
    "reproduction_available": True,
    "confidence": 0.92,
    "requires_human_review": False,
}


def test_valid_complete_bug_report():
    model = BugReport(**VALID_BUG_REPORT)
    assert model.category == "Authentication"
    assert model.severity == "High"
    assert model.priority == "P1"
    assert model.reproduction_available is True
    assert model.confidence == 0.92
    assert model.requires_human_review is False


def test_valid_bug_report_without_environment():
    payload = {**VALID_BUG_REPORT, "environment": None}
    model = BugReport(**payload)
    assert model.environment is None


def test_invalid_category_rejected():
    payload = {**VALID_BUG_REPORT, "category": "InvalidCategory"}
    with pytest.raises(ValidationError):
        BugReport(**payload)


def test_invalid_severity_rejected():
    payload = {**VALID_BUG_REPORT, "severity": "Urgent"}
    with pytest.raises(ValidationError):
        BugReport(**payload)


def test_invalid_priority_rejected():
    payload = {**VALID_BUG_REPORT, "priority": "P99"}
    with pytest.raises(ValidationError):
        BugReport(**payload)


def test_confidence_below_minimum_rejected():
    payload = {**VALID_BUG_REPORT, "confidence": -0.01}
    with pytest.raises(ValidationError):
        BugReport(**payload)


def test_confidence_above_maximum_rejected():
    payload = {**VALID_BUG_REPORT, "confidence": 1.01}
    with pytest.raises(ValidationError):
        BugReport(**payload)


def test_reproduction_available_type_rejected():
    payload = {**VALID_BUG_REPORT, "reproduction_available": "yes"}
    with pytest.raises(ValidationError):
        BugReport(**payload)


def test_missing_required_fields_rejected():
    required_fields = [
        "category",
        "severity",
        "priority",
        "issue",
        "reproduction_available",
        "confidence",
        "requires_human_review",
    ]

    for field_name in required_fields:
        payload = {**VALID_BUG_REPORT}
        payload.pop(field_name)
        with pytest.raises(ValidationError):
            BugReport(**payload)


def test_invalid_requires_human_review_rejected():
    payload = {**VALID_BUG_REPORT, "requires_human_review": "false"}
    with pytest.raises(ValidationError):
        BugReport(**payload)


def test_bug_report_serializes_to_json():
    model = BugReport(**VALID_BUG_REPORT)
    as_json = model.model_dump(mode="json")

    assert isinstance(as_json, dict)
    assert set(as_json.keys()) == {
        "category",
        "severity",
        "priority",
        "environment",
        "issue",
        "reproduction_available",
        "confidence",
        "requires_human_review",
    }
    assert as_json["category"] == "Authentication"
    assert as_json["confidence"] == 0.92
