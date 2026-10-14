from __future__ import annotations

import json

from app.bug_service import ClientFailureError
from app.schemas import BugReport
import scripts.classify_bug as classify_bug_cli


class FakeClassifier:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.received_report = None

    def classify(self, report: str) -> BugReport:
        self.received_report = report
        if self.error is not None:
            raise self.error
        return self.result


def valid_report() -> BugReport:
    return BugReport(
        category="Authentication",
        severity="High",
        priority="P1",
        environment="Android",
        issue="Sign-in remains loading after valid credentials are submitted.",
        reproduction_available=True,
        confidence=0.91,
        requires_human_review=False,
    )


def _mock_configuration(monkeypatch, classifier):
    monkeypatch.setattr(classify_bug_cli, "load_runner_environment", lambda: {"LLM_PROVIDER": "gemini"})
    monkeypatch.setattr(classify_bug_cli, "build_classifier_from_env", lambda env: classifier)


def test_cli_positional_report_prints_complete_validated_json(monkeypatch, capsys):
    raw_report = "Login keeps loading after I enter the correct password on Android"
    classifier = FakeClassifier(result=valid_report())
    _mock_configuration(monkeypatch, classifier)

    exit_code = classify_bug_cli.main([raw_report])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert classifier.received_report == raw_report
    assert payload == valid_report().model_dump(mode="json")
    assert set(payload) == set(BugReport.model_fields)


def test_cli_file_input_passes_file_contents_to_classifier(tmp_path, monkeypatch, capsys):
    raw_report = "The export button disappears after I open the dashboard."
    report_file = tmp_path / "bug-report.txt"
    report_file.write_text(raw_report, encoding="utf-8")
    classifier = FakeClassifier(result=valid_report())
    _mock_configuration(monkeypatch, classifier)

    exit_code = classify_bug_cli.main(["--file", str(report_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert classifier.received_report == raw_report
    assert json.loads(captured.out)["category"] == "Authentication"
    assert captured.err == ""


def test_cli_rejects_empty_positional_report_before_configuration(monkeypatch, capsys):
    def unexpected_configuration():
        raise AssertionError("configuration must not be loaded for empty input")

    monkeypatch.setattr(classify_bug_cli, "load_runner_environment", unexpected_configuration)

    exit_code = classify_bug_cli.main(["   "])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "empty or whitespace-only" in captured.err
    assert captured.out == ""


def test_cli_rejects_empty_file_input(tmp_path, monkeypatch, capsys):
    report_file = tmp_path / "empty-report.txt"
    report_file.write_text(" \n\t", encoding="utf-8")
    monkeypatch.setattr(
        classify_bug_cli,
        "load_runner_environment",
        lambda: (_ for _ in ()).throw(AssertionError("configuration must not be loaded")),
    )

    exit_code = classify_bug_cli.main(["--file", str(report_file)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "empty or whitespace-only" in captured.err
    assert captured.out == ""


def test_cli_classification_failure_is_safe_and_nonzero(monkeypatch, capsys):
    secret = "test-secret-value"
    classifier = FakeClassifier(
        error=ClientFailureError(f"provider failed api_key={secret} authorization=Bearer {secret}")
    )
    _mock_configuration(monkeypatch, classifier)

    exit_code = classify_bug_cli.main(["A messy report that cannot be classified"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Classification request failed" in captured.err
    assert secret not in captured.err
    assert "Traceback" not in captured.err
    assert "provider failed" not in captured.err


def test_cli_file_read_error_does_not_expose_exception_details(tmp_path, monkeypatch, capsys):
    report_file = tmp_path / "missing.txt"

    exit_code = classify_bug_cli.main(["--file", str(report_file)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Unable to read the report file" in captured.err
    assert str(report_file) not in captured.err
    assert captured.out == ""
