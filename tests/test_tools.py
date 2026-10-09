import sqlite3
from contextlib import closing

import pytest

from app.database import initialize_database
from app.tools import (
    ReadOnlyApplicationTools,
    TOOL_DESCRIPTIONS,
    TOOL_INPUT_SCHEMAS,
    ToolAuthorizationError,
    ToolInputError,
)


def make_tools(tmp_path, principal="synthetic-student-001"):
    database_path = tmp_path / "demo.sqlite3"
    initialize_database(database_path)
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    (policies_dir / "attendance_policy.md").write_text(
        "# Attendance\n\nContact the academic office to report an absence.",
        encoding="utf-8",
    )
    return (
        ReadOnlyApplicationTools(database_path, policies_dir, principal),
        database_path,
    )


def test_tool_input_schemas_are_explicit():
    assert set(TOOL_INPUT_SCHEMAS) == {
        "get_attendance",
        "get_courses",
        "search_policy",
    }
    assert set(TOOL_DESCRIPTIONS) == set(TOOL_INPUT_SCHEMAS)
    assert (
        TOOL_INPUT_SCHEMAS["get_attendance"]["properties"]["student_id"]["type"]
        == "string"
    )
    assert (
        TOOL_INPUT_SCHEMAS["search_policy"]["properties"]["question"]["type"]
        == "string"
    )


def test_get_attendance_returns_only_minimum_subject_data(tmp_path):
    tools, _ = make_tools(tmp_path)

    result = tools.get_attendance("synthetic-student-001")

    assert result["subjects"][0] == {
        "subject": "Database Systems",
        "course_code": "DB201",
        "attended_classes": 3,
        "total_classes": 4,
        "percentage": 75.0,
    }
    assert set(result) == {"subjects"}
    assert "student_id" not in result
    assert "display_name" not in str(result)
    assert "password" not in str(result).casefold()


def test_get_courses_returns_only_authorized_enrollments(tmp_path):
    tools, _ = make_tools(tmp_path)

    result = tools.get_courses("synthetic-student-001")

    assert result == {
        "courses": [
            {"code": "DB201", "title": "Database Systems"},
            {"code": "SE101", "title": "Software Engineering"},
        ]
    }
    assert "synthetic-student-002" not in str(result)


def test_student_tools_reject_other_students_in_application_code(tmp_path):
    tools, _ = make_tools(tmp_path)

    with pytest.raises(ToolAuthorizationError):
        tools.get_attendance("synthetic-student-002")
    with pytest.raises(ToolAuthorizationError):
        tools.get_courses("synthetic-student-002")


@pytest.mark.parametrize(
    "student_id",
    [
        "",
        "bad id",
        123,
    ],
)
def test_student_tool_validates_arguments(tmp_path, student_id):
    tools, _ = make_tools(tmp_path)

    with pytest.raises(ToolInputError):
        tools.get_attendance(student_id)
    with pytest.raises(ToolInputError):
        tools.get_courses(student_id)


def test_student_tools_require_an_authorized_principal(tmp_path):
    tools, _ = make_tools(tmp_path, principal=None)

    with pytest.raises(ToolAuthorizationError):
        tools.get_attendance("synthetic-student-001")
    with pytest.raises(ToolAuthorizationError):
        tools.get_courses("synthetic-student-001")


def test_student_tool_requires_its_schema_argument(tmp_path):
    tools, _ = make_tools(tmp_path)

    with pytest.raises(TypeError):
        tools.get_attendance()
    with pytest.raises(TypeError):
        tools.get_attendance("synthetic-student-001", include_all_students=True)


def test_search_policy_returns_passage_and_source_only(tmp_path):
    tools, _ = make_tools(tmp_path, principal=None)

    result = tools.search_policy("How do I report an absence?")

    assert result == {
        "found": True,
        "passage": "Contact the academic office to report an absence.",
        "source": "attendance_policy.md",
    }
    assert "student_id" not in result


def test_search_policy_rejects_invalid_or_extra_input(tmp_path):
    tools, _ = make_tools(tmp_path)

    with pytest.raises(ToolInputError):
        tools.search_policy("  ")
    with pytest.raises(ToolInputError):
        tools.search_policy("x" * 501)
    with pytest.raises(TypeError):
        tools.search_policy()
    with pytest.raises(TypeError):
        tools.search_policy("attendance", student_id="unrelated")


def test_search_policy_returns_no_match_without_unrelated_data(tmp_path):
    tools, _ = make_tools(tmp_path, principal=None)

    result = tools.search_policy("How are scholarships awarded?")

    assert result == {
        "found": False,
        "passage": None,
        "source": None,
    }


def test_tools_do_not_modify_database(tmp_path):
    tools, database_path = make_tools(tmp_path)
    tools.get_attendance("synthetic-student-001")
    tools.get_courses("synthetic-student-001")

    with closing(sqlite3.connect(database_path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM attendance").fetchone()[0] == 11
        assert connection.execute("SELECT COUNT(*) FROM enrollments").fetchone()[0] == 3
