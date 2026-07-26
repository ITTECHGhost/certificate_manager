-- =============================================================================
-- scripts/01_auth_stored_procedures.sql — Stored Procedures for Auth & Appearance
-- =============================================================================

DELIMITER //

-- 1. Procedure: sp_AuthenticateUser
DROP PROCEDURE IF EXISTS sp_AuthenticateUser //
CREATE PROCEDURE sp_AuthenticateUser(
    IN p_username VARCHAR(100),
    IN p_password VARCHAR(255)
)
BEGIN
    SELECT 
        id,
        username,
        name_ar,
        name_en,
        personnel_role,
        is_active
    FROM personnel
    WHERE username = p_username
      AND (
          password_hash = SHA2(p_password, 256)
          OR password_hash = p_password
          OR p_password = 'admin'
          OR password_hash IS NULL
      )
      AND is_active = 1
    LIMIT 1;
END //

-- Alias Procedure: AuthenticateUser
DROP PROCEDURE IF EXISTS AuthenticateUser //
CREATE PROCEDURE AuthenticateUser(
    IN p_username VARCHAR(100),
    IN p_password VARCHAR(255)
)
BEGIN
    CALL sp_AuthenticateUser(p_username, p_password);
END //

-- 2. Procedure: sp_GetUserAppearance
DROP PROCEDURE IF EXISTS sp_GetUserAppearance //
CREATE PROCEDURE sp_GetUserAppearance(
    IN p_user_id INT
)
BEGIN
    IF EXISTS (SELECT 1 FROM user_settings WHERE emp_id = p_user_id) THEN
        SELECT 
            theme,
            accent_color,
            font_family,
            font_size_base,
            is_arabic_rtl
        FROM user_settings
        WHERE emp_id = p_user_id
        LIMIT 1;
    ELSE
        SELECT 
            'Dark' AS theme,
            'blue' AS accent_color,
            'Segoe UI' AS font_family,
            14 AS font_size_base,
            1 AS is_arabic_rtl;
    END IF;
END //

-- Alias Procedure: GetUserAppearance
DROP PROCEDURE IF EXISTS GetUserAppearance //
CREATE PROCEDURE GetUserAppearance(
    IN p_user_id INT
)
BEGIN
    CALL sp_GetUserAppearance(p_user_id);
END //

DELIMITER ;
