# AI College Assistant — Requirements Specification

**Status:** Initial demo baseline; stakeholder decisions listed at the end are
open and must be resolved before use with real college systems or data.

## Stakeholders

- **Students:** ask policy questions and view their own fictional attendance
  and course information.
- **College policy owners / academic office:** approve policy documents and
  determine which sources are authoritative and current.
- **Faculty and academic administrators:** define attendance and course data
  rules and access responsibilities.
- **College IT / security / privacy staff:** define identity, access, retention,
  incident response, and deployment requirements.
- **Demonstrator / instructor:** operates the classroom example and explains
  system boundaries.
- **Development and testing team:** implements, tests, and maintains the demo.

## Scope

### In scope

- A local web UI and JSON API for a classroom demonstration.
- Read-only display of fictional course and attendance data stored in SQLite.
- A simple lookup against a small, fictional policy source, returning the
  matching source and declining unsupported questions.
- Health checking, input validation, consistent API errors, and automated tests.
- Explicit application-layer scoping of demo records, separate from policy
  lookup and independent of any model.

### Out of scope

- Real student/company data, production deployment, or integration with student
  information systems.
- Real authentication, campus SSO, role administration, or production-grade
  authorization.
- Writing/updating attendance, grades, or course records.
- Embeddings, vector search, autonomous agents, or model tools.
- Official policy interpretation, decision-making, or advice beyond the
  supplied sample source.

## Functional requirements

| ID | Requirement |
|---|---|
| FR-01 | The service shall serve a browser interface from the FastAPI application. |
| FR-02 | The service shall expose a health endpoint that reports application availability without exposing data. |
| FR-03 | The service shall initialize a local SQLite database and seed it with fictional students, courses, enrollments, and attendance records. |
| FR-04 | The service shall return the requesting demo student's per-subject attendance counts and percentage from SQLite, after validating the supplied fictional student ID. |
| FR-05 | The service shall return only the requesting demo student's enrolled courses from SQLite. |
| FR-06 | The service shall answer supported policy lookups using the question and retrieved context, restrict the model to that context, and identify source documents. |
| FR-07 | The service shall explicitly indicate when the policy source does not contain enough information to answer. |
| FR-08 | The UI shall let a user submit a policy question and display attendance, courses, source attribution, and API errors. |
| FR-09 | The API shall validate external input and return a consistent structured error response for invalid or failed requests. |
| FR-10 | All demo data operations shall be read-only after initial database seeding. |

## Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-01 | The implementation shall use Python, FastAPI, SQLite, HTML/CSS/JavaScript, and pytest, without requiring a cloud service. |
| NFR-02 | The application shall use small, readable modules and keep business rules outside any LLM. |
| NFR-03 | The app shall run locally with documented setup and test commands. |
| NFR-04 | Automated tests shall use isolated temporary databases and be repeatable. |
| NFR-05 | API errors shall not disclose stack traces, SQL, or internal file paths to clients. |
| NFR-06 | The design shall be simple enough to explain in a B.Tech Software Engineering lecture. |
| NFR-07 | The service shall preserve database records as the source of truth for transactional attendance/course data. |
| NFR-08 | Provider-specific LLM code shall be isolated behind a provider-neutral service interface, and model credentials shall come only from environment variables. |

## Security and privacy requirements

| ID | Requirement |
|---|---|
| SEC-01 | The demo shall use fictional data only and shall not be populated with actual student or company data. |
| SEC-02 | Application code shall enforce record scoping before returning attendance or course data; prompts or model behavior are not an authorization boundary. |
| SEC-03 | The current demo identity header shall be documented as an unauthenticated classroom convenience and shall not be represented as production authentication. |
| SEC-04 | SQL queries shall use parameters; user input shall not be concatenated into SQL statements. |
| SEC-05 | Policy-source text shall be treated as untrusted data. No instructions in it may alter authorization, system behavior, or access to internal information. |
| SEC-06 | The demo shall not expose secrets, hidden prompts, internal implementation details, or personal data. |
| SEC-07 | Any future tools shall be narrowly scoped, read-only, and invoked only after application-layer authorization. The MVP has no model tools. |
| SEC-08 | Retrieved policy content shall be treated as untrusted data; instructions inside it shall not alter model/application behavior or authorization. |

## Assumptions

- The first release is a local classroom demo, not a college-operated service.
- All seeded identities, attendance, courses, and policy content are fictional.
- The fictional Markdown files under `data/policies/` are the only knowledge
  sources for the MVP.
- Attendance is represented as individual attended/not-attended class records;
  the MVP reports per-subject counts and percentages and does not apply
  eligibility rules.
- The UI allows a user to enter one of a small set of seeded fictional IDs; the
  ID selects demo records but does not prove who the requester is.
- The LLM is used only for policy answers and is never a system of record.

## Constraints

- SQLite is the source of truth for attendance, students, and courses.
- Policy documents, not the LLM, are the source of policy statements.
- The LLM must not become a system of record; the MVP does not include one.
- Data endpoints and all hypothetical tools must be read-only.
- Authorization must be enforced in application code, outside a model.
- No cloud services, external data, or unnecessary frameworks.

## Use cases

| ID | Actor | Use case | Main outcome |
|---|---|---|---|
| UC-01 | Student (demo) | View attendance | Sees the summary associated with the selected demo identity, or a clear error. |
| UC-02 | Student (demo) | View courses | Sees only courses associated with the selected demo identity. |
| UC-03 | Student / demonstrator | Ask a policy question | Sees a sourced sample answer or an explicit insufficient-information response. |
| UC-04 | Operator / monitor | Check service health | Receives an availability response without student data. |
| UC-05 | Developer | Run automated tests | Verifies core routes, access scoping, policy fallback, and database behavior. |

## User stories

- **US-01:** As a student using the demo, I want to view my attendance so that I
  can see the fictional records associated with my selected demo identity.
- **US-02:** As a student using the demo, I want to see my enrolled courses so
  that course data is not mixed across demo identities.
- **US-03:** As a student, I want a policy answer to name its source so I can
  distinguish source-backed information from unsupported claims.
- **US-04:** As a student, I want the assistant to say when the sample source
  cannot answer so it does not invent a college policy.
- **US-05:** As an instructor, I want a health endpoint and simple tests so I
  can demonstrate basic service operation and verification.

## Acceptance criteria (Given / When / Then)

### AC-01 — Health

- **Given** the app has started, **when** a client requests `GET /api/health`,
  **then** it receives HTTP 200 and a healthy status without student data.

### AC-02 — Attendance scoping

- **Given** the database contains fictional attendance records for two demo
  identities, **when** a caller requests `GET /api/attendance` with a valid
  `X-Demo-Student-ID`, **then** the response contains per-subject counts and
  percentages for that identity only.
- **Given** the header is missing or identifies no seeded student, **when** the
  caller requests attendance, **then** the API rejects the request and returns
  a structured error rather than another student's records.

### AC-03 — Course scoping

- **Given** the database contains courses for multiple demo identities, **when**
  a valid demo identity requests `GET /api/courses`, **then** only its enrolled
  courses are returned.

### AC-04 — Grounded policy lookup

- **Given** a question matches a supported topic in the sample policy source,
  **when** the user submits it, **then** the response includes source-backed
  text and its source title.
- **Given** no source entry matches, **when** the user submits a question,
  **then** the response states that the source does not provide enough
  information and does not invent a policy.

### AC-05 — Input and errors

- **Given** an empty or overlong policy question, **when** it is submitted,
  **then** the API returns a validation error in the documented error shape.
- **Given** an unexpected server failure occurs, **when** a request is handled,
  **then** the client receives a generic error without a traceback or SQL detail.

### AC-06 — Read-only and fictional data

- **Given** the demo is running, **when** a user visits the UI or calls its API,
  **then** no endpoint writes attendance/course data and all included records
  are fictional.

## Edge cases

- Missing, empty, unknown, or malformed demo identity.
- Student with no enrolled courses or no attendance rows.
- Enrolled subject with zero recorded classes (percentage is null, not a
  division-by-zero result).
- Empty, whitespace-only, unusually long, or unsupported policy question.
- No matching policy source, malformed source file, or missing database directory.
- Database initialization repeated on restart without duplicate sample rows.
- SQLite unavailable or database file not writable.
- Unexpected endpoint failure; response must stay generic and be logged server-side.
- Policy text containing instruction-like or malicious content; it remains data.

## Stakeholder questions to resolve before implementation beyond this demo

1. Which college roles will use the system, and what can each role view?
2. Which identity provider and login flow are required (for example, campus SSO)?
3. What authoritative attendance/course system supplies records, and how often
   may it be queried or synchronized?
4. What are the official attendance calculation rules, rounding rules, and
   handling of excused absences or corrections?
5. Which policy documents are authoritative, who owns them, and how are
   versions, effective dates, and superseded documents handled?
6. Should policy answers cite exact passages/pages, and what is the required
   behavior when sources conflict?
7. Are any external LLM services permitted? If so, what data may be sent, and
   what retention, residency, and contractual controls apply?
8. What are the data retention/deletion, audit, accessibility, uptime, and
   performance requirements?
9. Which deployment environment, network boundaries, backup, and incident
   response procedures are required?
10. What languages and accessibility standards must the user interface support?

## Traceability

| Requirement | Covered by acceptance criteria | Use cases | MVP verification |
|---|---|---|---|
| FR-01, FR-08 | AC-04, AC-06 | UC-01 to UC-04 | Manual UI smoke check and API tests |
| FR-02 | AC-01 | UC-04 | `tests/test_api.py` |
| FR-03, FR-10, NFR-07 | AC-06 | UC-01, UC-02 | `tests/test_attendance.py`, API tests |
| FR-04, SEC-02 to SEC-04 | AC-02 | UC-01 | `tests/test_api.py` |
| FR-05, SEC-02 | AC-03 | UC-02 | `tests/test_api.py` |
| FR-06, FR-07, SEC-05, SEC-08 | AC-04 | UC-03 | `tests/test_api.py`, `tests/test_llm_service.py` |
| FR-09, NFR-05 | AC-05 | UC-01 to UC-04 | `tests/test_api.py` |
| NFR-01 to NFR-04, NFR-06 | AC-01 to AC-06 | UC-05 | Setup instructions and `pytest` |
| SEC-01, SEC-06, SEC-07 | AC-04, AC-06 | UC-01 to UC-05 | Review seeded sources and API scope |
