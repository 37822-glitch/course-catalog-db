from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PSQL_ENV = {
    **os.environ,
    "PGPASSWORD": os.getenv("LAB6_DB_PASSWORD", "change-me"),
}
PSQL_BASE = [
    "psql",
    "-X",
    "-h",
    os.getenv("LAB6_DB_HOST", "localhost"),
    "-p",
    os.getenv("LAB6_DB_PORT", "5432"),
    "-U",
    os.getenv("LAB6_DB_USER", "catalog_app"),
    "-d",
    os.getenv("LAB6_DB_NAME", "course_catalog"),
]


def run_psql(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [*PSQL_BASE, *args],
        cwd=ROOT,
        env=PSQL_ENV,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"psql failed ({result.returncode})\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


class Lab6SchemaTests(unittest.TestCase):
    def test_schema_is_repeatable_and_has_required_tables(self) -> None:
        schema = ROOT / "schema.sql"
        self.assertTrue(schema.exists(), "schema.sql must exist")

        for _ in range(2):
            run_psql("-v", "ON_ERROR_STOP=1", "-f", str(schema))

        tables = run_psql(
            "-Atc",
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name;",
        ).stdout.splitlines()
        self.assertEqual(tables, ["courses", "enrollments", "students"])

    def test_schema_columns_constraints_and_indexes(self) -> None:
        run_psql("-v", "ON_ERROR_STOP=1", "-f", str(ROOT / "schema.sql"))

        columns = run_psql(
            "-Atc",
            "SELECT table_name || '.' || column_name || ':' || data_type || ':' || "
            "is_nullable || ':' || coalesce(column_default, '') "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name IN ('courses','students','enrollments') "
            "ORDER BY table_name, ordinal_position;",
        ).stdout
        for expected in (
            "courses.id:text:NO:",
            "courses.credits:integer:NO:",
            "courses.is_elective:boolean:NO:false",
            "courses.likes:integer:NO:0",
            "enrollments.enrolled_at:timestamp with time zone:NO:now()",
            "students.id:bigint:NO:",
        ):
            self.assertIn(expected, columns)

        constraints = run_psql(
            "-Atc",
            "SELECT conname || ':' || pg_get_constraintdef(oid) "
            "FROM pg_constraint "
            "WHERE conrelid IN ('courses'::regclass,'students'::regclass,'enrollments'::regclass) "
            "ORDER BY conname;",
        ).stdout
        for expected in (
            "courses_credits_check:CHECK ((credits > 0))",
            "courses_likes_check:CHECK ((likes >= 0))",
            "students_name_check:CHECK ((char_length(name) >= 2))",
            "students_email_key:UNIQUE (email)",
            "students_email_format:CHECK ((POSITION(('@'::text) IN (email)) > 1))",
            "enrollments_course_id_student_id_key:UNIQUE (course_id, student_id)",
            "enrollments_course_id_fkey:FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT",
            "enrollments_student_id_fkey:FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE",
        ):
            self.assertIn(expected, constraints)

        indexes = run_psql(
            "-Atc",
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
            "AND tablename = 'enrollments' ORDER BY indexname;",
        ).stdout.splitlines()
        self.assertIn("enrollments_student_id_idx", indexes)


if __name__ == "__main__":
    unittest.main(verbosity=2)

