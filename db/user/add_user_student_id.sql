USE ibanking_account_db;

ALTER TABLE users
    ADD COLUMN student_id VARCHAR(20) NULL,
    ADD UNIQUE KEY uq_users_student_id (student_id);

-- Assign the demo user to an existing unpaid tuition record only when no mapping exists.
UPDATE users
SET student_id = '524H0104'
WHERE username = 'user01'
  AND student_id IS NULL;
