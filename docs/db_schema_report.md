# MySQL Database Schema & Stored Procedures Report
**Database**: `certificate_manager`  
**Host**: `localhost`  
**Total Tables**: 14 | **Total Stored Procedures**: 60

---

## 📋 Database Tables

### Table: `academic_periods`  (~792 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **student_id** | `int(11)` | NO | MUL | `NULL` |  |
| **academic_year** | `varchar(9)` | NO |  | `NULL` |  |
| **stage_number** | `int(11)` | NO |  | `NULL` |  |
| **semester_num** | `int(5)` | NO |  | `1` |  |
| **study_system_id** | `int(11)` | NO |  | `1` |  |

**Foreign Keys**:
- `student_id` -> `students(id)`


### Table: `countries`  (~195 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **name_ar** | `varchar(80)` | NO |  | `NULL` |  |
| **name_en** | `varchar(80)` | NO |  | `NULL` |  |
| **iso_code** | `varchar(3)` | NO | UNI | `NULL` |  |


### Table: `courses`  (~174 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **name_ar** | `varchar(100)` | NO |  | `NULL` |  |
| **name_en** | `varchar(100)` | NO | MUL | `NULL` |  |
| **credit_hours** | `int(11)` | NO |  | `NULL` |  |
| **department_id** | `int(11)` | YES | MUL | `NULL` |  |
| **stage_number** | `int(11)` | NO |  | `NULL` |  |

**Foreign Keys**:
- `department_id` -> `departments(id)`


### Table: `departments`  (~2 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **name_ar** | `varchar(100)` | NO |  | `NULL` |  |
| **name_en** | `varchar(100)` | NO |  | `NULL` |  |
| **university_settings_id** | `int(11)` | NO | MUL | `NULL` |  |

**Foreign Keys**:
- `university_settings_id` -> `university_settings(id)`


### Table: `enrollments`  (~3013 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **period_id** | `int(11)` | NO | MUL | `NULL` |  |
| **course_id** | `int(11)` | NO | MUL | `NULL` |  |
| **score** | `float` | NO |  | `NULL` |  |
| **passed_round** | `enum('1','2','3')` | NO |  | `1` |  |

**Foreign Keys**:
- `period_id` -> `academic_periods(id)`
- `course_id` -> `courses(id)`


### Table: `governorates`  (~18 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **name_ar** | `varchar(40)` | NO | UNI | `NULL` |  |
| **name_en** | `varchar(40)` | NO | UNI | `NULL` |  |


### Table: `graduation_orders`  (~60 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **order_number** | `varchar(60)` | NO | MUL | `NULL` |  |
| **order_date** | `date` | NO |  | `NULL` |  |
| **department_id** | `int(11)` | NO | MUL | `NULL` |  |
| **graduation_semester** | `enum('first','second','summer')` | NO |  | `NULL` |  |
| **num_students** | `int(11)` | YES |  | `NULL` |  |
| **graduation_year** | `int(11)` | YES |  | `NULL` |  |
| **study_system_id** | `int(11)` | NO |  | `NULL` |  |
| **notes** | `varchar(255)` | YES |  | `NULL` |  |
| **study_type** | `varchar(50)` | YES |  | `NULL` |  |
| **admission_year** | `int(11)` | YES |  | `NULL` |  |

**Foreign Keys**:
- `department_id` -> `departments(id)`


### Table: `personnel`  (~13 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **name_ar** | `varchar(80)` | NO |  | `NULL` |  |
| **name_en** | `varchar(80)` | NO |  | `NULL` |  |
| **academic_title_ar** | `varchar(50)` | YES |  | `NULL` |  |
| **academic_title_en** | `varchar(50)` | YES |  | `NULL` |  |
| **responsibility_ar** | `varchar(120)` | NO |  | `NULL` |  |
| **responsibility_en** | `varchar(120)` | NO |  | `NULL` |  |
| **display_order** | `int(11)` | NO |  | `0` |  |
| **username** | `varchar(50)` | NO | UNI | `NULL` |  |
| **password_hash** | `varchar(255)` | NO |  | `NULL` |  |
| **personnel_role** | `enum('admin','user','signer')` | NO |  | `user` |  |
| **university_settings_id** | `int(11)` | YES | MUL | `1` |  |
| **is_active** | `tinyint(1)` | NO |  | `1` |  |
| **created_at** | `timestamp` | NO |  | `CURRENT_TIMESTAMP` |  |

**Foreign Keys**:
- `university_settings_id` -> `university_settings(id)`


### Table: `settings`  (~13 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **theme** | `varchar(20)` | YES |  | `System` |  |
| **accent_color** | `varchar(20)` | YES |  | `blue` |  |
| **font_family** | `varchar(100)` | YES |  | `Arial` |  |
| **font_size_base** | `int(11)` | YES |  | `13` |  |
| **is_arabic_rtl** | `tinyint(1)` | NO |  | `1` |  |
| **EMP_ID** | `int(11)` | NO | MUL | `NULL` |  |

**Foreign Keys**:
- `EMP_ID` -> `personnel(id)`


### Table: `students`  (~1552 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **full_name_ar** | `varchar(150)` | NO |  | `NULL` |  |
| **full_name_en** | `varchar(150)` | NO |  | `NULL` |  |
| **gender** | `tinyint(4)` | NO |  | `NULL` |  |
| **nationality_id** | `int(11)` | NO | MUL | `274` |  |
| **date_of_birth** | `date` | YES |  | `NULL` |  |
| **birthplace_id** | `int(11)` | YES | MUL | `2` |  |
| **birthplace_other** | `varchar(100)` | YES |  | `NULL` |  |
| **study_system_id** | `int(11)` | NO | MUL | `NULL` |  |
| **degree_level** | `tinyint(4)` | NO |  | `NULL` |  |
| **department_id** | `int(11)` | NO | MUL | `NULL` |  |
| **admission_year** | `varchar(9)` | YES |  | `NULL` |  |
| **graduation_date** | `date` | YES |  | `NULL` |  |
| **graduation_semester** | `varchar(50)` | YES |  | `NULL` |  |
| **average** | `float` | YES |  | `NULL` |  |
| **order_id** | `int(11)` | YES | MUL | `NULL` |  |
| **sequence_number** | `int(11)` | YES |  | `NULL` |  |
| **postgraduation_number** | `int(11)` | YES |  | `NULL` |  |
| **summer_training_data** | `varchar(20)` | YES |  | `NULL` |  |

**Foreign Keys**:
- `birthplace_id` -> `governorates(id)`
- `nationality_id` -> `countries(id)`
- `department_id` -> `departments(id)`
- `study_system_id` -> `study_systems(id)`
- `order_id` -> `graduation_orders(id)`


### Table: `student_supervisors`  (~0 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **student_id** | `int(11)` | NO | MUL | `NULL` |  |
| **personnel_id** | `int(11)` | NO | MUL | `NULL` |  |
| **supervision_role** | `enum('Primary Supervisor','Co-Supervisor','Committee Member')` | NO |  | `NULL` |  |

**Foreign Keys**:
- `student_id` -> `students(id)`
- `personnel_id` -> `personnel(id)`


### Table: `study_systems`  (~4 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **name_ar** | `varchar(60)` | NO |  | `NULL` |  |
| **name_en** | `varchar(60)` | NO |  | `NULL` |  |
| **study_day_type** | `enum('Morning','Evening','Other')` | NO |  | `Morning` |  |
| **calculation_rule** | `enum('annual','semester')` | NO |  | `annual` |  |
| **calculation_weights** | `varchar(100)` | YES |  | `10:20:30:40` |  |
| **period_display** | `enum('year','semester')` | YES |  | `semester` |  |
| **is_active** | `tinyint(1)` | NO |  | `1` |  |
| **created_at** | `timestamp` | NO |  | `CURRENT_TIMESTAMP` |  |


### Table: `thesis_records`  (~0 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` | auto_increment |
| **student_id** | `int(11)` | NO | MUL | `NULL` |  |
| **title_ar** | `varchar(500)` | NO |  | `NULL` |  |
| **title_en** | `varchar(500)` | NO |  | `NULL` |  |
| **defense_date** | `date` | YES |  | `NULL` |  |
| **committee_decision** | `enum('Accepted with No Corrections','Accepted with Minor Corrections','Accepted with Major Corrections','Rejected')` | YES |  | `NULL` |  |
| **final_grade** | `float(5,2)` | YES |  | `NULL` |  |

**Foreign Keys**:
- `student_id` -> `students(id)`


### Table: `university_settings`  (~1 rows)
| Column Name | Type | Nullable | Key | Default | Extra |
|---|---|---|---|---|---|
| **id** | `int(11)` | NO | PRI | `NULL` |  |
| **univ_name_ar** | `varchar(100)` | NO |  | `جامعة البصرة` |  |
| **univ_name_en** | `varchar(100)` | NO |  | `University of Basrah` |  |
| **college_name_ar** | `varchar(100)` | NO |  | `كلية علوم الحاسوب وتكنولوجيا المعلومات` |  |
| **college_name_en** | `varchar(100)` | NO |  | `College of Computer Science and Information Technology` |  |


---

## ⚙️ Stored Procedures

### Procedure: `AuthenticateUser`
**Parameters**:
- `IN` **p_username**: `varchar(50)`
- `IN` **p_password_hash**: `varchar(255)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `AuthenticateUser`(IN `p_username` VARCHAR(50), IN `p_password_hash` VARCHAR(255))
BEGIN
        SELECT 
        id, 
        name_ar, 
        name_en, 
        personnel_role
    FROM personnel
    WHERE username = p_username 
      AND password_hash = p_password_hash
      AND is_active = 1
    LIMIT 1;
END
```

### Procedure: `ClearAuditLogs`
**Parameters**: None

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `ClearAuditLogs`()
BEGIN
        TRUNCATE TABLE audit_log;
END
```

### Procedure: `CountStudentsFiltered`
**Parameters**:
- `IN` **p_search**: `varchar(150)`
- `IN` **p_dept_id**: `int(11)`
- `IN` **p_year**: `varchar(9)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `CountStudentsFiltered`(
        IN p_search VARCHAR(150),
        IN p_dept_id INT,
        IN p_year VARCHAR(9)
    )
BEGIN
        SELECT COUNT(*) AS total_count
        FROM students s
        WHERE (p_search IS NULL OR p_search = '' OR s.full_name_ar LIKE CONCAT('%', p_search, '%') OR s.full_name_en LIKE CONCAT('%', p_search, '%'))
          AND (p_dept_id IS NULL OR s.department_id = p_dept_id)
          AND (p_year IS NULL OR p_year = '' OR YEAR(s.graduation_date) = p_year);
    END
```

### Procedure: `Create_Default_Settings`
**Parameters**:
- `IN` **p_EMP_ID**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `Create_Default_Settings`(
    IN p_EMP_ID INT
)
BEGIN
    INSERT INTO settings (EMP_ID, theme, accent_color, font_family, font_size_base, is_arabic_rtl)
    VALUES (
        p_EMP_ID, 
        'light',               'blue',               'Arial',              14,                   1                 );
END
```

### Procedure: `DeleteDepartment`
**Parameters**:
- `IN` **p_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteDepartment`(IN p_id INT)
BEGIN
    DELETE FROM departments WHERE id = p_id;
END
```

### Procedure: `DeleteGraduationOrder`
**Parameters**:
- `IN` **p_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteGraduationOrder`(IN p_id INT)
BEGIN
        UPDATE students SET order_id = NULL WHERE order_id = p_id;
        DELETE FROM graduation_orders WHERE id = p_id;
END
```

### Procedure: `DeletePersonnel`
**Parameters**:
- `IN` **p_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeletePersonnel`(
    IN p_id INT
)
BEGIN
    DELETE FROM personnel WHERE id = p_id;
END
```

### Procedure: `DeleteStudent`
**Parameters**:
- `IN` **p_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteStudent`(IN p_id INT)
BEGIN
    DELETE FROM students WHERE id = p_id;
END
```

### Procedure: `DeleteStudentSupervisor`
**Parameters**:
- `IN` **p_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteStudentSupervisor`(IN p_id INT)
BEGIN
        DELETE FROM student_supervisors WHERE id = p_id;
    END
```

### Procedure: `DeleteStudySystem`
**Parameters**:
- `IN` **p_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteStudySystem`(IN p_id INT)
BEGIN
    DELETE FROM study_systems WHERE id = p_id;
END
```

### Procedure: `DeleteThesis`
**Parameters**:
- `IN` **p_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteThesis`(IN p_id INT)
BEGIN
        DELETE FROM thesis_records WHERE id = p_id;
    END
```

### Procedure: `GetAcademicPeriodsByStudent`
**Parameters**:
- `IN` **p_student_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAcademicPeriodsByStudent`(IN p_student_id INT)
BEGIN
        SELECT id, student_id, academic_year, stage_number, semester_num, study_system_id
        FROM academic_periods 
        WHERE student_id = p_student_id 
        ORDER BY academic_year ASC, semester_num ASC;
    END
```

### Procedure: `GetActivePersonnel`
**Parameters**: None

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetActivePersonnel`()
BEGIN
    SELECT id, name_ar, name_en, academic_title_ar, academic_title_en, 
           responsibility_ar, responsibility_en, display_order 
    FROM personnel 
    WHERE is_active = 1 ORDER BY display_order ASC;
END
```

### Procedure: `GetActiveStudySystems`
**Parameters**: None

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetActiveStudySystems`()
BEGIN
    SELECT id, name_ar, name_en, study_day_type, calculation_rule, 
           calculation_weights, period_display
    FROM study_systems 
    WHERE is_active = 1 ORDER BY id ASC;
END
```

### Procedure: `GetAllCountries`
**Parameters**: None

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllCountries`()
BEGIN
    SELECT id, name_ar, name_en, iso_code FROM countries ORDER BY name_en ASC;
END
```

### Procedure: `GetAllCourses`
**Parameters**: None

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllCourses`()
BEGIN
    SELECT 
        c.id, 
        c.name_ar, 
        c.name_en, 
        c.credit_hours, 
        c.stage_number,
        c.study_system_id, 
        c.is_shared,
        c.department_id,
        COALESCE(
            d.name_ar, 
            (SELECT GROUP_CONCAT(d2.name_ar SEPARATOR '، ') 
             FROM course_departments cd 
             JOIN departments d2 ON cd.department_id = d2.id 
             WHERE cd.course_id = c.id)
        ) AS dept_name_ar,
        COALESCE(
            d.name_en, 
            (SELECT GROUP_CONCAT(d2.name_en SEPARATOR ', ') 
             FROM course_departments cd 
             JOIN departments d2 ON cd.department_id = d2.id 
             WHERE cd.course_id = c.id)
        ) AS dept_name_en,
        s.name_ar AS study_system_name_ar,
        s.name_en AS study_system_name_en
    FROM courses c
    LEFT JOIN departments d ON c.department_id = d.id
    LEFT JOIN study_systems s ON c.study_system_id = s.id
    ORDER BY c.name_ar ASC;
END
```

### Procedure: `GetAllDepartments`
**Parameters**: None

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllDepartments`()
BEGIN
    SELECT d.id, d.name_ar, d.name_en, u.college_name_ar, u.college_name_en
    FROM departments d
    LEFT JOIN university_settings u ON d.university_settings_id = u.id
    ORDER BY d.name_ar ASC;
END
```

### Procedure: `GetAllGovernorates`
**Parameters**: None

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllGovernorates`()
BEGIN
    SELECT id, name_ar, name_en FROM governorates ORDER BY id ASC;
END
```

### Procedure: `GetAllGraduationOrders`
**Parameters**:
- `IN` **p_limit**: `int(11)`
- `IN` **p_offset**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllGraduationOrders`(
    IN p_limit INT,
    IN p_offset INT
)
BEGIN
    SELECT 
        o.id, 
        o.order_number, 
        o.order_date, 
        o.department_id, 
        d.name_ar AS dept_name_ar, 
        d.name_en AS dept_name_en, 
        o.study_type, 
        o.graduation_year,         o.graduation_semester, 
        o.num_students, 
        o.notes, 
        o.study_system_id,
        (SELECT COUNT(s.id) FROM students s WHERE s.order_id = o.id) AS linked_count
    FROM graduation_orders o
    JOIN departments d ON o.department_id = d.id
    ORDER BY o.id DESC     LIMIT p_limit OFFSET p_offset; END
```

### Procedure: `GetAllPersonnel`
**Parameters**: None

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllPersonnel`()
BEGIN
    SELECT 
        p.id,
        COALESCE(p.name_ar, '') AS name_ar,
        COALESCE(p.name_en, '') AS name_en,
        COALESCE(p.academic_title_ar, '') AS academic_title_ar,
        COALESCE(p.academic_title_en, '') AS academic_title_en,
        COALESCE(p.responsibility_ar, '') AS responsibility_ar,
        COALESCE(p.responsibility_en, '') AS responsibility_en,
        COALESCE(p.display_order, 0) AS display_order,
        CASE 
            WHEN COALESCE(p.display_order, 0) > 0 THEN TRUE 
            ELSE FALSE 
        END AS is_signature,
        COALESCE(p.display_order, 0) AS page_location,
        COALESCE(p.username, '') AS username,
        COALESCE(p.personnel_role, 'user') AS personnel_role,
        COALESCE(p.university_settings_id, 1) AS university_settings_id,
        COALESCE(p.is_active, 1) AS is_active,
        p.created_at
    FROM personnel p
    LEFT JOIN university_settings us ON p.university_settings_id = us.id
    ORDER BY p.display_order ASC, p.id ASC;
END
```

### Procedure: `GetAllStudySystems`
**Parameters**: None

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllStudySystems`()
BEGIN
    SELECT id, name_ar, name_en, study_day_type, calculation_rule, 
           calculation_weights, period_display, is_active, created_at
    FROM study_systems ORDER BY id ASC;
END
```

### Procedure: `GetCoursesByDepartment`
**Parameters**:
- `IN` **p_dept_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetCoursesByDepartment`(IN p_dept_id INT)
BEGIN
    SELECT c.id, c.name_ar, c.name_en, c.credit_hours, c.study_system_id, c.is_shared
    FROM courses c
    WHERE c.department_id = p_dept_id 
       OR (c.is_shared = 1 AND c.id IN (SELECT course_id FROM course_departments WHERE department_id = p_dept_id))
    ORDER BY c.name_ar ASC;
END
```

### Procedure: `GetDepartmentByID`
**Parameters**:
- `IN` **p_dept_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetDepartmentByID`(IN p_dept_id INT)
BEGIN
    SELECT d.id, d.name_ar, d.name_en, u.college_name_ar, u.college_name_en
    FROM departments d
    LEFT JOIN university_settings u ON d.university_settings_id = u.id
    WHERE d.id = p_dept_id;
END
```

### Procedure: `GetEnrollmentsByPeriod`
**Parameters**:
- `IN` **p_period_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetEnrollmentsByPeriod`(IN p_period_id INT)
BEGIN
    SELECT e.id, e.period_id, e.course_id, e.score, e.passed_round,
           c.name_ar AS course_name_ar, c.name_en AS course_name_en, c.credit_hours
    FROM enrollments e 
    JOIN courses c ON e.course_id = c.id 
    WHERE e.period_id = p_period_id
    ORDER BY c.name_ar ASC;
END
```

### Procedure: `GetFullCertificateData`
**Parameters**:
- `IN` **p_student_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetFullCertificateData`(IN p_student_id INT)
BEGIN 
        DECLARE v_grad_year INT;
        DECLARE v_dept_id INT;
        DECLARE v_avg FLOAT;

        SELECT department_id, average, YEAR(graduation_date)
        INTO v_dept_id, v_avg, v_grad_year
        FROM students
        WHERE id = p_student_id;

        SELECT s.*, YEAR(s.graduation_date) AS graduation_year,
               d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, 
               ss.name_ar AS study_system_name_ar, ss.name_en AS study_system_name_en, 
               ss.calculation_rule, ss.calculation_weights, ss.period_display, 
               ss.study_day_type AS study_type, 
               c.name_ar AS nationality_ar, c.name_en AS nationality_en, 
               g.name_ar AS birthplace_ar, g.name_en AS birthplace_en, 
               o.order_number, o.order_date 
        FROM students s 
        LEFT JOIN departments d ON s.department_id = d.id 
        LEFT JOIN study_systems ss ON s.study_system_id = ss.id 
        LEFT JOIN countries c ON s.nationality_id = c.id 
        LEFT JOIN governorates g ON s.birthplace_id = g.id 
        LEFT JOIN graduation_orders o ON s.order_id = o.id 
        WHERE s.id = p_student_id; 

        SELECT (SELECT COUNT(*)+1 FROM students s2 WHERE s2.department_id = v_dept_id AND YEAR(s2.graduation_date) = v_grad_year AND s2.average > v_avg AND s2.average IS NOT NULL) AS class_rank, 
               (SELECT COUNT(*) FROM students s3 WHERE s3.department_id = v_dept_id AND YEAR(s3.graduation_date) = v_grad_year) AS total_graduates, 
               (SELECT MAX(average) FROM students s4 WHERE s4.department_id = v_dept_id AND YEAR(s4.graduation_date) = v_grad_year) AS top_average;

        SELECT id, student_id, academic_year, stage_number, semester_num, study_system_id 
        FROM academic_periods 
        WHERE student_id = p_student_id 
        ORDER BY academic_year ASC, semester_num ASC; 

        SELECT e.id, e.period_id, e.course_id, e.score, e.passed_round, 
               c.name_ar AS course_name_ar, c.name_en AS course_name_en, c.credit_hours 
        FROM enrollments e 
        JOIN academic_periods ap ON e.period_id = ap.id 
        JOIN courses c ON e.course_id = c.id 
        WHERE ap.student_id = p_student_id 
        ORDER BY ap.academic_year ASC, ap.semester_num ASC, c.name_ar ASC; 

        SELECT * FROM personnel WHERE is_active = 1 AND display_order <= 4 ORDER BY display_order ASC; 
        SELECT * FROM personnel WHERE is_active = 1 AND display_order > 4 ORDER BY display_order ASC; 
        SELECT * FROM university_settings ORDER BY id ASC LIMIT 1; 
    END
```

### Procedure: `GetGraduationOrderByID`
**Parameters**:
- `IN` **p_order_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetGraduationOrderByID`(IN p_order_id INT)
BEGIN
    SELECT o.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en 
    FROM graduation_orders o
    JOIN departments d ON o.department_id = d.id
    WHERE o.id = p_order_id;
END
```

### Procedure: `GetPersonnelById`
**Parameters**:
- `IN` **p_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetPersonnelById`(
    IN p_id INT
)
BEGIN
    SELECT 
        p.id,
        COALESCE(p.name_ar, '') AS name_ar,
        COALESCE(p.name_en, '') AS name_en,
        p.academic_title_ar,
        p.academic_title_en,
        COALESCE(p.responsibility_ar, '') AS responsibility_ar,
        COALESCE(p.responsibility_en, '') AS responsibility_en,
        COALESCE(p.display_order, 0) AS display_order,
        CASE 
            WHEN COALESCE(p.display_order, 0) > 0 THEN TRUE 
            ELSE FALSE 
        END AS is_signature,
        COALESCE(p.display_order, 0) AS page_location,
        COALESCE(p.username, '') AS username,
        COALESCE(p.personnel_role, 'user') AS personnel_role,
        p.university_settings_id,
        COALESCE(p.is_active, 1) AS is_active,
        p.created_at
    FROM personnel p
    LEFT JOIN university_settings us ON p.university_settings_id = us.id
    WHERE p.id = p_id
    LIMIT 1;
END
```

### Procedure: `GetStudentDossierByID`
**Parameters**:
- `IN` **p_student_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudentDossierByID`(IN p_student_id INT)
BEGIN 
    SELECT s.*, YEAR(s.graduation_date) AS graduation_year, 
           d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, 
           ss.name_ar AS study_system_name_ar, ss.name_en AS study_system_name_en, 
           ss.study_day_type AS study_type, 
           c.name_ar AS nationality_ar, c.name_en AS nationality_en, 
           g.name_ar AS birthplace_ar, g.name_en AS birthplace_en, 
           o.order_number, o.order_date, o.graduation_semester AS order_graduation_semester 
    FROM students s 
    LEFT JOIN departments d ON s.department_id = d.id 
    LEFT JOIN study_systems ss ON s.study_system_id = ss.id 
    LEFT JOIN countries c ON s.nationality_id = c.id 
    LEFT JOIN governorates g ON s.birthplace_id = g.id 
    LEFT JOIN graduation_orders o ON s.order_id = o.id 
    WHERE s.id = p_student_id; 
END
```

### Procedure: `GetStudentsByOrder`
**Parameters**:
- `IN` **p_order_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudentsByOrder`(IN p_order_id INT)
BEGIN
    SELECT s.id, s.full_name_ar, s.full_name_en, s.average, 
           s.graduation_date, s.graduation_semester, 
           d.name_ar AS dept_name_ar
    FROM students s
    JOIN departments d ON s.department_id = d.id
    WHERE s.order_id = p_order_id
    ORDER BY s.average DESC;
END
```

### Procedure: `GetStudentsPaginated`
**Parameters**:
- `IN` **p_limit**: `int(11)`
- `IN` **p_offset**: `int(11)`
- `IN` **p_search**: `varchar(150)`
- `IN` **p_dept_id**: `int(11)`
- `IN` **p_year**: `varchar(9)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudentsPaginated`(
        IN p_limit INT,
        IN p_offset INT,
        IN p_search VARCHAR(150),
        IN p_dept_id INT,
        IN p_year VARCHAR(9)
    )
BEGIN
        SELECT s.id, s.full_name_ar, s.full_name_en, YEAR(s.graduation_date) AS graduation_year, s.admission_year, s.average, s.order_id, 
               d.name_ar AS dept_name_ar
        FROM students s
        LEFT JOIN departments d ON s.department_id = d.id
        WHERE (p_search IS NULL OR p_search = '' OR s.full_name_ar LIKE CONCAT('%', p_search, '%') OR s.full_name_en LIKE CONCAT('%', p_search, '%'))
          AND (p_dept_id IS NULL OR s.department_id = p_dept_id)
          AND (p_year IS NULL OR p_year = '' OR YEAR(s.graduation_date) = p_year)
        ORDER BY s.full_name_ar ASC
        LIMIT p_limit OFFSET p_offset;
    END
```

### Procedure: `GetStudentTranscriptByID`
**Parameters**:
- `IN` **p_student_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudentTranscriptByID`(
    IN p_student_id INT
)
BEGIN
                SELECT 
        s.`id` AS `Student_ID`,
        s.`full_name_ar` AS `Arabic_Name`,
        s.`full_name_en` AS `English_Name`,
        s.`gender` AS `Gender`,
        s.`date_of_birth` AS `DOB`,
        gov.`name_ar` AS `Birthplace`,
        nat.`name_ar` AS `Nationality`,
        d.`name_ar` AS `Department`,
        s.`degree_level` AS `Degree_Level`,
        s.`admission_year` AS `Admission_Year`,
        s.`average` AS `Final_Average`,
        go.`order_number` AS `Graduation_Order_No`,
        go.`order_date` AS `Graduation_Order_Date`
    FROM `certificate_manager`.`students` AS s
    
        LEFT JOIN `certificate_manager`.`departments` AS d ON s.`department_id` = d.`id`
    LEFT JOIN `certificate_manager`.`governorates` AS gov ON s.`birthplace_id` = gov.`id`
    LEFT JOIN `certificate_manager`.`countries` AS nat ON s.`nationality_id` = nat.`id`
    LEFT JOIN `certificate_manager`.`graduation_orders` AS go ON s.`order_id` = go.`id`
    
    WHERE s.`id` = p_student_id;

                SELECT 
        ap.`academic_year` AS `Year`,
        ap.`semester_num` AS `Semester`,
        c.`name_ar` AS `Course_Name_AR`,
        c.`name_en` AS `Course_Name_EN`,
        c.`credit_hours` AS `Units`,
        e.`score` AS `Final_Score`,
        e.`passed_round` AS `Attempt_Round`
    FROM `certificate_manager`.`academic_periods` AS ap
    
    INNER JOIN `certificate_manager`.`enrollments` AS e 
        ON ap.`id` = e.`period_id`
        
    INNER JOIN `certificate_manager`.`courses` AS c 
        ON e.`course_id` = c.`id`
        
    WHERE ap.`student_id` = p_student_id
    
        ORDER BY 
        ap.`academic_year` ASC,
        ap.`semester_num` ASC;
        
END
```

### Procedure: `GetStudySystemByID`
**Parameters**:
- `IN` **p_system_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudySystemByID`(IN p_system_id INT)
BEGIN
    SELECT * FROM study_systems WHERE id = p_system_id;
END
```

### Procedure: `GetSupervisorsByStudent`
**Parameters**:
- `IN` **p_student_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetSupervisorsByStudent`(IN p_student_id INT)
BEGIN
        SELECT ss.id, ss.student_id, ss.personnel_id, ss.supervision_role,
               p.name_ar AS supervisor_name_ar, p.name_en AS supervisor_name_en, p.academic_title_ar, p.academic_title_en
        FROM student_supervisors ss JOIN personnel p ON ss.personnel_id = p.id
        WHERE ss.student_id = p_student_id ORDER BY ss.supervision_role ASC, p.display_order ASC;
    END
```

### Procedure: `GetSystemSettings`
**Parameters**: None

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetSystemSettings`()
BEGIN
    SELECT * FROM settings ORDER BY id ASC LIMIT 1;
END
```

### Procedure: `GetThesisByStudent`
**Parameters**:
- `IN` **p_student_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetThesisByStudent`(IN p_student_id INT)
BEGIN
        SELECT id, student_id, title_ar, title_en, defense_date, committee_decision, final_grade
        FROM thesis_records WHERE student_id = p_student_id ORDER BY id DESC;
    END
```

### Procedure: `GetUserPreferences`
**Parameters**:
- `IN` **p_emp_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetUserPreferences`(IN p_emp_id INT)
BEGIN CALL Get_User_Settings(p_emp_id); END
```

### Procedure: `Get_dashboard_counts`
**Parameters**: None

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `Get_dashboard_counts`()
BEGIN
        SELECT 
        COALESCE((SELECT COUNT(id) FROM students), 0) AS total_students,
        COALESCE((SELECT COUNT(id) FROM departments), 0) AS total_departments,
        COALESCE((SELECT COUNT(id) FROM courses), 0) AS total_courses,
        COALESCE((SELECT COUNT(id) FROM personnel), 0) AS total_personnel;
END
```

### Procedure: `Get_User_Settings`
**Parameters**:
- `IN` **p_emp_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `Get_User_Settings`(
    IN p_emp_id INT
)
BEGIN
    SELECT 
        s.id,
        COALESCE(s.theme, 'Dark') AS theme,
        COALESCE(s.accent_color, 'blue') AS accent_color,
        COALESCE(s.font_family, 'Arial') AS font_family,
        COALESCE(s.font_size_base, 14) AS font_size_base,
        COALESCE(s.is_arabic_rtl, 1) AS is_arabic_rtl
    FROM settings s
    WHERE s.id = p_emp_id
    LIMIT 1;
END
```

### Procedure: `InsertDepartment`
**Parameters**:
- `IN` **p_name_ar**: `varchar(100)`
- `IN` **p_name_en**: `varchar(100)`
- `IN` **p_university_settings_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertDepartment`(
    IN p_name_ar VARCHAR(100),
    IN p_name_en VARCHAR(100),
    IN p_university_settings_id INT
)
BEGIN
    INSERT INTO departments (name_ar, name_en, university_settings_id)
    VALUES (p_name_ar, p_name_en, p_university_settings_id);
    SELECT LAST_INSERT_ID() AS new_id;
END
```

### Procedure: `InsertGraduationOrder`
**Parameters**:
- `IN` **p_order_number**: `varchar(60)`
- `IN` **p_order_date**: `date`
- `IN` **p_department_id**: `int(11)`
- `IN` **p_study_type**: `varchar(50)`
- `IN` **p_graduation_year**: `int(11)`
- `IN` **p_graduation_semester**: `varchar(50)`
- `IN` **p_num_students**: `int(11)`
- `IN` **p_notes**: `varchar(255)`
- `IN` **p_study_system_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertGraduationOrder`(
    IN p_order_number VARCHAR(60),
    IN p_order_date DATE,
    IN p_department_id INT,
    IN p_study_type VARCHAR(50),
    IN p_graduation_year INT,
    IN p_graduation_semester VARCHAR(50),
    IN p_num_students INT,
    IN p_notes VARCHAR(255),
    IN p_study_system_id INT
)
BEGIN
    INSERT INTO graduation_orders (
        order_number, order_date, department_id, study_type, 
        graduation_year, graduation_semester, num_students, notes, study_system_id
    ) VALUES (
        p_order_number, p_order_date, p_department_id, p_study_type, 
        p_graduation_year, p_graduation_semester, p_num_students, p_notes, p_study_system_id
    );
    SELECT LAST_INSERT_ID() AS new_id;
END
```

### Procedure: `InsertPersonnel`
**Parameters**:
- `IN` **p_name_ar**: `varchar(80)`
- `IN` **p_name_en**: `varchar(80)`
- `IN` **p_academic_title_ar**: `varchar(50)`
- `IN` **p_academic_title_en**: `varchar(50)`
- `IN` **p_responsibility_ar**: `varchar(120)`
- `IN` **p_responsibility_en**: `varchar(120)`
- `IN` **p_display_order**: `int(11)`
- `IN` **p_username**: `varchar(50)`
- `IN` **p_password_hash**: `varchar(255)`
- `IN` **p_personnel_role**: `varchar(20)`
- `IN` **p_university_settings_id**: `int(11)`
- `IN` **p_is_active**: `tinyint(1)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertPersonnel`(
    IN p_name_ar VARCHAR(80),
    IN p_name_en VARCHAR(80),
    IN p_academic_title_ar VARCHAR(50),
    IN p_academic_title_en VARCHAR(50),
    IN p_responsibility_ar VARCHAR(120),
    IN p_responsibility_en VARCHAR(120),
    IN p_display_order INT,
    IN p_username VARCHAR(50),
    IN p_password_hash VARCHAR(255),
    IN p_personnel_role VARCHAR(20),
    IN p_university_settings_id INT,
    IN p_is_active TINYINT(1)
)
BEGIN
    INSERT INTO personnel (
        name_ar,
        name_en,
        academic_title_ar,
        academic_title_en,
        responsibility_ar,
        responsibility_en,
        display_order,
        username,
        password_hash,
        personnel_role,
        university_settings_id,
        is_active
    ) VALUES (
        TRIM(p_name_ar),
        TRIM(p_name_en),
        IF(TRIM(p_academic_title_ar) = '', NULL, TRIM(p_academic_title_ar)),
        IF(TRIM(p_academic_title_en) = '', NULL, TRIM(p_academic_title_en)),
        TRIM(p_responsibility_ar),
        TRIM(p_responsibility_en),
        COALESCE(p_display_order, 0),
        TRIM(p_username),
        p_password_hash,
        COALESCE(p_personnel_role, 'user'),
        p_university_settings_id,
        COALESCE(p_is_active, 1)
    );

    SELECT LAST_INSERT_ID() AS inserted_id;
END
```

### Procedure: `InsertStudent`
**Parameters**:
- `IN` **p_full_name_ar**: `varchar(150)`
- `IN` **p_full_name_en**: `varchar(150)`
- `IN` **p_gender**: `varchar(1)`
- `IN` **p_sequence_number**: `int(11)`
- `IN` **p_postgraduation_number**: `int(11)`
- `IN` **p_date_of_birth**: `date`
- `IN` **p_birthplace_id**: `int(11)`
- `IN` **p_birthplace_other**: `varchar(100)`
- `IN` **p_nationality_id**: `int(11)`
- `IN` **p_department_id**: `int(11)`
- `IN` **p_study_system_id**: `int(11)`
- `IN` **p_degree_level**: `varchar(50)`
- `IN` **p_order_id**: `int(11)`
- `IN` **p_admission_year**: `varchar(9)`
- `IN` **p_summer_training_data**: `varchar(20)`
- `IN` **p_average**: `float`
- `IN` **p_graduation_date**: `date`
- `IN` **p_graduation_semester**: `varchar(50)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertStudent`(
        IN p_full_name_ar VARCHAR(150),
        IN p_full_name_en VARCHAR(150),
        IN p_gender VARCHAR(1),
        IN p_sequence_number INT,
        IN p_postgraduation_number INT,
        IN p_date_of_birth DATE,
        IN p_birthplace_id INT,
        IN p_birthplace_other VARCHAR(100),
        IN p_nationality_id INT,
        IN p_department_id INT,
        IN p_study_system_id INT,
        IN p_degree_level VARCHAR(50),
        IN p_order_id INT,
        IN p_admission_year VARCHAR(9),
        IN p_summer_training_data VARCHAR(20),
        IN p_average FLOAT,
        IN p_graduation_date DATE,
        IN p_graduation_semester VARCHAR(50)
    )
BEGIN
        INSERT INTO students (
            full_name_ar, full_name_en, gender, sequence_number, postgraduation_number, 
            date_of_birth, birthplace_id, birthplace_other, nationality_id, department_id, 
            study_system_id, degree_level, order_id, admission_year, summer_training_data, 
            average, graduation_date, graduation_semester
        ) VALUES (
            p_full_name_ar, p_full_name_en, p_gender, p_sequence_number, p_postgraduation_number, 
            p_date_of_birth, p_birthplace_id, p_birthplace_other, p_nationality_id, p_department_id, 
            p_study_system_id, p_degree_level, p_order_id, p_admission_year, p_summer_training_data, 
            p_average, p_graduation_date, p_graduation_semester
        );
        SELECT LAST_INSERT_ID() AS new_id;
    END
```

### Procedure: `InsertStudentSupervisor`
**Parameters**:
- `IN` **p_student_id**: `int(11)`
- `IN` **p_personnel_id**: `int(11)`
- `IN` **p_supervision_role**: `varchar(50)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertStudentSupervisor`(IN p_student_id INT, IN p_personnel_id INT, IN p_supervision_role VARCHAR(50))
BEGIN
        INSERT INTO student_supervisors (student_id, personnel_id, supervision_role) VALUES (p_student_id, p_personnel_id, p_supervision_role);
        SELECT LAST_INSERT_ID() AS new_id;
    END
```

### Procedure: `InsertStudySystem`
**Parameters**:
- `IN` **p_name_ar**: `varchar(60)`
- `IN` **p_name_en**: `varchar(60)`
- `IN` **p_study_day_type**: `varchar(50)`
- `IN` **p_calculation_rule**: `varchar(50)`
- `IN` **p_calculation_weights**: `varchar(100)`
- `IN` **p_period_display**: `varchar(50)`
- `IN` **p_is_active**: `tinyint(1)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertStudySystem`(
    IN p_name_ar VARCHAR(60),
    IN p_name_en VARCHAR(60),
    IN p_study_day_type VARCHAR(50),
    IN p_calculation_rule VARCHAR(50),
    IN p_calculation_weights VARCHAR(100),
    IN p_period_display VARCHAR(50),
    IN p_is_active TINYINT(1)
)
BEGIN
    INSERT INTO study_systems (name_ar, name_en, study_day_type, calculation_rule, calculation_weights, period_display, is_active)
    VALUES (p_name_ar, p_name_en, p_study_day_type, p_calculation_rule, p_calculation_weights, p_period_display, p_is_active);
    SELECT LAST_INSERT_ID() AS new_id;
END
```

### Procedure: `InsertThesis`
**Parameters**:
- `IN` **p_student_id**: `int(11)`
- `IN` **p_title_ar**: `varchar(500)`
- `IN` **p_title_en**: `varchar(500)`
- `IN` **p_defense_date**: `date`
- `IN` **p_committee_decision**: `varchar(100)`
- `IN` **p_final_grade**: `float`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertThesis`(
        IN p_student_id INT, IN p_title_ar VARCHAR(500), IN p_title_en VARCHAR(500),
        IN p_defense_date DATE, IN p_committee_decision VARCHAR(100), IN p_final_grade FLOAT
    )
BEGIN
        INSERT INTO thesis_records (student_id, title_ar, title_en, defense_date, committee_decision, final_grade) 
        VALUES (p_student_id, p_title_ar, p_title_en, p_defense_date, p_committee_decision, p_final_grade);
        SELECT LAST_INSERT_ID() AS new_id;
    END
```

### Procedure: `LinkStudentsToOrder`
**Parameters**:
- `IN` **p_order_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `LinkStudentsToOrder`(IN p_order_id INT)
BEGIN
    DECLARE v_dept_id INT;
    DECLARE v_year INT;
    DECLARE v_study_system_id INT;
    DECLARE v_date DATE;
    DECLARE v_sem VARCHAR(50);

    SELECT department_id, graduation_year, study_system_id, order_date, graduation_semester
    INTO v_dept_id, v_year, v_study_system_id, v_date, v_sem
    FROM graduation_orders WHERE id = p_order_id;

    UPDATE students 
    SET order_id = p_order_id, 
        graduation_date = v_date, 
        graduation_semester = v_sem
    WHERE department_id = v_dept_id 
      AND study_system_id = v_study_system_id
      AND YEAR(graduation_date) = v_year
      AND order_id IS NULL;
      
    SELECT ROW_COUNT() AS affected_rows;
END
```

### Procedure: `SearchStudentByName`
**Parameters**:
- `IN` **p_search_name**: `varchar(150)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `SearchStudentByName`(
    IN p_search_name VARCHAR(150)
)
BEGIN
    SELECT 
        s.`id` AS `Student_ID`,
        s.`full_name_ar` AS `Arabic_Name`,
        s.`full_name_en` AS `English_Name`,
        d.`name_ar` AS `Department`,
        s.`admission_year` AS `Admission_Year`,
        s.`study_system_id` AS `System_ID`
    FROM `certificate_manager`.`students` AS s
    LEFT JOIN `certificate_manager`.`departments` AS d 
        ON s.`department_id` = d.`id`
    WHERE s.`full_name_ar` LIKE CONCAT('%', TRIM(p_search_name), '%')
       OR s.`full_name_en` LIKE CONCAT('%', TRIM(p_search_name), '%')
    ORDER BY s.`full_name_ar` ASC;
END
```

### Procedure: `SearchStudentsBasic`
**Parameters**:
- `IN` **p_search_term**: `varchar(255)`
- `IN` **p_limit**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `SearchStudentsBasic`(
        IN p_search_term VARCHAR(255),
        IN p_limit INT
    )
BEGIN
        SET p_search_term = TRIM(p_search_term);

        IF CHAR_LENGTH(p_search_term) < 2 THEN
            SELECT 
                s.id AS student_id,
                s.full_name_ar AS name_ar,
                s.full_name_en AS name_en,
                d.name_ar AS dept_name_ar,
                YEAR(s.graduation_date) AS graduation_year,
                s.admission_year,
                s.average
            FROM students s
            LEFT JOIN departments d ON s.department_id = d.id
            WHERE 1 = 0;
        ELSE
            SELECT 
                s.id AS student_id,
                s.full_name_ar AS name_ar,
                s.full_name_en AS name_en,
                d.name_ar AS dept_name_ar,
                YEAR(s.graduation_date) AS graduation_year,
                s.admission_year,
                s.average
            FROM 
                students s
            LEFT JOIN departments d ON s.department_id = d.id
            WHERE 
                s.full_name_ar LIKE CONCAT('%', p_search_term, '%') 
                OR s.full_name_en LIKE CONCAT('%', p_search_term, '%')
            ORDER BY
                CASE 
                    WHEN s.full_name_ar = p_search_term OR s.full_name_en = p_search_term THEN 1
                    WHEN s.full_name_ar LIKE CONCAT(p_search_term, '%') OR s.full_name_en LIKE CONCAT(p_search_term, '%') THEN 2
                    ELSE 3 
                END,
                s.full_name_ar ASC
            LIMIT p_limit;
        END IF;
    END
```

### Procedure: `SearchStudentsPaginated`
**Parameters**:
- `IN` **p_search_term**: `varchar(255)`
- `IN` **p_limit**: `int(11)`
- `IN` **p_offset**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `SearchStudentsPaginated`(
    IN p_search_term VARCHAR(255),
    IN p_limit INT,
    IN p_offset INT
)
BEGIN
    SET p_search_term = TRIM(COALESCE(p_search_term, ''));

        IF CHAR_LENGTH(p_search_term) < 2 THEN
        SELECT 
            s.id AS student_id,
            COALESCE(s.full_name_ar, 'Unknown') AS name_ar,
            COALESCE(s.full_name_en, 'Unknown') AS name_en,
            COALESCE(d.name_ar, 'Unknown') AS department_name_ar,
            COALESCE(YEAR(s.graduation_date), 'N/A') AS graduation_year,
            COALESCE(s.average, 0.0) AS average
        FROM students s
        LEFT JOIN departments d ON s.department_id = d.id
        ORDER BY s.id DESC
        LIMIT p_limit OFFSET p_offset;
    ELSE
                SELECT 
            s.id AS student_id,
            COALESCE(s.full_name_ar, 'Unknown') AS name_ar,
            COALESCE(s.full_name_en, 'Unknown') AS name_en,
            COALESCE(d.name_ar, 'Unknown') AS department_name_ar,
            COALESCE(YEAR(s.graduation_date), 'N/A') AS graduation_year,
            COALESCE(s.average, 0.0) AS average
        FROM students s
        LEFT JOIN departments d ON s.department_id = d.id
        WHERE 
            s.full_name_ar LIKE CONCAT('%', p_search_term, '%')
            OR s.full_name_en LIKE CONCAT('%', p_search_term, '%')
        ORDER BY 
            CASE 
                WHEN s.full_name_ar = p_search_term OR s.full_name_en = p_search_term THEN 1 
                WHEN s.full_name_ar LIKE CONCAT(p_search_term, '%') OR s.full_name_en LIKE CONCAT(p_search_term, '%') THEN 2 
                ELSE 3 
            END, 
            s.full_name_ar ASC
        LIMIT p_limit OFFSET p_offset;
    END IF;
END
```

### Procedure: `UnlinkStudentFromOrder`
**Parameters**:
- `IN` **p_student_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `UnlinkStudentFromOrder`(IN p_student_id INT)
BEGIN
    UPDATE students 
    SET order_id = NULL, 
        graduation_date = NULL, 
        graduation_semester = NULL 
    WHERE id = p_student_id;
END
```

### Procedure: `UpdateDepartment`
**Parameters**:
- `IN` **p_id**: `int(11)`
- `IN` **p_name_ar**: `varchar(100)`
- `IN` **p_name_en**: `varchar(100)`
- `IN` **p_university_settings_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateDepartment`(
    IN p_id INT,
    IN p_name_ar VARCHAR(100),
    IN p_name_en VARCHAR(100),
    IN p_university_settings_id INT
)
BEGIN
    UPDATE departments
    SET name_ar = p_name_ar,
        name_en = p_name_en,
        university_settings_id = p_university_settings_id
    WHERE id = p_id;
END
```

### Procedure: `UpdateGraduationOrder`
**Parameters**:
- `IN` **p_id**: `int(11)`
- `IN` **p_order_number**: `varchar(60)`
- `IN` **p_order_date**: `date`
- `IN` **p_department_id**: `int(11)`
- `IN` **p_study_type**: `varchar(50)`
- `IN` **p_graduation_year**: `int(11)`
- `IN` **p_graduation_semester**: `varchar(50)`
- `IN` **p_num_students**: `int(11)`
- `IN` **p_notes**: `varchar(255)`
- `IN` **p_study_system_id**: `int(11)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateGraduationOrder`(
    IN p_id INT,
    IN p_order_number VARCHAR(60),
    IN p_order_date DATE,
    IN p_department_id INT,
    IN p_study_type VARCHAR(50),
    IN p_graduation_year INT,
    IN p_graduation_semester VARCHAR(50),
    IN p_num_students INT,
    IN p_notes VARCHAR(255),
    IN p_study_system_id INT
)
BEGIN
    UPDATE graduation_orders
    SET order_number = p_order_number,
        order_date = p_order_date,
        department_id = p_department_id,
        study_type = p_study_type,
        graduation_year = p_graduation_year,
        graduation_semester = p_graduation_semester,
        num_students = p_num_students,
        notes = p_notes,
        study_system_id = p_study_system_id
    WHERE id = p_id;
END
```

### Procedure: `UpdatePersonnel`
**Parameters**:
- `IN` **p_id**: `int(11)`
- `IN` **p_name_ar**: `varchar(80)`
- `IN` **p_name_en**: `varchar(80)`
- `IN` **p_academic_title_ar**: `varchar(50)`
- `IN` **p_academic_title_en**: `varchar(50)`
- `IN` **p_responsibility_ar**: `varchar(120)`
- `IN` **p_responsibility_en**: `varchar(120)`
- `IN` **p_display_order**: `int(11)`
- `IN` **p_username**: `varchar(50)`
- `IN` **p_personnel_role**: `varchar(20)`
- `IN` **p_university_settings_id**: `int(11)`
- `IN` **p_is_active**: `tinyint(1)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdatePersonnel`(
    IN p_id INT,
    IN p_name_ar VARCHAR(80),
    IN p_name_en VARCHAR(80),
    IN p_academic_title_ar VARCHAR(50),
    IN p_academic_title_en VARCHAR(50),
    IN p_responsibility_ar VARCHAR(120),
    IN p_responsibility_en VARCHAR(120),
    IN p_display_order INT,
    IN p_username VARCHAR(50),
    IN p_personnel_role VARCHAR(20),
    IN p_university_settings_id INT,
    IN p_is_active TINYINT(1)
)
BEGIN
    UPDATE personnel
    SET 
        name_ar = TRIM(p_name_ar),
        name_en = TRIM(p_name_en),
        academic_title_ar = IF(TRIM(p_academic_title_ar) = '', NULL, TRIM(p_academic_title_ar)),
        academic_title_en = IF(TRIM(p_academic_title_en) = '', NULL, TRIM(p_academic_title_en)),
        responsibility_ar = TRIM(p_responsibility_ar),
        responsibility_en = TRIM(p_responsibility_en),
        display_order = COALESCE(p_display_order, 0),
        username = TRIM(p_username),
        personnel_role = COALESCE(p_personnel_role, 'user'),
        university_settings_id = p_university_settings_id,
        is_active = COALESCE(p_is_active, 1)
    WHERE id = p_id;
END
```

### Procedure: `UpdateStudent`
**Parameters**:
- `IN` **p_id**: `int(11)`
- `IN` **p_full_name_ar**: `varchar(150)`
- `IN` **p_full_name_en**: `varchar(150)`
- `IN` **p_gender**: `varchar(1)`
- `IN` **p_sequence_number**: `int(11)`
- `IN` **p_postgraduation_number**: `int(11)`
- `IN` **p_date_of_birth**: `date`
- `IN` **p_birthplace_id**: `int(11)`
- `IN` **p_birthplace_other**: `varchar(100)`
- `IN` **p_nationality_id**: `int(11)`
- `IN` **p_department_id**: `int(11)`
- `IN` **p_study_system_id**: `int(11)`
- `IN` **p_degree_level**: `varchar(50)`
- `IN` **p_order_id**: `int(11)`
- `IN` **p_admission_year**: `varchar(9)`
- `IN` **p_summer_training_data**: `varchar(20)`
- `IN` **p_average**: `float`
- `IN` **p_graduation_date**: `date`
- `IN` **p_graduation_semester**: `varchar(50)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateStudent`(
        IN p_id INT,
        IN p_full_name_ar VARCHAR(150),
        IN p_full_name_en VARCHAR(150),
        IN p_gender VARCHAR(1),
        IN p_sequence_number INT,
        IN p_postgraduation_number INT,
        IN p_date_of_birth DATE,
        IN p_birthplace_id INT,
        IN p_birthplace_other VARCHAR(100),
        IN p_nationality_id INT,
        IN p_department_id INT,
        IN p_study_system_id INT,
        IN p_degree_level VARCHAR(50),
        IN p_order_id INT,
        IN p_admission_year VARCHAR(9),
        IN p_summer_training_data VARCHAR(20),
        IN p_average FLOAT,
        IN p_graduation_date DATE,
        IN p_graduation_semester VARCHAR(50)
    )
BEGIN
        UPDATE students
        SET full_name_ar = p_full_name_ar,
            full_name_en = p_full_name_en,
            gender = p_gender,
            sequence_number = p_sequence_number,
            postgraduation_number = p_postgraduation_number,
            date_of_birth = p_date_of_birth,
            birthplace_id = p_birthplace_id,
            birthplace_other = p_birthplace_other,
            nationality_id = p_nationality_id,
            department_id = p_department_id,
            study_system_id = p_study_system_id,
            degree_level = p_degree_level,
            order_id = p_order_id,
            admission_year = p_admission_year,
            summer_training_data = p_summer_training_data,
            average = p_average,
            graduation_date = p_graduation_date,
            graduation_semester = p_graduation_semester
        WHERE id = p_id;
    END
```

### Procedure: `UpdateStudentSupervisor`
**Parameters**:
- `IN` **p_id**: `int(11)`
- `IN` **p_personnel_id**: `int(11)`
- `IN` **p_supervision_role**: `varchar(50)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateStudentSupervisor`(IN p_id INT, IN p_personnel_id INT, IN p_supervision_role VARCHAR(50))
BEGIN
        UPDATE student_supervisors SET personnel_id = p_personnel_id, supervision_role = p_supervision_role WHERE id = p_id;
    END
```

### Procedure: `UpdateStudySystem`
**Parameters**:
- `IN` **p_id**: `int(11)`
- `IN` **p_name_ar**: `varchar(60)`
- `IN` **p_name_en**: `varchar(60)`
- `IN` **p_study_day_type**: `varchar(50)`
- `IN` **p_calculation_rule**: `varchar(50)`
- `IN` **p_calculation_weights**: `varchar(100)`
- `IN` **p_period_display**: `varchar(50)`
- `IN` **p_is_active**: `tinyint(1)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateStudySystem`(
    IN p_id INT,
    IN p_name_ar VARCHAR(60),
    IN p_name_en VARCHAR(60),
    IN p_study_day_type VARCHAR(50),
    IN p_calculation_rule VARCHAR(50),
    IN p_calculation_weights VARCHAR(100),
    IN p_period_display VARCHAR(50),
    IN p_is_active TINYINT(1)
)
BEGIN
    UPDATE study_systems
    SET name_ar = p_name_ar,
        name_en = p_name_en,
        study_day_type = p_study_day_type,
        calculation_rule = p_calculation_rule,
        calculation_weights = p_calculation_weights,
        period_display = p_period_display,
        is_active = p_is_active
    WHERE id = p_id;
END
```

### Procedure: `UpdateSystemSettings`
**Parameters**:
- `IN` **p_id**: `int(11)`
- `IN` **p_theme**: `varchar(20)`
- `IN` **p_accent_color**: `varchar(20)`
- `IN` **p_font_family**: `varchar(100)`
- `IN` **p_font_size_base**: `int(11)`
- `IN` **p_is_arabic_rtl**: `tinyint(1)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateSystemSettings`(
    IN p_id INT,
    IN p_theme VARCHAR(20),
    IN p_accent_color VARCHAR(20),
    IN p_font_family VARCHAR(100),
    IN p_font_size_base INT,
    IN p_is_arabic_rtl TINYINT(1)
)
BEGIN
    UPDATE settings 
    SET theme = p_theme,
        accent_color = p_accent_color,
        font_family = p_font_family,
        font_size_base = p_font_size_base,
        is_arabic_rtl = p_is_arabic_rtl
    WHERE id = p_id;
END
```

### Procedure: `UpdateThesis`
**Parameters**:
- `IN` **p_id**: `int(11)`
- `IN` **p_title_ar**: `varchar(500)`
- `IN` **p_title_en**: `varchar(500)`
- `IN` **p_defense_date**: `date`
- `IN` **p_committee_decision**: `varchar(100)`
- `IN` **p_final_grade**: `float`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateThesis`(
        IN p_id INT, IN p_title_ar VARCHAR(500), IN p_title_en VARCHAR(500),
        IN p_defense_date DATE, IN p_committee_decision VARCHAR(100), IN p_final_grade FLOAT
    )
BEGIN
        UPDATE thesis_records SET title_ar = p_title_ar, title_en = p_title_en, defense_date = p_defense_date, 
            committee_decision = p_committee_decision, final_grade = p_final_grade WHERE id = p_id;
    END
```

### Procedure: `UpdateUserPreferences`
**Parameters**:
- `IN` **p_id**: `int(11)`
- `IN` **p_theme**: `varchar(20)`
- `IN` **p_accent_color**: `varchar(20)`
- `IN` **p_font_family**: `varchar(100)`
- `IN` **p_font_size_base**: `int(11)`
- `IN` **p_is_arabic_rtl**: `tinyint(1)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateUserPreferences`(
    IN p_id INT,
    IN p_theme VARCHAR(20),
    IN p_accent_color VARCHAR(20),
    IN p_font_family VARCHAR(100),
    IN p_font_size_base INT,
    IN p_is_arabic_rtl TINYINT(1)
)
BEGIN
    INSERT INTO settings (id, theme, accent_color, font_family, font_size_base, is_arabic_rtl)
    VALUES (p_id, p_theme, p_accent_color, p_font_family, p_font_size_base, p_is_arabic_rtl)
    ON DUPLICATE KEY UPDATE
        theme = VALUES(theme),
        accent_color = VALUES(accent_color),
        font_family = VALUES(font_family),
        font_size_base = VALUES(font_size_base),
        is_arabic_rtl = VALUES(is_arabic_rtl);
END
```

### Procedure: `Update_User_Settings`
**Parameters**:
- `IN` **p_EMP_ID**: `int(11)`
- `IN` **p_theme**: `varchar(20)`
- `IN` **p_accent_color**: `varchar(20)`
- `IN` **p_font_family**: `varchar(100)`
- `IN` **p_font_size_base**: `int(11)`
- `IN` **p_is_arabic_rtl**: `tinyint(4)`

```sql
CREATE DEFINER=`root`@`localhost` PROCEDURE `Update_User_Settings`(
    IN p_EMP_ID INT,
    IN p_theme VARCHAR(20),
    IN p_accent_color VARCHAR(20),
    IN p_font_family VARCHAR(100),
    IN p_font_size_base INT,
    IN p_is_arabic_rtl TINYINT
)
BEGIN
    IF EXISTS (SELECT 1 FROM settings WHERE EMP_ID = p_EMP_ID) THEN
        UPDATE settings
        SET 
            theme = p_theme,
            accent_color = p_accent_color,
            font_family = p_font_family,
            font_size_base = p_font_size_base,
            is_arabic_rtl = p_is_arabic_rtl
        WHERE EMP_ID = p_EMP_ID;
    ELSE
        INSERT INTO settings (EMP_ID, theme, accent_color, font_family, font_size_base, is_arabic_rtl)
        VALUES (p_EMP_ID, p_theme, p_accent_color, p_font_family, p_font_size_base, p_is_arabic_rtl);
    END IF;
END
```
