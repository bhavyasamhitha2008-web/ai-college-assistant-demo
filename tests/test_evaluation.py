import json
from collections import Counter

import pytest

from app.evaluation import (
    DEFAULT_DATASET,
    load_dataset,
    run_evaluation,
)


def test_dataset_includes_required_evaluation_categories():
    cases = load_dataset()
    counts = Counter(case["category"] for case in cases)

    assert counts["normal_policy"] >= 5
    assert counts["missing_policy"] >= 3
    assert counts["attendance"] >= 3
    assert counts["authorization_security"] >= 3
    assert counts["prompt_injection"] >= 3
    assert counts["paraphrased_policy"] >= 3


def test_evaluation_runner_passes_offline_dataset():
    report = run_evaluation()

    assert report["passed"] is True
    assert report["summary"]["passed"] == report["summary"]["total_cases"]
    assert report["summary"]["live_provider_calls"] == 0
    assert report["summary"]["estimated_provider_cost_usd"] == 0.0
    assert all(case["passed"] for case in report["cases"])


def test_evaluation_runner_reports_failed_expectations(tmp_path):
    cases = load_dataset()
    cases[0]["expected_source"] = "wrong-source.md"
    dataset_path = tmp_path / "bad-evaluation.json"
    dataset_path.write_text(json.dumps(cases), encoding="utf-8")

    report = run_evaluation(dataset_path)

    assert report["passed"] is False
    failed_case = next(case for case in report["cases"] if case["id"] == cases[0]["id"])
    assert failed_case["passed"] is False
    assert failed_case["criteria"]["groundedness"] is False


def test_loader_rejects_duplicate_case_ids(tmp_path):
    dataset_path = tmp_path / "duplicate-cases.json"
    dataset_path.write_text(
        json.dumps([{"id": "same"}, {"id": "same"}]), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="unique"):
        load_dataset(dataset_path)


def test_default_dataset_is_json_file():
    assert DEFAULT_DATASET.name == "evaluation_cases.json"
