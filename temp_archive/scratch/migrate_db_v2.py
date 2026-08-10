import mysql.connector

def run_migration():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="12345678",
        database="certificate_manager"
    )
    cursor = conn.cursor()
    
    # 1. Populating admission_year from graduation_year where admission_year is NULL
    print("Checking database tables for alignment...")
    cursor.execute("DESCRIBE students")
    cols = [r[0] for r in cursor.fetchall()]
    
    if "admission_year" in cols and "graduation_year" in cols:
        print("Ensuring admission_year is populated from graduation_year...")
        cursor.execute("UPDATE students SET admission_year = graduation_year WHERE admission_year IS NULL")
        conn.commit()
        
    if "graduation_year" in cols:
        print("Dropping graduation_year column...")
        cursor.execute("ALTER TABLE students DROP COLUMN graduation_year")
        conn.commit()

    # 2. Recreate stored procedures
    print("Recreating stored procedures...")

    procedures_to_drop = [
        "InsertStudent", "UpdateStudent", "GetFullCertificateData", 
        "CountStudentsFiltered", "GetStudentsPaginated", "SearchStudentsBasic"
    ]
    for proc in procedures_to_drop:
        cursor.execute(f"DROP PROCEDURE IF EXISTS {proc}")
        conn.commit()

    # Create InsertStudent
    cursor.execute("""
    CREATE PROCEDURE `InsertStudent`(
        IN p_full_name_ar VARCHAR(150),
        IN p_full_name_en VARCHAR(150),
        IN p_gender VARCHAR(1),
        IN p_sequence_number INT,
        IN p_postgraduation_number INT,
        IN p_date_of_birth DATE,
        IN p_birthplace_id INT,
        IN p_birthplace_other VARCHAR(100),
        IN p_nationality_id INT,
        IN p_department_id INT,
        IN p_study_system_id INT,
        IN p_degree_level VARCHAR(50),
        IN p_order_id INT,
        IN p_admission_year VARCHAR(9),
        IN p_summer_training_data VARCHAR(20),
        IN p_average FLOAT,
        IN p_graduation_date DATE,
        IN p_graduation_semester VARCHAR(50)
    )
    BEGIN
        INSERT INTO students (
            full_name_ar, full_name_en, gender, sequence_number, postgraduation_number, 
            date_of_birth, birthplace_id, birthplace_other, nationality_id, department_id, 
            study_system_id, degree_level, order_id, admission_year, summer_training_data, 
            average, graduation_date, graduation_semester
        ) VALUES (
            p_full_name_ar, p_full_name_en, p_gender, p_sequence_number, p_postgraduation_number, 
            p_date_of_birth, p_birthplace_id, p_birthplace_other, p_nationality_id, p_department_id, 
            p_study_system_id, p_degree_level, p_order_id, p_admission_year, p_summer_training_data, 
            p_average, p_graduation_date, p_graduation_semester
        );
        SELECT LAST_INSERT_ID() AS new_id;
    END
    """)
    conn.commit()
    print("Created InsertStudent procedure.")

    # Create UpdateStudent
    cursor.execute("""
    CREATE PROCEDURE `UpdateStudent`(
        IN p_id INT,
        IN p_full_name_ar VARCHAR(150),
        IN p_full_name_en VARCHAR(150),
        IN p_gender VARCHAR(1),
        IN p_sequence_number INT,
        IN p_postgraduation_number INT,
        IN p_date_of_birth DATE,
        IN p_birthplace_id INT,
        IN p_birthplace_other VARCHAR(100),
        IN p_nationality_id INT,
        IN p_department_id INT,
        IN p_study_system_id INT,
        IN p_degree_level VARCHAR(50),
        IN p_order_id INT,
        IN p_admission_year VARCHAR(9),
        IN p_summer_training_data VARCHAR(20),
        IN p_average FLOAT,
        IN p_graduation_date DATE,
        IN p_graduation_semester VARCHAR(50)
    )
    BEGIN
        UPDATE students
        SET full_name_ar = p_full_name_ar,
            full_name_en = p_full_name_en,
            gender = p_gender,
            sequence_number = p_sequence_number,
            postgraduation_number = p_postgraduation_number,
            date_of_birth = p_date_of_birth,
            birthplace_id = p_birthplace_id,
            birthplace_other = p_birthplace_other,
            nationality_id = p_nationality_id,
            department_id = p_department_id,
            study_system_id = p_study_system_id,
            degree_level = p_degree_level,
            order_id = p_order_id,
            admission_year = p_admission_year,
            summer_training_data = p_summer_training_data,
            average = p_average,
            graduation_date = p_graduation_date,
            graduation_semester = p_graduation_semester
        WHERE id = p_id;
    END
    """)
    conn.commit()
    print("Created UpdateStudent procedure.")

    # Create GetFullCertificateData
    cursor.execute("""
    CREATE PROCEDURE `GetFullCertificateData`(IN p_student_id INT)
    BEGIN 
        DECLARE v_grad_year INT;
        DECLARE v_dept_id INT;
        DECLARE v_avg FLOAT;

        SELECT department_id, average, YEAR(graduation_date)
        INTO v_dept_id, v_avg, v_grad_year
        FROM students
        WHERE id = p_student_id;

        SELECT s.*, YEAR(s.graduation_date) AS graduation_year,
               d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, 
               ss.name_ar AS study_system_name_ar, ss.name_en AS study_system_name_en, 
               ss.calculation_rule, ss.calculation_weights, ss.period_display, 
               ss.study_day_type AS study_type, 
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

        SELECT (SELECT COUNT(*)+1 FROM students s2 WHERE s2.department_id = v_dept_id AND YEAR(s2.graduation_date) = v_grad_year AND s2.average > v_avg AND s2.average IS NOT NULL) AS class_rank, 
               (SELECT COUNT(*) FROM students s3 WHERE s3.department_id = v_dept_id AND YEAR(s3.graduation_date) = v_grad_year) AS total_graduates, 
               (SELECT MAX(average) FROM students s4 WHERE s4.department_id = v_dept_id AND YEAR(s4.graduation_date) = v_grad_year) AS top_average;

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

        SELECT * FROM personnel WHERE is_active = 1 AND display_order <= 4 ORDER BY display_order ASC; 
        SELECT * FROM personnel WHERE is_active = 1 AND display_order > 4 ORDER BY display_order ASC; 
        SELECT * FROM university_settings ORDER BY id ASC LIMIT 1; 
    END
    """)
    conn.commit()
    print("Created GetFullCertificateData procedure.")

    # Create CountStudentsFiltered
    cursor.execute("""
    CREATE PROCEDURE `CountStudentsFiltered`(
        IN p_search VARCHAR(150),
        IN p_dept_id INT,
        IN p_year VARCHAR(9)
    )
    BEGIN
        SELECT COUNT(*) AS total_count
        FROM students s
        WHERE (p_search IS NULL OR p_search = '' OR s.full_name_ar LIKE CONCAT('%', p_search, '%') OR s.full_name_en LIKE CONCAT('%', p_search, '%'))
          AND (p_dept_id IS NULL OR s.department_id = p_dept_id)
          AND (p_year IS NULL OR p_year = '' OR YEAR(s.graduation_date) = p_year);
    END
    """)
    conn.commit()
    print("Created CountStudentsFiltered procedure.")

    # Create GetStudentsPaginated
    cursor.execute("""
    CREATE PROCEDURE `GetStudentsPaginated`(
        IN p_limit INT,
        IN p_offset INT,
        IN p_search VARCHAR(150),
        IN p_dept_id INT,
        IN p_year VARCHAR(9)
    )
    BEGIN
        SELECT s.id, s.full_name_ar, s.full_name_en, YEAR(s.graduation_date) AS graduation_year, s.admission_year, s.average, s.order_id, 
               d.name_ar AS dept_name_ar
        FROM students s
        LEFT JOIN departments d ON s.department_id = d.id
        WHERE (p_search IS NULL OR p_search = '' OR s.full_name_ar LIKE CONCAT('%', p_search, '%') OR s.full_name_en LIKE CONCAT('%', p_search, '%'))
          AND (p_dept_id IS NULL OR s.department_id = p_dept_id)
          AND (p_year IS NULL OR p_year = '' OR YEAR(s.graduation_date) = p_year)
        ORDER BY s.full_name_ar ASC
        LIMIT p_limit OFFSET p_offset;
    END
    """)
    conn.commit()
    print("Created GetStudentsPaginated procedure.")

    # Create SearchStudentsBasic
    cursor.execute("""
    CREATE PROCEDURE `SearchStudentsBasic`(
        IN p_search_term VARCHAR(255),
        IN p_limit INT
    )
    BEGIN
        SET p_search_term = TRIM(p_search_term);

        IF CHAR_LENGTH(p_search_term) < 2 THEN
            SELECT 
                s.id AS student_id,
                s.full_name_ar AS name_ar,
                s.full_name_en AS name_en,
                d.name_ar AS dept_name_ar,
                YEAR(s.graduation_date) AS graduation_year,
                s.admission_year,
                s.average
            FROM students s
            LEFT JOIN departments d ON s.department_id = d.id
            WHERE 1 = 0;
        ELSE
            SELECT 
                s.id AS student_id,
                s.full_name_ar AS name_ar,
                s.full_name_en AS name_en,
                d.name_ar AS dept_name_ar,
                YEAR(s.graduation_date) AS graduation_year,
                s.admission_year,
                s.average
            FROM 
                students s
            LEFT JOIN departments d ON s.department_id = d.id
            WHERE 
                s.full_name_ar LIKE CONCAT('%', p_search_term, '%') 
                OR s.full_name_en LIKE CONCAT('%', p_search_term, '%')
            ORDER BY
                CASE 
                    WHEN s.full_name_ar = p_search_term OR s.full_name_en = p_search_term THEN 1
                    WHEN s.full_name_ar LIKE CONCAT(p_search_term, '%') OR s.full_name_en LIKE CONCAT(p_search_term, '%') THEN 2
                    ELSE 3 
                END,
                s.full_name_ar ASC
            LIMIT p_limit;
        END IF;
    END
    """)
    conn.commit()
    print("Created SearchStudentsBasic procedure.")

    cursor.close()
    conn.close()
    print("Migration finished successfully!")

if __name__ == "__main__":
    run_migration()
