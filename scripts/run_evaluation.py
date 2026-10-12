from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

from dotenv import load_dotenv

from app.bug_service import (
    BugReportClassifier,
    ClientFailureError,
    ClassificationServiceError,
    InvalidStructuredOutputError,
)
from app.evaluator import FAILURE_CATEGORIES, FailureCategory, count_failures, evaluate_prediction
from app.llm_client import LLMClient, LLMClientConfig, MissingConfigurationError
from app.schemas import BugReport

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPOSITORY_ROOT / ".env"
DEFAULT_DATASET_PATH = REPOSITORY_ROOT / "data" / "eval_dataset.json"
DEFAULT_OUTPUT_PATH = REPOSITORY_ROOT / "data" / "evaluation_results.json"


def validate_dataset_records(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(records, list) or not records:
        raise ValueError("Evaluation dataset must be a non-empty list of records.")

    clean_records: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Dataset record at index {index} is not a JSON object.")

        missing_required = [field for field in ("id", "input", "expected") if field not in record]
        if missing_required:
            raise ValueError(f"Dataset record at index {index} is missing required fields: {missing_required}.")

        case_id = record["id"]
        user_input = record["input"]
        expected = record["expected"]
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"Dataset record at index {index} has an invalid 'id'.")
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError(f"Dataset record '{case_id}' has an empty or invalid 'input'.")
        if not isinstance(expected, dict):
            raise ValueError(f"Dataset record '{case_id}' has a non-object 'expected' value.")

        required_expected = ("category", "severity", "priority", "issue", "reproduction_available")
        missing_expected = [field for field in required_expected if field not in expected]
        if missing_expected:
            raise ValueError(
                f"Dataset record '{case_id}' is missing expected fields: {missing_expected}."
            )

        if "environment" not in expected:
            expected["environment"] = None

        clean_records.append(record)

    return clean_records


def _map_exception_to_failure(exc: BaseException) -> FailureCategory:
    if isinstance(exc, InvalidStructuredOutputError):
        return FailureCategory.INVALID_SCHEMA
    if isinstance(exc, ClassificationServiceError):
        category = getattr(exc, "category", None)
        if isinstance(category, FailureCategory):
            return category
    if isinstance(exc, ClientFailureError):
        category = getattr(exc, "category", None)
        if isinstance(category, FailureCategory):
            return category
    return FailureCategory.PROVIDER_ERROR


def _redact_sensitive_text(value: str | None) -> str | None:
    if value is None:
        return None
    redacted = value.replace("\r", " ").replace("\n", " ")
    for key_name in ("api_key", "apikey", "authorization", "token", "secret", "password"):
        redacted = re.sub(
            rf"(?i)(?:\b{key_name}\b\s*[:=]\s*)[^\s,;\]]+",
            f"{key_name}=[REDACTED]",
            redacted,
        )
    return redacted


def _safe_prediction_preview(prediction: object) -> dict[str, Any] | None:
    if isinstance(prediction, BugReport):
        return prediction.model_dump(mode="json")
    if isinstance(prediction, dict):
        return prediction
    if prediction is None:
        return None
    return {"type": prediction.__class__.__name__}


def evaluate_dataset_cases(
    dataset: Sequence[dict[str, Any]],
    classifier: BugReportClassifier,
    *,
    output_path: str | Path | None = None,
    expected_review_map: dict[str, bool] | None = None,
) -> dict[str, Any]:
    records = validate_dataset_records(list(dataset))
    output_target = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH

    successful_predictions: list[dict[str, Any]] = []
    case_results: list[dict[str, Any]] = []
    failure_counts = count_failures([])
    successful_classifications = 0
    failed_cases = 0

    for dataset_index, record in enumerate(records):
        case_id = record["id"]
        expected = record["expected"]
        expected_human_review = record.get("expected_human_review")
        if expected_review_map is not None:
            expected_human_review = expected_review_map.get(case_id, expected_human_review)

        try:
            prediction = classifier.classify(record["input"])
            metrics = evaluate_prediction(prediction, expected, expected_human_review=expected_human_review)
            successful_predictions.append({
                "id": case_id,
                "prediction": prediction,
                "metrics": metrics,
            })
            successful_classifications += 1
            status = "success"
            failure_category = None
            error_message = None
            error_diagnostics = None
        except Exception as exc:  # pragma: no cover - exercised via tests with mocked failures
            failed_cases += 1
            failure_category = _map_exception_to_failure(exc)
            failure_counts[failure_category.value] += 1
            status = "failure"
            error_message = _redact_sensitive_text(str(exc))
            error_diagnostics = getattr(exc, "diagnostics", None)
            metrics = {
                "schema_compliance": 0.0,
                "category_accuracy": 0.0,
                "severity_accuracy": 0.0,
                "priority_accuracy": 0.0,
                "reproduction_accuracy": 0.0,
                "overall_classification_accuracy": 0.0,
                "human_review_routing_accuracy": None,
            }

        case_result = {
            "id": case_id,
            "dataset_index": dataset_index,
            "status": status,
            "failure_category": failure_category.value if failure_category is not None else None,
            "error_message": error_message,
            "error_diagnostics": error_diagnostics,
            "metrics": metrics,
        }
        case_results.append(case_result)

    if successful_predictions:
        schema_compliance_values = [result["metrics"]["schema_compliance"] for result in successful_predictions]
        category_accuracy_values = [result["metrics"]["category_accuracy"] for result in successful_predictions]
        severity_accuracy_values = [result["metrics"]["severity_accuracy"] for result in successful_predictions]
        priority_accuracy_values = [result["metrics"]["priority_accuracy"] for result in successful_predictions]
        reproduction_accuracy_values = [result["metrics"]["reproduction_accuracy"] for result in successful_predictions]
        overall_accuracy_values = [result["metrics"]["overall_classification_accuracy"] for result in successful_predictions]
        review_accuracy_values = [
            result["metrics"]["human_review_routing_accuracy"]
            for result in successful_predictions
            if result["metrics"]["human_review_routing_accuracy"] is not None
        ]
        human_review_rate = sum(
            1 for result in successful_predictions if _safe_prediction_preview(result["prediction"]).get("requires_human_review")
        ) / len(successful_predictions)
    else:
        schema_compliance_values = []
        category_accuracy_values = []
        severity_accuracy_values = []
        priority_accuracy_values = []
        reproduction_accuracy_values = []
        overall_accuracy_values = []
        review_accuracy_values = []
        human_review_rate = 0.0

    def _average(values: Iterable[float]) -> float:
        values = list(values)
        if not values:
            return 0.0
        return sum(values) / len(values)

    summary: dict[str, Any] = {
        "dataset_case_count": len(records),
        "attempted_cases": len(records),
        "successful_classifications": successful_classifications,
        "failed_cases": failed_cases,
        "schema_compliance_rate": _average(schema_compliance_values),
        "category_accuracy": _average(category_accuracy_values),
        "severity_accuracy": _average(severity_accuracy_values),
        "priority_accuracy": _average(priority_accuracy_values),
        "reproduction_accuracy": _average(reproduction_accuracy_values),
        "overall_classification_accuracy": _average(overall_accuracy_values),
        "human_review_routing_rate": human_review_rate,
        "human_review_routing_accuracy": _average(review_accuracy_values) if review_accuracy_values else None,
        "failure_counts": failure_counts,
        "case_results": [
            {
                "id": case["id"],
                "dataset_index": case["dataset_index"],
                "status": case["status"],
                "failure_category": case["failure_category"],
                "error_message": case["error_message"],
                "error_diagnostics": case["error_diagnostics"],
                "metrics": case["metrics"],
            }
            for case in case_results
        ],
        "evaluation_complete": failed_cases == 0 and successful_classifications == len(records),
        "incomplete": failed_cases > 0 or successful_classifications != len(records),
        "output_path": str(output_target),
    }

    if output_target is not None:
        output_target.parent.mkdir(parents=True, exist_ok=True)
        output_target.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    return summary


def build_classifier_from_env(env: dict[str, str] | None = None) -> BugReportClassifier:
    config = LLMClientConfig.from_env(env)
    client = LLMClient(config)
    return BugReportClassifier(client)


def load_runner_environment() -> dict[str, str]:
    """Load repository-local dotenv values without overriding the process environment."""
    load_dotenv(dotenv_path=ENV_FILE, override=False)
    return dict(os.environ)


def _configure_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the bug report classifier against the evaluation dataset.")
    parser.add_argument("--dataset", type=str, default=str(DEFAULT_DATASET_PATH), help="Path to the evaluation dataset JSON file.")
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path where the machine-readable evaluation JSON should be written.",
    )
    parser.add_argument("--provider", type=str, default=None, help="Optional override for LLM_PROVIDER.")
    parser.add_argument("--model", type=str, default=None, help="Optional override for LLM_MODEL.")
    parser.add_argument("--api-key", type=str, default=None, help="Optional override for LLM_API_KEY.")
    parser.add_argument("--dry-run", action="store_true", help="Print the evaluation plan without executing a live LLM run.")
    return parser


def main() -> int:
    args = _configure_parser().parse_args()

    env = load_runner_environment()
    if args.provider is not None:
        env["LLM_PROVIDER"] = args.provider
    if args.model is not None:
        env["LLM_MODEL"] = args.model
    if args.api_key is not None:
        env["LLM_API_KEY"] = args.api_key

    dataset_path = Path(args.dataset)
    output_path = Path(args.output)

    try:
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Dataset not found: {dataset_path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Dataset is not valid JSON: {dataset_path}: {exc}") from exc

    try:
        validate_dataset_records(dataset)
    except ValueError as exc:
        raise SystemExit(f"Invalid evaluation dataset: {exc}") from exc

    if args.dry_run:
        print(f"Dataset: {dataset_path}")
        print(f"Cases: {len(dataset)}")
        print("Dry run enabled; no live LLM classification was executed.")
        return 0

    try:
        classifier = build_classifier_from_env(env)
    except MissingConfigurationError as exc:
        raise SystemExit(f"LLM credentials are not configured for a live evaluation run: {exc}") from exc
    except Exception as exc:  # pragma: no cover - environment-dependent path
        raise SystemExit(f"Unable to initialize the classifier for a live evaluation run: {exc}") from exc

    summary = evaluate_dataset_cases(dataset, classifier, output_path=output_path)
    print(json.dumps({
        "dataset_case_count": summary["dataset_case_count"],
        "successful_classifications": summary["successful_classifications"],
        "failed_cases": summary["failed_cases"],
        "schema_compliance_rate": summary["schema_compliance_rate"],
        "overall_classification_accuracy": summary["overall_classification_accuracy"],
        "evaluation_complete": summary["evaluation_complete"],
        "incomplete": summary["incomplete"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
