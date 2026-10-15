USE payment_db;

ALTER TABLE transactions
    MODIFY COLUMN status VARCHAR(32) NULL;