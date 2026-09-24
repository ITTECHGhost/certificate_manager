import re
import os

with open("sql/SP.sql", "r", encoding="utf-8") as f:
    content = f.read()

procs = [
    'sp_GetCertificate_Courses_Semester_ByStage',
    'sp_GetCertificate_Courses_Semester_ByYear',
    'sp_GetCertificate_Courses_Yearly_ByPeriodStage',
    'sp_GetCertificate_Courses_Yearly_ByCurriculumStage',
    'sp_GetCertificate_Courses_Yearly_ByAcademicYear',
    'sp_GetCertificate_Yearly_ByAcademicDefualte',
    'sp_GetCertificate_StudentInfo'
]

out = []
for p in procs:
    match = re.search(rf"(CREATE.*?PROCEDURE\s+`?{p}`?\(.*?\)\s*BEGIN.*?END //)", content, re.DOTALL | re.IGNORECASE)
    if match:
        out.append(f"=== {p} ===\n{match.group(1)}\n")
    else:
        out.append(f"=== {p} NOT FOUND ===\n")

with open("scratch/query_dump.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
