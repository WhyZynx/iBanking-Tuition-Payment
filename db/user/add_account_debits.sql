USE account_db;

CREATE TABLE IF NOT EXISTS account_debits (
    transaction_id VARCHAR(100) PRIMARY KEY,
    account_number VARCHAR(20) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    balance_after DECIMAL(15, 2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_account_debits_amount CHECK (amount > 0),
    CONSTRAINT chk_account_debits_balance CHECK (balance_after >= 0),
    CONSTRAINT fk_account_debits_account FOREIGN KEY (account_number)
        REFERENCES accounts(account_number),
    INDEX ix_account_debits_account_number (account_number)
);
