from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

from pydantic import ValidationError

from app.schemas import BugReport

FAILURE_CATEGORIES = (
    "INVALID_SCHEMA",
    "LOW_CONFIDENCE",
    "AMBIGUOUS_REPORT",
    "MISSING_INFORMATION",
    "LLM_TIMEOUT",
    "RATE_LIMITED",
    "PROVIDER_ERROR",
)

CLASSIFICATION_FIELDS = (
    "category",
    "severity",
    "priority",
    "reproduction_available",
)

DEFAULT_DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "eval_dataset.json"


def load_eval_dataset(path: str | Path = DEFAULT_DATASET_PATH) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        dataset = json.load(handle)
    if not isinstance(dataset, list):
        raise ValueError("Evaluation dataset must be a list of records.")
    return dataset


def _coerce_prediction(prediction: BugReport | dict[str, Any] | Any) -> dict[str, Any] | None:
    if prediction is None:
        return None
    if isinstance(prediction, BugReport):
        return prediction.model_dump(mode="json")
    if isinstance(prediction, dict):
        return prediction
    return None


def _validate_prediction(prediction: BugReport | dict[str, Any] | Any) -> bool:
    normalized = _coerce_prediction(prediction)
    if normalized is None:
        return False
    try:
        BugReport.model_validate(normalized)
    except ValidationError:
        return False
    return True


def evaluate_prediction(
    prediction: BugReport | dict[str, Any] | Any,
    expected: dict[str, Any],
    expected_human_review: bool | None = None,
) -> dict[str, Any]:
    normalized_prediction = _coerce_prediction(prediction)
    schema_valid = _validate_prediction(prediction)

    metrics: dict[str, Any] = {
        "schema_compliance": 1.0 if schema_valid else 0.0,
        "category_accuracy": 0.0,
        "severity_accuracy": 0.0,
        "priority_accuracy": 0.0,
        "reproduction_accuracy": 0.0,
        "overall_classification_accuracy": 0.0,
        "human_review_routing_accuracy": None,
    }

    if not schema_valid or normalized_prediction is None:
        return metrics

    metrics["category_accuracy"] = 1.0 if normalized_prediction.get("category") == expected.get("category") else 0.0
    metrics["severity_accuracy"] = 1.0 if normalized_prediction.get("severity") == expected.get("severity") else 0.0
    metrics["priority_accuracy"] = 1.0 if normalized_prediction.get("priority") == expected.get("priority") else 0.0
    metrics["reproduction_accuracy"] = (
        1.0 if normalized_prediction.get("reproduction_available") == expected.get("reproduction_available") else 0.0
    )

    matches = 0
    for field in CLASSIFICATION_FIELDS:
        if normalized_prediction.get(field) == expected.get(field):
            matches += 1
    metrics["overall_classification_accuracy"] = matches / len(CLASSIFICATION_FIELDS)

    if expected_human_review is not None:
        predicted_review = normalized_prediction.get("requires_human_review")
        metrics["human_review_routing_accuracy"] = 1.0 if predicted_review == expected_human_review else 0.0

    return metrics


def evaluate_dataset(
    predictions: Sequence[BugReport | dict[str, Any] | Any],
    dataset: Sequence[dict[str, Any]] | None = None,
    expected_review_map: dict[str, bool] | None = None,
) -> dict[str, Any]:
    dataset_records = list(dataset) if dataset is not None else load_eval_dataset()
    if len(predictions) != len(dataset_records):
        raise ValueError(
            "Prediction count must match dataset length. "
            f"Got {len(predictions)} predictions and {len(dataset_records)} dataset rows."
        )

    expected_review_map = expected_review_map or {}
    case_results = []
    for index, record in enumerate(dataset_records):
        expected = record.get("expected", record)
        case_id = record.get("id")
        expected_review = expected_review_map.get(case_id)
        case_results.append(
            evaluate_prediction(predictions[index], expected, expected_human_review=expected_review)
        )

    aggregated = {
        "schema_compliance": _average([result["schema_compliance"] for result in case_results]),
        "category_accuracy": _average([result["category_accuracy"] for result in case_results]),
        "severity_accuracy": _average([result["severity_accuracy"] for result in case_results]),
        "priority_accuracy": _average([result["priority_accuracy"] for result in case_results]),
        "reproduction_accuracy": _average([result["reproduction_accuracy"] for result in case_results]),
        "overall_classification_accuracy": _average(
            [result["overall_classification_accuracy"] for result in case_results]
        ),
        "human_review_routing_accuracy": _average(
            [result["human_review_routing_accuracy"] for result in case_results if result["human_review_routing_accuracy"] is not None]
        ) if any(result["human_review_routing_accuracy"] is not None for result in case_results) else None,
        "case_results": case_results,
    }
    return aggregated


def _average(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def count_failures(failure_names: Iterable[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for failure_name in failure_names:
        if failure_name in FAILURE_CATEGORIES:
            counts[failure_name] += 1
    return {category: counts.get(category, 0) for category in FAILURE_CATEGORIES}
