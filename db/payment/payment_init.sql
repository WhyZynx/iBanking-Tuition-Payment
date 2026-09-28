-- Tạo database riêng cho Payment Service
CREATE DATABASE IF NOT EXISTS payment_db;
USE payment_db;

-- Tạo bảng Lưu lịch sử giao dịch
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id VARCHAR(36) PRIMARY KEY,
    payer_user_id BIGINT,
    source_account_number VARCHAR(20),
    student_id VARCHAR(20),
    student_name VARCHAR(255) NULL,
    amount DECIMAL(15, 2),
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL
);

-- Tạo bảng Lưu mã OTP
CREATE TABLE IF NOT EXISTS otps (
    otp_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(36),
    otp_code VARCHAR(10),
    expires_at TIMESTAMP,
    is_used BOOLEAN DEFAULT FALSE
);
