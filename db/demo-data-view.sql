SELECT
    u.username AS Username,
    u.full_name AS FullName,
    a.account_number AS AccountNumber,
    a.balance AS CurrentBalance,
    a.status AS AccountStatus,
    u.student_id AS StudentID,
    t.student_id AS TuitionBillID,
    t.amount AS TuitionAmount,
    t.status AS TuitionStatus
FROM ibanking_account_db.users AS u
LEFT JOIN ibanking_account_db.accounts AS a ON a.user_id = u.user_id
LEFT JOIN ibanking_tuition_db.tuition_bills AS t
    ON t.student_id = u.student_id COLLATE utf8mb4_unicode_ci
ORDER BY u.username, a.is_default DESC, a.account_number;
