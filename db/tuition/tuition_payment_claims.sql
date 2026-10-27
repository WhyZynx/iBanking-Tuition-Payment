USE ibanking_tuition_db;

CREATE TABLE IF NOT EXISTS tuition_payment_claims (
    student_id VARCHAR(20) PRIMARY KEY,
    transaction_id VARCHAR(36) NOT NULL UNIQUE,
    claimed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tuition_payment_claim_student
        FOREIGN KEY (student_id) REFERENCES tuition_bills(student_id)
);
