-- Restore the local demo data without dropping databases, tables, or users.
-- Stop User, Tuition, and Payment Service payment activity before running.
-- Run only against the normal demo databases after reviewing every pre-reset SELECT.
-- Run each database block separately. Each COMMIT is independent; this is not one atomic cross-service reset.
-- If a block errors, stop and ROLLBACK that block before continuing. Verify the pre-reset account query returns 8 rows.

-- 1. User Service: inspect, restore the eight balances, then remove their debit ledger rows.
USE account_db;

SELECT u.username, u.student_id, a.account_number, a.balance
FROM users AS u
JOIN accounts AS a ON a.user_id = u.user_id
WHERE (u.username = 'user01' AND u.student_id = '524H0001' AND a.account_number = '6202000001')
   OR (u.username = 'user02' AND u.student_id = '524H0002' AND a.account_number = '6202000002')
   OR (u.username = 'user03' AND u.student_id = '524H0003' AND a.account_number = '6202000003')
   OR (u.username = 'user04' AND u.student_id = '524H0004' AND a.account_number = '6202000004')
   OR (u.username = 'user05' AND u.student_id = '723H0001' AND a.account_number = '6202000005')
   OR (u.username = 'user06' AND u.student_id = '723H0002' AND a.account_number = '6202000006')
   OR (u.username = 'user07' AND u.student_id = '723H0003' AND a.account_number = '6202000007')
   OR (u.username = 'user08' AND u.student_id = '723H0004' AND a.account_number = '6202000008');

SELECT transaction_id, account_number, amount, balance_after
FROM account_debits
WHERE account_number IN ('6202000001','6202000002','6202000003','6202000004','6202000005','6202000006','6202000007','6202000008');

SET SQL_SAFE_UPDATES = 0;
START TRANSACTION;
DELETE d FROM account_debits AS d
JOIN accounts AS a ON a.account_number = d.account_number
JOIN users AS u ON u.user_id = a.user_id
WHERE (u.username = 'user01' AND u.student_id = '524H0001' AND a.account_number = '6202000001')
   OR (u.username = 'user02' AND u.student_id = '524H0002' AND a.account_number = '6202000002')
   OR (u.username = 'user03' AND u.student_id = '524H0003' AND a.account_number = '6202000003')
   OR (u.username = 'user04' AND u.student_id = '524H0004' AND a.account_number = '6202000004')
   OR (u.username = 'user05' AND u.student_id = '723H0001' AND a.account_number = '6202000005')
   OR (u.username = 'user06' AND u.student_id = '723H0002' AND a.account_number = '6202000006')
   OR (u.username = 'user07' AND u.student_id = '723H0003' AND a.account_number = '6202000007')
   OR (u.username = 'user08' AND u.student_id = '723H0004' AND a.account_number = '6202000008');
UPDATE accounts SET balance = 25000000.00 WHERE account_number = '6202000001' AND user_id = (SELECT user_id FROM users WHERE username = 'user01' AND student_id = '524H0001');
UPDATE accounts SET balance = 15000000.00 WHERE account_number = '6202000002' AND user_id = (SELECT user_id FROM users WHERE username = 'user02' AND student_id = '524H0002');
UPDATE accounts SET balance = 4000000.00 WHERE account_number = '6202000003' AND user_id = (SELECT user_id FROM users WHERE username = 'user03' AND student_id = '524H0003');
UPDATE accounts SET balance = 30000000.00 WHERE account_number = '6202000004' AND user_id = (SELECT user_id FROM users WHERE username = 'user04' AND student_id = '524H0004');
UPDATE accounts SET balance = 12000000.00 WHERE account_number = '6202000005' AND user_id = (SELECT user_id FROM users WHERE username = 'user05' AND student_id = '723H0001');
UPDATE accounts SET balance = 20000000.00 WHERE account_number = '6202000006' AND user_id = (SELECT user_id FROM users WHERE username = 'user06' AND student_id = '723H0002');
UPDATE accounts SET balance = 8000000.00 WHERE account_number = '6202000007' AND user_id = (SELECT user_id FROM users WHERE username = 'user07' AND student_id = '723H0003');
UPDATE accounts SET balance = 35000000.00 WHERE account_number = '6202000008' AND user_id = (SELECT user_id FROM users WHERE username = 'user08' AND student_id = '723H0004');
COMMIT;

SELECT u.username, u.student_id, a.account_number, a.balance
FROM users AS u
JOIN accounts AS a ON a.user_id = u.user_id
WHERE (u.username = 'user01' AND u.student_id = '524H0001' AND a.account_number = '6202000001')
   OR (u.username = 'user02' AND u.student_id = '524H0002' AND a.account_number = '6202000002')
   OR (u.username = 'user03' AND u.student_id = '524H0003' AND a.account_number = '6202000003')
   OR (u.username = 'user04' AND u.student_id = '524H0004' AND a.account_number = '6202000004')
   OR (u.username = 'user05' AND u.student_id = '723H0001' AND a.account_number = '6202000005')
   OR (u.username = 'user06' AND u.student_id = '723H0002' AND a.account_number = '6202000006')
   OR (u.username = 'user07' AND u.student_id = '723H0003' AND a.account_number = '6202000007')
   OR (u.username = 'user08' AND u.student_id = '723H0004' AND a.account_number = '6202000008');
SELECT transaction_id, account_number, amount, balance_after
FROM account_debits
WHERE account_number IN ('6202000001','6202000002','6202000003','6202000004','6202000005','6202000006','6202000007','6202000008');

USE payment_db;

SELECT transaction_id, payer_user_id, source_account_number, student_id, amount, status
FROM transactions
WHERE source_account_number IN ('6202000001','6202000002','6202000003','6202000004','6202000005','6202000006','6202000007','6202000008');

SELECT transaction_id, payer_user_id, source_account_number, student_id, amount, status
FROM transactions
WHERE student_id IN ('524H0001','524H0002','524H0003','524H0004','723H0001','723H0002','723H0003','723H0004')
  AND (source_account_number IS NULL OR source_account_number NOT IN ('6202000001','6202000002','6202000003','6202000004','6202000005','6202000006','6202000007','6202000008'));

SELECT o.otp_id, o.transaction_id, o.is_used
FROM otps AS o
JOIN transactions AS t ON t.transaction_id = o.transaction_id
WHERE t.source_account_number IN ('6202000001','6202000002','6202000003','6202000004','6202000005','6202000006','6202000007','6202000008');

START TRANSACTION;
DELETE o FROM otps AS o
JOIN transactions AS t ON t.transaction_id = o.transaction_id
WHERE t.source_account_number IN ('6202000001','6202000002','6202000003','6202000004','6202000005','6202000006','6202000007','6202000008');

DELETE FROM transactions
WHERE source_account_number IN ('6202000001','6202000002','6202000003','6202000004','6202000005','6202000006','6202000007','6202000008');
COMMIT;

SELECT transaction_id, payer_user_id, source_account_number, student_id, amount, status
FROM transactions
WHERE payer_user_id IN (
    SELECT user_id FROM account_db.users
    WHERE (username = 'user01' AND student_id = '524H0001')
       OR (username = 'user02' AND student_id = '524H0002')
       OR (username = 'user03' AND student_id = '524H0003')
       OR (username = 'user04' AND student_id = '524H0004')
       OR (username = 'user05' AND student_id = '723H0001')
       OR (username = 'user06' AND student_id = '723H0002')
       OR (username = 'user07' AND student_id = '723H0003')
       OR (username = 'user08' AND student_id = '723H0004')
) OR source_account_number IN ('6202000001','6202000002','6202000003','6202000004','6202000005','6202000006','6202000007','6202000008');
SELECT o.otp_id, o.transaction_id, o.is_used
FROM otps AS o
JOIN transactions AS t ON t.transaction_id = o.transaction_id
WHERE t.source_account_number IN ('6202000001','6202000002','6202000003','6202000004','6202000005','6202000006','6202000007','6202000008');

USE ibanking_tuition;

SELECT student_id, student_name, amount, status
FROM tuition_bills
WHERE student_id IN ('524H0001','524H0002','524H0003','524H0004','723H0001','723H0002','723H0003','723H0004');
SELECT student_id, transaction_id
FROM tuition_payment_claims
WHERE student_id IN ('524H0001','524H0002','524H0003','524H0004','723H0001','723H0002','723H0003','723H0004');

START TRANSACTION;
DELETE FROM tuition_payment_claims
WHERE student_id IN ('524H0001','524H0002','524H0003','524H0004','723H0001','723H0002','723H0003','723H0004');
UPDATE tuition_bills
SET status = CASE student_id
    WHEN '524H0001' THEN 'UNPAID'
    WHEN '524H0002' THEN 'UNPAID'
    WHEN '524H0003' THEN 'UNPAID'
    WHEN '524H0004' THEN 'UNPAID'
    WHEN '723H0001' THEN 'UNPAID'
    WHEN '723H0002' THEN 'PAID'
    WHEN '723H0003' THEN 'UNPAID'
    WHEN '723H0004' THEN 'UNPAID'
    ELSE status
END
WHERE student_id IN ('524H0001','524H0002','524H0003','524H0004','723H0001','723H0002','723H0003','723H0004');
COMMIT;

SELECT student_id, student_name, amount, status
FROM tuition_bills
WHERE student_id IN ('524H0001','524H0002','524H0003','524H0004','723H0001','723H0002','723H0003','723H0004');
SELECT student_id, transaction_id
FROM tuition_payment_claims
WHERE student_id IN ('524H0001','524H0002','524H0003','524H0004','723H0001','723H0002','723H0003','723H0004');
SET SQL_SAFE_UPDATES = 1;