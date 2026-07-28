-- =============================================================================
-- schema.sql — Database Table Schemas for Certificate Manager
-- =============================================================================

-- 1. University Settings
CREATE TABLE IF NOT EXISTS `university_settings` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `univ_name_ar` VARCHAR(100) NOT NULL DEFAULT 'جامعة البصرة',
  `univ_name_en` VARCHAR(100) NOT NULL DEFAULT 'University of Basrah',
  `college_name_ar` VARCHAR(100) NOT NULL DEFAULT 'كلية علوم الحاسوب وتكنولوجيا المعلومات',
  `college_name_en` VARCHAR(100) NOT NULL DEFAULT 'College of Computer Science and Information Technology',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Countries
CREATE TABLE IF NOT EXISTS `countries` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name_ar` VARCHAR(80) NOT NULL,
  `name_en` VARCHAR(80) NOT NULL,
  `iso_code` VARCHAR(3) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `iso_code` (`iso_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Governorates
CREATE TABLE IF NOT EXISTS `governorates` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name_ar` VARCHAR(40) NOT NULL,
  `name_en` VARCHAR(40) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name_ar` (`name_ar`),
  UNIQUE KEY `name_en` (`name_en`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Study Systems
CREATE TABLE IF NOT EXISTS `study_systems` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name_ar` VARCHAR(60) NOT NULL,
  `name_en` VARCHAR(60) NOT NULL,
  `study_day_type` ENUM('Morning','Evening','Other') NOT NULL DEFAULT 'Morning',
  `calculation_rule` ENUM('annual','semester') NOT NULL DEFAULT 'annual',
  `calculation_weights` VARCHAR(100) DEFAULT '10:20:30:40',
  `period_display` ENUM('year','semester') DEFAULT 'semester',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. Departments
CREATE TABLE IF NOT EXISTS `departments` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name_ar` VARCHAR(100) NOT NULL,
  `name_en` VARCHAR(100) NOT NULL,
  `university_settings_id` INT NOT NULL,
  PRIMARY KEY (`id`),
  KEY `university_settings_id` (`university_settings_id`),
  CONSTRAINT `departments_ibfk_1` FOREIGN KEY (`university_settings_id`) REFERENCES `university_settings` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. Personnel / Users
CREATE TABLE IF NOT EXISTS `personnel` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name_ar` VARCHAR(80) NOT NULL,
  `name_en` VARCHAR(80) NOT NULL,
  `academic_title_ar` VARCHAR(50) NOT NULL,
  `academic_title_en` VARCHAR(50) NOT NULL,
  `responsibility_ar` VARCHAR(120) NOT NULL,
  `responsibility_en` VARCHAR(120) NOT NULL,
  `display_order` INT NOT NULL DEFAULT 0,
  `username` VARCHAR(50) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `personnel_role` ENUM('admin','user') NOT NULL DEFAULT 'user',
  `university_settings_id` INT DEFAULT 1,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  KEY `fk_personal_univ_settings` (`university_settings_id`),
  CONSTRAINT `fk_personal_univ_settings` FOREIGN KEY (`university_settings_id`) REFERENCES `university_settings` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. User Settings (Linked to Personnel via EMP_ID)
CREATE TABLE IF NOT EXISTS `settings` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `theme` VARCHAR(20) DEFAULT 'System',
  `accent_color` VARCHAR(20) DEFAULT 'blue',
  `font_family` VARCHAR(100) DEFAULT 'Arial',
  `font_size_base` INT DEFAULT 13,
  `is_arabic_rtl` TINYINT(1) NOT NULL DEFAULT 1,
  `EMP_ID` INT NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_settings_emp_id` (`EMP_ID`),
  CONSTRAINT `fk_settings_personnel` FOREIGN KEY (`EMP_ID`) REFERENCES `personnel` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. Graduation Orders
CREATE TABLE IF NOT EXISTS `graduation_orders` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `order_number` VARCHAR(60) NOT NULL,
  `order_date` DATE NOT NULL,
  `department_id` INT NOT NULL,
  `graduation_semester` ENUM('first','second','summer') NOT NULL,
  `num_students` INT DEFAULT NULL,
  `graduation_year` INT DEFAULT NULL,
  `study_system_id` INT NOT NULL,
  `notes` VARCHAR(255) DEFAULT NULL,
  `study_type` VARCHAR(50) DEFAULT NULL,
  `admission_year` INT DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_unique_grad_order_final` (`order_number`,`department_id`,`study_system_id`,`graduation_semester`),
  KEY `department_id` (`department_id`),
  CONSTRAINT `graduation_orders_ibfk_1` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 9. Courses
CREATE TABLE IF NOT EXISTS `courses` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name_ar` VARCHAR(100) NOT NULL,
  `name_en` VARCHAR(100) NOT NULL,
  `credit_hours` INT NOT NULL,
  `department_id` INT DEFAULT NULL,
  `stage_number` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name_dep` (`name_en`,`department_id`,`credit_hours`),
  KEY `department_id` (`department_id`),
  CONSTRAINT `courses_ibfk_1` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 10. Students
CREATE TABLE IF NOT EXISTS `students` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `full_name_ar` VARCHAR(150) NOT NULL,
  `full_name_en` VARCHAR(150) NOT NULL,
  `gender` TINYINT NOT NULL COMMENT '1: Male, 2: Female',
  `nationality_id` INT NOT NULL DEFAULT 274,
  `date_of_birth` DATE DEFAULT NULL,
  `birthplace_id` INT DEFAULT 2,
  `birthplace_other` VARCHAR(100) DEFAULT NULL,
  `study_system_id` INT NOT NULL,
  `degree_level` TINYINT NOT NULL COMMENT '1: Bachelor, 2: Higher Diploma, 3: Master, 4: PhD',
  `department_id` INT NOT NULL,
  `admission_year` VARCHAR(9) DEFAULT NULL,
  `graduation_date` DATE DEFAULT NULL,
  `graduation_semester` VARCHAR(50) DEFAULT NULL,
  `average` FLOAT DEFAULT NULL,
  `order_id` INT DEFAULT NULL,
  `sequence_number` INT DEFAULT NULL COMMENT 'each student has their own number in case it was different from the uni_orders',
  `postgraduation_number` INT DEFAULT NULL COMMENT 'each student has their own number in case it was different from the uni_orders',
  `summer_training_data` VARCHAR(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `birthplace_id` (`birthplace_id`),
  KEY `nationality_id` (`nationality_id`),
  KEY `department_id` (`department_id`),
  KEY `study_system_id` (`study_system_id`),
  KEY `order_id` (`order_id`),
  CONSTRAINT `students_ibfk_1` FOREIGN KEY (`birthplace_id`) REFERENCES `governorates` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `students_ibfk_2` FOREIGN KEY (`nationality_id`) REFERENCES `countries` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `students_ibfk_3` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `students_ibfk_4` FOREIGN KEY (`study_system_id`) REFERENCES `study_systems` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `students_ibfk_5` FOREIGN KEY (`order_id`) REFERENCES `graduation_orders` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 11. Academic Periods
CREATE TABLE IF NOT EXISTS `academic_periods` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `student_id` INT NOT NULL,
  `academic_year` VARCHAR(9) NOT NULL,
  `stage_number` INT NOT NULL,
  `semester_num` INT NOT NULL DEFAULT 1,
  `study_system_id` INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_period_precise` (`student_id`,`academic_year`,`stage_number`,`semester_num`),
  CONSTRAINT `academic_periods_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 12. Enrollments
CREATE TABLE IF NOT EXISTS `enrollments` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `period_id` INT NOT NULL,
  `course_id` INT NOT NULL,
  `score` FLOAT NOT NULL,
  `passed_round` ENUM('1','2','3') NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `period_id` (`period_id`,`course_id`),
  KEY `course_id` (`course_id`),
  CONSTRAINT `enrollments_ibfk_1` FOREIGN KEY (`period_id`) REFERENCES `academic_periods` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `enrollments_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 13. Student Supervisors
CREATE TABLE IF NOT EXISTS `student_supervisors` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `student_id` INT NOT NULL,
  `personnel_id` INT NOT NULL,
  `supervision_role` ENUM('Primary Supervisor','Co-Supervisor','Committee Member') NOT NULL,
  PRIMARY KEY (`id`),
  KEY `student_id` (`student_id`),
  KEY `personnel_id` (`personnel_id`),
  CONSTRAINT `student_supervisors_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `student_supervisors_ibfk_2` FOREIGN KEY (`personnel_id`) REFERENCES `personnel` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 14. Thesis Records
CREATE TABLE IF NOT EXISTS `thesis_records` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `student_id` INT NOT NULL,
  `title_ar` VARCHAR(500) NOT NULL,
  `title_en` VARCHAR(500) NOT NULL,
  `defense_date` DATE DEFAULT NULL,
  `committee_decision` ENUM('Accepted with No Corrections','Accepted with Minor Corrections','Accepted with Major Corrections','Rejected') DEFAULT NULL,
  `final_grade` FLOAT(5,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `student_id` (`student_id`),
  CONSTRAINT `thesis_records_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
