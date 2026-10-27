-- Optional fictional demo users and accounts for ibanking_account_db.
-- Check for username, student ID, and account-number conflicts before running.
-- This script inserts rows only; it never resets existing balances.

USE ibanking_account_db;
START TRANSACTION;

INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'user01', '$2b$12$VAd7NjVsm7/.42McDH4OTO0SSO8a4pgHd91Qkiyuzge19UWefyX22',
       'Nguyen Minh Anh', '0900000001', 'user01@example.com', '524H0001'
WHERE NOT EXISTS (
    SELECT 1 FROM users
    WHERE username = 'user01' AND student_id = '524H0001'
      AND full_name = 'Nguyen Minh Anh' AND phone = '0900000001'
      AND email = 'user01@example.com'
);
INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'user02', '$2b$12$VAd7NjVsm7/.42McDH4OTO0SSO8a4pgHd91Qkiyuzge19UWefyX22',
       'Tran Ngoc Han', '0900000002', 'user02@example.com', '524H0002'
WHERE NOT EXISTS (
    SELECT 1 FROM users
    WHERE username = 'user02' AND student_id = '524H0002'
      AND full_name = 'Tran Ngoc Han' AND phone = '0900000002'
      AND email = 'user02@example.com'
);
INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'user03', '$2b$12$VAd7NjVsm7/.42McDH4OTO0SSO8a4pgHd91Qkiyuzge19UWefyX22',
       'Le Hoang Nam', '0900000003', 'user03@example.com', '524H0003'
WHERE NOT EXISTS (
    SELECT 1 FROM users
    WHERE username = 'user03' AND student_id = '524H0003'
      AND full_name = 'Le Hoang Nam' AND phone = '0900000003'
      AND email = 'user03@example.com'
);
INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'user04', '$2b$12$VAd7NjVsm7/.42McDH4OTO0SSO8a4pgHd91Qkiyuzge19UWefyX22',
       'Pham Gia Linh', '0900000004', 'user04@example.com', '524H0004'
WHERE NOT EXISTS (
    SELECT 1 FROM users
    WHERE username = 'user04' AND student_id = '524H0004'
      AND full_name = 'Pham Gia Linh' AND phone = '0900000004'
      AND email = 'user04@example.com'
);
INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'user05', '$2b$12$VAd7NjVsm7/.42McDH4OTO0SSO8a4pgHd91Qkiyuzge19UWefyX22',
       'Vo Thanh Tung', '0900000005', 'user05@example.com', '723H0001'
WHERE NOT EXISTS (
    SELECT 1 FROM users
    WHERE username = 'user05' AND student_id = '723H0001'
      AND full_name = 'Vo Thanh Tung' AND phone = '0900000005'
      AND email = 'user05@example.com'
);
INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'user06', '$2b$12$VAd7NjVsm7/.42McDH4OTO0SSO8a4pgHd91Qkiyuzge19UWefyX22',
       'Do Khanh Vy', '0900000006', 'user06@example.com', '723H0002'
WHERE NOT EXISTS (
    SELECT 1 FROM users
    WHERE username = 'user06' AND student_id = '723H0002'
      AND full_name = 'Do Khanh Vy' AND phone = '0900000006'
      AND email = 'user06@example.com'
);
INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'user07', '$2b$12$VAd7NjVsm7/.42McDH4OTO0SSO8a4pgHd91Qkiyuzge19UWefyX22',
       'Bui Quoc Bao', '0900000007', 'user07@example.com', '723H0003'
WHERE NOT EXISTS (
    SELECT 1 FROM users
    WHERE username = 'user07' AND student_id = '723H0003'
      AND full_name = 'Bui Quoc Bao' AND phone = '0900000007'
      AND email = 'user07@example.com'
);
INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'user08', '$2b$12$VAd7NjVsm7/.42McDH4OTO0SSO8a4pgHd91Qkiyuzge19UWefyX22',
       'Huynh Thao My', '0900000008', 'user08@example.com', '723H0004'
WHERE NOT EXISTS (
    SELECT 1 FROM users
    WHERE username = 'user08' AND student_id = '723H0004'
      AND full_name = 'Huynh Thao My' AND phone = '0900000008'
      AND email = 'user08@example.com'
);

INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6202000001', u.user_id, 25000000.00, TRUE, 'ACTIVE' FROM users AS u
WHERE u.username = 'user01' AND u.student_id = '524H0001'
  AND NOT EXISTS (SELECT 1 FROM accounts AS a WHERE a.account_number = '6202000001' AND a.user_id = u.user_id AND a.is_default = TRUE AND a.status = 'ACTIVE');
INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6202000002', u.user_id, 15000000.00, TRUE, 'ACTIVE' FROM users AS u
WHERE u.username = 'user02' AND u.student_id = '524H0002'
  AND NOT EXISTS (SELECT 1 FROM accounts AS a WHERE a.account_number = '6202000002' AND a.user_id = u.user_id AND a.is_default = TRUE AND a.status = 'ACTIVE');
INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6202000003', u.user_id, 4000000.00, TRUE, 'ACTIVE' FROM users AS u
WHERE u.username = 'user03' AND u.student_id = '524H0003'
  AND NOT EXISTS (SELECT 1 FROM accounts AS a WHERE a.account_number = '6202000003' AND a.user_id = u.user_id AND a.is_default = TRUE AND a.status = 'ACTIVE');
INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6202000004', u.user_id, 30000000.00, TRUE, 'ACTIVE' FROM users AS u
WHERE u.username = 'user04' AND u.student_id = '524H0004'
  AND NOT EXISTS (SELECT 1 FROM accounts AS a WHERE a.account_number = '6202000004' AND a.user_id = u.user_id AND a.is_default = TRUE AND a.status = 'ACTIVE');
INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6202000005', u.user_id, 12000000.00, TRUE, 'ACTIVE' FROM users AS u
WHERE u.username = 'user05' AND u.student_id = '723H0001'
  AND NOT EXISTS (SELECT 1 FROM accounts AS a WHERE a.account_number = '6202000005' AND a.user_id = u.user_id AND a.is_default = TRUE AND a.status = 'ACTIVE');
INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6202000006', u.user_id, 20000000.00, TRUE, 'ACTIVE' FROM users AS u
WHERE u.username = 'user06' AND u.student_id = '723H0002'
  AND NOT EXISTS (SELECT 1 FROM accounts AS a WHERE a.account_number = '6202000006' AND a.user_id = u.user_id AND a.is_default = TRUE AND a.status = 'ACTIVE');
INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6202000007', u.user_id, 8000000.00, TRUE, 'ACTIVE' FROM users AS u
WHERE u.username = 'user07' AND u.student_id = '723H0003'
  AND NOT EXISTS (SELECT 1 FROM accounts AS a WHERE a.account_number = '6202000007' AND a.user_id = u.user_id AND a.is_default = TRUE AND a.status = 'ACTIVE');
INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6202000008', u.user_id, 35000000.00, TRUE, 'ACTIVE' FROM users AS u
WHERE u.username = 'user08' AND u.student_id = '723H0004'
  AND NOT EXISTS (SELECT 1 FROM accounts AS a WHERE a.account_number = '6202000008' AND a.user_id = u.user_id AND a.is_default = TRUE AND a.status = 'ACTIVE');

COMMIT;
