-- =============================================================================
-- db_procedures.sql — Core Stored Procedures for Certificate Manager
-- =============================================================================

DELIMITER //

-- 1. Procedure: AuthenticateUser
DROP PROCEDURE IF EXISTS AuthenticateUser //
CREATE PROCEDURE AuthenticateUser(
    IN p_username VARCHAR(50),
    IN p_password_hash VARCHAR(255)
)
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
END //

-- 2. Procedure: Get_User_Settings
DROP PROCEDURE IF EXISTS Get_User_Settings //
CREATE PROCEDURE Get_User_Settings(
    IN p_EMP_ID INT
)
BEGIN
    SELECT 
        id, 
        EMP_ID, 
        theme, 
        accent_color, 
        font_family, 
        font_size_base, 
        is_arabic_rtl
    FROM settings
    WHERE EMP_ID = p_EMP_ID
    LIMIT 1;
END //

-- 3. Procedure: Update_User_Settings
DROP PROCEDURE IF EXISTS Update_User_Settings //
CREATE PROCEDURE Update_User_Settings(
    IN p_EMP_ID INT,
    IN p_theme VARCHAR(20),
    IN p_accent_color VARCHAR(20),
    IN p_font_family VARCHAR(100),
    IN p_font_size_base INT,
    IN p_is_arabic_rtl TINYINT
)
BEGIN
    UPDATE settings
    SET 
        theme = p_theme,
        accent_color = p_accent_color,
        font_family = p_font_family,
        font_size_base = p_font_size_base,
        is_arabic_rtl = p_is_arabic_rtl
    WHERE EMP_ID = p_EMP_ID;
END //

-- 4. Procedure: Create_Default_Settings
DROP PROCEDURE IF EXISTS Create_Default_Settings //
CREATE PROCEDURE Create_Default_Settings(
    IN p_EMP_ID INT
)
BEGIN
    INSERT INTO settings (EMP_ID, theme, accent_color, font_family, font_size_base, is_arabic_rtl)
    VALUES (
        p_EMP_ID, 
        'light', 
        'blue', 
        'Arial', 
        14, 
        1
    );
END //

DELIMITER ;
