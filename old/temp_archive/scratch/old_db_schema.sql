CREATE TABLE `admin` (
  `id` int(11) NOT NULL,
  `name` varchar(50) NOT NULL,
  `username` varchar(50) NOT NULL,
  `password` varchar(50) NOT NULL,
  `terms` enum('مستخدم','مسؤول') NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `department` (
  `id` int(11) NOT NULL,
  `name_ar` varchar(100) NOT NULL COMMENT 'اسم القسم بالعربي',
  `name_en` varchar(100) NOT NULL COMMENT 'اسم القسم بالنكليزي'
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `info_system` (
  `id` int(11) NOT NULL,
  `university_ar` varchar(100) NOT NULL COMMENT 'اسم الجامعه ',
  `collage_ar` varchar(100) NOT NULL COMMENT 'اسم  الكلية',
  `university_en` varchar(100) NOT NULL COMMENT 'اسم الجامعه ',
  `collage_en` varchar(100) NOT NULL COMMENT 'اسم  الكلية'
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `order_university` (
  `id` int(255) NOT NULL,
  `dep` varchar(100) NOT NULL,
  `study` varchar(100) NOT NULL,
  `year_study` varchar(100) NOT NULL,
  `graduation_semester` varchar(100) DEFAULT NULL,
  `role` varchar(100) NOT NULL,
  `order_university` varchar(100) NOT NULL,
  `date` varchar(100) NOT NULL,
  `num_students` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `signatures` (
  `id` int(11) NOT NULL,
  `associate_dean` varchar(100) NOT NULL COMMENT 'معاون العميد للشوون العلميه',
  `associate_dean_en` varchar(50) NOT NULL,
  `sin_asst_dean` varchar(50) NOT NULL,
  `sin_asst_dean_en` varchar(50) NOT NULL,
  `pos_associate_dean` varchar(100) NOT NULL,
  `pos_associate_dean_en` varchar(100) NOT NULL,
  `doc_unit` varchar(100) NOT NULL COMMENT 'مسئوله وحده الوثائق',
  `doc_unit_en` varchar(50) NOT NULL,
  `sin_doc_unit` varchar(50) NOT NULL,
  `sin_doc_unit_en` varchar(50) NOT NULL,
  `pos_doc_unit` varchar(100) NOT NULL,
  `pos_doc_unit_en` varchar(100) NOT NULL,
  `doc_organize` varchar(100) NOT NULL COMMENT 'منظمه الوثيقه',
  `doc_organize_en` varchar(50) NOT NULL,
  `sin_doc_organize` varchar(50) NOT NULL,
  `sin_doc_organize_en` varchar(50) NOT NULL,
  `pos_doc_organize` varchar(100) NOT NULL,
  `pos_doc_organize_en` varchar(100) NOT NULL,
  `assist_university` varchar(100) NOT NULL COMMENT 'مساعد رئيس الجامعه للشوون العلميه',
  `assist_university_en` varchar(100) NOT NULL,
  `sin_assist_university` varchar(50) NOT NULL,
  `sin_assist_university_en` varchar(50) NOT NULL,
  `pos_assist_university` varchar(100) NOT NULL,
  `pos_assist_university_en` varchar(100) NOT NULL,
  `dean` varchar(100) NOT NULL COMMENT 'عميد الكليه',
  `dean_en` varchar(50) NOT NULL,
  `sin_dean` varchar(50) NOT NULL,
  `sin_dean_en` varchar(50) NOT NULL,
  `pos_dean` varchar(100) NOT NULL,
  `pos_dean_en` varchar(100) NOT NULL,
  `sign_m` varchar(50) NOT NULL DEFAULT 'مرتجى علي ساري' COMMENT 'مدير التسجيل',
  `sin_sign_m` varchar(50) NOT NULL DEFAULT 'المدرس الدكتور',
  `pos_sign_m` varchar(50) NOT NULL DEFAULT 'مدير التسجيل',
  `sign_m_en` varchar(50) NOT NULL DEFAULT 'Murtaja Ali Sari',
  `sin_sign_m_en` varchar(50) NOT NULL DEFAULT 'Lecturer Dr.',
  `pos_sign_m_en` varchar(50) NOT NULL DEFAULT 'Director of Registration'
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `statistics` (
  `id` int(11) NOT NULL,
  `name` varchar(50) NOT NULL,
  `organize` varchar(30) NOT NULL,
  `type_document` varchar(100) NOT NULL,
  `reciever` varchar(50) NOT NULL,
  `date` date NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `students_140` (
  `id` int(11) NOT NULL,
  `name` varchar(100) NOT NULL,
  `name_en` varchar(100) NOT NULL,
  `gender` varchar(25) NOT NULL,
  `study` varchar(25) NOT NULL,
  `department` varchar(25) NOT NULL,
  `graduation_year` varchar(25) NOT NULL,
  `graduation_semester` varchar(25) NOT NULL,
  `average` varchar(25) NOT NULL,
  `sequence` varchar(25) NOT NULL,
  `num_students` varchar(100) NOT NULL,
  `order_university` varchar(25) NOT NULL,
  `date` varchar(25) NOT NULL,
  `nationality_en` varchar(20) DEFAULT 'Iraqi',
  `birthplace_en` varchar(20) DEFAULT 'Basrah',
  `graduation_semester_en` varchar(15) DEFAULT 'First',
  `study_en` varchar(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `students_q` (
  `id` int(11) NOT NULL,
  `name` varchar(100) NOT NULL,
  `name_en` varchar(100) NOT NULL,
  `gender` varchar(25) NOT NULL,
  `study` varchar(25) NOT NULL,
  `department` varchar(25) NOT NULL,
  `graduation_year` varchar(25) NOT NULL,
  `role` varchar(25) NOT NULL,
  `average` varchar(25) NOT NULL,
  `sequence` varchar(25) NOT NULL,
  `num_students` varchar(100) NOT NULL,
  `order_university` varchar(25) NOT NULL,
  `date` varchar(25) NOT NULL,
  `nationality_en` varchar(20) DEFAULT 'Iraqi',
  `birthplace_en` varchar(20) DEFAULT 'Basrah',
  `graduation_semester_en` varchar(15) DEFAULT 'First',
  `study_en` varchar(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `subjects_140` (
  `id` int(11) NOT NULL,
  `code` varchar(100) NOT NULL COMMENT 'رمز المقرر',
  `name_ar` varchar(100) NOT NULL COMMENT 'اسم المقرر عربي',
  `name_en` varchar(100) NOT NULL COMMENT 'اسم المقرر انكليزي',
  `units` enum('1','2','3','4') DEFAULT NULL COMMENT 'الفصل',
  `dep` varchar(100) NOT NULL COMMENT 'القسم',
  `requirment` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `subjects_q` (
  `id` int(255) NOT NULL,
  `name_ar` varchar(100) DEFAULT NULL,
  `name_en` varchar(100) DEFAULT NULL,
  `units` varchar(100) DEFAULT NULL,
  `dep` varchar(100) DEFAULT NULL,
  `requirment` varchar(100) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `subjects_students_140` (
  `id` int(255) NOT NULL,
  `id_student` int(255) NOT NULL,
  `code` varchar(10) NOT NULL,
  `name_ar` varchar(100) NOT NULL,
  `name_en` varchar(100) NOT NULL,
  `requirment` varchar(100) NOT NULL,
  `units` varchar(25) NOT NULL,
  `degree` varchar(4) NOT NULL,
  `yearr` varchar(25) NOT NULL,
  `semester` varchar(25) NOT NULL,
  `failed` varchar(25) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `subjects_students_q` (
  `id` int(100) NOT NULL,
  `id_student` int(255) NOT NULL,
  `name_ar` varchar(100) NOT NULL,
  `name_en` varchar(100) NOT NULL,
  `requirment` varchar(100) NOT NULL,
  `degree` varchar(4) NOT NULL,
  `units` varchar(25) NOT NULL,
  `yearr` varchar(25) NOT NULL,
  `role` varchar(25) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

