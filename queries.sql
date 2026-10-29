-- queries.sql: core API queries and the two optional reporting queries

-- 1. GET /courses: first page of non-elective courses, most popular first.
SELECT id, title, credits, likes
FROM courses
WHERE is_elective = false
ORDER BY likes DESC, id
LIMIT 3 OFFSET 0;

-- 1b. GET /courses: second page with the same deterministic ordering.
SELECT id, title, credits, likes
FROM courses
WHERE is_elective = false
ORDER BY likes DESC, id
LIMIT 3 OFFSET 3;

-- 2. GET /courses/{course_id}: existing course.
SELECT id, title, credits, is_elective, likes
FROM courses
WHERE id = 'api-design';

-- 2b. GET /courses/{course_id}: missing course (returns zero rows).
SELECT id, title, credits, is_elective, likes
FROM courses
WHERE id = 'no-such-course';

-- 3. POST /courses/{course_id}/like: existing and missing course examples.
-- The transaction is rolled back so the script is safe to run repeatedly.
BEGIN;
UPDATE courses
SET likes = likes + 1
WHERE id = 'api-design'
RETURNING id, likes;

UPDATE courses
SET likes = likes + 1
WHERE id = 'no-such-course'
RETURNING id, likes;
ROLLBACK;

-- 4. POST /enrollments: enroll student 3 in web-security.
-- This write is also rolled back to keep the six-row seed unchanged.
BEGIN;
INSERT INTO enrollments (course_id, student_id)
VALUES ('web-security', 3)
RETURNING id, course_id, student_id;
ROLLBACK;

-- 5. GET /enrollments: joined enrollment list.
SELECT e.id, s.name AS student, c.title AS course
FROM enrollments AS e
JOIN students AS s ON s.id = e.student_id
JOIN courses AS c ON c.id = e.course_id
ORDER BY e.id;

-- 6. GET /courses/stats: enrollment counts, including zero-enrollment courses.
SELECT c.id, count(e.id) AS enrolled
FROM courses AS c
LEFT JOIN enrollments AS e ON e.course_id = c.id
GROUP BY c.id
ORDER BY enrolled DESC, c.id;

-- 7. Bonus: courses with no enrollments.
SELECT c.id, c.title
FROM courses AS c
LEFT JOIN enrollments AS e ON e.course_id = c.id
WHERE e.id IS NULL
ORDER BY c.id;

-- 8. Bonus: students enrolled in more than one course.
SELECT s.name, count(*) AS courses
FROM students AS s
JOIN enrollments AS e ON e.student_id = s.id
GROUP BY s.id, s.name
HAVING count(*) > 1
ORDER BY courses DESC, s.name;
