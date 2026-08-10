import os

file_path = os.path.join(os.path.dirname(__file__), "..", "tools", "migrate_mysql.py")
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

old_140_loop = """    # Map each chronological year to a stage number
    student_years = {}
    for (old_sid, yearr, sem_ar) in groups.keys():
        if old_sid not in student_years:
            student_years[old_sid] = set()
        student_years[old_sid].add(_int_or(yearr, 2020))
        
    student_stage_map = {}
    for old_sid, years in student_years.items():
        for idx, y in enumerate(sorted(list(years))):
            student_stage_map[(old_sid, y)] = idx + 1

    for (old_sid, yearr, sem_ar), rows in groups.items():
        new_sid = student_map.get(old_sid)
        if not new_sid:
            skipped_students += 1
            continue

        year_int    = _int_or(yearr, 2020)
        acad_year   = f"{year_int}-{year_int + 1}"

        # Stage is strictly the chronological year (1st year = 1, 2nd year = 2...)
        stage = student_stage_map[(old_sid, year_int)]"""

new_140_loop = """    # Map each chronological semester to a stage number (1 to N)
    student_sems = {}
    for (old_sid, yearr, sem_ar) in groups.keys():
        if old_sid not in student_sems:
            student_sems[old_sid] = set()
        year_int = _int_or(yearr, 2020)
        # map semester to int for sorting
        sem_int = 1 if 'اول' in sem_ar else (2 if 'ثان' in sem_ar else 3)
        student_sems[old_sid].add((year_int, sem_int, sem_ar))
        
    student_stage_map = {}
    for old_sid, sems in student_sems.items():
        # Sort by year then by sem_int
        for idx, s in enumerate(sorted(list(sems), key=lambda x: (x[0], x[1]))):
            student_stage_map[(old_sid, s[0], s[2])] = idx + 1

    for (old_sid, yearr, sem_ar), rows in groups.items():
        new_sid = student_map.get(old_sid)
        if not new_sid:
            skipped_students += 1
            continue

        year_int    = _int_or(yearr, 2020)
        acad_year   = f"{year_int}-{year_int + 1}"

        # Stage is strictly the chronological semester (1 to N)
        stage = student_stage_map[(old_sid, year_int, sem_ar)]"""

content = content.replace(old_140_loop, new_140_loop)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Migration script patched for subjects_students_140!")
