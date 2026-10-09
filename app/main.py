import logging
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.assistant import AssistantRequest, AssistantService
from app.database import initialize_database
from app.llm_service import (
    LLMConfigurationError,
    LLMProviderError,
    PolicyModel,
    answer_policy_question,
)
from app.tools import (
    ReadOnlyApplicationTools,
    ToolAuthorizationError,
    ToolInputError,
    ToolStudentNotFoundError,
)


logger = logging.getLogger(__name__)
APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
DEFAULT_DATABASE_PATH = PROJECT_DIR / "data" / "demo.sqlite3"
POLICY_DOCUMENTS_DIR = PROJECT_DIR / "data" / "policies"


def create_app(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    policy_model: PolicyModel | None = None,
) -> FastAPI:
    app = FastAPI(title="AI College Assistant Demo", version="0.1.0")
    app.state.database_path = Path(database_path)
    app.state.policy_model = policy_model
    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")

    @app.on_event("startup")
    def startup() -> None:
        initialize_database(app.state.database_path)

    @app.exception_handler(HTTPException)
    async def http_error_handler(
        request: Request, exception: HTTPException
    ) -> JSONResponse:
        codes = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            422: "INVALID_REQUEST",
            502: "MODEL_UNAVAILABLE",
            503: "MODEL_NOT_CONFIGURED",
        }
        if exception.status_code == 401:
            codes[401] = "UNAUTHORIZED"
        return JSONResponse(
            status_code=exception.status_code,
            content={
                "error": {
                    "code": codes.get(exception.status_code, "REQUEST_ERROR"),
                    "message": str(exception.detail),
                }
            },
            headers=exception.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exception: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "The request contains invalid or missing input.",
                }
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request, exception: Exception
    ) -> JSONResponse:
        logger.exception("Unexpected error handling %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected server error occurred.",
                }
            },
        )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(APP_DIR / "static" / "index.html")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    def required_student_id(demo_student_id: str | None) -> str:
        if not demo_student_id:
            raise HTTPException(
                status_code=401, detail="A demo student identity is required."
            )
        return demo_student_id

    def application_tools(student_id: str | None) -> ReadOnlyApplicationTools:
        return ReadOnlyApplicationTools(
            app.state.database_path, POLICY_DOCUMENTS_DIR, student_id
        )

    @app.post("/api/assistant")
    def assistant(
        payload: AssistantRequest,
        x_demo_student_id: str | None = Header(
            default=None, alias="X-Demo-Student-ID", min_length=1, max_length=80
        ),
    ) -> dict[str, object]:
        service = AssistantService(
            app.state.database_path,
            POLICY_DOCUMENTS_DIR,
            app.state.policy_model,
        )
        try:
            result = service.respond(payload.question, x_demo_student_id)
        except ToolInputError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ToolAuthorizationError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ToolStudentNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except LLMConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except LLMProviderError as error:
            logger.error("Policy model request failed: %s", error)
            raise HTTPException(
                status_code=502,
                detail="The policy answer service is temporarily unavailable.",
            ) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return result

    @app.get("/api/attendance")
    def attendance(
        x_demo_student_id: str | None = Header(
            default=None, alias="X-Demo-Student-ID", min_length=1, max_length=80
        ),
    ) -> dict[str, str | list[dict[str, int | float | str | None]]]:
        student_id = required_student_id(x_demo_student_id)
        try:
            result = application_tools(student_id).get_attendance(student_id)
        except ToolInputError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ToolAuthorizationError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ToolStudentNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"student_id": student_id, **result}

    @app.get("/api/courses")
    def courses(
        x_demo_student_id: str | None = Header(
            default=None, alias="X-Demo-Student-ID", min_length=1, max_length=80
        ),
    ) -> dict[str, list[dict[str, str]]]:
        student_id = required_student_id(x_demo_student_id)
        try:
            return application_tools(student_id).get_courses(student_id)
        except ToolInputError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ToolAuthorizationError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ToolStudentNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/ask")
    def ask(
        q: str = Query(min_length=1, max_length=500),
    ) -> dict[str, object]:
        if not q.strip():
            raise HTTPException(
                status_code=422, detail="The question must not be blank."
            )
        try:
            return answer_policy_question(
                q,
                str(POLICY_DOCUMENTS_DIR),
                app.state.policy_model,
                application_tools(None),
            )
        except LLMConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except LLMProviderError as error:
            logger.error("Policy model request failed: %s", error)
            raise HTTPException(
                status_code=502,
                detail="The policy answer service is temporarily unavailable.",
            ) from error

    return app


app = create_app()
