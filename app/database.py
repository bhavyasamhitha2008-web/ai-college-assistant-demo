from pathlib import Path
import sqlite3
from contextlib import closing


DEMO_STUDENTS = (
    ("synthetic-student-001", "Alex Example"),
    ("synthetic-student-002", "Jamie Sample"),
)

DEMO_COURSES = (
    ("course-se-101", "SE101", "Software Engineering"),
    ("course-db-201", "DB201", "Database Systems"),
)

DEMO_ENROLLMENTS = (
    ("synthetic-student-001", "course-se-101"),
    ("synthetic-student-001", "course-db-201"),
    ("synthetic-student-002", "course-se-101"),
)

DEMO_ATTENDANCE = (
    (1, "synthetic-student-001", "course-se-101", "2026-09-01", 1),
    (2, "synthetic-student-001", "course-se-101", "2026-09-08", 1),
    (3, "synthetic-student-001", "course-se-101", "2026-09-15", 0),
    (4, "synthetic-student-001", "course-se-101", "2026-09-22", 1),
    (5, "synthetic-student-001", "course-se-101", "2026-09-29", 1),
    (6, "synthetic-student-001", "course-db-201", "2026-09-02", 1),
    (7, "synthetic-student-001", "course-db-201", "2026-09-09", 0),
    (8, "synthetic-student-001", "course-db-201", "2026-09-16", 1),
    (9, "synthetic-student-001", "course-db-201", "2026-09-23", 1),
    (10, "synthetic-student-002", "course-se-101", "2026-09-01", 1),
    (11, "synthetic-student-002", "course-se-101", "2026-09-08", 1),
)


def connect_database(database_path: str | Path) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path) -> None:
    with closing(connect_database(database_path)) as connection, connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS courses (
                id TEXT PRIMARY KEY,
                code TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS enrollments (
                student_id TEXT NOT NULL REFERENCES students(id),
                course_id TEXT NOT NULL REFERENCES courses(id),
                PRIMARY KEY (student_id, course_id)
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY,
                student_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                class_date TEXT NOT NULL,
                attended INTEGER NOT NULL CHECK (attended IN (0, 1)),
                FOREIGN KEY (student_id, course_id)
                    REFERENCES enrollments(student_id, course_id),
                UNIQUE (student_id, course_id, class_date)
            );
            """
        )
        connection.executemany(
            "INSERT OR IGNORE INTO students (id, display_name) VALUES (?, ?)",
            DEMO_STUDENTS,
        )
        connection.executemany(
            "INSERT OR IGNORE INTO courses (id, code, title) VALUES (?, ?, ?)",
            DEMO_COURSES,
        )
        connection.executemany(
            "INSERT OR IGNORE INTO enrollments (student_id, course_id) "
            "VALUES (?, ?)",
            DEMO_ENROLLMENTS,
        )
        connection.executemany(
            "INSERT OR IGNORE INTO attendance "
            "(id, student_id, course_id, class_date, attended) "
            "VALUES (?, ?, ?, ?, ?)",
            DEMO_ATTENDANCE,
        )
