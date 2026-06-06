from data.repositories import StudentRepository, AcademicPeriodRepository, EnrollmentRepository

# Let's count totals
total_students = StudentRepository().count()
print(f"Total students: {total_students}")

# Let's see some students who have academic periods
from db import get_connection
conn = get_connection()
cursor = conn.cursor(dictionary=True)

cursor.execute("SELECT student_id, COUNT(*) as c FROM academic_periods GROUP BY student_id LIMIT 10")
ap_counts = cursor.fetchall()
print("Students with academic periods:")
for row in ap_counts:
    student = StudentRepository().get_by_id(row['student_id'])
    print(f"Student ID {row['student_id']}: {student['full_name_ar'] if student else 'None'} ({row['c']} periods)")

# Let's check enrollments count
cursor.execute("SELECT COUNT(*) FROM enrollments")
total_enrollments = cursor.fetchone()['COUNT(*)']
print(f"Total enrollments in DB: {total_enrollments}")

# Let's check academic periods count
cursor.execute("SELECT COUNT(*) FROM academic_periods")
total_periods = cursor.fetchone()['COUNT(*)']
print(f"Total academic periods in DB: {total_periods}")

conn.close()
