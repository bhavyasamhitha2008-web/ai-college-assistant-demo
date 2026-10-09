import logging
import re
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel, Field, StrictStr

from app.llm_service import PolicyModel, answer_retrieved_policy
from app.tools import ReadOnlyApplicationTools, ToolAuthorizationError


logger = logging.getLogger(__name__)
MAX_TOOL_CALLS = 3
APPROVED_TOOLS = MappingProxyType(
    {
        "attendance": "get_attendance",
        "courses": "get_courses",
        "policy_question": "search_policy",
    }
)

RequestPath = Literal["attendance", "courses", "policy_question", "unsupported"]

ATTENDANCE_PATTERN = re.compile(
    r"\b(attendance|attend|absent|absence|present)\b", re.IGNORECASE
)
COURSES_PATTERN = re.compile(
    r"\b(courses?|subjects?|enrollments?)\b", re.IGNORECASE
)
POLICY_PATTERN = re.compile(
    r"\b(policy|policies|handbook|exam|examination|leave|deadline)\b",
    re.IGNORECASE,
)
STUDENT_ID_IN_REQUEST_PATTERN = re.compile(
    r"\b[A-Za-z][A-Za-z0-9_-]*-\d{3,}\b"
)

UNSUPPORTED_RESPONSE = (
    "I can help with attendance, courses, and questions answered by the "
    "available college policy documents. I cannot help with that request."
)


class AssistantRequest(BaseModel):
    question: StrictStr = Field(..., min_length=1, max_length=500)

    class Config:
        extra = "forbid"


def classify_request(question: str) -> RequestPath:
    if POLICY_PATTERN.search(question):
        return "policy_question"
    if ATTENDANCE_PATTERN.search(question):
        return "attendance"
    if COURSES_PATTERN.search(question):
        return "courses"
    return "unsupported"


class AssistantService:
    def __init__(
        self,
        database_path: str | Path,
        policy_documents_dir: str | Path,
        policy_model: PolicyModel | None = None,
        tools_factory: type[ReadOnlyApplicationTools] = ReadOnlyApplicationTools,
    ):
        self._database_path = Path(database_path)
        self._policy_documents_dir = Path(policy_documents_dir)
        self._policy_model = policy_model
        self._tools_factory = tools_factory

    def respond(
        self, question: str, authorized_student_id: str | None
    ) -> dict[str, Any]:
        request = AssistantRequest(question=question)
        normalized_question = request.question.strip()
        if not normalized_question:
            raise ValueError("Question must not be blank.")

        path = classify_request(normalized_question)
        if path == "unsupported":
            return {"path": path, "answer": UNSUPPORTED_RESPONSE}

        tools = self._tools_factory(
            self._database_path,
            self._policy_documents_dir,
            authorized_student_id,
        )
        selected_tool = APPROVED_TOOLS[path]
        tool_call_count = 0
        for _ in range(MAX_TOOL_CALLS):
            tool_call_count += 1
            logger.info("Agent selected tool=%s", selected_tool)
            try:
                result = self._call_tool(
                    selected_tool,
                    tools,
                    normalized_question,
                    authorized_student_id,
                )
                if not isinstance(result, dict):
                    raise RuntimeError("Approved tool returned an invalid result.")
            except ToolAuthorizationError:
                logger.warning(
                    "Agent tool outcome tool=%s outcome=unauthorized",
                    selected_tool,
                )
                raise
            except Exception:
                logger.exception(
                    "Agent tool outcome tool=%s outcome=failed",
                    selected_tool,
                )
                raise

            logger.info("Agent tool outcome tool=%s outcome=success", selected_tool)
            response = self._inspect_result(path, normalized_question, result)
            logger.info(
                "Agent stopped reason=final_answer tool_calls=%d",
                tool_call_count,
            )
            return response

        logger.error(
            "Agent stopped reason=tool_call_limit tool_calls=%d",
            tool_call_count,
        )
        raise RuntimeError("The assistant reached its tool-call limit.")

    def _call_tool(
        self,
        tool_name: str,
        tools: ReadOnlyApplicationTools,
        question: str,
        authorized_student_id: str | None,
    ) -> dict[str, Any]:
        if tool_name == "search_policy":
            return tools.search_policy(question)

        if authorized_student_id is None:
            raise ToolAuthorizationError(
                "An authorized student identity is required."
            )
        requested_student_id = self._requested_student_id(
            question, authorized_student_id
        )
        if tool_name == "get_attendance":
            return tools.get_attendance(requested_student_id)
        if tool_name == "get_courses":
            return tools.get_courses(requested_student_id)
        raise RuntimeError("The selected tool is not approved.")

    def _inspect_result(
        self, path: RequestPath, question: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        if path == "policy_question":
            inspected = answer_retrieved_policy(
                question, result, self._policy_model
            )
            return {"path": path, "result": inspected}
        return {"path": path, "result": result}

    @staticmethod
    def _requested_student_id(question: str, authorized_student_id: str) -> str:
        requested_ids = set(STUDENT_ID_IN_REQUEST_PATTERN.findall(question))
        if len(requested_ids) > 1:
            raise ToolAuthorizationError(
                "The request includes multiple student IDs and cannot be completed."
            )
        if requested_ids:
            return next(iter(requested_ids))
        return authorized_student_id
