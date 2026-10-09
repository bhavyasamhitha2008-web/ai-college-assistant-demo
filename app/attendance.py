import sqlite3


class StudentNotFoundError(ValueError):
    """Raised when attendance is requested for an unknown student."""


def ensure_student_exists(
    connection: sqlite3.Connection, student_id: str
) -> None:
    student = connection.execute(
        "SELECT 1 FROM students WHERE id = ?", (student_id,)
    ).fetchone()
    if student is None:
        raise StudentNotFoundError(student_id)


def get_attendance_by_subject(
    connection: sqlite3.Connection, student_id: str
) -> list[dict[str, int | float | str | None]]:
    ensure_student_exists(connection, student_id)

    rows = connection.execute(
        """
        SELECT courses.code, courses.title,
               COUNT(attendance.id) AS total_classes,
               COALESCE(SUM(attendance.attended), 0) AS attended_classes
        FROM enrollments
        JOIN courses ON courses.id = enrollments.course_id
        LEFT JOIN attendance
          ON attendance.student_id = enrollments.student_id
         AND attendance.course_id = enrollments.course_id
        WHERE enrollments.student_id = ?
        GROUP BY courses.id, courses.code, courses.title
        ORDER BY courses.code
        """,
        (student_id,),
    ).fetchall()

    subjects = []
    for row in rows:
        total = row["total_classes"]
        attended = row["attended_classes"]
        percentage = round(attended * 100 / total, 1) if total else None
        subjects.append(
            {
                "subject": row["title"],
                "course_code": row["code"],
                "attended_classes": attended,
                "total_classes": total,
                "percentage": percentage,
            }
        )
    return subjects


def get_student_courses(
    connection: sqlite3.Connection, student_id: str
) -> list[dict[str, str]]:
    ensure_student_exists(connection, student_id)
    rows = connection.execute(
        """
        SELECT courses.code, courses.title
        FROM courses
        JOIN enrollments ON enrollments.course_id = courses.id
        WHERE enrollments.student_id = ?
        ORDER BY courses.code
        """,
        (student_id,),
    ).fetchall()
    return [dict(row) for row in rows]
