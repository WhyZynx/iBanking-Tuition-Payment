CREATE DATABASE IF NOT EXISTS account_db;
USE account_db;

CREATE TABLE IF NOT EXISTS users (
	user_id BIGINT AUTO_INCREMENT PRIMARY KEY,
	username VARCHAR(50) NOT NULL UNIQUE,
	password_hash VARCHAR(255) NOT NULL,
	full_name VARCHAR(100) NOT NULL,
	phone VARCHAR(20) NOT NULL,
	email VARCHAR(100) NOT NULL,
	student_id VARCHAR(20) NULL UNIQUE,
	created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounts (
	account_number VARCHAR(20) PRIMARY KEY,
	user_id BIGINT NOT NULL,
	balance DECIMAL(15, 2) NOT NULL,
	is_default BOOLEAN NOT NULL DEFAULT FALSE,
	status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
	CONSTRAINT chk_accounts_balance_nonnegative CHECK (balance >= 0),
	CONSTRAINT fk_accounts_user FOREIGN KEY (user_id) REFERENCES users(user_id)
);

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
