import re

with open("data/query.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace student_info query
student_info_start = '    student = sqlite_read_one('
student_info_end = '        (st_id,)\n    )'
match = re.search(re.escape(student_info_start) + r'.*?' + re.escape(student_info_end), content, re.DOTALL)
if match:
    new_query = """    student = sqlite_read_one(
        "SELECT "
        "s.student_id, "
        "NULL AS department_id, "
        "IFNULL(s.full_name_ar, '') AS full_name_ar, "
        "IFNULL(s.full_name_en, '') AS full_name_en, "
        "ROUND(IFNULL(s.average, 0.0), 3) AS average, "
        "IFNULL(CAST(strftime('%Y', s.graduation_date) AS INTEGER), 0) AS graduation_year, "
        "IFNULL(s.graduation_date, '1970-01-01') AS graduation_date, "
        "IFNULL(s.graduation_semester, 1) AS graduation_semester, "
        "IFNULL(s.date_of_birth, '1970-01-01') AS date_of_birth, "
        "IFNULL(s.sequence_number, 0) AS sequence_number, "
        "CAST(CASE "
        "  WHEN s.postgraduation_number = 0 OR s.postgraduation_number IS NULL THEN IFNULL(o.num_students, '') "
        "  ELSE IFNULL(s.postgraduation_number, '') "
        "END AS TEXT) AS postgraduation_number, "
        "IFNULL(s.admission_year, 0) AS admission_year, "
        "IFNULL(s.summer_training_data, '') AS summer_training_data, "
        "IFNULL(s.order_id, 0) AS order_id, "
        "IFNULL(d.name_ar, '') AS dept_name_ar, "
        "IFNULL(d.name_en, '') AS dept_name_en, "
        "IFNULL(ss.name_ar, '') AS study_system_name_ar, "
        "IFNULL(ss.name_en, '') AS study_system_name_en, "
        "IFNULL(ss.calculation_rule, '') AS calculation_rule, "
        "IFNULL(ss.calculation_weights, '') AS calculation_weights, "
        "IFNULL(ss.period_display, '') AS period_display, "
        "IFNULL(ss.study_day_type, '') AS study_type, "
        "IFNULL(c.name_ar, '') AS nationality_ar, "
        "IFNULL(c.name_en, '') AS nationality_en, "
        "IFNULL(g.name_ar, '') AS birthplace_ar, "
        "IFNULL(g.name_en, '') AS birthplace_en, "
        "IFNULL(o.order_number, '') AS order_number, "
        "IFNULL(o.order_date, '1970-01-01') AS order_date, "
        "us.univ_name_ar, "
        "us.univ_name_en, "
        "us.college_name_ar, "
        "us.college_name_en, "
        "1 AS university_settings_id "
        "FROM ("
        "  SELECT id AS student_id, full_name_ar, full_name_en, sequence_number, postgraduation_number, date_of_birth, "
        "         birthplace_id, birthplace_other, nationality_id, department_id, study_system_id, "
        "         order_id, admission_year, summer_training_data, average, graduation_date, graduation_semester "
        "  FROM students "
        "  UNION ALL "
        "  SELECT id AS student_id, full_name_ar, full_name_en, sequence_number, postgraduation_number, date_of_birth, "
        "         birthplace_id, birthplace_other, nationality_id, department_id, study_system_id, "
        "         order_id, admission_year, summer_training_data, average, graduation_date, graduation_semester "
        "  FROM local_students "
        ") s "
        "LEFT JOIN departments d    ON s.department_id   = d.id "
        "LEFT JOIN study_systems ss ON s.study_system_id = ss.id "
        "LEFT JOIN countries c      ON s.nationality_id  = c.id "
        "LEFT JOIN governorates g   ON s.birthplace_id   = g.id "
        "LEFT JOIN graduation_orders o ON s.order_id = o.id "
        "LEFT JOIN university_settings us ON us.id = 1 "
        "WHERE s.student_id = ?",
        (st_id,)
    )"""
    content = content[:match.start()] + new_query + content[match.end():]
    with open("data/query.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("student_info updated")
else:
    print("Not found")
