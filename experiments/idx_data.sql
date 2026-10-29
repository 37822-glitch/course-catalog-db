-- idx_data.sql: deterministic scale data for the index experiment.
-- Run schema.sql in idx_demo first, then run this file.

TRUNCATE TABLE enrollments, students, courses RESTART IDENTITY;

INSERT INTO courses (id, title, description, credits, is_elective, likes)
SELECT
    'course-' || course_no,
    'Generated course ' || course_no,
    'Deterministic row for the Lab 6 index experiment.',
    3 + (course_no % 3),
    course_no % 5 = 0,
    course_no % 101
FROM generate_series(1, 500) AS generated(course_no);

INSERT INTO students (name, email)
SELECT
    'Student ' || student_no,
    'student' || student_no || '@example.com'
FROM generate_series(1, 20000) AS generated(student_no);

-- Every pair is unique: each student appears two or three times and the
-- course offset changes on each pass through the 20,000 students.
INSERT INTO enrollments (course_id, student_id)
SELECT
    'course-' || (1 + ((row_no + row_no / 20000) % 500)),
    1 + (row_no % 20000)
FROM generate_series(1, 50000) AS generated(row_no);

ANALYZE courses;
ANALYZE students;
ANALYZE enrollments;
