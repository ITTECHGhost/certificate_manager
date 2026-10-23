import os

file_path = os.path.join(os.path.dirname(__file__), "..", "tools", "migrate_mysql.py")
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# For 140 (yearly)
old_140_loop = """    for (old_sid, yearr, sem_ar), rows in groups.items():
        new_sid = student_map.get(old_sid)
        if not new_sid:
            skipped_students += 1
            continue

        year_int    = _int_or(yearr, 2020)
        acad_year   = f"{year_int}-{year_int + 1}"

        # Derive stage from the highest course code in this group
        stages = [_code_to_stage(_str(r.get("code", "CS101"))) for r in rows]
        stage = max(stages) if stages else 1"""

new_140_loop = """    # Map each chronological year to a stage number
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

content = content.replace(old_140_loop, new_140_loop)

# For q (semester)
old_q_loop = """    for (old_sid, stage), rows in groups.items():
        new_sid = student_map.get(old_sid)
        if not new_sid:
            skipped_students += 1
            continue

        # Use the most recent yearr in this stage group for academic_year
        years = [_int_or(r.get("yearr"), 2020) for r in rows]
        year_int   = max(years)
        acad_year  = f"{year_int}-{year_int + 1}\""""

new_q_loop = """    # Map each chronological semester to a stage number
    student_sems = {}
    for (old_sid, stage) in groups.keys():
        if old_sid not in student_sems:
            student_sems[old_sid] = set()
        student_sems[old_sid].add(stage)
        
    student_stage_map_q = {}
    for old_sid, sems in student_sems.items():
        for idx, s in enumerate(sorted(list(sems))):
            student_stage_map_q[(old_sid, s)] = idx + 1

    for (old_sid, stage), rows in groups.items():
        new_sid = student_map.get(old_sid)
        if not new_sid:
            skipped_students += 1
            continue

        years = [_int_or(r.get("yearr"), 2020) for r in rows]
        year_int   = max(years)
        acad_year  = f"{year_int}-{year_int + 1}"
        
        # Override stage with strictly chronological stage
        stage = student_stage_map_q[(old_sid, stage)]"""

content = content.replace(old_q_loop, new_q_loop)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Migration script patched!")
