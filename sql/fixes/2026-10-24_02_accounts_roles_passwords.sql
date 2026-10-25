-- =============================================================================
-- 2026-10-24_02_accounts_roles_passwords.sql
-- Accounts: "must change password" flag, and roles stored in MySQL.
--
-- Run ONCE in phpMyAdmin / MySQL Workbench on the certificate_manager database.
-- The program keeps working before this is run (roles stay local to each PC,
-- no forced password change); after it, every laptop shares the same roles.
-- =============================================================================

-- 1. Forced password change after an admin gives out a (temporary) password.
--    (If you run this file twice, this line fails with "Duplicate column" - that is fine.)
ALTER TABLE personnel ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0;

-- 2. Roles (responsibility profiles) shared by all laptops.
--    allowed_pages / allowed_actions hold JSON lists, as in the program's local copy.
CREATE TABLE IF NOT EXISTS roles (
    id               VARCHAR(64)  NOT NULL PRIMARY KEY,
    name_ar          VARCHAR(150) NOT NULL,
    name_en          VARCHAR(150) NOT NULL,
    description_ar   TEXT,
    base_role        VARCHAR(20)  NOT NULL DEFAULT 'user',
    allowed_pages    TEXT         NOT NULL,
    allowed_actions  TEXT         NOT NULL,
    department_scope VARCHAR(255) NOT NULL DEFAULT 'all',
    is_system        TINYINT(1)   NOT NULL DEFAULT 0,
    created_at       TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Which role each staff member has.
CREATE TABLE IF NOT EXISTS user_roles (
    personnel_id INT          NOT NULL PRIMARY KEY,
    role_id      VARCHAR(64)  NOT NULL,
    updated_at   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Current roles and assignments (copied from the developer laptop on 2026-10-24).
--    Existing rows are left unchanged if this is run again.
INSERT INTO roles (id, name_ar, name_en, description_ar, base_role, allowed_pages, allowed_actions, department_scope, is_system) VALUES ('admin', 'مدير النظام', 'System Administrator', 'صلاحيات وتحكم كامل بكافة وظائف وشاشات وإعدادات النظام', 'admin', '["home", "students", "orders", "departments", "courses", "personnel", "certificate", "issued_certs", "settings", "history"]', '["students:create", "students:delete", "students:edit", "students:grades", "students:view", "orders:create", "orders:delete", "orders:edit", "orders:view", "certificates:issue", "issued_certs:delete", "issued_certs:export", "issued_certs:view", "departments:create", "departments:delete", "departments:edit", "departments:view", "courses:create", "courses:delete", "courses:edit", "courses:view", "personnel:manage", "personnel:view", "settings:appearance", "settings:institution", "settings:logs", "settings:manage", "settings:roles", "settings:study_systems", "settings:templates", "settings:view"]', 'all', 1)
  ON DUPLICATE KEY UPDATE id = id;
INSERT INTO roles (id, name_ar, name_en, description_ar, base_role, allowed_pages, allowed_actions, department_scope, is_system) VALUES ('auditor', 'مدقق درجات وبيانات', 'Academic Data Auditor', 'تدقيق ومراجعة سجلات الطلاب والدرجات وأوامر التخرج دون صلاحية تعديل مباشر', 'user', '["home", "students", "orders", "departments", "courses", "personnel", "certificate", "issued_certs", "settings"]', '["students:create", "students:delete", "students:edit", "students:grades", "students:view", "orders:create", "orders:delete", "orders:edit", "orders:view", "certificates:issue", "issued_certs:delete", "issued_certs:export", "issued_certs:view", "departments:create", "departments:delete", "departments:edit", "departments:view", "courses:create", "courses:delete", "courses:edit", "courses:view", "personnel:manage", "personnel:view", "settings:appearance", "settings:logs"]', 'all', 1)
  ON DUPLICATE KEY UPDATE id = id;
INSERT INTO roles (id, name_ar, name_en, description_ar, base_role, allowed_pages, allowed_actions, department_scope, is_system) VALUES ('cert_officer', 'مسؤول إصدار الوثائق', 'Certificate Officer', 'صلاحية فحص بيانات الطلاب وإصدار وطباعة الوثائق الرسمية وتصدير السجلات', 'user', '["home", "students", "orders", "departments", "courses", "personnel", "certificate", "issued_certs", "settings"]', '["students:create", "students:delete", "students:edit", "students:grades", "students:view", "orders:create", "orders:delete", "orders:edit", "orders:view", "certificates:issue", "issued_certs:delete", "issued_certs:export", "issued_certs:view", "departments:create", "departments:delete", "departments:edit", "departments:view", "courses:create", "courses:delete", "courses:edit", "courses:view", "personnel:manage", "personnel:view", "settings:appearance", "settings:institution", "settings:logs", "settings:study_systems", "settings:templates"]', 'all', 1)
  ON DUPLICATE KEY UPDATE id = id;
INSERT INTO roles (id, name_ar, name_en, description_ar, base_role, allowed_pages, allowed_actions, department_scope, is_system) VALUES ('dept_head', 'رئيس قسم / مقرر دراسي', 'Department Head / Coordinator', 'إدارة المقررات الدراسية وإدخال وتدقيق درجات طلبة القسم', 'user', '["home", "students", "departments", "courses"]', '["students:view", "students:grades", "catalog:manage"]', 'all', 1)
  ON DUPLICATE KEY UPDATE id = id;
INSERT INTO roles (id, name_ar, name_en, description_ar, base_role, allowed_pages, allowed_actions, department_scope, is_system) VALUES ('registrar', 'مدير التسجيل وشؤون الطلاب', 'Registrar Director', 'إدارة كاملة لشؤون الطلاب، الدرجات، أوامر التخرج، وإصدار الوثائق لكافة الأقسام', 'user', '["home", "students", "orders", "departments", "courses", "certificate", "issued_certs"]', '["students:view", "students:create", "students:edit", "students:grades", "orders:view", "orders:create", "orders:edit", "certificates:issue", "issued_certs:view", "issued_certs:export", "catalog:manage"]', 'all', 1)
  ON DUPLICATE KEY UPDATE id = id;
INSERT INTO roles (id, name_ar, name_en, description_ar, base_role, allowed_pages, allowed_actions, department_scope, is_system) VALUES ('signer', 'موقع معتمد للوثائق', 'Authorized Signer', 'ظهور الاسم والتوقيع المعتمد على الوثائق الصادرة ومراجعة السجلات', 'signer', '["home", "issued_certs"]', '["issued_certs:view"]', 'all', 1)
  ON DUPLICATE KEY UPDATE id = id;
INSERT INTO roles (id, name_ar, name_en, description_ar, base_role, allowed_pages, allowed_actions, department_scope, is_system) VALUES ('user', 'مستخدم عادي', 'Standard User', 'صلاحيات الاطلاع الأساسية على لوحة التحكم وبيانات الطلاب', 'user', '["home", "students", "orders", "issued_certs"]', '["students:view", "orders:view", "issued_certs:view"]', 'all', 1)
  ON DUPLICATE KEY UPDATE id = id;
INSERT INTO user_roles (personnel_id, role_id) VALUES (8, 'cert_officer')
  ON DUPLICATE KEY UPDATE personnel_id = personnel_id;
INSERT INTO user_roles (personnel_id, role_id) VALUES (9, 'auditor')
  ON DUPLICATE KEY UPDATE personnel_id = personnel_id;
