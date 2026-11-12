-- 0004: expected graduation year, in this order:
--   1. the graduation year of the student's linked graduation order (always wins);
--   2. otherwise, if empty: admission start + study years - 1.
-- Same triggers as 0003 (average 0-100 check kept), with rule 1 added.

UPDATE `students` s
JOIN `graduation_orders` o ON o.id = s.order_id
SET s.expected_graduation_year = o.graduation_year
WHERE o.graduation_year IS NOT NULL AND o.graduation_year > 0
  AND NOT (s.expected_graduation_year <=> o.graduation_year);

DROP TRIGGER IF EXISTS `trg_students_bi`;
DELIMITER //
CREATE TRIGGER `trg_students_bi` BEFORE INSERT ON `students` FOR EACH ROW
BEGIN
    DECLARE v_years INT DEFAULT 4;
    DECLARE v_w VARCHAR(100);
    DECLARE v_order_year INT DEFAULT NULL;
    IF NEW.average IS NOT NULL AND (NEW.average < 0 OR NEW.average > 100) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'average must be between 0 and 100';
    END IF;
    IF NEW.order_id IS NOT NULL AND NEW.order_id > 0 THEN
        SELECT graduation_year INTO v_order_year FROM graduation_orders WHERE id = NEW.order_id;
    END IF;
    IF v_order_year IS NOT NULL AND v_order_year > 0 THEN
        SET NEW.expected_graduation_year = v_order_year;
    ELSEIF NEW.expected_graduation_year IS NULL AND NEW.admission_year REGEXP '^(19|20)[0-9]{2}' THEN
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
    DECLARE v_order_year INT DEFAULT NULL;
    IF NEW.average IS NOT NULL AND NOT (NEW.average <=> OLD.average)
       AND (NEW.average < 0 OR NEW.average > 100) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'average must be between 0 and 100';
    END IF;
    IF NEW.order_id IS NOT NULL AND NEW.order_id > 0 THEN
        SELECT graduation_year INTO v_order_year FROM graduation_orders WHERE id = NEW.order_id;
    END IF;
    IF v_order_year IS NOT NULL AND v_order_year > 0 THEN
        SET NEW.expected_graduation_year = v_order_year;
    ELSEIF NEW.expected_graduation_year IS NULL AND NEW.admission_year REGEXP '^(19|20)[0-9]{2}' THEN
        SELECT calculation_weights INTO v_w FROM study_systems WHERE id = NEW.study_system_id;
        IF COALESCE(v_w, '') <> '' THEN
            SET v_years = LENGTH(v_w) - LENGTH(REPLACE(v_w, ':', '')) + 1;
        END IF;
        SET NEW.expected_graduation_year = CAST(LEFT(NEW.admission_year, 4) AS UNSIGNED) + v_years - 1;
    END IF;
END //
DELIMITER ;
