-- norm_demo.sql: deliberately denormalized data used to explain anomalies.

DROP TABLE IF EXISTS course_enrollments_flat;

CREATE TABLE course_enrollments_flat (
    student_id     bigint NOT NULL,
    student_name   text NOT NULL,
    student_email  text NOT NULL,
    course_id      text NOT NULL,
    course_title   text NOT NULL,
    credits        integer NOT NULL
);

INSERT INTO course_enrollments_flat
    (student_id, student_name, student_email, course_id, course_title, credits)
VALUES
    (1, 'Aigerim Sadykova', 'aigerim@example.com', 'modern-frontend',
     'Modern Frontend: React & Next.js', 5),
    (1, 'Aigerim Sadykova', 'aigerim@example.com', 'ai-integration',
     'AI/LLM Integration', 5),
    (2, 'Daniyar Bekov', 'daniyar@example.com', 'modern-frontend',
     'Modern Frontend: React & Next.js', 5),
    (2, 'Daniyar Bekov', 'daniyar@example.com', 'backend-fastapi',
     'Backend Foundations: FastAPI', 5),
    (2, 'Daniyar Bekov', 'daniyar@example.com', 'ai-integration',
     'AI/LLM Integration', 5),
    (3, 'Asel Omarova', 'asel@example.com', 'ai-integration',
     'AI/LLM Integration', 5);

-- Compare the repeated student/course facts above with the normalized
-- courses, students, and enrollments tables in schema.sql.
SELECT *
FROM course_enrollments_flat
ORDER BY student_id, course_id;
