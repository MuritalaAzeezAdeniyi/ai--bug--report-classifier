from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.evaluator import FailureCategory
from app.schemas import BugReport
from app.bug_service import ClientFailureError
import scripts.run_evaluation as evaluation_runner
from scripts.run_evaluation import evaluate_dataset_cases, validate_dataset_records


class FakeClassifier:
    def __init__(self, responses=None, error_map=None):
        self.responses = responses or {}
        self.error_map = error_map or {}
        self.calls = []

    def classify(self, report: str):
        self.calls.append(report)
        if report in self.error_map:
            raise self.error_map[report]
        if report not in self.responses:
            raise KeyError(f"No canned response for: {report}")
        return self.responses[report]


def dataset_for_metrics():
    return [
        {
            "id": "CASE-1",
            "input": "case one",
            "expected": {
                "category": "Authentication",
                "severity": "High",
                "priority": "P1",
                "environment": "Production / Web",
                "issue": "Users cannot sign in with valid credentials.",
                "reproduction_available": True,
            },
        },
        {
            "id": "CASE-2",
            "input": "case two",
            "expected": {
                "category": "Authorization",
                "severity": "Low",
                "priority": "P3",
                "environment": "Staging / Web",
                "issue": "Restricted access is denied for managers.",
                "reproduction_available": False,
            },
        },
    ]


def _valid_prediction(**overrides):
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


def test_run_dataset_evaluation_computes_metric_summary(tmp_path):
    dataset = dataset_for_metrics()
    classifier = FakeClassifier(
        {
            "case one": _valid_prediction(),
            "case two": _valid_prediction(category="UI", severity="Low", priority="P3", reproduction_available=False),
        }
    )

    result = evaluate_dataset_cases(dataset, classifier, output_path=tmp_path / "metrics.json")
    assert result["dataset_case_count"] == 2
    assert result["attempted_cases"] == 2
    assert result["successful_classifications"] == 2
    assert result["failed_cases"] == 0
    assert result["schema_compliance_rate"] == 1.0
    assert result["category_accuracy"] == 0.5
    assert result["severity_accuracy"] == 1.0
    assert result["priority_accuracy"] == 1.0
    assert result["reproduction_accuracy"] == 1.0
    assert result["overall_classification_accuracy"] == 0.875
    assert result["evaluation_complete"] is True
    assert result["incomplete"] is False


def test_run_dataset_evaluation_counts_failed_case_without_treating_it_as_correct(tmp_path):
    dataset = [
        {
            "id": "CASE-1",
            "input": "case one",
            "expected": {
                "category": "Authentication",
                "severity": "High",
                "priority": "P1",
                "environment": "Production / Web",
                "issue": "Users cannot sign in with valid credentials.",
                "reproduction_available": True,
            },
        },
        {
            "id": "CASE-2",
            "input": "case two",
            "expected": {
                "category": "Authorization",
                "severity": "Low",
                "priority": "P3",
                "environment": "Staging / Web",
                "issue": "Restricted access is denied for managers.",
                "reproduction_available": False,
            },
        },
    ]
    classifier = FakeClassifier(
        {"case one": _valid_prediction()},
        {"case two": RuntimeError("provider blew up")},
    )

    result = evaluate_dataset_cases(dataset, classifier, output_path=tmp_path / "failure.json")

    assert result["successful_classifications"] == 1
    assert result["failed_cases"] == 1
    assert result["failure_counts"][FailureCategory.PROVIDER_ERROR.value] == 1
    assert result["evaluation_complete"] is False
    assert result["incomplete"] is True
    assert result["case_results"][1]["status"] == "failure"
    assert result["case_results"][1]["failure_category"] == FailureCategory.PROVIDER_ERROR.value


def test_run_dataset_evaluation_serializes_safe_failure_diagnostics(tmp_path):
    dataset = dataset_for_metrics()[:1]
    failure = ClientFailureError(
        "Gemini request failed (cause=model_not_found; exception=SDKError; http_status=404; provider_code=MODEL_NOT_FOUND).",
        diagnostics={
            "provider_error_type": "SDKError",
            "http_status_code": 404,
            "provider_error_code": "MODEL_NOT_FOUND",
            "diagnostic_cause": "model_not_found",
        },
    )
    classifier = FakeClassifier(error_map={"case one": failure})
    output_path = tmp_path / "diagnostic-results.json"

    result = evaluate_dataset_cases(dataset, classifier, output_path=output_path)
    case_result = result["case_results"][0]

    assert case_result["error_diagnostics"]["diagnostic_cause"] == "model_not_found"
    assert case_result["error_diagnostics"]["http_status_code"] == 404
    assert json.loads(output_path.read_text(encoding="utf-8"))["case_results"][0]["error_diagnostics"] == case_result["error_diagnostics"]


def test_run_dataset_evaluation_tracks_dataset_ids_and_partial_results(tmp_path):
    dataset = [
        {
            "id": "CASE-100",
            "input": "ok",
            "expected": {
                "category": "Authentication",
                "severity": "High",
                "priority": "P1",
                "environment": "Production / Web",
                "issue": "Users cannot sign in with valid credentials.",
                "reproduction_available": True,
            },
        },
        {
            "id": "CASE-200",
            "input": "broken",
            "expected": {
                "category": "Authorization",
                "severity": "Low",
                "priority": "P3",
                "environment": "Staging / Web",
                "issue": "Restricted access is denied for managers.",
                "reproduction_available": False,
            },
        },
    ]
    classifier = FakeClassifier({"ok": _valid_prediction()})

    result = evaluate_dataset_cases(dataset, classifier, output_path=tmp_path / "case-association.json")

    assert [case["id"] for case in result["case_results"]] == ["CASE-100", "CASE-200"]
    assert result["case_results"][0]["status"] == "success"
    assert result["case_results"][1]["status"] == "failure"
    assert result["case_results"][1]["dataset_index"] == 1


def test_validate_dataset_records_rejects_empty_or_malformed_input():
    with pytest.raises(ValueError):
        validate_dataset_records([])

    with pytest.raises(ValueError):
        validate_dataset_records([
            {"id": "CASE-1", "input": "ok"},
        ])

    with pytest.raises(ValueError):
        validate_dataset_records([
            {"id": "CASE-1", "input": "ok", "expected": {"category": "Authentication"}},
        ])


def test_run_dataset_evaluation_writes_json_output_and_redacts_secrets(tmp_path):
    dataset = [
        {
            "id": "CASE-1",
            "input": "case one",
            "expected": {
                "category": "Authentication",
                "severity": "High",
                "priority": "P1",
                "environment": "Production / Web",
                "issue": "Users cannot sign in with valid credentials.",
                "reproduction_available": True,
            },
        }
    ]
    classifier = FakeClassifier({"case one": _valid_prediction()})
    output_path = tmp_path / "eval-output.json"

    result = evaluate_dataset_cases(dataset, classifier, output_path=output_path)

    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["dataset_case_count"] == 1
    assert payload["case_results"][0]["id"] == "CASE-1"
    assert "api_key" not in json.dumps(payload).lower()
    assert result["output_path"] == str(output_path)


def test_load_runner_environment_reads_repository_dotenv_without_overriding_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation_runner.os, "environ", {})
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "LLM_PROVIDER=gemini\nLLM_MODEL=dotenv-model\nLLM_API_KEY=test-only-key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(evaluation_runner, "ENV_FILE", dotenv_file)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    environment = evaluation_runner.load_runner_environment()

    assert environment["LLM_PROVIDER"] == "openai"
    assert environment["LLM_MODEL"] == "dotenv-model"
    assert environment["LLM_API_KEY"] == "test-only-key"
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)


def test_env_file_path_is_derived_from_runner_location():
    expected_root = Path(evaluation_runner.__file__).resolve().parent.parent

    assert evaluation_runner.REPOSITORY_ROOT == expected_root
    assert evaluation_runner.ENV_FILE == expected_root / ".env"


def test_cli_configuration_overrides_loaded_dotenv_values(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation_runner.os, "environ", {})
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "LLM_PROVIDER=gemini\nLLM_MODEL=dotenv-model\nLLM_API_KEY=test-only-key\n",
        encoding="utf-8",
    )
    dataset_file = tmp_path / "dataset.json"
    dataset_file.write_text(json.dumps(dataset_for_metrics()[:1]), encoding="utf-8")
    output_file = tmp_path / "output.json"
    monkeypatch.setattr(evaluation_runner, "ENV_FILE", dotenv_file)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_evaluation.py",
            "--dataset",
            str(dataset_file),
            "--output",
            str(output_file),
            "--provider",
            "openai",
            "--model",
            "cli-model",
        ],
    )
    captured_environment = {}

    def fake_build_classifier(env):
        captured_environment.update(env)
        return object()

    monkeypatch.setattr(evaluation_runner, "build_classifier_from_env", fake_build_classifier)
    monkeypatch.setattr(
        evaluation_runner,
        "evaluate_dataset_cases",
        lambda dataset, classifier, output_path: {
            "dataset_case_count": 1,
            "successful_classifications": 1,
            "failed_cases": 0,
            "schema_compliance_rate": 1.0,
            "overall_classification_accuracy": 1.0,
            "evaluation_complete": True,
            "incomplete": False,
        },
    )

    assert evaluation_runner.main() == 0
    assert captured_environment["LLM_PROVIDER"] == "openai"
    assert captured_environment["LLM_MODEL"] == "cli-model"
    assert captured_environment["LLM_API_KEY"] == "test-only-key"
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)


def test_test_run_does_not_modify_repository_default_results_file(tmp_path, monkeypatch):
    shared_results_path = evaluation_runner.DEFAULT_OUTPUT_PATH
    original_contents = shared_results_path.read_bytes() if shared_results_path.exists() else None
    test_output_path = tmp_path / "isolated-results.json"
    monkeypatch.setattr(evaluation_runner, "DEFAULT_OUTPUT_PATH", test_output_path)
    classifier = FakeClassifier({"case one": _valid_prediction()})

    result = evaluate_dataset_cases(dataset_for_metrics()[:1], classifier)

    assert test_output_path.is_file()
    assert result["output_path"] == str(test_output_path)
    current_contents = shared_results_path.read_bytes() if shared_results_path.exists() else None
    assert current_contents == original_contents
