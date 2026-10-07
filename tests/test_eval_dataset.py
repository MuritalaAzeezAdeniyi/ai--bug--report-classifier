import json
from pathlib import Path

DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "eval_dataset.json"

VALID_CATEGORIES = {
    "Authentication",
    "Authorization",
    "API",
    "UI",
    "Database",
    "Performance",
    "Security",
    "Validation",
    "Other",
}

VALID_SEVERITIES = {"Critical", "High", "Medium", "Low"}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}


def load_dataset():
    assert DATASET_PATH.exists(), "Dataset file does not exist"
    with DATASET_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_dataset_file_exists_and_is_valid_json():
    dataset = load_dataset()
    assert isinstance(dataset, list)


def test_dataset_has_exactly_thirty_cases():
    dataset = load_dataset()
    assert len(dataset) == 30


def test_ids_are_unique():
    dataset = load_dataset()
    ids = [case["id"] for case in dataset]
    assert len(ids) == len(set(ids))


def test_each_case_shape_is_exact():
    dataset = load_dataset()
    for case in dataset:
        assert set(case.keys()) == {"id", "input", "expected"}
        assert isinstance(case["id"], str) and case["id"]
        assert isinstance(case["input"], str) and case["input"].strip()
        assert set(case["expected"].keys()) == {
            "category",
            "severity",
            "priority",
            "environment",
            "issue",
            "reproduction_available",
        }


def test_expected_fields_are_valid():
    dataset = load_dataset()
    for case in dataset:
        expected = case["expected"]
        assert expected["category"] in VALID_CATEGORIES
        assert expected["severity"] in VALID_SEVERITIES
        assert expected["priority"] in VALID_PRIORITIES
        assert expected["environment"] is None or isinstance(expected["environment"], str)
        assert isinstance(expected["issue"], str) and expected["issue"].strip()
        assert type(expected["reproduction_available"]) is bool


def test_every_approved_category_appears_at_least_once():
    dataset = load_dataset()
    categories = {case["expected"]["category"] for case in dataset}
    assert categories >= VALID_CATEGORIES


def test_every_severity_level_appears():
    dataset = load_dataset()
    severities = {case["expected"]["severity"] for case in dataset}
    assert severities == VALID_SEVERITIES


def test_every_priority_level_appears():
    dataset = load_dataset()
    priorities = {case["expected"]["priority"] for case in dataset}
    assert priorities == VALID_PRIORITIES


def test_both_reproduction_values_appear():
    dataset = load_dataset()
    reproduction_true = sum(
        1 for case in dataset if case["expected"]["reproduction_available"] is True
    )
    reproduction_false = sum(
        1 for case in dataset if case["expected"]["reproduction_available"] is False
    )
    assert reproduction_true > 0
    assert reproduction_false > 0


def test_some_cases_have_null_environment():
    dataset = load_dataset()
    null_environment_count = sum(
        1 for case in dataset if case["expected"]["environment"] is None
    )
    assert null_environment_count > 0
