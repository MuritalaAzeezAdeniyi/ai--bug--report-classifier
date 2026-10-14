from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from app.bug_service import (
    BugReportClassifier,
    ClientFailureError,
    EmptyBugReportError,
    InvalidStructuredOutputError,
)
from app.schemas import BugReport
from scripts.run_evaluation import build_classifier_from_env, load_runner_environment


def _configure_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Classify one unstructured bug report and print its validated JSON result."
    )
    parser.add_argument(
        "report",
        nargs="?",
        help="Bug report text. Use either this argument or --file.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Read the bug report from a UTF-8 text file instead of a positional argument.",
    )
    return parser


def _read_report(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    if args.file is not None and args.report is not None:
        parser.error("provide the report as a positional argument or with --file, not both")
    if args.file is None and args.report is None:
        parser.error("a report argument or --file is required")

    if args.file is not None:
        try:
            report = args.file.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise ValueError("Unable to read the report file as UTF-8 text.") from None
    else:
        report = args.report

    if not isinstance(report, str) or not report.strip():
        raise ValueError("The bug report must not be empty or whitespace-only.")
    return report


def _safe_classification_error(exc: Exception) -> str:
    if isinstance(exc, EmptyBugReportError):
        return "The bug report must not be empty or whitespace-only."
    if isinstance(exc, InvalidStructuredOutputError):
        return "Classification failed because the model response was invalid."
    if isinstance(exc, ClientFailureError):
        return "Classification request failed. Check the configured provider and try again."
    return "Classification could not be completed. Check the input and provider configuration."


def main(argv: Sequence[str] | None = None) -> int:
    parser = _configure_parser()
    args = parser.parse_args(argv)

    try:
        report = _read_report(args, parser)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        environment = load_runner_environment()
        classifier: BugReportClassifier = build_classifier_from_env(environment)
        result: BugReport = classifier.classify(report)
        serialized_result = result.model_dump_json(indent=2)
    except Exception as exc:
        print(f"Error: {_safe_classification_error(exc)}", file=sys.stderr)
        return 1

    print(serialized_result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
