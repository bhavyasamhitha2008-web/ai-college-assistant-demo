# Classroom Demonstration Script

This script uses only fictional records. Run commands in **PowerShell** from a
fresh clone. Keep the application bound to `127.0.0.1`; do not expose it to a
public or campus network.

## 1. Clone and install

```powershell
git clone https://github.com/bhavyasamhitha2008-web/ai-college-assistant-demo.git
Set-Location ai-college-assistant-demo
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `py` is not installed, replace it with `python`. Use Python 3.10 or newer.

## 2. Run the checks

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m app.evaluation
```

Both commands use local fixtures and fake models; no provider key is needed.
The evaluation runner prints a case summary and exits nonzero if any case
fails.

## 3. Start the local app

In the first PowerShell terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Wait for Uvicorn to report that it is running. Open a second PowerShell
terminal, change to the cloned repository directory, then open the page:

```powershell
Set-Location ai-college-assistant-demo
Start-Process http://127.0.0.1:8000
```

The page loads attendance for fictional student `synthetic-student-001`.
Demonstrate that the attendance output is calculated per subject and that the
ID field is a demo selector, not a login.

## 4. Demonstrate the API (second terminal)

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected: status `ok`.

Attendance for one fictional student:

```powershell
$headers = @{ "X-Demo-Student-ID" = "synthetic-student-001" }
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/attendance -Headers $headers
```

Expected: two subjects, DB201 at 75.0% and SE101 at 80.0%.

Courses for the same fictional student:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/courses -Headers $headers
```

Expected: DB201 and SE101 only for the selected ID.

Safe unsupported request:

```powershell
$body = @{ question = "Tell me a joke" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/assistant `
  -ContentType "application/json" -Body $body
```

Expected: path `unsupported` and a fixed response describing supported topics.

## 5. Optional: demonstrate a model-backed policy answer

This step makes a real request to the configured external provider. Only use a
test key and confirm the provider is approved for the demonstration. In the
first terminal, stop Uvicorn with `Ctrl+C`, set the environment variable, and
restart:

```powershell
$env:OPENAI_API_KEY = "your-provider-api-key"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then in the second terminal:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/ask?q=Where%20do%20I%20report%20an%20absence"
```

Expected: a response grounded in `attendance_policy.md` with a source reference.
Do not use this optional provider call in an offline classroom that has not
approved sending the question and retrieved passage to that provider.

## 6. Stop

Return to the first terminal and press `Ctrl+C`. The generated local database is
`data/demo.sqlite3`; it contains only fictional seeded records and is ignored
by Git.

## Presenter notes

- SQLite is authoritative for attendance and course results; the model does
  not calculate them.
- The demo ID header can be forged, so it is not real authentication.
- Policy answers are limited by the small fictional Markdown knowledge base.
- The default tests and evaluation are offline. A live provider call is
  optional and incurs provider usage under the configured account.
