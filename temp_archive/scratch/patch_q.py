import os

file_path = os.path.join(os.path.dirname(__file__), "..", "tools", "migrate_mysql.py")
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

old_q_grouping = """    # Group rows by (old_student_id, requirment_derived_stage)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in tables.get("subjects_students_q", []):
        old_sid = _int_or(row.get("id_student"), 0)
        req     = _str(row.get("requirment", ""))
        stage   = _requirment_to_stage(req) if req else 1
        groups[(old_sid, stage)].append(row)

    periods_inserted = 0
    enrolls_inserted = 0
    skipped_students = 0

    # Map each chronological semester to a stage number
    student_sems = {}
    for (old_sid, stage) in groups.keys():
        if old_sid not in student_sems:
            student_sems[old_sid] = set()
        student_sems[old_sid].add(stage)
        
    student_stage_map_q = {}
    for old_sid, sems in student_sems.items():
        for idx, s in enumerate(sorted(list(sems))):
            student_stage_map_q[(old_sid, s)] = idx + 1

    for (old_sid, stage), rows in groups.items():"""

new_q_grouping = """    # Group rows chronologically by (old_student_id, yearr, role)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in tables.get("subjects_students_q", []):
        old_sid = _int_or(row.get("id_student"), 0)
        yearr   = _int_or(row.get("yearr", "0"), 2020)
        role    = _str(row.get("role", "الاول"))
        groups[(old_sid, yearr, role)].append(row)

    periods_inserted = 0
    enrolls_inserted = 0
    skipped_students = 0

    # Map each chronological semester to a stage number
    student_sems = {}
    for (old_sid, yearr, role) in groups.keys():
        if old_sid not in student_sems:
            student_sems[old_sid] = set()
        # map role to int for sorting
        role_int = 1 if 'اول' in role else (2 if 'ثان' in role else 3)
        student_sems[old_sid].add((yearr, role_int, role))
        
    student_stage_map_q = {}
    for old_sid, sems in student_sems.items():
        # Sort by year then by role_int
        for idx, s in enumerate(sorted(list(sems), key=lambda x: (x[0], x[1]))):
            student_stage_map_q[(old_sid, s[0], s[2])] = idx + 1

    for (old_sid, yearr, role), rows in groups.items():"""

content = content.replace(old_q_grouping, new_q_grouping)

old_q_loop = """        years = [_int_or(r.get("yearr"), 2020) for r in rows]
        year_int   = max(years)
        acad_year  = f"{year_int}-{year_int + 1}"
        
        # Override stage with strictly chronological stage
        stage = student_stage_map_q[(old_sid, stage)]"""

new_q_loop = """        year_int   = yearr
        acad_year  = f"{year_int}-{year_int + 1}"
        
        # Override stage with strictly chronological stage
        stage = student_stage_map_q[(old_sid, yearr, role)]"""

content = content.replace(old_q_loop, new_q_loop)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Migration script patched for subjects_students_q!")
