CREATE DATABASE IF NOT EXISTS ibanking_tuition
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE ibanking_tuition;

CREATE TABLE IF NOT EXISTS tuition_bills (
    student_id VARCHAR(20) PRIMARY KEY,
    student_name VARCHAR(100) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'UNPAID',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT chk_tuition_amount
        CHECK (amount > 0),

    CONSTRAINT chk_tuition_status
        CHECK (status IN ('UNPAID', 'PAID'))
);

CREATE TABLE IF NOT EXISTS tuition_payment_claims (
    student_id VARCHAR(20) PRIMARY KEY,
    transaction_id VARCHAR(36) NOT NULL UNIQUE,
    claimed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tuition_payment_claim_student
        FOREIGN KEY (student_id) REFERENCES tuition_bills(student_id)
);


INSERT INTO tuition_bills
    (student_id, student_name, amount, status)
VALUES
    ('524H0012', 'Nguyen Minh Anh', 18500000, 'UNPAID'),
    ('524H0035', 'Tran Gia Huy', 16250000, 'UNPAID'),
    ('524H0078', 'Le Hoang Phuc', 19750000, 'PAID'),
    ('524H0104', 'Pham Ngoc Han', 17300000, 'UNPAID'),
    ('524H0126', 'Vo Minh Khang', 21000000, 'UNPAID'),
    ('524H0159', 'Bui Thanh Truc', 15800000, 'PAID')
ON DUPLICATE KEY UPDATE
    student_name = VALUES(student_name),
    amount = VALUES(amount);
