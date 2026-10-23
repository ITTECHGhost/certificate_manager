import re

with open("data/query.py", "r", encoding="utf-8") as f:
    content = f.read()

# Convert all line endings to \n for easy replacement
content = content.replace("\r\n", "\n")

# 1. Merge university_settings into student_info
student_info_target = """        "FROM (SELECT * FROM students UNION ALL SELECT * FROM local_students) s "\n        "LEFT JOIN (SELECT * FROM departments UNION ALL SELECT * FROM local_departments) d ON s.department_id = d.id "\n        "LEFT JOIN (SELECT * FROM colleges UNION ALL SELECT * FROM local_colleges) c ON d.college_id = c.id "\n        "WHERE s.id = ?","""
student_info_repl = """        "FROM (SELECT * FROM students UNION ALL SELECT * FROM local_students) s "\n        "LEFT JOIN (SELECT * FROM departments UNION ALL SELECT * FROM local_departments) d ON s.department_id = d.id "\n        "LEFT JOIN (SELECT * FROM colleges UNION ALL SELECT * FROM local_colleges) c ON d.college_id = c.id "\n        "LEFT JOIN university_settings us ON us.id = 1 "\n        "WHERE s.id = ?","""
if student_info_target in content:
    content = content.replace(student_info_target, student_info_repl)
    print("1a success")
else:
    print("1a failed")

student_info_target_2 = """        "IFNULL(s.note_en, '') AS note_en "\n"""
student_info_repl_2 = """        "IFNULL(s.note_en, '') AS note_en, "\n        "us.univ_name_ar, "\n        "us.univ_name_en, "\n        "us.college_name_ar, "\n        "us.college_name_en, "\n        "1 AS university_settings_id "\n"""
if student_info_target_2 in content:
    content = content.replace(student_info_target_2, student_info_repl_2)
    print("1b success")
else:
    print("1b failed")

# 2. Add result_status_code and label to Q_COURSES_YEARLY_BY_ACADEMIC_YEAR
q_courses_yearly_target = """    CAST(ap.academic_year AS TEXT) AS grouping_key\nFROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap"""
q_courses_yearly_repl = """    CAST(ap.academic_year AS TEXT) AS grouping_key,\n    1 AS result_status_code,\n    'PASSED' AS result_status_label\nFROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap"""
if q_courses_yearly_target in content:
    content = content.replace(q_courses_yearly_target, q_courses_yearly_repl)
    print("2 success")
else:
    print("2 failed")

# 3. Add result_status_code and label to Q_COURSES_YEARLY_BY_PERIOD_STAGE
q_courses_stage_target = """    CAST(ap.stage_number AS TEXT) AS grouping_key\nFROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap"""
q_courses_stage_repl = """    CAST(ap.stage_number AS TEXT) AS grouping_key,\n    1 AS result_status_code,\n    'PASSED' AS result_status_label\nFROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap"""
if q_courses_stage_target in content:
    content = content.replace(q_courses_stage_target, q_courses_stage_repl)
    print("3 success")
else:
    print("3 failed")

# 4. Add result_status_code and label to Q_COURSES_YEARLY_BY_CURRICULUM_STAGE
q_courses_curr_target = """    CAST(COALESCE(c.stage_number, ap.stage_number) AS TEXT) AS grouping_key\nFROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap"""
q_courses_curr_repl = """    CAST(COALESCE(c.stage_number, ap.stage_number) AS TEXT) AS grouping_key,\n    1 AS result_status_code,\n    'PASSED' AS result_status_label\nFROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap"""
if q_courses_curr_target in content:
    content = content.replace(q_courses_curr_target, q_courses_curr_repl)
    print("4 success")
else:
    print("4 failed")

# 5. Fix timeline DISTINCT
timeline_target = """        "       REPLACE(GROUP_CONCAT(COALESCE(ap.result_status, 'PASSED')), ',', ' / ') AS result_status " """
timeline_repl = """        "       REPLACE(GROUP_CONCAT(DISTINCT COALESCE(ap.result_status, 'PASSED')), ',', ' / ') AS result_status " """
if timeline_target in content:
    content = content.replace(timeline_target, timeline_repl)
    print("5 success")
else:
    print("5 failed")

# 6. Remove float casting from courses
float_cast_target = """    # Force float for semester_num to match Pydantic API response\n    for row in res:\n        if "semester_num" in row and row["semester_num"] is not None:\n            row["semester_num"] = float(row["semester_num"])\n            \n    return res"""
if float_cast_target in content:
    content = content.replace(float_cast_target, """    return res""")
    print("6 success")
else:
    print("6 failed")

with open("data/query.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixes applied.")
