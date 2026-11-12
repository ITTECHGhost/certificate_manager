-- 0003: (1) expected graduation year uses the order convention: the START of the academic year
--           (2025/2026 -> 2025). 0001 wrongly took the calendar year of graduation_date.
--       (2) new students get an expected year automatically: admission start + study years - 1.
--       (3) averages above 100 are refused from now on; old ones stay, and the program marks them.

-- (1) students in an order: the order's year is the truth
UPDATE `students` s
JOIN `graduation_orders` o ON o.id = s.order_id
SET s.expected_graduation_year = o.graduation_year
WHERE o.graduation_year IS NOT NULL AND o.graduation_year > 0;

-- not in an order but with a graduation date: academic year that contains the date (starts in September)
UPDATE `students`
SET `expected_graduation_year` = YEAR(`graduation_date`) - (MONTH(`graduation_date`) < 9)
WHERE (`order_id` IS NULL OR `order_id` = 0) AND `graduation_date` IS NOT NULL;

-- no date, no order: from the admission year
UPDATE `students` s
LEFT JOIN `study_systems` ss ON ss.id = s.study_system_id
SET s.expected_graduation_year = CAST(LEFT(s.admission_year, 4) AS UNSIGNED)
    + IF(COALESCE(ss.calculation_weights, '') = '', 4,
         LENGTH(ss.calculation_weights) - LENGTH(REPLACE(ss.calculation_weights, ':', '')) + 1) - 1
WHERE s.expected_graduation_year IS NULL AND s.graduation_date IS NULL
  AND (s.order_id IS NULL OR s.order_id = 0)
  AND s.admission_year REGEXP '^(19|20)[0-9]{2}';

-- (2) and (3): one trigger per event, so every way of saving a student goes through them
DROP TRIGGER IF EXISTS `trg_students_bi`;
DELIMITER //
CREATE TRIGGER `trg_students_bi` BEFORE INSERT ON `students` FOR EACH ROW
BEGIN
    DECLARE v_years INT DEFAULT 4;
    DECLARE v_w VARCHAR(100);
    IF NEW.average IS NOT NULL AND (NEW.average < 0 OR NEW.average > 100) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'average must be between 0 and 100';
    END IF;
    IF NEW.expected_graduation_year IS NULL AND NEW.admission_year REGEXP '^(19|20)[0-9]{2}' THEN
        SELECT calculation_weights INTO v_w FROM study_systems WHERE id = NEW.study_system_id;
        IF COALESCE(v_w, '') <> '' THEN
            SET v_years = LENGTH(v_w) - LENGTH(REPLACE(v_w, ':', '')) + 1;
        END IF;
        SET NEW.expected_graduation_year = CAST(LEFT(NEW.admission_year, 4) AS UNSIGNED) + v_years - 1;
    END IF;
END //
DELIMITER ;

DROP TRIGGER IF EXISTS `trg_students_bu`;
DELIMITER //
CREATE TRIGGER `trg_students_bu` BEFORE UPDATE ON `students` FOR EACH ROW
BEGIN
    DECLARE v_years INT DEFAULT 4;
    DECLARE v_w VARCHAR(100);
    -- an old wrong average may stay as it is, but a changed one must be valid
    IF NEW.average IS NOT NULL AND NOT (NEW.average <=> OLD.average)
       AND (NEW.average < 0 OR NEW.average > 100) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'average must be between 0 and 100';
    END IF;
    IF NEW.expected_graduation_year IS NULL AND NEW.admission_year REGEXP '^(19|20)[0-9]{2}' THEN
        SELECT calculation_weights INTO v_w FROM study_systems WHERE id = NEW.study_system_id;
        IF COALESCE(v_w, '') <> '' THEN
            SET v_years = LENGTH(v_w) - LENGTH(REPLACE(v_w, ':', '')) + 1;
        END IF;
        SET NEW.expected_graduation_year = CAST(LEFT(NEW.admission_year, 4) AS UNSIGNED) + v_years - 1;
    END IF;
END //
DELIMITER ;
