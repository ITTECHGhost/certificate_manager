SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS `students`;
CREATE TABLE `students` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `full_name_ar` varchar(150) NOT NULL,
  `full_name_en` varchar(150) NOT NULL,
  `gender` tinyint(4) NOT NULL COMMENT '1: Male, 2: Female',
  `nationality_id` int(11) NOT NULL DEFAULT '274',
  `date_of_birth` date DEFAULT NULL,
  `birthplace_id` int(11) DEFAULT '2',
  `birthplace_other` varchar(100) DEFAULT NULL,
  `study_system_id` int(11) NOT NULL,
  `degree_level` tinyint(4) NOT NULL COMMENT '1: Bachelor, 2: Higher Diploma, 3: Master, 4: PhD',
  `department_id` int(11) NOT NULL,
  `admission_year` varchar(9) DEFAULT NULL,
  `graduation_date` date DEFAULT NULL,
  `graduation_semester` varchar(50) DEFAULT NULL,
  `average` float DEFAULT NULL,
  `order_id` int(11) DEFAULT NULL,
  `sequence_number` int(11) DEFAULT NULL COMMENT 'each student has their own number in case it was different from the uni_orders',
  `postgraduation_number` int(11) DEFAULT NULL COMMENT 'each student has their own number in case it was different from the uni_orders',
  `summer_training_data` varchar(20) DEFAULT NULL,
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
) ENGINE=InnoDB AUTO_INCREMENT=2137 DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `academic_periods`;
CREATE TABLE `academic_periods` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `student_id` int(11) NOT NULL,
  `academic_year` varchar(9) NOT NULL,
  `stage_number` int(11) NOT NULL,
  `semester_num` int(5) NOT NULL DEFAULT '1',
  `result_status` varchar(20) DEFAULT NULL COMMENT 'PASSED, CARRIED_OVER, EXCEPTIONAL_PASS, FAILED_REPEAT, DEFERRED, DISMISSED',
  `study_system_id` int(11) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_period_precise` (`student_id`,`academic_year`,`stage_number`,`semester_num`),
  CONSTRAINT `academic_periods_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1032 DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `enrollments`;
CREATE TABLE `enrollments` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `period_id` int(11) NOT NULL,
  `course_id` int(11) NOT NULL,
  `score` float NOT NULL,
  `passed_round` enum('1','2','3') NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `period_id` (`period_id`,`course_id`),
  KEY `course_id` (`course_id`),
  CONSTRAINT `enrollments_ibfk_1` FOREIGN KEY (`period_id`) REFERENCES `academic_periods` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `enrollments_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4126 DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `courses`;
CREATE TABLE `courses` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name_ar` varchar(100) NOT NULL,
  `name_en` varchar(100) NOT NULL,
  `credit_hours` int(11) NOT NULL,
  `department_id` int(11) DEFAULT NULL,
  `stage_number` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name_dep_units` (`name_en`,`department_id`,`credit_hours`) USING BTREE,
  UNIQUE KEY `name_dep` (`name_en`,`department_id`,`credit_hours`),
  KEY `department_id` (`department_id`),
  CONSTRAINT `courses_ibfk_1` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=310 DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `study_systems`;
CREATE TABLE `study_systems` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name_ar` varchar(60) NOT NULL,
  `name_en` varchar(60) NOT NULL,
  `study_day_type` enum('Morning','Evening','Other') NOT NULL DEFAULT 'Morning',
  `calculation_rule` enum('annual','semester') NOT NULL DEFAULT 'annual',
  `calculation_weights` varchar(100) DEFAULT '10:20:30:40',
  `period_display` enum('year','semester') DEFAULT 'semester',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `personnel`;
CREATE TABLE `personnel` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name_ar` varchar(80) NOT NULL,
  `name_en` varchar(80) NOT NULL,
  `academic_title_ar` varchar(50) DEFAULT NULL,
  `academic_title_en` varchar(50) DEFAULT NULL,
  `responsibility_ar` varchar(120) NOT NULL,
  `responsibility_en` varchar(120) NOT NULL,
  `display_order` int(11) NOT NULL DEFAULT '0',
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `personnel_role` enum('admin','user','signer') NOT NULL DEFAULT 'user',
  `university_settings_id` int(11) DEFAULT '1',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  KEY `fk_personal_univ_settings` (`university_settings_id`),
  CONSTRAINT `fk_personal_univ_settings` FOREIGN KEY (`university_settings_id`) REFERENCES `university_settings` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=37 DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS `university_settings`;
CREATE TABLE `university_settings` (
  `id` int(11) NOT NULL,
  `univ_name_ar` varchar(100) NOT NULL DEFAULT 'جامعة البصرة',
  `univ_name_en` varchar(100) NOT NULL DEFAULT 'University of Basrah',
  `college_name_ar` varchar(100) NOT NULL DEFAULT 'كلية علوم الحاسوب وتكنولوجيا المعلومات',
  `college_name_en` varchar(100) NOT NULL DEFAULT 'College of Computer Science and Information Technology',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS=1;
