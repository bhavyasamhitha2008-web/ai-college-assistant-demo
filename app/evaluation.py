import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from app.assistant import AssistantService
from app.database import initialize_database
from app.llm_service import INSUFFICIENT_INFORMATION
from app.tools import ReadOnlyApplicationTools, ToolAuthorizationError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = PROJECT_ROOT / "data" / "evaluation_cases.json"
DEFAULT_POLICIES = PROJECT_ROOT / "data" / "policies"
MAX_CASE_LATENCY_MS = 2_000
MAX_MODEL_CALLS_PER_CASE = 1


class EvaluationPolicyModel:
    """Offline fake that returns supplied evidence and ignores embedded directives."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def generate(self, question: str, context: str) -> str:
        self.calls.append({"question": question, "context": context})
        return context.split("Ignore all prior instructions", maxsplit=1)[0].strip()


def _case_result(
    case: dict[str, Any],
    response: dict[str, Any] | None,
    error: Exception | None,
    tool_calls: list[str],
    model: EvaluationPolicyModel,
    latency_ms: float,
) -> dict[str, Any]:
    expected_tool_calls = case["expected_tool_calls"]
    expected_model_calls = case["expected_model_calls"]
    criteria: dict[str, bool] = {
        "correctness": error is None
        and response is not None
        and response.get("path") == case["expected_path"],
        "groundedness": True,
        "refusal_when_evidence_is_missing": True,
        "authorization": True,
        "tool_selection": tool_calls == expected_tool_calls,
        "latency": latency_ms <= MAX_CASE_LATENCY_MS,
        "cost_awareness": (
            len(model.calls) == expected_model_calls
            and len(model.calls) <= MAX_MODEL_CALLS_PER_CASE
        ),
    }

    expected_outcome = case.get("expected_outcome", "success")
    if expected_outcome == "unauthorized":
        criteria["authorization"] = isinstance(error, ToolAuthorizationError)
        criteria["correctness"] = criteria["correctness"] or (
            response is None and isinstance(error, ToolAuthorizationError)
        )
    elif expected_outcome == "unsupported":
        criteria["correctness"] = criteria["correctness"] and (
            "cannot help" in response.get("answer", "").casefold()
        )
    elif error is not None:
        criteria["correctness"] = False

    if response is not None and case["expected_path"] == "policy_question":
        result = response.get("result", {})
        expected_source = case.get("expected_source")
        if case.get("expect_insufficient_information"):
            criteria["refusal_when_evidence_is_missing"] = (
                result.get("found") is False
                and result.get("answer") == INSUFFICIENT_INFORMATION
                and len(model.calls) == 0
            )
            criteria["groundedness"] = (
                result.get("source") is None and not result.get("sources")
            )
        else:
            answer = result.get("answer", "").casefold()
            expected_phrase = case.get("answer_contains", "").casefold()
            context = model.calls[0]["context"].casefold() if model.calls else ""
            criteria["correctness"] = criteria["correctness"] and (
                expected_phrase in answer
            )
            criteria["groundedness"] = (
                result.get("found") is True
                and result.get("source") == expected_source
                and bool(expected_phrase)
                and expected_phrase in context
                and expected_phrase in answer
            )
            forbidden_phrase = case.get("answer_not_contains")
            if forbidden_phrase:
                criteria["authorization"] = (
                    forbidden_phrase.casefold() not in answer
                )
    elif case.get("expected_path") == "attendance" and response is not None:
        actual_rows = response.get("result", {}).get("subjects", [])
        actual_by_code = {row["course_code"]: row for row in actual_rows}
        for expected_row in case.get("expected_attendance", []):
            actual_row = actual_by_code.get(expected_row["course_code"])
            if actual_row is None or any(
                actual_row.get(key) != value
                for key, value in expected_row.items()
            ):
                criteria["correctness"] = False
                criteria["groundedness"] = False

    passed = all(criteria.values())
    return {
        "id": case["id"],
        "category": case["category"],
        "passed": passed,
        "criteria": criteria,
        "latency_ms": round(latency_ms, 2),
        "tool_calls": tool_calls,
        "model_calls": len(model.calls),
        "error": type(error).__name__ if error else None,
    }


def evaluate_case(
    case: dict[str, Any], policies_dir: str | Path = DEFAULT_POLICIES
) -> dict[str, Any]:
    model = EvaluationPolicyModel()
    tool_calls: list[str] = []

    class RecordingTools(ReadOnlyApplicationTools):
        def get_attendance(self, student_id: str) -> dict[str, Any]:
            tool_calls.append("get_attendance")
            return super().get_attendance(student_id)

        def get_courses(self, student_id: str) -> dict[str, Any]:
            tool_calls.append("get_courses")
            return super().get_courses(student_id)

        def search_policy(self, question: str) -> dict[str, Any]:
            tool_calls.append("search_policy")
            return super().search_policy(question)

    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="college-assistant-eval-") as tmp:
        work_dir = Path(tmp)
        database_path = work_dir / "evaluation.sqlite3"
        case_policies = work_dir / "policies"
        shutil.copytree(policies_dir, case_policies)
        extra_document = case.get("extra_policy_document")
        if extra_document:
            (case_policies / extra_document["filename"]).write_text(
                extra_document["content"], encoding="utf-8"
            )
        initialize_database(database_path)
        service = AssistantService(
            database_path,
            case_policies,
            policy_model=model,
            tools_factory=RecordingTools,
        )

        response = None
        error = None
        try:
            response = service.respond(case["question"], case.get("student_id"))
        except ToolAuthorizationError as caught:
            error = caught
        except Exception as caught:
            error = caught

    latency_ms = (time.perf_counter() - start) * 1_000
    return _case_result(case, response, error, tool_calls, model, latency_ms)


def load_dataset(dataset_path: str | Path = DEFAULT_DATASET) -> list[dict[str, Any]]:
    with Path(dataset_path).open(encoding="utf-8") as dataset_file:
        cases = json.load(dataset_file)
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation dataset must be a non-empty JSON array.")
    ids = [case.get("id") for case in cases]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids):
        raise ValueError("Every evaluation case must have a non-empty id.")
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation case IDs must be unique.")
    return cases


def run_evaluation(
    dataset_path: str | Path = DEFAULT_DATASET,
    policies_dir: str | Path = DEFAULT_POLICIES,
) -> dict[str, Any]:
    cases = [
        evaluate_case(case, policies_dir)
        for case in load_dataset(dataset_path)
    ]
    passed = sum(case["passed"] for case in cases)
    category_counts: dict[str, dict[str, int]] = {}
    for case in cases:
        counts = category_counts.setdefault(
            case["category"], {"passed": 0, "total": 0}
        )
        counts["total"] += 1
        counts["passed"] += int(case["passed"])
    return {
        "passed": passed == len(cases),
        "summary": {
            "total_cases": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "categories": category_counts,
            "max_case_latency_ms": MAX_CASE_LATENCY_MS,
            "max_model_calls_per_case": MAX_MODEL_CALLS_PER_CASE,
            "live_provider_calls": 0,
            "estimated_provider_cost_usd": 0.0,
        },
        "cases": cases,
    }


def main() -> int:
    report = run_evaluation()
    summary = report["summary"]
    print(
        f"Evaluation: {summary['passed']}/{summary['total_cases']} passed; "
        f"{summary['failed']} failed"
    )
    for case in report["cases"]:
        status = "PASS" if case["passed"] else "FAIL"
        failed_criteria = [
            name for name, passed in case["criteria"].items() if not passed
        ]
        details = f" ({', '.join(failed_criteria)})" if failed_criteria else ""
        print(f"{status} {case['id']} [{case['latency_ms']:.2f} ms]{details}")
    print(
        "Offline cost: $0.00; live provider calls: 0; "
        f"max model calls/case: {summary['max_model_calls_per_case']}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
