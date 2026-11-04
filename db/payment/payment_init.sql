-- Tạo database riêng cho Payment Service
CREATE DATABASE IF NOT EXISTS ibanking_payment_db;
USE ibanking_payment_db;

-- Tạo bảng Lưu lịch sử giao dịch
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id VARCHAR(36) PRIMARY KEY,
    payer_user_id BIGINT NOT NULL,
    source_account_number VARCHAR(20) NOT NULL,
    student_id VARCHAR(20) NOT NULL,
    student_name VARCHAR(255) NULL,
    amount DECIMAL(15, 2),
    status VARCHAR(32) NOT NULL,
    reconciliation_code VARCHAR(64) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL
);

-- Tạo bảng Lưu mã OTP
CREATE TABLE IF NOT EXISTS otps (
    otp_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(36) NOT NULL,
    otp_code VARCHAR(10) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    INDEX ix_otps_transaction_id (transaction_id),
    CONSTRAINT fk_otps_transaction
        FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
