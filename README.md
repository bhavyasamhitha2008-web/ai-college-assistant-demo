# AI College Assistant Demo

A small, local-first classroom demonstration built with Python, FastAPI,
SQLite, HTML, CSS, and JavaScript. It uses fictional student records and
fictional Markdown policy sources. Attendance and course records come from
SQLite; policy answers can use an optional external LLM provider.

This is a teaching demo, **not a production service**. The demo student ID is
caller-supplied and is not authentication. Never use real student or company
data, and do not expose this app to a public network.

## Requirements

- Git
- Python 3.10 or newer
- pip (included with standard Python installers)
- PowerShell on Windows, or a terminal with Python and venv support

## Setup from a fresh clone (Windows PowerShell)

Run these commands from the directory where you want the project:

```powershell
git clone https://github.com/bhavyasamhitha2008-web/ai-college-assistant-demo.git
Set-Location ai-college-assistant-demo
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If the `py` launcher is unavailable, use `python` in its place. The application
creates `data/demo.sqlite3` and seeds fictional records automatically on its
first startup; that generated database is ignored by Git.

## Start the application

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave this terminal running. Open <http://127.0.0.1:8000> in a browser. The
browser interface demonstrates attendance and policy lookup. Course data is
available through the API.

Policy questions that retrieve a passage require an API key. Set it in the
environment before starting the server; do not put it in source control:

```powershell
$env:OPENAI_API_KEY = "your-provider-api-key"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Optionally set `OPENAI_MODEL` before startup to choose a supported model. When
no key is configured, health, attendance, courses, and unsupported-policy
fallback requests work locally, but an in-scope policy question that finds
evidence returns HTTP 503. The test and evaluation commands use fake models
where applicable and never make live provider calls.

## API endpoint summary

| Method and path | Input | Behavior |
|---|---|---|
| `GET /api/health` | None | Returns a minimal application health status. |
| `GET /api/attendance` | `X-Demo-Student-ID` header | Returns per-course attended/total counts and percentage for the selected fictional student. |
| `GET /api/courses` | `X-Demo-Student-ID` header | Returns course codes and titles for the selected fictional student. |
| `GET /api/ask?q=...` | Required question, up to 500 characters | Retrieves a policy passage and, if found, asks the configured model for a context-grounded answer with a source reference. |
| `POST /api/assistant` | JSON `{"question":"..."}` and optional `X-Demo-Student-ID` header | Deterministically routes to attendance, courses, policy, or a safe unsupported response. |

Attendance/course requests require a seeded ID such as
`synthetic-student-001` or `synthetic-student-002`. This header only demonstrates
where record scoping belongs; anyone who can access the demo can supply either
ID. API errors use a structured `error` object. Input validation errors return
HTTP 422, missing identity is rejected, and attempts to access a different
student are denied by application code.

## Classroom demo script

Follow [the demo script](docs/demo-script.md) for exact setup, startup, browser,
and API commands, plus expected observations.

## Tests

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Tests use temporary databases and fake models; they do not require a provider
key or modify the demo database.

## Offline evaluation

Run the evaluation dataset from the repository root:

```powershell
.\.venv\Scripts\python.exe -m app.evaluation
```

The dataset includes policy questions, missing-evidence questions, attendance,
authorization/security, prompt injection, and paraphrases. The runner prints
per-case pass/fail and a summary. It uses a fake policy model, makes no live
provider requests, and reports zero provider cost. Details and evaluation
limitations are in [docs/evaluation.md](docs/evaluation.md).

## Architecture at a glance

- **FastAPI** serves the UI and validates API input.
- **SQLite** is the source of truth for fictional students, enrollments,
  courses, and attendance. SQL queries are parameterized; the application tools
  are read-only.
- **Policy retrieval** searches local Markdown documents using transparent
  token overlap. A matched passage and its source are passed to the optional
  provider adapter; a missing match returns an insufficient-information answer
  without calling a model.
- **Assistant routing** is deterministic. The model cannot select tools or
  access the database, Python, shell commands, or student records. Record
  authorization is enforced in application code.

See [docs/architecture.md](docs/architecture.md) for the component diagram,
database schema, boundaries, failure modes, and trade-offs.

## Known limitations

- The demo ID header is not authentication or production authorization.
- Student/course records and policy documents are fictional fixtures, not a
  college integration or an authoritative handbook.
- The keyword classifier and token-overlap retrieval are intentionally simple
  and can miss valid questions or match weakly related text.
- Prompt instructions reduce, but cannot guarantee elimination of, unsupported
  model output or prompt-injection effects.
- Matched policy questions send the question and retrieved passage to the
  configured external provider. Review provider privacy, retention, and usage
  terms before any use beyond this fictional classroom demo.
- The bounded agent currently selects a single relevant tool for each supported
  request; the three-call ceiling is a guard, not evidence of multi-step
  planning.
- The offline evaluation measures deterministic fixtures and a fake model. It
  does not measure real provider accuracy, latency, or cost.

## Troubleshooting

- **`py` or Python is not recognized:** install Python 3.10+ and enable the
  Python launcher, or substitute `python` for `py` during environment creation.
- **`No module named ...`:** activate the virtual environment or run commands
  using `.\.venv\Scripts\python.exe`, then install dependencies with
  `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- **Port 8000 is in use:** stop the other local server or change the Uvicorn
  port consistently, for example `--port 8001`, then browse to that port.
- **Policy endpoint returns HTTP 503 / `MODEL_NOT_CONFIGURED`:** set
  `OPENAI_API_KEY` in the same PowerShell session before starting Uvicorn.
  Never paste a real key into source code, tests, or screenshots.
- **Policy answer is insufficient:** check that the question relates to content
  in `data/policies/`; the sample documents deliberately omit many policy
  details.
- **Attendance/course endpoint returns 401 or 403:** send a seeded fictional
  `X-Demo-Student-ID` header. For example, `synthetic-student-001`.
- **Evaluation or tests fail:** run them from the repository root, check the
  reported failing case, and verify dependencies installed successfully.

## Project documents

- [Requirements and traceability](docs/requirements.md)
- [Architecture and boundaries](docs/architecture.md)
- [Classroom demo script](docs/demo-script.md)
- [Evaluation cases and criteria](docs/evaluation.md)
# ai-college-assistant-demo
