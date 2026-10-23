import os
import sys
import traceback

sys.path.insert(0, os.path.abspath("."))
from data.query import get_offline_certificate_data

print("Fetching offline data for student 2138...")
try:
    data = get_offline_certificate_data(2138, "DEFAULT")
    print("Success!")
    print(f"Student Name (AR): {data['student_info'][0].get('full_name_ar', 'N/A') if data.get('student_info') else 'N/A'}")
    print(f"Number of courses: {len(data['courses_grouped']) if data.get('courses_grouped') else 0}")
    if data.get('courses_grouped'):
        print(f"First course: {data['courses_grouped'][0]}")
except Exception as e:
    traceback.print_exc()
