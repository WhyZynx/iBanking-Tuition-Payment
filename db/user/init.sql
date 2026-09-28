CREATE DATABASE IF NOT EXISTS account_db;
USE account_db;

CREATE TABLE IF NOT EXISTS users (
	user_id BIGINT AUTO_INCREMENT PRIMARY KEY,
	username VARCHAR(50) NOT NULL UNIQUE,
	password_hash VARCHAR(255) NOT NULL,
	full_name VARCHAR(100) NOT NULL,
	phone VARCHAR(20) NOT NULL,
	email VARCHAR(100) NOT NULL,
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

INSERT INTO users (username, password_hash, full_name, phone, email)
VALUES (
	'user01',
	'$2b$12$PxWXN9r0ukABcgaalI/pEOwMnEOLN2R9bjZFCLOWNCstuW2r5huhG',
	'Nguyen Van A',
	'0901234567',
	'user01@example.com'
)
ON DUPLICATE KEY UPDATE username = VALUES(username);

INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '1012345678', user_id, 15000000.00, TRUE, 'ACTIVE'
FROM users WHERE username = 'user01'
ON DUPLICATE KEY UPDATE account_number = VALUES(account_number);

INSERT INTO accounts (account_number, user_id, balance, is_default, status)
SELECT '1012345679', user_id, 5000000.00, FALSE, 'ACTIVE'
FROM users WHERE username = 'user01'
ON DUPLICATE KEY UPDATE account_number = VALUES(account_number);
