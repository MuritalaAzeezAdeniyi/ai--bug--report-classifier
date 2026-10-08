import json
from pathlib import Path

import pytest

from app.evaluator import (
    FAILURE_CATEGORIES,
    count_failures,
    evaluate_dataset,
    evaluate_prediction,
    load_eval_dataset,
)
from app.schemas import BugReport


DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "eval_dataset.json"


def _make_prediction(**overrides):
    payload = {
        "category": "Authentication",
        "severity": "High",
        "priority": "P1",
        "environment": "Production / Web",
        "issue": "Users cannot sign in with valid credentials.",
        "reproduction_available": True,
        "confidence": 0.92,
        "requires_human_review": False,
    }
    payload.update(overrides)
    return BugReport(**payload)


def test_perfect_prediction():
    expected = {
        "category": "Authentication",
        "severity": "High",
        "priority": "P1",
        "environment": "Production / Web",
        "issue": "Users cannot sign in with valid credentials.",
        "reproduction_available": True,
    }
    prediction = _make_prediction()
    result = evaluate_prediction(prediction, expected)

    assert result["schema_compliance"] == 1.0
    assert result["category_accuracy"] == 1.0
    assert result["severity_accuracy"] == 1.0
    assert result["priority_accuracy"] == 1.0
    assert result["reproduction_accuracy"] == 1.0
    assert result["overall_classification_accuracy"] == 1.0
    assert result["human_review_routing_accuracy"] is None


def test_incorrect_category():
    expected = {
        "category": "Authentication",
        "severity": "High",
        "priority": "P1",
        "environment": "Production / Web",
        "issue": "Users cannot sign in with valid credentials.",
        "reproduction_available": True,
    }
    prediction = _make_prediction(category="Authorization")
    result = evaluate_prediction(prediction, expected)

    assert result["category_accuracy"] == 0.0
    assert result["overall_classification_accuracy"] == 0.75


def test_incorrect_severity():
    expected = {
        "category": "Authentication",
        "severity": "High",
        "priority": "P1",
        "environment": "Production / Web",
        "issue": "Users cannot sign in with valid credentials.",
        "reproduction_available": True,
    }
    prediction = _make_prediction(severity="Critical")
    result = evaluate_prediction(prediction, expected)

    assert result["severity_accuracy"] == 0.0
    assert result["overall_classification_accuracy"] == 0.75


def test_incorrect_priority():
    expected = {
        "category": "Authentication",
        "severity": "High",
        "priority": "P1",
        "environment": "Production / Web",
        "issue": "Users cannot sign in with valid credentials.",
        "reproduction_available": True,
    }
    prediction = _make_prediction(priority="P2")
    result = evaluate_prediction(prediction, expected)

    assert result["priority_accuracy"] == 0.0
    assert result["overall_classification_accuracy"] == 0.75


def test_incorrect_reproduction_available():
    expected = {
        "category": "Authentication",
        "severity": "High",
        "priority": "P1",
        "environment": "Production / Web",
        "issue": "Users cannot sign in with valid credentials.",
        "reproduction_available": True,
    }
    prediction = _make_prediction(reproduction_available=False)
    result = evaluate_prediction(prediction, expected)

    assert result["reproduction_accuracy"] == 0.0
    assert result["overall_classification_accuracy"] == 0.75


def test_multiple_incorrect_fields():
    expected = {
        "category": "Authentication",
        "severity": "High",
        "priority": "P1",
        "environment": "Production / Web",
        "issue": "Users cannot sign in with valid credentials.",
        "reproduction_available": True,
    }
    prediction = _make_prediction(category="UI", severity="Low", priority="P3", reproduction_available=False)
    result = evaluate_prediction(prediction, expected)

    assert result["category_accuracy"] == 0.0
    assert result["severity_accuracy"] == 0.0
    assert result["priority_accuracy"] == 0.0
    assert result["reproduction_accuracy"] == 0.0
    assert result["overall_classification_accuracy"] == 0.0


def test_invalid_prediction_schema_failure():
    invalid_prediction = {"category": "NotARealCategory"}
    expected = {
        "category": "Authentication",
        "severity": "High",
        "priority": "P1",
        "environment": "Production / Web",
        "issue": "Users cannot sign in with valid credentials.",
        "reproduction_available": True,
    }
    result = evaluate_prediction(invalid_prediction, expected)

    assert result["schema_compliance"] == 0.0
    assert result["category_accuracy"] == 0.0
    assert result["overall_classification_accuracy"] == 0.0


def test_dataset_aggregation_across_multiple_cases():
    dataset = load_eval_dataset(DATASET_PATH)
    predictions = [
        _make_prediction(
            category=dataset[0]["expected"]["category"],
            severity=dataset[0]["expected"]["severity"],
            priority=dataset[0]["expected"]["priority"],
            reproduction_available=dataset[0]["expected"]["reproduction_available"],
        ),
        _make_prediction(
            category="UI",
            severity=dataset[1]["expected"]["severity"],
            priority=dataset[1]["expected"]["priority"],
            reproduction_available=dataset[1]["expected"]["reproduction_available"],
        ),
    ]
    aggregated = evaluate_dataset(predictions, dataset[:2])

    assert aggregated["schema_compliance"] == 1.0
    assert aggregated["category_accuracy"] == 0.5
    assert aggregated["severity_accuracy"] == 1.0
    assert aggregated["priority_accuracy"] == 1.0
    assert aggregated["reproduction_accuracy"] == 1.0
    assert aggregated["overall_classification_accuracy"] == 0.875


def test_failure_category_counting():
    counted = count_failures(["INVALID_SCHEMA", "LOW_CONFIDENCE", "INVALID_SCHEMA", "PROVIDER_ERROR"])

    assert counted["INVALID_SCHEMA"] == 2
    assert counted["LOW_CONFIDENCE"] == 1
    assert counted["PROVIDER_ERROR"] == 1
    assert sum(counted.values()) == 4
    assert set(counted) == set(FAILURE_CATEGORIES)


def test_human_review_routing_accuracy_when_explicit_expected_review_is_supplied():
    expected = {
        "category": "Authentication",
        "severity": "High",
        "priority": "P1",
        "environment": "Production / Web",
        "issue": "Users cannot sign in with valid credentials.",
        "reproduction_available": True,
    }
    prediction = _make_prediction(requires_human_review=False)
    result = evaluate_prediction(prediction, expected, expected_human_review=False)
    assert result["human_review_routing_accuracy"] == 1.0

    prediction = _make_prediction(requires_human_review=True)
    result = evaluate_prediction(prediction, expected, expected_human_review=False)
    assert result["human_review_routing_accuracy"] == 0.0


def test_human_review_routing_accuracy_is_none_without_explicit_review_value():
    expected = {
        "category": "Authentication",
        "severity": "High",
        "priority": "P1",
        "environment": "Production / Web",
        "issue": "Users cannot sign in with valid credentials.",
        "reproduction_available": True,
    }
    prediction = _make_prediction()
    result = evaluate_prediction(prediction, expected)
    assert result["human_review_routing_accuracy"] is None


def test_evaluator_does_not_require_dataset_confidence_or_review_values():
    dataset_entry = {
        "id": "BUG-999",
        "input": "Test input only",
        "expected": {
            "category": "Authentication",
            "severity": "High",
            "priority": "P1",
            "environment": "Production / Web",
            "issue": "Login fails with valid credentials.",
            "reproduction_available": True,
        },
    }
    prediction = _make_prediction()
    result = evaluate_prediction(prediction, dataset_entry["expected"])

    assert result["schema_compliance"] == 1.0
    assert result["category_accuracy"] == 1.0
    assert result["severity_accuracy"] == 1.0
    assert result["priority_accuracy"] == 1.0
    assert result["reproduction_accuracy"] == 1.0
