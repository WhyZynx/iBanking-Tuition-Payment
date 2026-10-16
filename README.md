# iBanking Tuition Payment System

## Table of Contents

- [Project Overview](#project-overview)
- [Requirements](#requirements)
- [Initial Setup](#initial-setup)
- [How to Run](#how-to-run)
- [Demo Accounts](#demo-accounts)
- [Demo Flow](#demo-flow)
- [Testing](#testing)
- [Reset Demo Data](#reset-demo-data)
- [Troubleshooting](#troubleshooting)

## Project Overview

iBanking is a student project for checking tuition bills and paying them from demo bank accounts. It has three FastAPI services: User, Tuition, and Payment. The frontend uses HTML, CSS, and JavaScript; services use MySQL, Python, and email OTP.

## Requirements

- Windows 10 or newer with PowerShell and VS Code.
- Python 3.10 or newer. The repository does not pin one Python version.
- MySQL Server and MySQL Workbench. The SQL uses MySQL syntax; MySQL 8 is recommended.
- Git.
- Node.js is not required to run the frontend. It is only needed if you want to run `node --check`.
- A Gmail account with 2-Step Verification and an App Password is needed to receive OTP email through Gmail SMTP.

## Initial Setup

### 1. Clone and open the project

```powershell
git clone <repository-url>
cd iBanking-System-Final
code .
```

Replace `<repository-url>` with the repository address. If the `code` command is unavailable, open this folder from VS Code using **File > Open Folder**.

### 2. Create a Python environment

Run from the repository root:

```powershell
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/user_service/requirements.txt
python -m pip install -r backend/tuition_service/requirements.txt
python -m pip install -r backend/payment_service/requirements.txt
```

Run all three install commands. Each service has its own `requirements.txt`.

### 3. Create the databases and tables

In MySQL Workbench, open and run these schema files in order on a new local installation:

1. `db/user/init.sql` creates `account_db`.
2. `db/tuition/tuition.sql` creates `ibanking_tuition`.
3. `db/payment/payment_init.sql` creates `payment_db`.

These files create the current schemas. Do not run legacy `ALTER TABLE` migrations on a fresh database. For an existing database, inspect its tables first and use only the migration that matches its current schema. Some older migrations are one-time operations; see `db/` before applying them. Never use these demo instructions to reset a shared or production database.

Demo records are optional. After checking for conflicts, run `db/user/demo_seed.sql` on `account_db`, then `db/tuition/demo_seed.sql` on `ibanking_tuition`. The seeds add records and do not restore balances or overwrite tuition status. If a seed reports a duplicate key or any error, stop, run `ROLLBACK;` in that Workbench session, and resolve the conflict manually. In particular, an older `user01` record (`Nguyen Van A`, student ID `524H0104`) conflicts with the current demo data. Do not change or delete that account to make the seed run; use clean local demo databases instead. See [docs/DEMO_DATA.md](docs/DEMO_DATA.md) for read-only conflict checks.

### 4. Create service environment files

Copy each example beside that service's `config.py`:

```powershell
Copy-Item backend/user_service/.env.example backend/user_service/.env
Copy-Item backend/tuition_service/.env.example backend/tuition_service/.env
Copy-Item backend/payment_service/.env.example backend/payment_service/.env
```

Edit these local files:

- `backend/user_service/.env`: set `DATABASE_URL` to your MySQL credentials and `account_db`; set a local `JWT_SECRET_KEY` and `INTERNAL_API_KEY`.
- `backend/tuition_service/.env`: set `DATABASE_URL` to the same MySQL server and `ibanking_tuition`; set the same `INTERNAL_API_KEY`.
- `backend/payment_service/.env`: set `PAYMENT_DATABASE_URL` to `payment_db`; use matching `JWT_SECRET_KEY` and `INTERNAL_API_KEY`; keep `USER_SERVICE_URL=http://localhost:8001` and `TUITION_SERVICE_URL=http://localhost:8002` for local runs.

Use the same MySQL username/password in the three database URLs if that account has access to all three databases. Do not paste secrets into source files, this README, or `.env.example`. The `.env` files are ignored by Git.

### 5. Configure Gmail SMTP for OTP

In the Payment Service `.env`, set:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-gmail-address@gmail.com
SMTP_PASSWORD=your-16-character-app-password
SMTP_FROM_EMAIL=your-gmail-address@gmail.com
```

Use a Gmail App Password, not your normal Google password. Google requires 2-Step Verification to create one; open your Google Account security settings and create an App Password if the option is available. Some managed, security-key-only, or Advanced Protection accounts may not offer it. Keep the App Password only in the local Payment Service `.env`. See [Google's App Password help](https://support.google.com/accounts/answer/185833).

The seed uses `example.com` addresses, which cannot receive mail. For a disposable local demo database, set the demo user's `email` to a mailbox you control before testing OTP. Do not change an existing real user's email or put your mailbox address in a seed or committed file.

## How to Run

Activate `.venv` in each PowerShell terminal. From the repository root, start every service in its own terminal:

### 1. User Service — port 8001

```powershell
python -m uvicorn backend.user_service.main:app --host 127.0.0.1 --port 8001
```

### 2. Tuition Service — port 8002

```powershell
python -m uvicorn backend.tuition_service.main:app --host 127.0.0.1 --port 8002
```

### 3. Payment Service — port 8003

```powershell
python -m uvicorn backend.payment_service.main:app --host 127.0.0.1 --port 8003
```

### 4. Frontend — port 5500

```powershell
python -m http.server 5500 --directory frontend
```

Open the application at <http://localhost:5500>. Swagger pages are at <http://localhost:8001/docs>, <http://localhost:8002/docs>, and <http://localhost:8003/docs>. Health checks use `/health` on each backend port. Press `Ctrl+C` in each terminal to stop its service.

## Demo Accounts

These values come from `db/user/demo_seed.sql`. The password is bcrypt-hashed in the database. Initial balances may change after payments.

| Username | Demo Password | Student ID | Initial Balance (VND) |
| --- | --- | --- | ---: |
| user01 | `password123` | 524H0001 | 25,000,000 |
| user02 | `password123` | 524H0002 | 15,000,000 |
| user03 | `password123` | 524H0003 | 4,000,000 |
| user04 | `password123` | 524H0004 | 30,000,000 |
| user05 | `password123` | 723H0001 | 12,000,000 |
| user06 | `password123` | 723H0002 | 20,000,000 |
| user07 | `password123` | 723H0003 | 8,000,000 |
| user08 | `password123` | 723H0004 | 35,000,000 |

## Demo Flow

1. Log in with one of the demo accounts.
2. Open **Accounts** and check the balance.
3. Choose **Pay for Me** or **Pay for Others**.
4. Search for the student's ID and review the tuition bill.
5. Request an OTP. Check the mailbox configured for that demo user.
6. Enter the OTP and confirm payment.
7. Check the updated balance, tuition status, and Payment History.

## Testing

Run local unit and mock tests from the repository root:

```powershell
python -m pytest tests/user_service tests/tuition_service tests/payment_service -q
```

These suites use temporary SQLite databases or mocks. The optional MySQL concurrency tests require an explicitly configured `USER_SERVICE_TEST_DATABASE_URL` pointing to `account_db_test`; they are database integration tests, not SQLite tests. Real HTTP E2E tests can write data and send OTP through a test SMTP sink, so do not run them against demo databases without following their safety setup and approval requirements.

| Test | How to run or perform | Expected result |
| --- | --- | --- |
| Normal successful payment | Manual demo flow with MySQL and configured SMTP | One debit, tuition becomes `PAID`, transaction becomes `SUCCESS`, history shows it |
| Invalid OTP | `python -m pytest tests/payment_service/test_payment_otp.py -k "expired_wrong_or_used" -q` | Wrong, expired, and used codes are rejected; no debit or tuition update |
| Expired OTP | `python -m pytest tests/payment_service/test_payment_otp.py -k "expired_wrong_or_used" -q` | Rejected; no debit |
| OTP resend | `python -m pytest tests/payment_service/test_payment_otp.py -k "requesting_otp_again" -q` | Previous OTP is invalid; newest code is usable after successful email |
| EX08 — OTP replay | `python -m pytest tests/payment_service/test_payment_database_concurrency.py -k "otp_consume" -q` | OTP can be consumed only once |
| EX12 — Concurrent payment | `python -m pytest tests/payment_service/test_payment_concurrency.py -q` | Competing payers produce at most one successful payment and debit |
| EX13 — Concurrent debit | `python -m pytest tests/user_service/test_user_service.py -k "concurrent" -q` | No overdraft; a repeated transaction ID debits once |
| EX16 — Service outage | `python -m pytest tests/payment_service/test_payment_confirmation.py -k "unavailable" -q` | Service failure is reported; no unsafe debit is made |
| EX18 — Partial failure recovery | `python -m pytest tests/payment_service/test_payment_confirmation.py -k "tuition_failure_after_debit" -q` | Mock fault test marks `RECONCILIATION_REQUIRED`; no automatic refund is implemented |
| EX19 — SMTP failure | `python -m pytest tests/payment_service/test_payment_otp.py tests/payment_service/test_payment_confirmation.py -k "smtp_failure or success_email_failure" -q` | Failed OTP email is not reported as sent; email failure after success does not change `SUCCESS` |

EX08–EX19 pytest commands are mock/SQLite tests; they do not send real email or connect to MySQL. Manual MySQL concurrency and SMTP checks require a separately prepared test environment. EX18 is only tested with pytest mocks; do not inject faults while using demo databases. The system has no automatic refund; uncertain partial payment is recorded as `RECONCILIATION_REQUIRED` for manual review.

## Reset Demo Data

Stop all three backends and make sure no payment is in progress. Back up the three local demo databases. Run reset scripts only on `account_db`, `payment_db`, and `ibanking_tuition`; never use E2E, shared, or production databases.

- `db/demo_reset_balance.sql` restores the eight demo account balances only.
- `db/demo_reset_full.sql` also removes payment transactions, OTPs, debit ledger rows, and tuition claims for the demo records, and restores the seeded tuition statuses. It does not drop databases, tables, or users. Changes across three databases are separate commits, not one atomic transaction.

In Workbench, keep the confirmation flag at `0` and run the script once to review its preflight results. Continue only when all eight exact demo account mappings are present. For the full reset, also require all eight seeded tuition bills, zero `PROCESSING` or `RECONCILIATION_REQUIRED` transactions, and zero out-of-scope transaction counts. Check the listed transactions with a `NULL` source account. Stop and resolve any mismatch or uncertain row manually.

After reviewing, set `@demo_reset_confirmed = 1` in the same Workbench connection. For the balance-only file, execute from `SET @demo_reset_ready` through the guarded balance transaction. For the full file, execute the three marked mutation blocks one at a time in order: Payment, Tuition, then User. Do not rerun the entire file after confirmation; it resets the flag to `0`. The full reset removes demo transaction history. Verify the post-reset `SELECT` results before restarting services.

The scripts keep MySQL Safe Updates enabled and filter writes/deletes by primary or indexed keys. If Workbench reports Safe Update Error 1175, stop and inspect the selected database and target rows; do not disable Safe Updates globally or bypass the check without reviewing the statement.

## Troubleshooting

- **MySQL connection failed:** check MySQL is running, the service `.env` URL has the right host, credentials, and database name, and the user can access that database.
- **Backend service not running:** check its terminal for startup errors and open the matching `/health` URL.
- **Port already in use:** stop the old process or close its terminal, then restart the service on the required port.
- **OTP email not received:** verify the demo user's email is a mailbox you control, the Payment Service SMTP settings are correct, and `SMTP_PASSWORD` is a Gmail App Password. Check spam and the Payment terminal for an error without sharing secrets.

## Docker Deployment

Nginx is not strictly required to run the application, but it provides one browser entry point for the Docker deployment. It serves the static frontend on port `8080` and routes browser API requests to the User, Tuition, or Payment Service by URL path. This keeps the Docker frontend on one origin instead of hard-coding backend ports in browser requests, and makes the deployment closer to a typical reverse-proxy setup. Nginx does not replace backend authentication or authorization.

### 1. Requirements

- Docker Engine and Docker Compose installed and running. Docker Desktop is also supported.
- Git.

### 2. Configure Environment

Create the Docker environment file:

```bash
cp .env.docker.example .env.docker
```

Update `.env.docker` with your local configuration and credentials. Do not commit this file to Git.

### 3. Build and Run

Run from the project root:

```bash
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up --build -d
```

### 4. Check Services

```bash
docker compose --env-file .env.docker ps
```

Open the application through Nginx:

- Frontend: http://localhost:8080

Nginx routes `/api/v1/tuition` to the Tuition Service, `/api/v1/payments` and `/api/v1/transactions` to the Payment Service, and other `/api/v1/` requests to the User Service. Backend ports are not published on the host; services communicate over the private Docker network.

The backend Swagger pages are not exposed through Nginx in this setup. To access them from the host for debugging, temporarily publish the required backend port in `docker-compose.yml` and recreate that service.

### 5. Stop Services

```bash
docker compose --env-file .env.docker down
```

To start the services again:

```bash
docker compose --env-file .env.docker up -d
```

**Note:** `docker compose down -v` removes named volumes and may delete database data. Use it only when you intend to reset the database.