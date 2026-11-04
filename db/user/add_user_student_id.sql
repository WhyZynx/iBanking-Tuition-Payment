USE ibanking_account_db;

DROP PROCEDURE IF EXISTS upgrade_user_student_id;

DELIMITER $$

CREATE PROCEDURE upgrade_user_student_id()
BEGIN
    DECLARE has_student_id BIGINT DEFAULT 0;
    DECLARE has_student_id_unique_index BIGINT DEFAULT 0;

    -- Check whether the student_id column already exists
    SELECT COUNT(*) INTO has_student_id
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'users'
      AND column_name = 'student_id';

    -- Add student_id only when it does not exist
    IF has_student_id = 0 THEN
        ALTER TABLE users
        ADD COLUMN student_id VARCHAR(20) NULL;
    END IF;

    -- Check whether student_id already has a single-column unique index
    SELECT COUNT(*) INTO has_student_id_unique_index
    FROM (
        SELECT index_name
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = 'users'
          AND non_unique = 0
        GROUP BY index_name
        HAVING COUNT(*) = 1
           AND SUM(column_name = 'student_id') = 1
    ) AS student_id_indexes;

    -- Add unique index only when it does not exist
    IF has_student_id_unique_index = 0 THEN
        ALTER TABLE users
        ADD UNIQUE KEY uq_users_student_id (student_id);
    END IF;

    -- Assign student ID to the existing demo user
    UPDATE users
    SET student_id = '524H0001'
    WHERE username = 'user01'
      AND student_id IS NULL;
END$$

DELIMITER ;

CALL upgrade_user_student_id();

DROP PROCEDURE upgrade_user_student_id;