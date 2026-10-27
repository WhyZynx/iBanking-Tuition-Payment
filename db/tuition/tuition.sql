CREATE DATABASE IF NOT EXISTS ibanking_tuition_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE ibanking_tuition_db;

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
