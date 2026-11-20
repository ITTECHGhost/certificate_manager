# 01 — Extract order/grade-sheet samples into the grades-matrix template (TODO A1)
- Goal: user's 3–5 order images + 3–5 grade sheets → filled `generate_grades_matrix_template` xlsx → graduation unit reviews → `/bulk-import`; measure accuracy.
- Files: none in code (session work); results note in `docs/ocr_accuracy.md`. Samples stay outside git, deleted after.
- DB / migration: none (existing bulk import).
- Tests first: none new; run `services/excel_import` parse on the produced file (`parse` must accept it).
- Risks: real student data in git or cloud logs; mis-read Arabic names; bulk-import gender bug (fixed in 4192604 — confirm on main first).
- Model: Opus (vision + Arabic judgement).
- Question: Do you approve processing the real samples in a Claude session and deleting them afterwards?
