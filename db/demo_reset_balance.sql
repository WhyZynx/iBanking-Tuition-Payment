-- Restore only the balances of the eight known demo accounts.
-- This script does NOT reset account_debits, Payment transactions, or transaction history.
-- Stop all three services before starting. Run the preflight first and inspect its output.
-- The confirmation flag defaults to 0, so running this whole file makes no changes.
-- After confirming exactly eight account/user matches, set the flag to 1 in this Workbench
-- session, then execute only the guarded transaction block below.

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

SET @demo_account_count = (
    SELECT COUNT(*)
    FROM users AS u
    JOIN accounts AS a ON a.user_id = u.user_id
    WHERE (u.username = 'user01' AND u.student_id = '524H0001' AND a.account_number = '6202000001')
       OR (u.username = 'user02' AND u.student_id = '524H0002' AND a.account_number = '6202000002')
       OR (u.username = 'user03' AND u.student_id = '524H0003' AND a.account_number = '6202000003')
       OR (u.username = 'user04' AND u.student_id = '524H0004' AND a.account_number = '6202000004')
       OR (u.username = 'user05' AND u.student_id = '723H0001' AND a.account_number = '6202000005')
       OR (u.username = 'user06' AND u.student_id = '723H0002' AND a.account_number = '6202000006')
       OR (u.username = 'user07' AND u.student_id = '723H0003' AND a.account_number = '6202000007')
       OR (u.username = 'user08' AND u.student_id = '723H0004' AND a.account_number = '6202000008')
);
SET @demo_reset_confirmed = 0;
SELECT @demo_account_count AS matched_demo_accounts,
       'Expected: 8. Leave confirmation at 0 unless exactly eight correct rows are shown.' AS instruction;

-- MANUAL CHECKPOINT:
-- After reviewing the SELECT output above, run this in the same Workbench session:
-- SET @demo_reset_confirmed = 1;
-- Then execute starting at SET @demo_reset_ready below. Do not confirm if the count is
-- not exactly 8 or any row is unexpected. Running the full file with the default flag is a no-op.

SET @demo_reset_ready = IF(@demo_account_count = 8 AND @demo_reset_confirmed = 1, 1, 0);
SELECT IF(@demo_reset_ready = 1,
          'READY: guarded balance update is enabled',
          'STOP: balance update is disabled; no data will change') AS reset_check;

START TRANSACTION;

UPDATE accounts
SET balance = 25000000.00
WHERE account_number = '6202000001'
  AND user_id = (SELECT user_id FROM users WHERE username = 'user01' AND student_id = '524H0001')
  AND @demo_reset_ready = 1;
UPDATE accounts
SET balance = 15000000.00
WHERE account_number = '6202000002'
  AND user_id = (SELECT user_id FROM users WHERE username = 'user02' AND student_id = '524H0002')
  AND @demo_reset_ready = 1;
UPDATE accounts
SET balance = 4000000.00
WHERE account_number = '6202000003'
  AND user_id = (SELECT user_id FROM users WHERE username = 'user03' AND student_id = '524H0003')
  AND @demo_reset_ready = 1;
UPDATE accounts
SET balance = 30000000.00
WHERE account_number = '6202000004'
  AND user_id = (SELECT user_id FROM users WHERE username = 'user04' AND student_id = '524H0004')
  AND @demo_reset_ready = 1;
UPDATE accounts
SET balance = 12000000.00
WHERE account_number = '6202000005'
  AND user_id = (SELECT user_id FROM users WHERE username = 'user05' AND student_id = '723H0001')
  AND @demo_reset_ready = 1;
UPDATE accounts
SET balance = 20000000.00
WHERE account_number = '6202000006'
  AND user_id = (SELECT user_id FROM users WHERE username = 'user06' AND student_id = '723H0002')
  AND @demo_reset_ready = 1;
UPDATE accounts
SET balance = 8000000.00
WHERE account_number = '6202000007'
  AND user_id = (SELECT user_id FROM users WHERE username = 'user07' AND student_id = '723H0003')
  AND @demo_reset_ready = 1;
UPDATE accounts
SET balance = 35000000.00
WHERE account_number = '6202000008'
  AND user_id = (SELECT user_id FROM users WHERE username = 'user08' AND student_id = '723H0004')
  AND @demo_reset_ready = 1;

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
