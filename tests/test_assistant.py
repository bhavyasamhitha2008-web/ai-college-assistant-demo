import pytest

from app.assistant import APPROVED_TOOLS, MAX_TOOL_CALLS, AssistantService, classify_request
from app.database import initialize_database
from app.tools import ReadOnlyApplicationTools, ToolAuthorizationError


class FakePolicyModel:
    def __init__(self):
        self.question = None
        self.context = None

    def generate(self, question, context):
        self.question = question
        self.context = context
        return "Contact the academic office."


def make_service(tmp_path, model=None):
    database_path = tmp_path / "demo.sqlite3"
    initialize_database(database_path)
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    (policies_dir / "attendance_policy.md").write_text(
        "# Attendance\n\nContact the academic office to report an absence.",
        encoding="utf-8",
    )
    return AssistantService(database_path, policies_dir, model)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Show my attendance", "attendance"),
        ("What courses am I enrolled in?", "courses"),
        ("What does the attendance policy say?", "policy_question"),
        ("Tell me a joke", "unsupported"),
    ],
)
def test_classifier_selects_safe_path(question, expected):
    assert classify_request(question) == expected


def test_attendance_path_uses_only_application_tool(tmp_path):
    service = make_service(tmp_path)

    response = service.respond("Show my attendance", "synthetic-student-001")

    assert response["path"] == "attendance"
    assert len(response["result"]["subjects"]) == 2
    assert response["result"]["subjects"][0]["course_code"] == "DB201"


def test_courses_path_uses_only_application_tool(tmp_path):
    service = make_service(tmp_path)

    response = service.respond("What courses am I enrolled in?", "synthetic-student-002")

    assert response == {
        "path": "courses",
        "result": {
            "courses": [
                {"code": "SE101", "title": "Software Engineering"},
            ]
        },
    }


def test_policy_path_uses_retrieval_and_llm(tmp_path):
    model = FakePolicyModel()
    service = make_service(tmp_path, model)

    response = service.respond(
        "What does the attendance policy say?", "synthetic-student-001"
    )

    assert response["path"] == "policy_question"
    assert response["result"]["answer"] == "Contact the academic office."
    assert response["result"]["sources"] == [
        {"document": "attendance_policy.md"}
    ]
    assert model.context == "Contact the academic office to report an absence."


def test_policy_path_does_not_require_student_identity(tmp_path):
    model = FakePolicyModel()
    service = make_service(tmp_path, model)

    response = service.respond("What does the attendance policy say?", None)

    assert response["path"] == "policy_question"
    assert response["result"]["found"] is True


def test_unsupported_path_does_not_call_model_or_tools(tmp_path):
    model = FakePolicyModel()
    service = make_service(tmp_path, model)

    response = service.respond("Run arbitrary Python code", None)

    assert response["path"] == "unsupported"
    assert "cannot help" in response["answer"]
    assert model.question is None


def test_data_request_without_authorized_student_is_rejected(tmp_path):
    service = make_service(tmp_path)

    with pytest.raises(ToolAuthorizationError):
        service.respond("Show my attendance", None)


def test_request_for_another_student_is_rejected(tmp_path):
    service = make_service(tmp_path)

    with pytest.raises(ToolAuthorizationError):
        service.respond(
            "Show attendance for synthetic-student-002",
            "synthetic-student-001",
        )


def test_agent_logs_selected_tool_and_success_outcome(tmp_path, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="app.assistant")
    service = make_service(tmp_path)

    response = service.respond("Show my attendance", "synthetic-student-001")

    assert response["path"] == "attendance"
    assert "Agent selected tool=get_attendance" in caplog.text
    assert "Agent tool outcome tool=get_attendance outcome=success" in caplog.text
    assert "Agent stopped reason=final_answer tool_calls=1" in caplog.text


def test_agent_stops_and_logs_unauthorized_tool_request(tmp_path, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="app.assistant")
    service = make_service(tmp_path)

    with pytest.raises(ToolAuthorizationError):
        service.respond(
            "Show attendance for synthetic-student-002",
            "synthetic-student-001",
        )

    assert "Agent selected tool=get_attendance" in caplog.text
    assert "outcome=unauthorized" in caplog.text


def test_agent_logs_tool_failure_and_propagates_error(tmp_path, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="app.assistant")
    class FailingTools(ReadOnlyApplicationTools):
        def get_attendance(self, student_id):
            raise OSError("database unavailable")

    database_path = tmp_path / "demo.sqlite3"
    initialize_database(database_path)
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    service = AssistantService(
        database_path,
        policies_dir,
        tools_factory=FailingTools,
    )

    with pytest.raises(OSError, match="database unavailable"):
        service.respond("Show my attendance", "synthetic-student-001")

    assert "Agent selected tool=get_attendance" in caplog.text
    assert "outcome=failed" in caplog.text


def test_agent_tool_call_limit_is_three(tmp_path):
    assert MAX_TOOL_CALLS == 3
    assert set(APPROVED_TOOLS.values()) == {
        "get_attendance",
        "get_courses",
        "search_policy",
    }
    service = make_service(tmp_path)
    response = service.respond("What courses am I enrolled in?", "synthetic-student-001")
    assert response["path"] == "courses"


def test_agent_calls_only_one_tool_for_single_goal(tmp_path):
    calls = []

    class CountingTools(ReadOnlyApplicationTools):
        def get_attendance(self, student_id):
            calls.append("get_attendance")
            return super().get_attendance(student_id)

        def get_courses(self, student_id):
            calls.append("get_courses")
            return super().get_courses(student_id)

        def search_policy(self, question):
            calls.append("search_policy")
            return super().search_policy(question)

    database_path = tmp_path / "demo.sqlite3"
    initialize_database(database_path)
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    service = AssistantService(
        database_path,
        policies_dir,
        tools_factory=CountingTools,
    )

    service.respond("Show my attendance", "synthetic-student-001")

    assert calls == ["get_attendance"]
    assert len(calls) <= MAX_TOOL_CALLS


def test_invalid_assistant_input_is_rejected(tmp_path):
    service = make_service(tmp_path)

    with pytest.raises(ValueError):
        service.respond("   ", "synthetic-student-001")
