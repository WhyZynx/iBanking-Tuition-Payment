-- Optional local demo data for ibanking_tuition. Insert-only; never update bills.
USE ibanking_tuition;
START TRANSACTION;

-- Original sample bills, preserved as optional inserts rather than schema initialization.
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '524H0012', 'Nguyen Minh Anh', 18500000.00, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '524H0012');
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '524H0035', 'Tran Gia Huy', 16250000.00, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '524H0035');
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '524H0078', 'Le Hoang Phuc', 19750000.00, 'PAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '524H0078');
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '524H0104', 'Pham Ngoc Han', 17300000.00, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '524H0104');
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '524H0126', 'Vo Minh Khang', 21000000.00, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '524H0126');
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT '524H0159', 'Bui Thanh Truc', 15800000.00, 'PAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = '524H0159');

-- Additional fictional bills linked to the demo user mappings in demo_seed.sql.
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT 'DEMO24001', 'Minh Nguyen', 12000000.00, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = 'DEMO24001');
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT 'DEMO24002', 'Linh Tran', 18000000.00, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = 'DEMO24002');
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT 'DEMO24003', 'Khoa Le', 7500000.00, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = 'DEMO24003');
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT 'DEMO24004', 'Hanh Pham', 24000000.00, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = 'DEMO24004');
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT 'DEMO24005', 'Shared Scenario Student', 15000000.00, 'UNPAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = 'DEMO24005');
INSERT INTO tuition_bills (student_id, student_name, amount, status)
SELECT 'DEMO24006', 'Paid Scenario Student', 11000000.00, 'PAID'
WHERE NOT EXISTS (SELECT 1 FROM tuition_bills WHERE student_id = 'DEMO24006');

COMMIT;
