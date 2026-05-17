import mysql.connector
from mysql.connector.cursor import MySQLCursorDict

# =============================================================================
# CONFIGURATION
# =============================================================================
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '12345678', # Replace with local DB password
    'charset': 'utf8mb4'
}

# =============================================================================
# DATA EXTRACTION MODULES (PATCHED)
# =============================================================================
def get_legacy_student(cursor: MySQLCursorDict, search_term: str) -> dict:
    """Retrieves student and grades from project2 (Legacy)."""
    search_query = f"%{search_term}%"
    
    # 1. Check Semester System (140)
    cursor.execute("""
        SELECT id, name AS name_ar, name_en, CAST(average AS DECIMAL(5,2)) AS average, study, department 
        FROM project2.students_140 
        WHERE name LIKE %s OR name_en LIKE %s LIMIT 1
    """, (search_query, search_query))
    student = cursor.fetchone()
    
    if student:
        cursor.execute("""
            SELECT yearr, name_ar AS course_name, CAST(degree AS DECIMAL(5,2)) AS score, failed AS round_info 
            FROM project2.subjects_students_140 WHERE id_student = %s
        """, (student['id'],))
        grades = cursor.fetchall()
        system_type = "Semester"
    else:
        # 2. Fallback to Annual System (Q)
        cursor.execute("""
            SELECT id, name AS name_ar, name_en, CAST(average AS DECIMAL(5,2)) AS average, study, department 
            FROM project2.students_q 
            WHERE name LIKE %s OR name_en LIKE %s LIMIT 1
        """, (search_query, search_query))
        student = cursor.fetchone()
        if not student:
            return None
            
        cursor.execute("""
            SELECT yearr, name_ar AS course_name, CAST(degree AS DECIMAL(5,2)) AS score, role AS round_info 
            FROM project2.subjects_students_q WHERE id_student = %s
        """, (student['id'],))
        grades = cursor.fetchall()
        system_type = "Annual"

    return {
        "core": student,
        "system": system_type,
        "grades": sorted(grades, key=lambda x: (x['yearr'], x['course_name']))
    }

def get_new_student(cursor: MySQLCursorDict, search_term: str) -> dict:
    """Retrieves normalized student and grades from certificate_manager."""
    search_query = f"%{search_term}%"
    
    cursor.execute("""
        SELECT s.id, s.full_name_ar AS name_ar, s.full_name_en AS name_en, 
               CAST(s.average AS DECIMAL(5,2)) AS average, d.name_ar AS department, 
               d.study_day_type AS study, s.study_system_id
        FROM certificate_manager.students s
        JOIN certificate_manager.departments d ON s.department_id = d.id
        WHERE s.full_name_ar LIKE %s OR s.full_name_en LIKE %s LIMIT 1
    """, (search_query, search_query))
    
    student = cursor.fetchone()
    if not student:
        return None

    system_type = "Annual" if student['study_system_id'] == 1 else "Semester"

    cursor.execute("""
        SELECT ap.academic_year AS yearr, c.name_ar AS course_name, 
               CAST(e.score AS DECIMAL(5,2)) AS score, CAST(e.passed_round AS CHAR) AS round_info
        FROM certificate_manager.enrollments e
        JOIN certificate_manager.academic_periods ap ON e.period_id = ap.id
        JOIN certificate_manager.courses c ON e.course_id = c.id
        WHERE ap.student_id = %s
    """, (student['id'],))
    
    grades = cursor.fetchall()

    return {
        "core": student,
        "system": system_type,
        "grades": sorted(grades, key=lambda x: (x['yearr'], x['course_name']))
    }

# =============================================================================
# COMPARISON ENGINE
# =============================================================================
def compare_databases(search_name: str):
    """Orchestrates connection and executes comparative logic."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        print(f"--- Starting Data Integrity Check for: '{search_name}' ---")
        
        legacy_data = get_legacy_student(cursor, search_name)
        new_data = get_new_student(cursor, search_name)

        if not legacy_data or not new_data:
            print("ERROR: Student not found in one or both databases.")
            return

        # Core Comparison
        print("\n[CORE DATA ALIGNMENT]")
        print(f"Legacy Name: {legacy_data['core']['name_ar']} | New Name: {new_data['core']['name_ar']}")
        print(f"Legacy Avg:  {legacy_data['core']['average']} | New Avg:  {new_data['core']['average']}")
        print(f"System Match: {'SUCCESS' if legacy_data['system'] == new_data['system'] else 'FAILED'}")

        # Grades Comparison
        print("\n[ACADEMIC RECORD ALIGNMENT]")
        old_course_count = len(legacy_data['grades'])
        new_course_count = len(new_data['grades'])
        
        print(f"Total Courses Migrated: {new_course_count} / {old_course_count}")
        
        if old_course_count != new_course_count:
            print("WARNING: Course counts do not match. Checking diff...")
        
        # Sample checking first 3 courses to verify data fidelity
        print("\n[SAMPLE GRADE MAPPING (First 3 Records)]")
        limit = min(3, old_course_count, new_course_count)
        for i in range(limit):
            old_g = legacy_data['grades'][i]
            new_g = new_data['grades'][i]
            
            score_match = (old_g['score'] == new_g['score'])
            print(f"Year: {old_g['yearr']} | Course: {old_g['course_name'][:20].ljust(20)} | "
                  f"Old Score: {old_g['score']} -> New Score: {new_g['score']} | Match: {score_match}")

    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

# =============================================================================
# EXECUTION
# =============================================================================
if __name__ == "__main__":
    # Test execution for the requested student
    compare_databases("Adian")
    # compare_databases("اديان") # Alternative search using Arabic