-- Tạo database riêng cho Payment Service
CREATE DATABASE IF NOT EXISTS ibanking_payment_db;
USE ibanking_payment_db;

-- Canonical fresh-install schema. Existing tables are upgraded below.
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

DROP PROCEDURE IF EXISTS upgrade_payment_schema;
DELIMITER $$
CREATE PROCEDURE upgrade_payment_schema()
BEGIN
    DECLARE has_student_name BIGINT DEFAULT 0;
    DECLARE has_reconciliation_code BIGINT DEFAULT 0;
    DECLARE has_otp_index BIGINT DEFAULT 0;
    DECLARE has_otp_foreign_key BIGINT DEFAULT 0;
    DECLARE invalid_rows BIGINT DEFAULT 0;

    SELECT COUNT(*) INTO has_student_name
      FROM information_schema.columns
     WHERE table_schema = DATABASE()
       AND table_name = 'transactions'
       AND column_name = 'student_name';
    IF has_student_name = 0 THEN
        ALTER TABLE transactions ADD COLUMN student_name VARCHAR(255) NULL;
    END IF;

    SELECT COUNT(*) INTO has_reconciliation_code
      FROM information_schema.columns
     WHERE table_schema = DATABASE()
       AND table_name = 'transactions'
       AND column_name = 'reconciliation_code';
    IF has_reconciliation_code = 0 THEN
        ALTER TABLE transactions ADD COLUMN reconciliation_code VARCHAR(64) NULL;
    END IF;

    SELECT
        (SELECT COUNT(*) FROM transactions
         WHERE payer_user_id IS NULL
            OR source_account_number IS NULL
            OR student_id IS NULL
            OR status IS NULL
            OR created_at IS NULL)
        +
        (SELECT COUNT(*) FROM otps
         WHERE transaction_id IS NULL
            OR otp_code IS NULL
            OR expires_at IS NULL
            OR is_used IS NULL)
        +
        (SELECT COUNT(*)
         FROM otps o
         LEFT JOIN transactions t ON t.transaction_id = o.transaction_id
         WHERE t.transaction_id IS NULL)
    INTO invalid_rows;

    IF invalid_rows <> 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Payment schema upgrade stopped: required NULL values or orphan OTP rows exist';
    END IF;

    ALTER TABLE transactions
        MODIFY COLUMN payer_user_id BIGINT NOT NULL,
        MODIFY COLUMN source_account_number VARCHAR(20) NOT NULL,
        MODIFY COLUMN student_id VARCHAR(20) NOT NULL,
        MODIFY COLUMN status VARCHAR(32) NOT NULL,
        MODIFY COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

    ALTER TABLE otps
        MODIFY COLUMN transaction_id VARCHAR(36) NOT NULL,
        MODIFY COLUMN otp_code VARCHAR(10) NOT NULL,
        MODIFY COLUMN expires_at TIMESTAMP NOT NULL,
        MODIFY COLUMN is_used BOOLEAN NOT NULL DEFAULT FALSE;

    SELECT COUNT(*) INTO has_otp_index
      FROM information_schema.statistics
     WHERE table_schema = DATABASE()
       AND table_name = 'otps'
       AND index_name = 'ix_otps_transaction_id';
    IF has_otp_index = 0 THEN
        ALTER TABLE otps ADD INDEX ix_otps_transaction_id (transaction_id);
    END IF;

    SELECT COUNT(*) INTO has_otp_foreign_key
      FROM information_schema.key_column_usage
     WHERE table_schema = DATABASE()
       AND table_name = 'otps'
       AND column_name = 'transaction_id'
       AND referenced_table_name = 'transactions'
       AND referenced_column_name = 'transaction_id';
    IF has_otp_foreign_key = 0 THEN
        ALTER TABLE otps
            ADD CONSTRAINT fk_otps_transaction
            FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id);
    END IF;
END$$
DELIMITER ;

CALL upgrade_payment_schema();
DROP PROCEDURE upgrade_payment_schema;
