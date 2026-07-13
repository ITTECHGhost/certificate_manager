import mysql.connector

def update_sp():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="12345678",
        database="certificate_manager"
    )
    cursor = conn.cursor()
    
    print("Dropping old SearchStudentsBasic procedure...")
    cursor.execute("DROP PROCEDURE IF EXISTS SearchStudentsBasic")
    conn.commit()
    
    print("Recreating SearchStudentsBasic procedure with detailed columns...")
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
                s.graduation_year,
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
                s.graduation_year,
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
    cursor.close()
    conn.close()
    print("Stored procedure updated successfully!")

if __name__ == "__main__":
    update_sp()
