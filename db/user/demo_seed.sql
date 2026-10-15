-- Optional local demo data for account_db. Insert-only: never update users or balances.
-- All added usernames are explicitly prefixed with demo_.
-- Shared demo login password: CampusDemo!2026
-- Hash generated with bcrypt (cost 12), compatible with User Service verify_password().

USE account_db;
START TRANSACTION;

-- Retain the original demo identity when absent. Its existing password is not documented here.
INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'user01',
       '$2b$12$PxWXN9r0ukABcgaalI/pEOwMnEOLN2R9bjZFCLOWNCstuW2r5huhG',
       'Nguyen Van A', '0901234567', 'user01@example.com', '524H0104'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'user01')
  AND NOT EXISTS (SELECT 1 FROM users WHERE student_id = '524H0104');

INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'demo_minh',
       '$2b$12$8z0P56S92sjqyF.EAB.IneWszMkQ/ivxc.tQHeBwVpObmGry70yEa',
       'Minh Nguyen', '0902000001', 'demo.minh@example.test', 'DEMO24001'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'demo_minh')
  AND NOT EXISTS (SELECT 1 FROM users WHERE student_id = 'DEMO24001');

INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'demo_linh',
       '$2b$12$8z0P56S92sjqyF.EAB.IneWszMkQ/ivxc.tQHeBwVpObmGry70yEa',
       'Linh Tran', '0902000002', 'demo.linh@example.test', 'DEMO24002'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'demo_linh')
  AND NOT EXISTS (SELECT 1 FROM users WHERE student_id = 'DEMO24002');

INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'demo_khoa',
       '$2b$12$8z0P56S92sjqyF.EAB.IneWszMkQ/ivxc.tQHeBwVpObmGry70yEa',
       'Khoa Le', '0902000003', 'demo.khoa@example.test', 'DEMO24003'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'demo_khoa')
  AND NOT EXISTS (SELECT 1 FROM users WHERE student_id = 'DEMO24003');

INSERT INTO users (username, password_hash, full_name, phone, email, student_id)
SELECT 'demo_hanh',
       '$2b$12$8z0P56S92sjqyF.EAB.IneWszMkQ/ivxc.tQHeBwVpObmGry70yEa',
       'Hanh Pham', '0902000004', 'demo.hanh@example.test', 'DEMO24004'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'demo_hanh')
  AND NOT EXISTS (SELECT 1 FROM users WHERE student_id = 'DEMO24004');

-- Keep the original account numbers, but only insert them if they are absent.
INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '1012345678', user_id, 15000000.00, TRUE, 'ACTIVE'
FROM users
WHERE username = 'user01'
  AND student_id = '524H0104'
  AND password_hash = '$2b$12$PxWXN9r0ukABcgaalI/pEOwMnEOLN2R9bjZFCLOWNCstuW2r5huhG'
  AND NOT EXISTS (SELECT 1 FROM accounts WHERE account_number = '1012345678');

INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '1012345679', user_id, 5000000.00, FALSE, 'ACTIVE'
FROM users
WHERE username = 'user01'
  AND student_id = '524H0104'
  AND password_hash = '$2b$12$PxWXN9r0ukABcgaalI/pEOwMnEOLN2R9bjZFCLOWNCstuW2r5huhG'
  AND NOT EXISTS (SELECT 1 FROM accounts WHERE account_number = '1012345679');

INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6201000001', user_id, 25000000.00, TRUE, 'ACTIVE'
FROM users
WHERE username = 'demo_minh'
  AND student_id = 'DEMO24001'
  AND password_hash = '$2b$12$8z0P56S92sjqyF.EAB.IneWszMkQ/ivxc.tQHeBwVpObmGry70yEa'
  AND NOT EXISTS (SELECT 1 FROM accounts WHERE account_number = '6201000001');

INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6201000002', user_id, 4000000.00, FALSE, 'ACTIVE'
FROM users
WHERE username = 'demo_minh'
  AND student_id = 'DEMO24001'
  AND password_hash = '$2b$12$8z0P56S92sjqyF.EAB.IneWszMkQ/ivxc.tQHeBwVpObmGry70yEa'
  AND NOT EXISTS (SELECT 1 FROM accounts WHERE account_number = '6201000002');

INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6201000003', user_id, 13000000.00, TRUE, 'ACTIVE'
FROM users
WHERE username = 'demo_linh'
  AND student_id = 'DEMO24002'
  AND password_hash = '$2b$12$8z0P56S92sjqyF.EAB.IneWszMkQ/ivxc.tQHeBwVpObmGry70yEa'
  AND NOT EXISTS (SELECT 1 FROM accounts WHERE account_number = '6201000003');

INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6201000004', user_id, 8000000.00, TRUE, 'ACTIVE'
FROM users
WHERE username = 'demo_khoa'
  AND student_id = 'DEMO24003'
  AND password_hash = '$2b$12$8z0P56S92sjqyF.EAB.IneWszMkQ/ivxc.tQHeBwVpObmGry70yEa'
  AND NOT EXISTS (SELECT 1 FROM accounts WHERE account_number = '6201000004');

INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '6201000005', user_id, 26000000.00, TRUE, 'ACTIVE'
FROM users
WHERE username = 'demo_hanh'
  AND student_id = 'DEMO24004'
  AND password_hash = '$2b$12$8z0P56S92sjqyF.EAB.IneWszMkQ/ivxc.tQHeBwVpObmGry70yEa'
  AND NOT EXISTS (SELECT 1 FROM accounts WHERE account_number = '6201000005');

COMMIT;
