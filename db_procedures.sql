DELIMITER $$
DROP PROCEDURE IF EXISTS `AuthenticateUser`$$
CREATE PROCEDURE `AuthenticateUser`(
    IN p_username VARCHAR(50),
    IN p_password_hash VARCHAR(255)
)
BEGIN
    SELECT id, name_ar, name_en, personnel_role
    FROM personnel
    WHERE username = p_username 
      AND password_hash = p_password_hash
      AND is_active = 1
    LIMIT 1;
END$$
DELIMITER ;
