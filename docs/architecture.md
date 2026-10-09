# AI College Assistant — MVP Architecture

**Status:** Implements the classroom-demo baseline in
[`requirements.md`](requirements.md). Production decisions remain open until
college stakeholders answer its questions.

## Architecture goals

- Keep a small, local-first, explainable application.
- Keep SQLite authoritative for attendance and course records.
- Keep policy content separate from transactional records.
- Enforce data scoping in Python before response serialization.
- Keep LLM use bounded to policy question answering; no LLM controls records.

## Text architecture diagram

```text
 Student / Demonstrator
           |
           | same-origin HTTP (HTML form + JSON)
           v
 +---------------------------+
 | FastAPI                   |
 | - static UI and API       |
 | - validation/error shape  |
 | - demo identity boundary |
 +-------------+-------------+
               |
       +-------+-------------------+
       |                           |
       v                           v
 +---------------------+   +----------------------+      +------------------+
 | Attendance/Course   |   | Policy retrieval +   |----->| LLM service      |
 | application logic   |   | answer orchestration |      | provider adapter |
 +----------+----------+   +----------+-----------+      +--------+---------+
            |                         |                           |
            v                         v                           v
 +---------------------+   +----------------------+      External LLM API
 | SQLite              |   | data/policies/*.md   |      (policy only)
 | students, courses,  |   | (read-only fictional |
 | enrollments,        |   | documents)           |
 | attendance          |   +----------------------+
 +---------------------+

 No RAG index, model tool, or college-system integration in this MVP.
```

## Components and responsibilities

| Component | Responsibility |
|---|---|
| `app/main.py` | Create the FastAPI application, serve static files, validate API inputs, enforce the demo identity boundary, and format expected/unexpected errors. |
| `app/database.py` | Create SQLite schema, connect to the database, and idempotently seed fictional records. |
| `app/attendance.py` | Validate student existence and calculate read-only per-subject attendance with parameterized SQL. |
| `app/knowledge.py` | Search local Markdown passages with transparent token overlap and aliases; return no-answer when unmatched. |
| `app/llm_service.py` | Provide a provider-neutral model protocol, no-context fallback, context-grounded answer orchestration, and source references. |
| `app/providers/openai_provider.py` | Isolate OpenAI-compatible HTTP details and read credentials from environment variables. |
| `app/static/` | Provide the browser UI and same-origin JavaScript API client. |
| `data/` | Hold the generated ignored SQLite database and checked-in fictional Markdown policy sources. |
| `tests/` | Verify database logic, API behavior, access scoping, errors, and source-grounded fallback with temporary databases. |

## API boundaries

All endpoints are same-origin JSON except `GET /`, which serves the UI.

| Endpoint | Input | Output / access |
|---|---|---|
| `GET /api/health` | None | Minimal `{"status":"ok"}`; no data access. |
| `GET /api/attendance` | Required `X-Demo-Student-ID` header entered in the UI | Per-subject attended/total counts and percentage only for the matching fictional identity; unknown IDs return 404 and malformed IDs return 422. |
| `GET /api/courses` | Required `X-Demo-Student-ID` header | Courses enrolled by that demo identity only. |
| `GET /api/ask?q=...` | Required, bounded question string | Retrieved context is passed with the question to a provider model. Response includes the answer and source reference. No access to student records. Returns 503 if a model is needed but not configured and 502 for provider failures. The question appears in the URL and may be recorded by browser/server access logs. |
| `POST /api/assistant` | JSON `{"question":"..."}` and optional demo identity header | Deterministic classification routes to attendance, courses, policy, or a fixed unsupported response. Student identity comes from the application header; policy LLM receives no data tools. |

Errors use `{"error":{"code":"...","message":"..."}}`. Validation errors
produce HTTP 422. Missing identity returns HTTP 401 from the attendance/course
endpoints and HTTP 403 when the assistant classifies a request as requiring
student data. Unknown demo identity returns HTTP 404; attempts to access a
different student's data return HTTP 403. Unexpected server errors return HTTP
500 with details logged only server-side.

The browser UI currently demonstrates attendance and policy lookup. Course
information is exposed through the API but is not currently displayed in the
page. Policy lookup uses GET in this demo; avoid sensitive question content.

## Database schema

SQLite is authoritative for transactional records.

```text
students(
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL
)

courses(
  id TEXT PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL
)

enrollments(
  student_id TEXT NOT NULL REFERENCES students(id),
  course_id TEXT NOT NULL REFERENCES courses(id),
  PRIMARY KEY(student_id, course_id)
)

attendance(
  id INTEGER PRIMARY KEY,
  student_id TEXT NOT NULL,
  course_id TEXT NOT NULL,
  class_date TEXT NOT NULL,
  attended INTEGER NOT NULL CHECK(attended IN (0, 1)),
  FOREIGN KEY(student_id, course_id)
    REFERENCES enrollments(student_id, course_id),
  UNIQUE(student_id, course_id, class_date)
)
```

The schema is initialized at application startup. Idempotent seed inserts add
fictional records only when absent. API routes issue `SELECT` queries only;
record writes are limited to initialization/seeding.

## Knowledge / RAG and LLM boundary

- Markdown files under `data/policies/` are the only policy sources in the MVP.
- `app/knowledge.py` splits documents into paragraphs, normalizes terms using a
  small explicit stop-word/synonym list, and selects the passage with greatest
  token overlap. It returns the original passage text and source filename.
- No embeddings or vector database are included. A small LLM service receives
  only the user's policy question and the retrieved passage. Attendance remains
  independent of the LLM.
- Unmatched requests return that the source does not provide enough information.
- Source text is untrusted data: it cannot direct application behavior, choose
  identity, or authorize access. The provider system instruction tells the model
  to use only the supplied context, decline when it is insufficient, and ignore
  instructions embedded in retrieved text. Source references are attached by
  application code from retrieval metadata, not generated by the model.
- Provider-specific HTTP behavior is isolated in `app/providers/`; credentials
  are read from `OPENAI_API_KEY` and never stored in source. Tests inject fake
  model implementations and do not make network calls.
- A matching question and retrieved passage are sent to the configured
  external provider. The no-provider evaluation uses a fake model; it does not
  measure real provider quality, latency, or cost.

## Tool boundary

`app/tools.py` exposes three allowlisted read-only application tools:

| Tool | Input | Output |
|---|---|---|
| `get_attendance` | `{"student_id": "..."}` | Per-subject names/codes, attended and total classes, percentage. |
| `get_courses` | `{"student_id": "..."}` | Enrolled course codes and titles. |
| `search_policy` | `{"question": "..."}` | Match status, retrieved passage, and source filename. |

Pydantic input models provide explicit JSON schemas, reject extra fields, and
bound string lengths; student IDs are also restricted to ASCII identifier
characters. Student tools compare the requested ID to an application-authorized
principal before making parameterized read-only queries. Policy lookup is
read-only and returns only passage/source information. No tool exposes arbitrary
SQL, credentials, or unrelated student records.

The API's attendance and course routes invoke their respective tools directly.
Policy answering uses `search_policy` to retrieve context before calling the LLM
service; that service never receives student-record tools.

`app/assistant.py` classifies requests with local keyword rules, not with an
LLM. It can call only the corresponding application tool or the policy-answer
service. An explicit different student ID in a data request is rejected by
application authorization. Unsupported requests never call a tool or model.
Each selected tool and coarse outcome (success, unauthorized, or failure) is
logged without recording question text, tool arguments, or returned student
data. The agent loop is capped at three tool calls; current request paths stop
after one tool result is inspected.

The demo principal is still selected using the caller-supplied
`X-Demo-Student-ID`; this is not authentication. Production use requires a
trusted identity and an application-populated principal, never a model-selected
identity.

## Authentication / authorization boundary

- The MVP uses `X-Demo-Student-ID` to select a seeded synthetic identity.
- FastAPI application code validates the provided ID through the attendance
  service before returning scoped attendance/course data.
- This is **not authentication**: any caller able to reach the demo can forge
  the header. It is only a classroom demonstration of where application-level
  record scoping belongs.
- Production requires college-approved authentication (such as SSO), trusted
  identity claims, role/record-level authorization, transport security, and
  security review. Do not put real student records behind the demo header.

## Observability

- Uvicorn provides local access and server logs.
- Unexpected API exceptions are logged with server-side stack traces; clients
  receive a generic 500 response.
- Health response reveals only service status.
- The MVP does not log question text, attendance, student identifiers, or
  policy content and does not implement analytics/audit storage.
- Production logging, auditability, alerting, retention, and redaction require
  stakeholder decisions before adding them.

## Testing strategy

- Unit-test SQLite initialization, idempotent seeding, per-subject attendance
  calculations, zero-class behavior, and invalid IDs with temporary database
  files.
- Unit-test each application tool's schema validation, principal scoping,
  minimal structured output, and read-only behavior.
- API-test health, UI response, missing/unknown identities, own-record scoping,
  policy source match/no-match, and validation/error response shapes.
- Manually smoke-test the local browser UI against the same-origin API.
- No live college service, network dependency, external model, or real data is
  required for the test suite.

## Major failure modes

| Failure | Expected behavior / mitigation |
|---|---|
| SQLite cannot be created or read | Startup/request fails visibly in server logs; do not return fabricated data. |
| Repeated startup | Idempotent seed inserts and unique constraints prevent duplicate fixtures. |
| Missing/unknown demo identity | Reject with structured 401/404; never fall back to a default identity in the API. |
| Enrolled course has no attendance rows | Return zero counts and a null percentage; do not divide by zero. |
| Policy file unavailable/invalid | Fail visibly rather than reporting a fabricated answer. |
| No policy match | Return explicit insufficient information locally without making a model call. |
| Malicious or instruction-like retrieved text | Treat as ordinary source text; it cannot affect application authorization or behavior. |
| Unexpected bug | Log exception server-side and return a generic structured 500 response. |

## Architecture decisions and trade-offs

| Decision | Rationale | Trade-off |
|---|---|---|
| FastAPI with static files served by the same app | Minimal setup and no CORS/build pipeline for a classroom demo. | UI and API deploy together; not optimized for larger deployments. |
| SQLite local file | Simple, inspectable source of truth for a single-process demonstration. | Not a multi-instance production database or concurrent campus system. |
| Seeded synthetic fixtures | Runnable without external systems and safe for teaching. | Does not validate real SIS integration or official attendance semantics. |
| Header as explicit demo identity selector | Demonstrates app-layer scoping without introducing an auth provider. | Not authentication; must never be mistaken for production security. |
| Curated Markdown plus token overlap | Small, deterministic, attributable, and easy to test; aliases can cover simple paraphrases. | Less flexible than RAG; matching can still miss paraphrases. |
| LLM only after retrieval for policy answers | Provides natural-language responses while limiting input context and preserving SQLite/business logic independence. | Provider can still produce unsupported content; instructions and context-only use reduce but cannot eliminate this risk. |
| Read-only routes | Limits impact and keeps records authoritative in SQLite. | No administration or correction workflow. |
