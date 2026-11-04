-- Forward migration for Payment reconciliation reason tracking.
-- Run against ibanking_payment_db after a reviewed, verified backup.
USE ibanking_payment_db;

ALTER TABLE transactions
    ADD COLUMN reconciliation_code VARCHAR(64) NULL;
