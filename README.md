# iBanking Tuition Payment System

A university Service-Oriented Architecture (SOA) demo for paying tuition from a simulated bank account. It uses three FastAPI services, three separate MySQL databases, and an email OTP confirmation step.

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Prerequisites](#4-prerequisites)
5. [Quick Start](#5-quick-start)
6. [Interactive Setup Menu](#6-interactive-setup-menu)
7. [Demo Accounts and Data](#7-demo-accounts-and-data)
8. [Manual Testing -- Mailpit](#8-manual-testing----mailpit)
9. [Testing OTP with Real Gmail](#9-testing-otp-with-real-gmail)
10. [Additional Testing Scenarios](#10-additional-testing-scenarios)
11. [Stop, Restart and Reset](#11-stop-restart-and-reset)
12. [Project Structure](#12-project-structure)
13. [Troubleshooting](#13-troubleshooting)

## 1. Project Overview

Users can sign in, view their simulated bank account, find an unpaid tuition bill, and pay it after confirming an email OTP. Payment history and the current account balance are available in the web app.

## 2. System Architecture

```text
Browser -> Nginx -> User & Account Service -> ibanking_account_db
                 -> Tuition Service       -> ibanking_tuition_db
                 -> Payment Service       -> ibanking_payment_db
                                           -> Mailpit or configured SMTP
```

- **User & Account Service** authenticates users and provides profile and account data. It protects account debits against duplicate requests and concurrent balance changes.
- **Tuition Service** looks up student bills and claims or confirms tuition payments.
- **Payment Service** creates payment transactions, sends and verifies OTPs, and coordinates the other services.
- **Nginx** serves the frontend and routes public API requests to the services.
- **MySQL** stores separate user/account, tuition, and payment data.
- **Mailpit** receives demo email locally. Gmail SMTP is an optional delivery configuration.

The repository also contains older submission diagrams in `diagram/`. The microservice diagram includes an external tuition system that is not part of the current Compose runtime, so the diagram is retained as project material but is not presented as the current runtime architecture.

## 3. Technology Stack

- Python 3.12, FastAPI, SQLAlchemy, and PyMySQL for the backend services.
- MySQL 8.4 for persistent service databases.
- Docker Compose for local setup and service networking.
- Nginx for frontend hosting and API routing.
- HTML, CSS, and JavaScript for the web frontend.
- Pytest for unit, database, and concurrency tests.
- Mailpit for local SMTP capture; Gmail SMTP is optional.

## 4. Prerequisites

- Git.
- Docker Desktop with Docker Compose v2, installed and running before setup.
- To use `./setup.sh` on Windows, use Git Bash. Linux and macOS need Docker Compose v2 and the standard shell utilities used by the script.

No host MySQL server, Python installation, database import, or email account is required for the default demo.

## 5. Quick Start

Clone the repository, start Docker Desktop, then run setup from the project directory.

```bash
git clone https://github.com/WhyZynx/iBanking-Tuition-Payment.git
cd iBanking-Tuition-Payment
./setup.sh
```

On Windows, run:

```bat
setup.bat
```

Setup creates `.env.docker` with local random secrets if the file is missing. It does not overwrite an existing file or reset databases. It starts the services, waits for their health checks, verifies the frontend and Mailpit, checks demo login, then shows the interactive menu. Fresh installations use Mailpit and initialize all three databases automatically.

Default addresses:

- Frontend: <http://localhost:8080>
- Mailpit inbox: <http://localhost:8025>

If a web port is already in use, set `FRONTEND_PORT` or `MAILPIT_WEB_PORT` in the ignored `.env.docker` and run setup again. MySQL and backend ports are not published to the host.

## 6. Interactive Setup Menu

After successful setup, the menu provides:

| Option | Action |
| --- | --- |
| `1` | View current demo data from MySQL using read-only queries. |
| `2` | Open the iBanking frontend in the default browser. |
| `3` | Open the Mailpit inbox in the default browser. |
| `4` | Choose Mailpit or configure Gmail SMTP for Payment Service. |
| `0` | Exit the menu. Docker services continue running. |

Invalid input returns to the menu. A database viewer error also returns to the menu after showing a troubleshooting hint.

Option 4 has this submenu:

| Option | Email mode |
| --- | --- |
| `1` | Mailpit local testing: `mailpit:1025`, no authentication or TLS. |
| `2` | Gmail SMTP: `smtp.gmail.com:587`, authenticated with STARTTLS. |
| `0` | Return to the main menu. |

Changing the mode updates only SMTP settings in `.env.docker` and recreates Payment Service. MySQL, other services, and stored data are left running. The Gmail App Password is entered without displaying it, stored locally in the Git-ignored `.env.docker`, and not printed by the menu. Gmail delivery is not tested automatically.

## 7. Demo Accounts and Data

The demo users are `user01` through `user08`. Their shared demo password is `password123`.

The following are **initial seed values**, not guaranteed current values:

| Username | Student ID | Initial balance (VND) | Initial tuition (VND) | Initial tuition status |
| --- | --- | ---: | ---: | --- |
| `user01` | `524H0001` | 25,000,000 | 18,500,000 | UNPAID |
| `user02` | `524H0002` | 15,000,000 | 16,500,000 | UNPAID |
| `user03` | `524H0003` | 4,000,000 | 19,000,000 | UNPAID |
| `user04` | `524H0004` | 30,000,000 | 17,500,000 | UNPAID |
| `user05` | `723H0001` | 12,000,000 | 14,000,000 | UNPAID |
| `user06` | `723H0002` | 20,000,000 | 18,000,000 | PAID |
| `user07` | `723H0003` | 8,000,000 | 12,500,000 | UNPAID |
| `user08` | `723H0004` | 35,000,000 | 21,000,000 | UNPAID |

Choose option 1 to view current database values before testing. For an initial successful-payment example, `user04` has enough seed balance for the `524H0004` bill. For an insufficient-balance example, `user03` does not have enough seed balance for the `524H0003` bill. A previous payment may have changed either balance or bill status, so always check the live viewer first. A fresh seed does not replace data in an existing MySQL volume.

## 8. Manual Testing -- Mailpit

1. Run `setup.bat` or `./setup.sh` and leave the email mode set to Mailpit.
2. Choose option 1 and select an account with an unpaid bill and sufficient current balance.
3. Choose option 2 and log in with that username and `password123`.
4. Open Tuition, select the unpaid bill, and start the payment.
5. Choose option 3 or open <http://localhost:8025>.
6. Find the OTP email addressed to the selected user's registered email.
7. Enter the OTP and confirm the payment.
8. Check the account balance, tuition status, and payment history in the app or choose option 1 again.

For a successful payment, the tuition status becomes `PAID`, the account is debited by the bill amount, and the transaction is recorded as successful. The OTP is generated and verified by the normal application flow; Mailpit does not bypass OTP checks.

## 9. Testing OTP with Real Gmail

This is a **manual local demo procedure**. The normal setup remains on Mailpit, and setup never sends real email. Do not use a shared or production database.

1. Start the system and choose option 4, then option 2.
2. Google requires 2-Step Verification to create an App Password. Open Google's [App Passwords page](https://myaccount.google.com/apppasswords), sign in, and create an App Password for this demo.
3. Enter the Gmail sender address and App Password in the menu. The password input is hidden. The menu applies Gmail SMTP on port 587 with STARTTLS to Payment Service.
4. Seeded emails such as `user04@example.com` are placeholders and cannot receive real mail. Changing SMTP mode does not change a user's registered email.
5. The profile page only displays user details; it does not update email addresses. To receive a real OTP, manually change the email for **one selected demo user** in the local `ibanking_account_db` database as described below.
6. Log in as that user, start a payment for an unpaid tuition bill, receive the OTP in the controlled inbox, enter it, and confirm the payment.
7. Restore the original email using the guarded restore procedure below. Then choose option 4 and option 1 to return Payment Service to Mailpit.

### LOCAL DEMO USE ONLY: Change one user's email

Do not run this against production or shared data. The setup menu never changes user records. The procedure below changes only `users.email`; it does not update balances, passwords, tuition bills, or payment history.

Open a MySQL client in the existing container. The `-p` option prompts for the local database password; do not put the password in the command:

```bash
docker compose --env-file .env.docker -p ibanking-demo exec mysql mysql -uroot -p ibanking_account_db
```

First inspect the selected user's current email and record it exactly for restoration:

```sql
SELECT username, email FROM users WHERE username = 'user04';
```

Before running the update, explicitly confirm that `user04` is the account you chose, the selected row shows the original email you recorded, and the replacement address belongs to you. Replace both placeholders below with the values you inspected and confirmed. Keep the confirmation variable set to `NO` until you are ready to make this one local demo change, then type `YES`. The `WHERE` clause protects against changing the row if its email has changed since inspection.

```sql
START TRANSACTION;
SET @confirm_email_change = 'NO'; -- change to YES only after explicit confirmation
UPDATE users
SET email = 'YOUR_CONTROLLED_EMAIL'
WHERE username = 'user04' AND email = 'ORIGINAL_EMAIL_FROM_SELECT'
  AND @confirm_email_change = 'YES';
SELECT ROW_COUNT() AS updated_rows;
SELECT username, email FROM users WHERE username = 'user04';
```

Commit only if `updated_rows` is exactly `1` and the SELECT shows the intended address. Otherwise run `ROLLBACK;` and inspect the row again.

After testing, explicitly restore the original address you recorded. Replace the placeholders with the exact original and test addresses. As above, execute the guarded update only after confirming the selected account and values:

```sql
START TRANSACTION;
SET @confirm_email_restore = 'NO'; -- change to YES only after explicit confirmation
UPDATE users
SET email = 'ORIGINAL_EMAIL_FROM_SELECT'
WHERE username = 'user04' AND email = 'YOUR_CONTROLLED_EMAIL'
  AND @confirm_email_restore = 'YES';
SELECT ROW_COUNT() AS restored_rows;
SELECT username, email FROM users WHERE username = 'user04';
```

Commit only when `restored_rows` is exactly `1` and the SELECT confirms the original email. Otherwise run `ROLLBACK;`. Exit the client with `exit;`. Do not run either update unless you have confirmed the intended user and email values.

## 10. Additional Testing Scenarios

- **Successful payment:** manual with an unpaid bill and sufficient current balance; confirm the OTP in Mailpit or, after the manual setup above, the user's real inbox.
- **Insufficient balance:** manual with an unpaid bill whose amount exceeds the selected account's current balance. The payment is rejected and no successful debit is expected.
- **Invalid, expired, or already-used OTP:** invalid and expired/used OTP behavior is covered by automated Payment Service tests. An OTP expires after five minutes; an expired OTP can also be checked manually by waiting before confirmation.
- **Duplicate payment:** manual retry after a bill is paid should be rejected. Automated tests cover repeated requests and confirmation behavior.
- **Two accounts paying separate bills:** can be exercised manually if both accounts currently have unpaid bills and enough balance.
- **Concurrent debits and payment confirmations:** use the automated concurrency tests with an isolated test database. Do not simulate concurrent requests against data you need to preserve.

Run the project test suite from an isolated Python environment with service dependencies installed:

```bash
python -m pytest tests -q
```

MySQL concurrency tests require an isolated `ibanking_account_db_test` database. HTTP E2E tests are opt-in and must use explicitly configured disposable databases, never the demo databases.

## 11. Stop, Restart and Reset

- Run `stop.bat` on Windows or `./stop.sh` on Linux/macOS to stop this Compose project. The database volume, records, and `.env.docker` remain.
- Run `setup.bat` or `./setup.sh` to start or restart services. Setup preserves the existing database volume.
- Choosing option 0 exits only the menu; containers continue running.

Resetting demo data is a separate destructive action. Back up any data you need, stop the project, and remove only its MySQL volume. For the default Compose project:

```bash
docker compose --env-file .env.docker -p ibanking-demo down
docker volume ls
docker volume rm ibanking-demo_mysql_data
```

Confirm the volume name belongs to `ibanking-demo` before removing it. Then run setup again. Removing this volume permanently deletes all three databases, including demo transactions and payment history. Never use global Docker prune commands or `docker compose down -v` for this procedure.

## 12. Project Structure

```text
backend/                 FastAPI service code
db/docker-init/          Fresh-install schemas and demo seeds
db/{user,tuition,payment}/ SQL schemas, seeds, and forward migrations
diagram/                 Existing SOA submission diagrams
docs/                    Existing-database migration guide
frontend/                Static web app
nginx/                   Nginx routing configuration
tests/                   Unit, database, concurrency, and opt-in HTTP tests
docker-compose.yml
setup.bat, setup.sh      Setup, health checks, and interactive menu
setup-menu.ps1           Windows menu and SMTP configuration
stop.bat, stop.sh        Stop services without removing data
```

## 13. Troubleshooting

- **Docker Desktop is not running:** Start Docker Desktop and retry setup.
- **A container is unhealthy:** Run `docker compose --env-file .env.docker -p ibanking-demo logs --tail=80`.
- **Frontend is unavailable:** Check Nginx with `docker compose --env-file .env.docker -p ibanking-demo ps` and confirm `FRONTEND_PORT` is free.
- **MySQL connection or viewer error:** Check MySQL health and logs with the commands above. The viewer needs initialized `users`, `accounts`, and `tuition_bills` tables.
- **Demo data is missing:** Existing MySQL volumes are not reseeded. Inspect the current database before considering a reset.
- **Mailpit OTP is missing:** Confirm the mode is Mailpit (option 4, then 1), the payment service is healthy, and the selected user's email is present. Open Mailpit at <http://localhost:8025>.
- **Google App Password is unavailable:** Confirm 2-Step Verification is enabled. Some account policies may not offer App Passwords; use Mailpit for the local demo if so.
- **Gmail SMTP authentication fails:** Check the sender address, App Password, port `587`, and STARTTLS. Use an App Password, not the regular Google account password. Delivery is not tested by setup.
- **Gmail message goes nowhere:** Check the paying user's registered email. Seeded `example.com` addresses are placeholders and are not changed by the SMTP menu.
- **Payment Service is not healthy after changing email mode:** The menu restores the previous `.env.docker` SMTP settings if applying the new settings fails. Inspect service logs; MySQL is not restarted by the menu.
