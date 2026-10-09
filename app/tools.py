import re
from contextlib import closing
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, StrictStr, ValidationError

from app.attendance import (
    StudentNotFoundError,
    get_attendance_by_subject,
    get_student_courses,
)
from app.database import connect_database
from app.knowledge import retrieve_passage


STUDENT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


class StudentIdInput(BaseModel):
    student_id: StrictStr = Field(
        ...,
        min_length=1,
        max_length=80,
        description="Fictional student ID authorized for the current caller.",
    )

    class Config:
        extra = "forbid"


class PolicyQuestionInput(BaseModel):
    question: StrictStr = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Question to search in the college policy documents.",
    )

    class Config:
        extra = "forbid"


class ToolInputError(ValueError):
    """Raised when tool input does not match its input schema."""


class ToolAuthorizationError(PermissionError):
    """Raised when a student-data tool targets a different student."""


class ToolStudentNotFoundError(LookupError):
    """Raised when the authorized student ID does not exist."""


def _parse_input(model: type[BaseModel], value: Any) -> BaseModel:
    try:
        validator = getattr(model, "model_validate", None)
        if validator is not None:
            return validator(value)
        return model.parse_obj(value)
    except ValidationError as error:
        raise ToolInputError("Tool input does not match its schema.") from error


def _validate_student_id(value: Any) -> str:
    parsed = _parse_input(StudentIdInput, value)
    student_id = parsed.student_id
    if not STUDENT_ID_PATTERN.fullmatch(student_id):
        raise ToolInputError("Student ID contains unsupported characters.")
    return student_id


def _schema(model: type[BaseModel]) -> dict[str, Any]:
    schema_builder = getattr(model, "model_json_schema", None)
    if schema_builder is not None:
        return schema_builder()
    return model.schema()


TOOL_INPUT_SCHEMAS = {
    "get_attendance": _schema(StudentIdInput),
    "get_courses": _schema(StudentIdInput),
    "search_policy": _schema(PolicyQuestionInput),
}

TOOL_DESCRIPTIONS = {
    "get_attendance": "Read per-subject attendance for the authorized student.",
    "get_courses": "Read enrolled course codes and titles for the authorized student.",
    "search_policy": "Search fictional college policy documents for one passage.",
}


class ReadOnlyApplicationTools:
    """Read-only tools scoped to one application-authorized demo identity."""

    def __init__(
        self,
        database_path: str | Path,
        policy_documents_dir: str | Path,
        authorized_student_id: str | None,
    ):
        self._database_path = Path(database_path)
        self._policy_documents_dir = Path(policy_documents_dir)
        self._authorized_student_id = authorized_student_id

    def _authorize_student(self, student_id: str) -> None:
        if not self._authorized_student_id:
            raise ToolAuthorizationError("An authorized student identity is required.")
        if student_id != self._authorized_student_id:
            raise ToolAuthorizationError(
                "The requested student is not authorized for this caller."
            )

    def get_attendance(self, student_id: str) -> dict[str, Any]:
        """Return per-subject attendance for the authorized student only."""
        student_id = _validate_student_id({"student_id": student_id})
        self._authorize_student(student_id)
        with closing(connect_database(self._database_path)) as connection:
            try:
                subjects = get_attendance_by_subject(connection, student_id)
            except StudentNotFoundError as error:
                raise ToolStudentNotFoundError(
                    "The authorized student ID was not found."
                ) from error
        return {"subjects": subjects}

    def get_courses(self, student_id: str) -> dict[str, Any]:
        """Return course codes and titles for the authorized student only."""
        student_id = _validate_student_id({"student_id": student_id})
        self._authorize_student(student_id)
        with closing(connect_database(self._database_path)) as connection:
            try:
                courses = get_student_courses(connection, student_id)
            except StudentNotFoundError as error:
                raise ToolStudentNotFoundError(
                    "The authorized student ID was not found."
                ) from error
        return {"courses": courses}

    def search_policy(self, question: str) -> dict[str, Any]:
        """Return one retrieved policy passage and its filename, without a model."""
        parsed = _parse_input(PolicyQuestionInput, {"question": question})
        question = parsed.question.strip()
        if not question:
            raise ToolInputError("Policy question must not be blank.")
        result = retrieve_passage(question, self._policy_documents_dir)
        return {
            "found": result["found"],
            "passage": result["answer"] if result["found"] else None,
            "source": result["source"],
        }
