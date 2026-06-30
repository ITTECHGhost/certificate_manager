import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import mysql.connector
from config import DBConfig

sql_statements = [
    "DROP PROCEDURE IF EXISTS GetAcademicPeriodsByStudent",
    """
    CREATE PROCEDURE GetAcademicPeriodsByStudent(IN p_student_id INT)
    BEGIN
        SELECT id, student_id, academic_year, stage_number, semester_num, study_system_id
        FROM academic_periods 
        WHERE student_id = p_student_id 
        ORDER BY academic_year ASC, semester_num ASC;
    END
    """,
    "DROP PROCEDURE IF EXISTS GetFullCertificateData",
    """
    CREATE PROCEDURE GetFullCertificateData(IN p_student_id INT)
    BEGIN
        SELECT s.*, 
               d.name_ar AS dept_name_ar, d.name_en AS dept_name_en,
               ss.name_ar AS study_system_name_ar, ss.name_en AS study_system_name_en,
               ss.calculation_rule, ss.calculation_weights, ss.period_display,
               c.name_ar AS nationality_ar, c.name_en AS nationality_en,
               g.name_ar AS birthplace_ar, g.name_en AS birthplace_en,
               o.order_number, o.order_date
        FROM students s
        LEFT JOIN departments d ON s.department_id = d.id
        LEFT JOIN study_systems ss ON s.study_system_id = ss.id
        LEFT JOIN countries c ON s.nationality_id = c.id
        LEFT JOIN governorates g ON s.birthplace_id = g.id
        LEFT JOIN graduation_orders o ON s.order_id = o.id
        WHERE s.id = p_student_id;

        SELECT 
            (SELECT COUNT(*)+1 FROM students s2 WHERE s2.department_id = s.department_id AND s2.admission_year = s.admission_year AND s2.average > s.average AND s2.average IS NOT NULL) AS class_rank,
            (SELECT COUNT(*) FROM students s3 WHERE s3.department_id = s.department_id AND s3.admission_year = s.admission_year) AS total_graduates,
            (SELECT MAX(average) FROM students s4 WHERE s4.department_id = s.department_id AND s4.admission_year = s.admission_year) AS top_average
        FROM students s 
        WHERE s.id = p_student_id;

        SELECT id, student_id, academic_year, stage_number, semester_num, study_system_id
        FROM academic_periods
        WHERE student_id = p_student_id
        ORDER BY academic_year ASC, semester_num ASC;

        SELECT e.id, e.period_id, e.course_id, e.score, e.passed_round,
               c.name_ar AS course_name_ar, c.name_en AS course_name_en, c.credit_hours
        FROM enrollments e
        JOIN academic_periods ap ON e.period_id = ap.id
        JOIN courses c ON e.course_id = c.id
        WHERE ap.student_id = p_student_id
        ORDER BY ap.academic_year ASC, ap.semester_num ASC, c.name_ar ASC;

        SELECT * FROM personnel 
        WHERE is_active = 1 AND display_order <= 4 
        ORDER BY display_order ASC;

        SELECT * FROM personnel 
        WHERE is_active = 1 AND display_order > 4 
        ORDER BY display_order ASC;

        SELECT * FROM university_settings ORDER BY id ASC LIMIT 1;
    END
    """
]

def update_db():
    conn = mysql.connector.connect(
        host=DBConfig.DB_HOST,
        user=DBConfig.DB_USER,
        password=DBConfig.DB_PASSWORD,
        database=DBConfig.DB_NAME
    )
    cur = conn.cursor()
    print("Updating stored procedures to include stage_number...")
    for stmt in sql_statements:
        cur.execute(stmt)
    conn.commit()
    print("Procedures updated successfully.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    update_db()
