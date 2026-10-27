-- Optional tuition demo bills matching db/user/demo_seed.sql.
-- Existing bills are never updated. On any duplicate-key error, run ROLLBACK and resolve it manually.

USE ibanking_tuition_db;
START TRANSACTION;

INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '524H0001', 'Nguyen Minh Anh', 18500000, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '524H0001' AND student_name = 'Nguyen Minh Anh' AND amount = 18500000 AND status IN ('UNPAID', 'PAID'));
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '524H0002', 'Tran Ngoc Han', 16500000, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '524H0002' AND student_name = 'Tran Ngoc Han' AND amount = 16500000 AND status IN ('UNPAID', 'PAID'));
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '524H0003', 'Le Hoang Nam', 19000000, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '524H0003' AND student_name = 'Le Hoang Nam' AND amount = 19000000 AND status IN ('UNPAID', 'PAID'));
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '524H0004', 'Pham Gia Linh', 17500000, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '524H0004' AND student_name = 'Pham Gia Linh' AND amount = 17500000 AND status IN ('UNPAID', 'PAID'));
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '723H0001', 'Vo Thanh Tung', 14000000, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '723H0001' AND student_name = 'Vo Thanh Tung' AND amount = 14000000 AND status IN ('UNPAID', 'PAID'));
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '723H0002', 'Do Khanh Vy', 18000000, 'PAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '723H0002' AND student_name = 'Do Khanh Vy' AND amount = 18000000 AND status = 'PAID');
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '723H0003', 'Bui Quoc Bao', 12500000, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '723H0003' AND student_name = 'Bui Quoc Bao' AND amount = 12500000 AND status IN ('UNPAID', 'PAID'));
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '723H0004', 'Huynh Thao My', 21000000, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '723H0004' AND student_name = 'Huynh Thao My' AND amount = 21000000 AND status IN ('UNPAID', 'PAID'));

COMMIT;
