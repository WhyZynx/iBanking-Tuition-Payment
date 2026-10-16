-- Forward-only integrity migration for payment_db.
-- SAFETY: inspect the preflight result first. This script signals an error and
-- stops before ALTER TABLE if any required value is NULL, any OTP is orphaned,
-- or an OTP foreign key already exists. It never changes historical row values.
-- Run only against an explicitly selected, backed-up target database.

USE payment_db;

DROP PROCEDURE IF EXISTS assert_payment_integrity_preflight;
DELIMITER $$
CREATE PROCEDURE assert_payment_integrity_preflight()
BEGIN
    DECLARE invalid_rows BIGINT DEFAULT 0;
    DECLARE existing_otp_fks BIGINT DEFAULT 0;

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

    SELECT COUNT(*)
      INTO existing_otp_fks
      FROM information_schema.key_column_usage
     WHERE table_schema = DATABASE()
       AND table_name = 'otps'
       AND column_name = 'transaction_id'
       AND referenced_table_name IS NOT NULL;

    IF invalid_rows <> 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Preflight failed: NULL required fields or orphan OTP rows exist; no schema changes applied';
    END IF;

    IF existing_otp_fks <> 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Preflight failed: an OTP transaction_id foreign key already exists; inspect schema before migration';
    END IF;
END$$
DELIMITER ;

CALL assert_payment_integrity_preflight();
DROP PROCEDURE assert_payment_integrity_preflight;

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
    MODIFY COLUMN is_used BOOLEAN NOT NULL DEFAULT FALSE,
    ADD INDEX ix_otps_transaction_id (transaction_id),
    ADD CONSTRAINT fk_otps_transaction
        FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id);
