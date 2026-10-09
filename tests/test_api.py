from fastapi.testclient import TestClient

from app.main import create_app


class FakePolicyModel:
    def generate(self, question, context):
        return "Contact the academic office to report an absence."


def client_for(tmp_path, policy_model=None):
    return TestClient(create_app(tmp_path / "test.sqlite3", policy_model))


def test_health_and_ui_are_available(tmp_path):
    with client_for(tmp_path) as client:
        health = client.get("/api/health")
        page = client.get("/")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert page.status_code == 200
    assert "Fictional student ID" in page.text
    assert "SQLite" not in page.text


def test_attendance_api_validates_id_and_returns_subject_details(tmp_path):
    with client_for(tmp_path) as client:
        missing = client.get("/api/attendance")
        invalid = client.get(
            "/api/attendance",
            headers={"X-Demo-Student-ID": "not-a-student"},
        )
        malformed = client.get(
            "/api/attendance",
            headers={"X-Demo-Student-ID": "student id"},
        )
        valid = client.get(
            "/api/attendance",
            headers={"X-Demo-Student-ID": "synthetic-student-001"},
        )

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "UNAUTHORIZED"
    assert invalid.status_code == 404
    assert invalid.json()["error"]["code"] == "NOT_FOUND"
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "INVALID_REQUEST"
    assert valid.status_code == 200
    assert valid.json() == {
        "student_id": "synthetic-student-001",
        "subjects": [
            {
                "subject": "Database Systems",
                "course_code": "DB201",
                "attended_classes": 3,
                "total_classes": 4,
                "percentage": 75.0,
            },
            {
                "subject": "Software Engineering",
                "course_code": "SE101",
                "attended_classes": 4,
                "total_classes": 5,
                "percentage": 80.0,
            },
        ],
    }


def test_courses_are_scoped_and_unknown_identity_is_rejected(tmp_path):
    with client_for(tmp_path) as client:
        first_student = client.get(
            "/api/courses",
            headers={"X-Demo-Student-ID": "synthetic-student-001"},
        )
        second_student = client.get(
            "/api/courses",
            headers={"X-Demo-Student-ID": "synthetic-student-002"},
        )
        unknown = client.get(
            "/api/courses",
            headers={"X-Demo-Student-ID": "not-a-student"},
        )

    assert [course["code"] for course in first_student.json()["courses"]] == [
        "DB201",
        "SE101",
    ]
    assert [course["code"] for course in second_student.json()["courses"]] == [
        "SE101"
    ]
    assert unknown.status_code == 404


def test_policy_api_returns_retrieved_document(tmp_path):
    with client_for(tmp_path, FakePolicyModel()) as client:
        response = client.get(
            "/api/ask", params={"q": "What should I do if I miss a lecture?"}
        )

    assert response.status_code == 200
    assert response.json()["found"] is True
    assert response.json()["source"] == "attendance_policy.md"
    assert response.json()["sources"] == [
        {"document": "attendance_policy.md"}
    ]
    assert "contact the academic office" in response.json()["answer"]


def test_policy_api_reports_missing_provider_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with client_for(tmp_path) as client:
        response = client.get(
            "/api/ask", params={"q": "What should I do if I miss a lecture?"}
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODEL_NOT_CONFIGURED"
    assert "OPENAI_API_KEY" in response.json()["error"]["message"]


def test_assistant_api_attendance_path_requires_student_identity(tmp_path):
    with client_for(tmp_path) as client:
        unauthorized = client.post(
            "/api/assistant", json={"question": "Show my attendance"}
        )
        authorized = client.post(
            "/api/assistant",
            json={"question": "Show my attendance"},
            headers={"X-Demo-Student-ID": "synthetic-student-001"},
        )

    assert unauthorized.status_code == 403
    assert unauthorized.json()["error"]["code"] == "FORBIDDEN"
    assert authorized.status_code == 200
    assert authorized.json()["path"] == "attendance"


def test_assistant_api_routes_unsupported_safely(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post(
            "/api/assistant", json={"question": "Run arbitrary Python code"}
        )

    assert response.status_code == 200
    assert response.json()["path"] == "unsupported"
    assert "cannot help" in response.json()["answer"]


def test_assistant_api_rejects_request_for_another_student(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post(
            "/api/assistant",
            json={"question": "Show attendance for synthetic-student-002"},
            headers={"X-Demo-Student-ID": "synthetic-student-001"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_assistant_api_uses_policy_llm_path(tmp_path):
    with client_for(tmp_path, FakePolicyModel()) as client:
        response = client.post(
            "/api/assistant",
            json={"question": "What does the attendance policy say?"},
        )

    assert response.status_code == 200
    assert response.json()["path"] == "policy_question"
    assert response.json()["result"]["sources"] == [
        {"document": "attendance_policy.md"}
    ]
