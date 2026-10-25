-- =============================================================================
-- 2026-10-24_01_fix_result_status_zero.sql
-- Repair academic periods whose result_status was stored as 0.
--
-- Cause (fixed in code, Bug Ledger #231): result_status is an INT column
-- (1=PASSED, 2=FAILED_REPEAT, 3=EXCEPTIONAL_PASS, 4=CARRIED_OVER, 5=DEFERRED,
-- 6=DISMISSED) but some paths wrote the text 'PASSED', which MySQL stores as 0.
-- Every affected row was created as PASSED (applying a study routine), so 0 -> 1.
--
-- Run in phpMyAdmin / MySQL Workbench on the certificate_manager database.
-- Step 1 only reads. Check the list, then run step 2.
-- =============================================================================

-- Step 1: preview (on 2026-10-24 there were 24 rows: students 2138, 2139, 2140)
SELECT ap.id, ap.student_id, s.full_name_ar, ap.academic_year,
       ap.stage_number, ap.semester_num, ap.result_status
FROM academic_periods ap
JOIN students s ON s.id = ap.student_id
WHERE ap.result_status = 0
ORDER BY ap.student_id, ap.stage_number, ap.semester_num;

-- Step 2: repair
UPDATE academic_periods SET result_status = 1 WHERE result_status = 0;
