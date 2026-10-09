from contextlib import closing

import pytest

from app.attendance import (
    StudentNotFoundError,
    get_attendance_by_subject,
    get_student_courses,
)
from app.database import connect_database, initialize_database


def test_database_initialization_is_idempotent(tmp_path):
    database_path = tmp_path / "nested" / "demo.sqlite3"
    initialize_database(database_path)
    initialize_database(database_path)

    with closing(connect_database(database_path)) as connection:
        student_count = connection.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        attendance_count = connection.execute(
            "SELECT COUNT(*) FROM attendance"
        ).fetchone()[0]

    assert student_count == 2
    assert attendance_count == 11


def test_attendance_for_subject_with_zero_classes_is_explicit(tmp_path):
    database_path = tmp_path / "demo.sqlite3"
    initialize_database(database_path)

    with closing(connect_database(database_path)) as connection:
        connection.execute(
            "INSERT INTO students (id, display_name) VALUES (?, ?)",
            ("synthetic-zero-classes", "Zero Classes"),
        )
        connection.execute(
            "INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)",
            ("synthetic-zero-classes", "course-se-101"),
        )
        subjects = get_attendance_by_subject(connection, "synthetic-zero-classes")

    assert subjects == [
        {
            "subject": "Software Engineering",
            "course_code": "SE101",
            "attended_classes": 0,
            "total_classes": 0,
            "percentage": None,
        }
    ]


def test_normal_attendance_is_calculated_per_subject(tmp_path):
    database_path = tmp_path / "demo.sqlite3"
    initialize_database(database_path)

    with closing(connect_database(database_path)) as connection:
        subjects = get_attendance_by_subject(connection, "synthetic-student-001")

    assert subjects == [
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
    ]


def test_100_percent_attendance(tmp_path):
    database_path = tmp_path / "demo.sqlite3"
    initialize_database(database_path)

    with closing(connect_database(database_path)) as connection:
        subjects = get_attendance_by_subject(connection, "synthetic-student-002")

    assert subjects == [
        {
            "subject": "Software Engineering",
            "course_code": "SE101",
            "attended_classes": 2,
            "total_classes": 2,
            "percentage": 100.0,
        }
    ]


def test_invalid_student_id_is_not_treated_as_zero_attendance(tmp_path):
    database_path = tmp_path / "demo.sqlite3"
    initialize_database(database_path)

    with closing(connect_database(database_path)) as connection:
        with pytest.raises(StudentNotFoundError):
            get_attendance_by_subject(connection, "not-a-student")

        with pytest.raises(StudentNotFoundError):
            get_student_courses(connection, "not-a-student")
