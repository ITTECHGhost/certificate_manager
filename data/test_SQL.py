import mysql.connector

# 1. Establish connection
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="12345678",
    database="certificate_manager"
)

# dictionary=True treats rows as easy-to-read key/value maps
cursor = conn.cursor(dictionary=True)

# 2. Call Stored Procedure
student_id = 2
cursor.execute(f"CALL GetStudentTranscriptByID({student_id})")

# 3. Fetch FIRST result set (Profile)
# FIX: fetchone() gives us a direct dictionary object instead of wrapping it in a list
student_profile = cursor.fetchone()

# 4. Move to SECOND result set (Grades)
has_more_results = cursor.nextset()

# 5. Fetch SECOND result set
academic_transcript = []
if has_more_results:
    academic_transcript = cursor.fetchall()

# Close resources safely
cursor.close()
conn.close()

# =============================================================================
# PRINT RESULTS (Your original, unmodified display code)
# =============================================================================
print("--- STUDENT PROFILE ---")
if student_profile:
    print(f"Name: {student_profile['Arabic_Name']}")
    print(f"Department: {student_profile['Department']}")

print("\n--- ACADEMIC TRANSCRIPT ---")
for course in academic_transcript:
    print(f"Year: {course['Year']} | Semester: {course['Semester']} | Course: {course['Course_Name_AR']} | Score: {course['Final_Score']}")