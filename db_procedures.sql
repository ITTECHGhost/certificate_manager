-- =============================================================================
-- db_procedures.sql — Core Stored Procedures for Certificate Manager
-- =============================================================================
DELIMITER / /
-- 1. Procedure: AuthenticateUser
DROP PROCEDURE IF EXISTS AuthenticateUser / / CREATE PROCEDURE AuthenticateUser (
    IN p_username VARCHAR(50),
    IN p_password_hash VARCHAR(255)
) BEGIN
SELECT
    id,
    username,
    name_ar,
    name_en,
    personnel_role,
    is_active
FROM
    personnel
WHERE
    username = p_username
    AND password_hash = p_password_hash
    AND is_active = 1
LIMIT
    1;

END / /
-- 2. Procedure: Get_User_Settings
DROP PROCEDURE IF EXISTS Get_User_Settings / / CREATE PROCEDURE Get_User_Settings (IN p_emp_id INT) BEGIN
SELECT
    s.EMP_ID,
    COALESCE(s.theme, 'Dark') AS theme,
    COALESCE(s.accent_color, 'blue') AS accent_color,
    COALESCE(s.font_family, 'Arial') AS font_family,
    COALESCE(s.font_size_base, 14) AS font_size_base,
    COALESCE(s.is_arabic_rtl, 1) AS is_arabic_rtl
FROM
    settings s
WHERE
    s.EMP_ID = p_emp_id
LIMIT
    1;

END / /
-- 3. Procedure: Update_User_Settings
DROP PROCEDURE IF EXISTS Update_User_Settings / / CREATE PROCEDURE Update_User_Settings (
    IN p_EMP_ID INT,
    IN p_theme VARCHAR(20),
    IN p_accent_color VARCHAR(20),
    IN p_font_family VARCHAR(100),
    IN p_font_size_base INT,
    IN p_is_arabic_rtl TINYINT
) BEGIN IF EXISTS (
    SELECT
        1
    FROM
        settings
    WHERE
        EMP_ID = p_EMP_ID
) THEN
UPDATE settings
SET
    theme = p_theme,
    accent_color = p_accent_color,
    font_family = p_font_family,
    font_size_base = p_font_size_base,
    is_arabic_rtl = p_is_arabic_rtl
WHERE
    EMP_ID = p_EMP_ID;

ELSE
INSERT INTO
    settings (
        EMP_ID,
        theme,
        accent_color,
        font_family,
        font_size_base,
        is_arabic_rtl
    )
VALUES
    (
        p_EMP_ID,
        p_theme,
        p_accent_color,
        p_font_family,
        p_font_size_base,
        p_is_arabic_rtl
    );

END IF;

END / /
-- 4. Procedure: Create_Default_Settings
DROP PROCEDURE IF EXISTS Create_Default_Settings / / CREATE PROCEDURE Create_Default_Settings (IN p_EMP_ID INT) BEGIN
INSERT INTO
    settings (
        EMP_ID,
        theme,
        accent_color,
        font_family,
        font_size_base,
        is_arabic_rtl
    )
VALUES
    (p_EMP_ID, 'light', 'blue', 'Arial', 14, 1);

END / / DELIMITER;