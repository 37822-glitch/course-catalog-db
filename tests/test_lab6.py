from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path
from typing import Optional


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


def run_psql(
    *args: str,
    check: bool = True,
    database: Optional[str] = None,
) -> subprocess.CompletedProcess[str]:
    command = PSQL_BASE.copy()
    if database is not None:
        command[-1] = database
    result = subprocess.run(
        [*command, *args],
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


class Lab6SeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        run_psql("-v", "ON_ERROR_STOP=1", "-f", str(ROOT / "schema.sql"))
        run_psql("-v", "ON_ERROR_STOP=1", "-f", str(ROOT / "seed.sql"))

    def test_seed_has_exact_required_row_counts(self) -> None:
        counts = run_psql(
            "-Atc",
            "SELECT (SELECT count(*) FROM courses), "
            "(SELECT count(*) FROM students), "
            "(SELECT count(*) FROM enrollments);",
        ).stdout.strip()
        self.assertEqual(counts, "6|3|6")

    def test_seed_preserves_course_and_student_order(self) -> None:
        courses = run_psql(
            "-Atc",
            "SELECT id || ':' || credits || ':' || is_elective || ':' || likes "
            "FROM courses ORDER BY id;",
        ).stdout.splitlines()
        self.assertEqual(
            courses,
            [
                "ai-integration:5:true:32",
                "api-design:4:true:11",
                "backend-fastapi:5:false:19",
                "databases-postgresql:5:false:15",
                "modern-frontend:5:false:24",
                "web-security:4:false:21",
            ],
        )

        students = run_psql(
            "-Atc",
            "SELECT id || ':' || name || ':' || email FROM students ORDER BY id;",
        ).stdout.splitlines()
        self.assertEqual(
            students,
            [
                "1:Aigerim Sadykova:aigerim@example.com",
                "2:Daniyar Bekov:daniyar@example.com",
                "3:Asel Omarova:asel@example.com",
            ],
        )


class Lab6ConstraintBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        run_psql("-v", "ON_ERROR_STOP=1", "-f", str(ROOT / "schema.sql"))
        run_psql("-v", "ON_ERROR_STOP=1", "-f", str(ROOT / "seed.sql"))

    def test_unique_foreign_key_and_email_checks_reject_bad_data(self) -> None:
        cases = (
            (
                "INSERT INTO students (name, email) "
                "VALUES ('Duplicate', 'aigerim@example.com');",
                "students_email_key",
            ),
            (
                "INSERT INTO enrollments (course_id, student_id) "
                "VALUES ('no-such-course', 1);",
                "enrollments_course_id_fkey",
            ),
            (
                "INSERT INTO students (name, email) "
                "VALUES ('Bad Email', 'invalid-email');",
                "students_email_format",
            ),
        )
        for sql, expected_constraint in cases:
            result = run_psql("-v", "ON_ERROR_STOP=1", "-c", sql, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(expected_constraint, result.stderr)

    def test_delete_actions_are_restrict_and_cascade(self) -> None:
        restricted = run_psql(
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "DELETE FROM courses WHERE id = 'modern-frontend';",
            check=False,
        )
        self.assertNotEqual(restricted.returncode, 0)
        self.assertIn("enrollments_course_id_fkey", restricted.stderr)

        cascade = run_psql(
            "-Atc",
            "BEGIN; DELETE FROM students WHERE id = 2; "
            "SELECT count(*) FROM enrollments; ROLLBACK;",
        ).stdout.splitlines()
        self.assertIn("3", cascade)
        remaining = run_psql("-Atc", "SELECT count(*) FROM enrollments;").stdout.strip()
        self.assertEqual(remaining, "6")


class Lab6QueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        run_psql("-v", "ON_ERROR_STOP=1", "-f", str(ROOT / "schema.sql"))
        run_psql("-v", "ON_ERROR_STOP=1", "-f", str(ROOT / "seed.sql"))

    def test_queries_run_twice_without_changing_seed_state(self) -> None:
        queries = ROOT / "queries.sql"
        self.assertTrue(queries.exists(), "queries.sql must exist")

        for _ in range(2):
            run_psql("-v", "ON_ERROR_STOP=1", "-f", str(queries))

        state = run_psql(
            "-Atc",
            "SELECT (SELECT count(*) FROM courses), "
            "(SELECT count(*) FROM students), "
            "(SELECT count(*) FROM enrollments), "
            "(SELECT likes FROM courses WHERE id = 'api-design');",
        ).stdout.strip()
        self.assertEqual(state, "6|3|6|11")

    def test_queries_return_required_and_bonus_results(self) -> None:
        output = run_psql(
            "-A",
            "-t",
            "-v",
            "ON_ERROR_STOP=1",
            "-f",
            str(ROOT / "queries.sql"),
        ).stdout
        for expected in (
            "modern-frontend|Modern Frontend: React & Next.js|5|24",
            "databases-postgresql|Relational Databases: PostgreSQL|5|15",
            "api-design|API Design: REST vs GraphQL|4|t|11",
            "api-design|12",
            "web-security|3",
            "Aigerim Sadykova|Modern Frontend: React & Next.js",
            "ai-integration|3",
            "api-design|0",
            "Daniyar Bekov|3",
            "Aigerim Sadykova|2",
        ):
            self.assertIn(expected, output)

    def test_modifying_examples_are_wrapped_in_rollback_transactions(self) -> None:
        sql = (ROOT / "queries.sql").read_text(encoding="utf-8")
        like_block = re.search(
            r"-- 3\..*?BEGIN;(?P<body>.*?)ROLLBACK;",
            sql,
            flags=re.DOTALL,
        )
        enrollment_block = re.search(
            r"-- 4\..*?BEGIN;(?P<body>.*?)ROLLBACK;",
            sql,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(like_block)
        self.assertIsNotNone(enrollment_block)
        self.assertIn("UPDATE courses", like_block.group("body"))
        self.assertIn("INSERT INTO enrollments", enrollment_block.group("body"))
        self.assertIn("count(e.id)", sql)


class Lab6ExperimentFileTests(unittest.TestCase):
    def test_index_dataset_has_required_scale(self) -> None:
        data_file = ROOT / "experiments" / "idx_data.sql"
        self.assertTrue(data_file.exists(), "experiments/idx_data.sql must exist")

        run_psql(
            "-v",
            "ON_ERROR_STOP=1",
            "-f",
            str(ROOT / "schema.sql"),
            database="idx_demo",
        )
        run_psql(
            "-v",
            "ON_ERROR_STOP=1",
            "-f",
            str(data_file),
            database="idx_demo",
        )
        counts = run_psql(
            "-Atc",
            "SELECT (SELECT count(*) FROM courses), "
            "(SELECT count(*) FROM students), "
            "(SELECT count(*) FROM enrollments);",
            database="idx_demo",
        ).stdout.strip()
        self.assertEqual(counts, "500|20000|50000")

    def test_normalization_demo_is_repeatable(self) -> None:
        demo_file = ROOT / "experiments" / "norm_demo.sql"
        self.assertTrue(demo_file.exists(), "experiments/norm_demo.sql must exist")

        for _ in range(2):
            run_psql(
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                str(demo_file),
                database="norm_demo",
            )
        rows = run_psql(
            "-Atc",
            "SELECT count(*) FROM course_enrollments_flat;",
            database="norm_demo",
        ).stdout.strip()
        self.assertEqual(rows, "6")


class Lab6DocumentationTests(unittest.TestCase):
    def test_readme_contains_all_required_lab_sections(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for heading in (
            "## How to run",
            "## Schema",
            "## Design decisions",
            "## Constraint violation log",
            "## Index experiment",
            "## Transaction experiment",
            "## Bonus tasks",
            "## Self-review checklist",
        ):
            self.assertIn(heading, readme)

        for evidence in (
            "PostgreSQL 16.15",
            "49,997",
            "24.5× faster",
            "0|0",
            "1|1",
            "Lost update",
            "SQL injection",
            "students_email_format",
            "erDiagram",
        ):
            self.assertIn(evidence, readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)

