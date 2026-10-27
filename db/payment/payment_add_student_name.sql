USE ibanking_payment_db;

ALTER TABLE transactions
    ADD COLUMN student_name VARCHAR(255) NULL;
