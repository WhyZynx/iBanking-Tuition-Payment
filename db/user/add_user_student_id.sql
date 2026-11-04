USE ibanking_account_db;

DROP PROCEDURE IF EXISTS upgrade_user_student_id;
DELIMITER $$
CREATE PROCEDURE upgrade_user_student_id()
BEGIN
    DECLARE has_student_id BIGINT DEFAULT 0;
    DECLARE has_student_id_unique_index BIGINT DEFAULT 0;

    SELECT COUNT(*) INTO has_student_id
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'users'
      AND column_name = 'student_id';
    IF has_student_id = 0 THEN
        ALTER TABLE users ADD COLUMN student_id VARCHAR(20) NULL;
    END IF;

    SELECT COUNT(*) INTO has_student_id_unique_index
    FROM (
        SELECT index_name
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = 'users'
          AND non_unique = 0
        GROUP BY index_name
        HAVING COUNT(*) = 1 AND MAX(column_name) = 'student_id'
           AND MAX(sub_part) IS NULL
    ) AS student_id_indexes;
    IF has_student_id_unique_index = 0 THEN
        ALTER TABLE users ADD UNIQUE KEY uq_users_student_id (student_id);
    END IF;

    UPDATE users
    SET student_id = '524H0001'
    WHERE username = 'user01'
      AND student_id IS NULL;
END$$
DELIMITER ;

CALL upgrade_user_student_id();
DROP PROCEDURE upgrade_user_student_id;
