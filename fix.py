import sys

path = r'f:\CR_PY\certificate_manager\nicegui_screens\certificate_screen.py'
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# The broken lines are:
# 435:         study_type_disp = "Evening" if is_english else "الم    # 4. Consolidate course history according to Rules A (Annual) & B (Semester)
# 436:     grouping_mode = str(options.get("grouping_mode") or data.get("grouping_mode") or "DEFAULT").upper()

lines[434:436] = [
    '        study_type_disp = "Evening" if is_english else "المسائية"\n',
    '    else:\n',
    '        study_type_disp = "Morning" if is_english else "الصباحية"\n',
    '\n',
    '    # 4. Consolidate course history according to Rules A (Annual) & B (Semester)\n',
    '    grouping_mode = str(options.get("grouping_mode") or data.get("grouping_mode") or "DEFAULT").upper()\n'
]

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
