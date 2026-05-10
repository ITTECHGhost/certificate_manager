-- -------------------------------------------------------------------------
-- Logs & Settings
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `settings` (
    `id` INT PRIMARY KEY,
    `theme` VARCHAR(20) DEFAULT 'System',
    `accent_color` VARCHAR(20) DEFAULT 'blue',
    `font_family` VARCHAR(100) DEFAULT 'Arial',
    `font_size_base` INT DEFAULT 13,
    `is_arabic_rtl` TINYINT(1) NOT NULL DEFAULT 1,
    CONSTRAINT `check_single_row` CHECK (`id` = 1)
) ENGINE = InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `university_settings` (
    `id` INT PRIMARY KEY,
    `univ_name_ar` VARCHAR(100) NOT NULL DEFAULT 'جامعة البصرة',
    `univ_name_en` VARCHAR(100) NOT NULL DEFAULT 'University of Basrah',
    `college_name_ar` VARCHAR(100) NOT NULL DEFAULT 'كلية علوم الحاسوب وتكنولوجيا المعلومات',
    `college_name_en` VARCHAR(100) NOT NULL DEFAULT 'College of Computer Science and Information Technology',
    CONSTRAINT `chk_single_config` CHECK (`id` = 1)
) ENGINE = InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------------------------
-- countries & governorates
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS countries (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name_ar VARCHAR(80) NOT NULL,
    name_en VARCHAR(80) NOT NULL,
    iso_code VARCHAR(3) NOT NULL UNIQUE
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS governorates (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name_ar VARCHAR(40) NOT NULL UNIQUE,
    name_en VARCHAR(40) NOT NULL UNIQUE
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------
-- study_systems: Dynamic study system definitions
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS study_systems (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name_ar VARCHAR(60) NOT NULL,
    name_en VARCHAR(60) NOT NULL,
    calculation_rule ENUM ('annual', 'semester') NOT NULL,
    calculation_weights VARCHAR(100) DEFAULT '10:20:30:40',
    prefix VARCHAR(10),
    period_display ENUM ('year', 'semester') DEFAULT 'semester',
    is_active TINYINT (1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------
-- departments
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS departments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name_ar VARCHAR(100) NOT NULL,
    name_en VARCHAR(100) NOT NULL,
    university_settings_id INT NOT NULL,
    FOREIGN KEY (university_settings_id) REFERENCES university_settings (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------
-- personnel
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `personnel` (
    `id` INT PRIMARY KEY AUTO_INCREMENT,
    `name_ar` VARCHAR(80) NOT NULL,
    `name_en` VARCHAR(80) NOT NULL,
    `academic_title_ar` VARCHAR(50) NOT NULL,
    `academic_title_en` VARCHAR(50) NOT NULL,
    `responsibility_ar` VARCHAR(120) NOT NULL,
    `responsibility_en` VARCHAR(120) NOT NULL,
    `display_order` INT,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `personnel_role` ENUM('admin', 'user') NOT NULL DEFAULT 'user',
    `settings_id` INT,
    `university_settings_id` INT,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Constraints and Foreign Keys
    CONSTRAINT `chk_display_order_range` CHECK (`display_order` IS NULL OR (`display_order` >= 1 AND `display_order` <= 6)),
    CONSTRAINT `fk_personal_settings` FOREIGN KEY (`settings_id`) 
        REFERENCES `settings` (`id`) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_personal_univ_settings` FOREIGN KEY (`university_settings_id`) 
        REFERENCES `university_settings` (`id`) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------------------------
-- courses
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS courses (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name_ar VARCHAR(100) NOT NULL,
    name_en VARCHAR(100) NOT NULL,
    credit_hours INT NOT NULL CHECK (credit_hours BETWEEN 1 AND 6),
    department_id INT,
    stage_number INT NOT NULL,
    study_system_id INT NOT NULL,
    is_shared TINYINT (1) NOT NULL DEFAULT 0,
    UNIQUE (name_ar, department_id, study_system_id),
    FOREIGN KEY (department_id) REFERENCES departments (id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (study_system_id) REFERENCES study_systems (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------
-- graduation_orders (Required before students due to FK)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS graduation_orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_number VARCHAR(60) NOT NULL,
    order_date DATE NOT NULL,
    department_id INT NOT NULL,
    study_type ENUM ('morning', 'evening') NOT NULL DEFAULT 'morning',
    graduation_semester ENUM ('first', 'second') NOT NULL,
    num_students INT CHECK (num_students > 0),
    notes TEXT,
    UNIQUE (
        order_number,
        department_id,
        study_type
    ),
    FOREIGN KEY (department_id) REFERENCES departments (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------
-- students
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    id INT PRIMARY KEY AUTO_INCREMENT,
    full_name_ar VARCHAR(150) NOT NULL,
    full_name_en VARCHAR(150) NOT NULL,
    gender ENUM ('M', 'F') NOT NULL DEFAULT 'M',
    sequence_number INT,
    postgraduation_number INT,
    date_of_birth DATE NOT NULL,
    birthplace_id INT DEFAULT 1,
    birthplace_other VARCHAR(100),
    nationality_id INT NOT NULL DEFAULT 1,
    department_id INT NOT NULL,
    study_system_id INT NOT NULL,
    order_id INT,
    admission_year VARCHAR(9) NOT NULL,
    summer_training_data VARCHAR(20) DEFAULT NULL,
    average FLOAT CHECK (average BETWEEN 50 AND 100),
    FOREIGN KEY (birthplace_id) REFERENCES governorates (id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (nationality_id) REFERENCES countries (id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (department_id) REFERENCES departments (id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (study_system_id) REFERENCES study_systems (id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (order_id) REFERENCES graduation_orders (id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------
-- academic_periods & enrollments
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS academic_periods (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    academic_year VARCHAR(9) NOT NULL, -- e.g. 2023-2024
    study_system_id INT NOT NULL,
    stage_number INT NOT NULL,
    passed_round ENUM ('first', 'second') NOT NULL,
    UNIQUE (student_id, stage_number, academic_year),
    FOREIGN KEY (student_id) REFERENCES students (id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (study_system_id) REFERENCES study_systems (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS enrollments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    period_id INT NOT NULL,
    course_id INT NOT NULL,
    score FLOAT(3, 1) NOT NULL CHECK (score BETWEEN 50 AND 100),
    is_second_round TINYINT (1) NOT NULL DEFAULT 0,
    UNIQUE (period_id, course_id),
    FOREIGN KEY (period_id) REFERENCES academic_periods (id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------
-- Triggers
-- -------------------------------------------------------------------------
DELIMITER //

CREATE TRIGGER `limit_six_signatories`
BEFORE INSERT ON `personnel`
FOR EACH ROW
BEGIN
    DECLARE signer_count INT;
    
    -- Only count if the new row is attempting to be a signatory
    IF NEW.display_order IS NOT NULL THEN
        SELECT COUNT(*) INTO signer_count 
        FROM `personnel` 
        WHERE `display_order` IS NOT NULL;
        
        IF signer_count >= 6 THEN
            SIGNAL SQLSTATE '45000' 
            SET MESSAGE_TEXT = 'Operation Denied: Maximum limit of 6 signatories reached.';
        END IF;
    END IF;
END //

CREATE TRIGGER `limit_six_signatories_update`
BEFORE UPDATE ON `personnel`
FOR EACH ROW
BEGIN
    DECLARE signer_count INT;
    
    -- Check only if changing from NULL to a value
    IF OLD.display_order IS NULL AND NEW.display_order IS NOT NULL THEN
        SELECT COUNT(*) INTO signer_count 
        FROM `personnel` 
        WHERE `display_order` IS NOT NULL;
        
        IF signer_count >= 6 THEN
            SIGNAL SQLSTATE '45000' 
            SET MESSAGE_TEXT = 'Operation Denied: Maximum limit of 6 signatories reached.';
        END IF;
    END IF;
END //

DELIMITER ;


-- Seed Defualt Personnel
INSERT INTO `personnel` (
    `name_ar`, `name_en`, `academic_title_ar`, `academic_title_en`, 
    `responsibility_ar`, `responsibility_en`, `display_order`, 
    `username`, `password_hash`, `personnel_role`
)
VALUES (
    'مدير النظام', 'System Admin', 'المبرمج', 'Programmer', 
    'إدارة التقنية', 'IT Admin', NULL, '1', '1', 'admin'
);
-- Seed Study Systems
INSERT IGNORE INTO study_systems (id, name_ar, name_en, calculation_rule, prefix, period_display) 
VALUES 
(1, 'النظام الفصلي', 'Annual System', 'annual', 'A', 'year'),
(2, 'نظام المقررات', 'Semester System', 'semester', 'S', 'semester');

-- Seed Governorates
INSERT IGNORE INTO governorates (name_ar, name_en) VALUES 
('بغداد', 'Baghdad'), ('البصرة', 'Basra'), ('نينوى', 'Nineveh'), ('أربيل', 'Erbil'), 
('النجف', 'Najaf'), ('كربلاء', 'Karbala'), ('الأنبار', 'Anbar'), ('ذي قار', 'Dhi Qar'), 
('ميسان', 'Maysan'), ('واسط', 'Wasit'), ('بابل', 'Babylon'), ('ديالى', 'Diyala'), 
('صلاح الدين', 'Saladin'), ('كركوك', 'Kirkuk'), ('المثنى', 'Muthanna'), 
('القادسية', 'Al-Qadisiyyah'), ('السليمانية', 'Sulaymaniyah'), ('دهوك', 'Dohuk');

-- Seed countries
INSERT INTO countries (name_ar, name_en, iso_code) VALUES 
("AF","أفغانستان","Afghanistan"),("AL","ألبانيا","Albania"),("DZ","الجزائر","Algeria"),
("AD","أندورا","Andorra"),("AO","أنغولا","Angola"),("AG","أنتيغوا وباربودا","Antigua and Barbuda"),
("AR","الأرجنتين","Argentina"),("AM","أرمينيا","Armenia"),("AU","أستراليا","Australia"),
("AT","النمسا","Austria"),("AZ","أذربيجان","Azerbaijan"),("BS","جزر البهاما","Bahamas"),
("BH","البحرين","Bahrain"),("BD","بنغلاديش","Bangladesh"),("BB","بربادوس","Barbados"),
("BY","بيلاروسيا","Belarus"),("BE","بلجيكا","Belgium"),("BZ","بليز","Belize"),
("BJ","بنين","Benin"),("BT","بوتان","Bhutan"),("BO","بوليفيا","Bolivia"),
("BA","البوسنة والهرسك","Bosnia and Herzegovina"),("BW","بوتسوانا","Botswana"),
("BR","البرازيل","Brazil"),("BN","بروناي","Brunei"),("BG","بلغاريا","Bulgaria"),
("BF","بوركينا فاسو","Burkina Faso"),("BI","بوروندي","Burundi"),("CV","الرأس الأخضر","Cape Verde"),
("KH","كمبوديا","Cambodia"),("CM","الكاميرون","Cameroon"),("CA","كندا","Canada"),
("CF","جمهورية أفريقيا الوسطى","Central African Republic"),("TD","تشاد","Chad"),
("CL","تشيلي","Chile"),("CN","الصين","China"),("CO","كولومبيا","Colombia"),
("KM","جزر القمر","Comoros"),("CG","جمهورية الكونغو","Republic of the Congo"),
("CD","جمهورية الكونغو الديمقراطية","Democratic Republic of the Congo"),
("CR","كوستاريكا","Costa Rica"),("HR","كرواتيا","Croatia"),("CU","كوبا","Cuba"),
("CY","قبرص","Cyprus"),("CZ","جمهورية التشيك","Czech Republic"),("DK","الدنمارك","Denmark"),
("DJ","جيبوتي","Djibouti"),("DM","دومينيكا","Dominica"),("DO","جمهورية الدومينيكان","Dominican Republic"),
("EC","الإكوادور","Ecuador"),("EG","مصر","Egypt"),("SV","السلفادور","El Salvador"),
("GQ","غينيا الاستوائية","Equatorial Guinea"),("ER","إريتريا","Eritrea"),("EE","إستونيا","Estonia"),
("SZ","إسواتيني","Eswatini"),("ET","إثيوبيا","Ethiopia"),("FJ","فيجي","Fiji"),
("FI","فنلندا","Finland"),("FR","فرنسا","France"),("GA","الغابون","Gabon"),
("GM","غامبيا","Gambia"),("GE","جورجيا","Georgia"),("DE","ألمانيا","Germany"),
("GH","غانا","Ghana"),("GR","اليونان","Greece"),("GD","غرينادا","Grenada"),
("GT","غواتيمالا","Guatemala"),("GN","غينيا","Guinea"),("GW","غينيا بيساو","Guinea-Bissau"),
("GY","غيانا","Guyana"),("HT","هايتي","Haiti"),("HN","هندوراس","Honduras"),
("HU","هنغاريا","Hungary"),("IS","آيسلندا","Iceland"),("IN","الهند","India"),
("ID","إندونيسيا","Indonesia"),("IR","إيران","Iran"),("IQ","العراق","Iraq"),
("IE","أيرلندا","Ireland"),("IL","إسرائيل","Israel"),("IT","إيطاليا","Italy"),
("JM","جامايكا","Jamaica"),("JP","اليابان","Japan"),("JO","الأردن","Jordan"),
("KZ","كازاخستان","Kazakhstan"),("KE","كينيا","Kenya"),("KI","كيريباتي","Kiribati"),
("KP","كوريا الشمالية","North Korea"),("KR","كوريا الجنوبية","South Korea"),("KW","الكويت","Kuwait"),
("KG","قيرغيزستان","Kyrgyzstan"),("LA","لاوس","Laos"),("LV","لاتفيا","Latvia"),
("LB","لبنان","Lebanon"),("LS","ليسوتو","Lesotho"),("LR","ليبيريا","Liberia"),
("LY","ليبيا","Libya"),("LI","ليختنشتاين","Liechtenstein"),("LT","ليتوانيا","Lithuania"),
("LU","لوكسمبورغ","Luxembourg"),("MG","مدغشقر","Madagascar"),("MW","مالاوي","Malawi"),
("MY","ماليزيا","Malaysia"),("MV","جزر المالديف","Maldives"),("ML","مالي","Mali"),
("MT","مالطا","Malta"),("MH","جزر مارشال","Marshall Islands"),("MR","موريتانيا","Mauritania"),
("MU","موريشيوس","Mauritius"),("MX","المكسيك","Mexico"),("FM","ميكرونيزيا","Micronesia"),
("MD","مولدوفا","Moldova"),("MC","موناكو","Monaco"),("MN","منغوليا","Mongolia"),
("ME","الجبل الأسود","Montenegro"),("MA","المغرب","Morocco"),("MZ","موزمبيق","Mozambique"),
("MM","ميانمار","Myanmar"),("NA","ناميبيا","Namibia"),("NR","ناورو","Nauru"),
("NP","نيبال","Nepal"),("NL","هولندا","Netherlands"),("NZ","نيوزيلندا","New Zealand"),
("NI","نيكاراغوا","Nicaragua"),("NE","النيجر","Niger"),("NG","نيجيريا","Nigeria"),
("MK","مقدونيا الشمالية","North Macedonia"),("NO","النرويج","Norway"),("OM","عُمان","Oman"),
("PK","باكستان","Pakistan"),("PW","بالاو","Palau"),("PS","فلسطين","Palestine"),
("PA","بنما","Panama"),("PG","بابوا غينيا الجديدة","Papua New Guinea"),("PY","باراغواي","Paraguay"),
("PE","بيرو","Peru"),("PH","الفلبين","Philippines"),("PL","بولندا","Poland"),
("PT","البرتغال","Portugal"),("QA","قطر","Qatar"),("RO","رومانيا","Romania"),
("RU","روسيا","Russia"),("RW","رواندا","Rwanda"),("KN","سانت كيتس ونيفيس","Saint Kitts and Nevis"),
("LC","سانت لوسيا","Saint Lucia"),("VC","سانت فنسنت وجزر غرينادين","Saint Vincent and the Grenadines"),
("WS","ساموا","Samoa"),("SM","سان مارينو","San Marino"),("ST","ساو تومي وبرينسيبي","Sao Tome and Principe"),
("SA","المملكة العربية السعودية","Saudi Arabia"),("SN","السنغال","Senegal"),("RS","صربيا","Serbia"),
("SC","سيشل","Seychelles"),("SL","سيراليون","Sierra Leone"),("SG","سنغافورة","Singapore"),
("SK","سلوفاكيا","Slovakia"),("SI","سلوفينيا","Slovenia"),("SB","جزر سليمان","Solomon Islands"),
("SO","الصومال","Somalia"),("ZA","جنوب أفريقيا","South Africa"),("SS","جنوب السودان","South Sudan"),
("ES","إسبانيا","Spain"),("LK","سريلانكا","Sri Lanka"),("SD","السودان","Sudan"),
("SR","سورينام","Suriname"),("SE","السويد","Sweden"),("CH","سويسرا","Switzerland"),
("SY","سوريا","Syria"),("TJ","طاجيكستان","Tajikistan"),("TZ","تنزانيا","Tanzania"),
("TH","تايلاند","Thailand"),("TL","تيمور الشرقية","Timor-Leste"),("TG","توغو","Togo"),
("TO","تونغا","Tonga"),("TT","ترينيداد وتوباغو","Trinidad and Tobago"),("TN","تونس","Tunisia"),
("TR","تركيا","Turkey"),("TM","تركمانستان","Turkmenistan"),("TV","توفالو","Tuvalu"),
("UG","أوغندا","Uganda"),("UA","أوكرانيا","Ukraine"),("AE","الإمارات العربية المتحدة","United Arab Emirates"),
("GB","المملكة المتحدة","United Kingdom"),("US","الولايات المتحدة الأمريكية","United States"),
("UY","أوروغواي","Uruguay"),("UZ","أوزبكستان","Uzbekistan"),("VU","فانواتو","Vanuatu"),
("VA","الفاتيكان","Vatican City"),("VE","فنزويلا","Venezuela"),("VN","فيتنام","Vietnam"),
("YE","اليمن","Yemen"),("ZM","زامبيا","Zambia"),("ZW","زيمبابوي","Zimbabwe"),("XK","كوسوفو","Kosovo");


-- Initialize the single row of settings
INSERT IGNORE INTO `settings` (`id`) VALUES (1);