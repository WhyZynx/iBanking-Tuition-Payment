# iBanking Tuition Payment System

A university Service-Oriented Architecture (SOA) demo for paying tuition from a simulated bank account.

The system uses **3 FastAPI microservices**, **3 separate MySQL databases**, and **email OTP verification**.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Prerequisites](#4-prerequisites)
5. [Quick Start](#5-quick-start)
6. [Setup Menu](#6-setup-menu)
7. [Demo Accounts](#7-demo-accounts)
8. [Manual Payment Test](#8-manual-payment-test)
9. [Test with Real Gmail](#9-test-with-real-gmail)
10. [Automated Tests](#10-automated-tests)
11. [Stop, Restart and Reset](#11-stop-restart-and-reset)
12. [Project Structure](#12-project-structure)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Project Overview

Users can:

- Log in to the system.
- View their profile and simulated bank accounts.
- Check unpaid tuition bills.
- Pay tuition using their bank account.
- Confirm payments using an email OTP.
- View account balances and payment history.

## 2. System Architecture

### Architecture Overview

```text
                         Browser
                            |
                          Nginx
                            |
          +-----------------+-----------------+
          |                 |                 |
     User Service      Tuition Service   Payment Service
          |                 |                 |
   Account Database   Tuition Database   Payment Database
          |                 |                 |
          +-----------------+-----------------+
                            |
                       Email Service
                      Mailpit / Gmail
```

### Main Services

| Service | Responsibility |
|---|---|
| User & Account Service | Login, user profiles, bank accounts, and account balance operations. |
| Tuition Service | Student information and tuition bills. |
| Payment Service | Payment transactions, OTP generation, OTP verification, and payment coordination. |
| Nginx | Frontend hosting and API routing. |
| MySQL | Stores data in 3 separate databases. |
| Mailpit | Captures demo emails locally. |

**Note:** The repository also contains older SOA diagrams in `diagram/`. Some diagrams show an external tuition system that is not part of the current Docker Compose runtime.

## 3. Technology Stack

| Component | Technology |
|---|---|
| Backend | Python 3.12, FastAPI |
| ORM / Database Driver | SQLAlchemy, PyMySQL |
| Database | MySQL 8.4 |
| Containerization | Docker Compose |
| Web Server | Nginx |
| Frontend | HTML, CSS, JavaScript |
| Testing | Pytest |
| Email Testing | Mailpit |
| Real Email | Gmail SMTP (optional) |

## 4. Prerequisites

Install and start:

- Git
- Docker Desktop
- Docker Compose V2

**Windows users:** Run `setup.bat` in PowerShell or Command Prompt.

No local MySQL installation or Python installation is required for the default Docker demo.

---

## 5. Quick Start

### Step 1. Clone the repository

```bash
git clone https://github.com/WhyZynx/iBanking-Tuition-Payment.git
cd iBanking-Tuition-Payment
```

### Step 2. Start Docker Desktop

Make sure Docker Desktop is running.

### Step 3. Start the system

**Windows:**

```bat
setup.bat
```

**Linux / macOS / Git Bash:**

```bash
./setup.sh
```

The setup process will:

1. Create `.env.docker` if it does not exist.
2. Start Docker containers.
3. Wait for service health checks.
4. Initialize the databases on a fresh installation.
5. Check the frontend and Mailpit.
6. Verify demo login.
7. Open the interactive setup menu.

**Important:**

- Existing `.env.docker` settings are preserved.
- Existing MySQL data is not reset.
- Running setup again does not delete existing database records.

### Step 4. Open the application

| Application | URL |
|---|---|
| iBanking Frontend | http://localhost:8080 |
| Mailpit Inbox | http://localhost:8025 |

---

## 6. Setup Menu

After setup finishes, the interactive menu provides:

| Option | Function |
|---|---|
| `1` | View current demo data |
| `2` | Open the frontend |
| `3` | Open the Mailpit inbox |
| `4` | Configure email delivery |
| `0` | Exit the menu |

Choosing `0` only exits the menu. Docker containers continue running.

### Email Configuration

Choose option `4` to open the email configuration menu.

| Option | Email Mode | Configuration |
|---|---|---|
| `1` | Mailpit | `mailpit:1025` |
| `2` | Gmail SMTP | `smtp.gmail.com:587` |
| `0` | Back | Return to the main menu |

**Mailpit** is the default mode and is recommended for local testing.

Changing the email mode updates the SMTP settings in `.env.docker` and recreates Payment Service. Other services and database records are not reset.

For Gmail, the App Password is entered without displaying it and stored locally in the Git-ignored `.env.docker`.

---

## 7. Demo Accounts

All demo accounts use the password:

```text
password123
```

### Initial Demo Data

The following values are the **initial seed data**, not guaranteed current values.

| Username | Student ID | Initial Balance (VND) | Tuition (VND) | Initial Status |
|---|---|---:|---:|---|
| `user01` | `524H0001` | 25,000,000 | 18,500,000 | UNPAID |
| `user02` | `524H0002` | 15,000,000 | 16,500,000 | UNPAID |
| `user03` | `524H0003` | 4,000,000 | 19,000,000 | UNPAID |
| `user04` | `524H0004` | 30,000,000 | 17,500,000 | UNPAID |
| `user05` | `723H0001` | 12,000,000 | 14,000,000 | UNPAID |
| `user06` | `723H0002` | 20,000,000 | 18,000,000 | PAID |
| `user07` | `723H0003` | 8,000,000 | 12,500,000 | UNPAID |
| `user08` | `723H0004` | 35,000,000 | 21,000,000 | UNPAID |

### Before Testing

Choose option `1` in the setup menu to view the current database values.

Examples:

- Successful payment: `user04` has enough initial balance for `524H0004`.
- Insufficient balance: `user03` does not have enough initial balance for `524H0003`.

Previous tests may change account balances and tuition statuses. Always check the current data before testing.

---

## 8. Manual Payment Test

Use Mailpit to test the complete payment process without sending real emails.

### Steps

1. Start the system using `setup.bat` or `./setup.sh`.
2. Make sure the email mode is **Mailpit**.
3. Choose menu option `1` to check current demo data.
4. Choose a user with an unpaid bill and sufficient balance.
5. Choose menu option `2` or open http://localhost:8080.
6. Log in using the selected username and `password123`.
7. Open the Tuition section and start a payment.
8. Open Mailpit at http://localhost:8025.
9. Find the OTP email sent to the selected user's registered email.
10. Enter the OTP and confirm the payment.
11. Check the account balance, tuition status, and payment history.

### Expected Result

After a successful payment:

- Tuition status becomes `PAID`.
- The bank account is debited by the tuition amount.
- The payment transaction is recorded as `SUCCESS`.
- The OTP is verified through the normal application flow.

---

## 9. Test with Real Gmail

This is an optional local demonstration. The default setup uses Mailpit and does not send real emails.

### Step 1. Create a Gmail App Password

1. Enable Google 2-Step Verification.
2. Open [Google App Passwords](https://myaccount.google.com/apppasswords).
3. Create an App Password for this demo.

### Step 2. Configure Gmail SMTP

1. Start the system.
2. Choose menu option `4`.
3. Select option `2` for Gmail SMTP.
4. Enter the Gmail sender address and App Password.

The system uses:

```text
SMTP Host: smtp.gmail.com
SMTP Port: 587
Security: STARTTLS
```

### Step 3. Update a Demo User's Email

Seeded addresses such as `user04@example.com` are placeholders and cannot receive real emails.

The setup menu does not change user email addresses. To receive a real OTP, you must temporarily update one selected demo user's email in the local database.

**Local demo use only. Do not use production or shared databases.**

Open the MySQL client:

```bash
docker compose --env-file .env.docker -p ibanking-demo exec mysql mysql -uroot -p ibanking_account_db
```

Inspect the selected user's current email:

```sql
SELECT username, email
FROM users
WHERE username = 'user04';
```

Record the original email before making any change.

To update the email, replace the placeholders with the values you inspected and confirmed:

```sql
START TRANSACTION;

SET @confirm_email_change = 'NO';

UPDATE users
SET email = 'YOUR_CONTROLLED_EMAIL'
WHERE username = 'user04'
  AND email = 'ORIGINAL_EMAIL_FROM_SELECT'
  AND @confirm_email_change = 'YES';

SELECT ROW_COUNT() AS updated_rows;

SELECT username, email
FROM users
WHERE username = 'user04';
```

Change `NO` to `YES` only after confirming the selected user and email values.

Commit only if `updated_rows` is exactly `1` and the result shows the intended email:

```sql
COMMIT;
```

Otherwise:

```sql
ROLLBACK;
```

### Step 4. Test the Real OTP

1. Log in as the selected demo user.
2. Start a payment for an unpaid tuition bill.
3. Check the controlled Gmail inbox.
4. Enter the OTP and confirm the payment.

### Step 5. Restore the Original Email

After testing, restore the original email address you recorded.

```sql
START TRANSACTION;

SET @confirm_email_restore = 'NO';

UPDATE users
SET email = 'ORIGINAL_EMAIL_FROM_SELECT'
WHERE username = 'user04'
  AND email = 'YOUR_CONTROLLED_EMAIL'
  AND @confirm_email_restore = 'YES';

SELECT ROW_COUNT() AS restored_rows;

SELECT username, email
FROM users
WHERE username = 'user04';
```

Change `NO` to `YES` only after confirming the values.

Commit only if `restored_rows` is exactly `1` and the original email is restored:

```sql
COMMIT;
```

Otherwise, run:

```sql
ROLLBACK;
```

Exit MySQL:

```sql
exit;
```

Finally, return to Mailpit mode using menu option `4`, then option `1`.

---

## 10. Automated Tests

Run tests from the project root with the Python test environment activated.

### Run the full test suite

```bash
python -m pytest tests -q
```

### Important Test Scenarios

| Scenario | Purpose |
|---|---|
| Successful payment | Verify a valid payment and account debit. |
| Insufficient balance | Ensure an account cannot pay more than its available balance. |
| Invalid OTP | Reject an incorrect OTP. |
| Expired OTP | Reject an OTP after its expiration time. |
| Reused OTP | Prevent an OTP from being used more than once. |
| Duplicate payment | Prevent duplicate payment requests. |
| Concurrent payments | Verify safe handling of simultaneous payment requests. |

Some MySQL integration tests require an isolated test database. The demo concurrency test below is different: it uses the actual local demo stack and changes demo data.

### Two Demo Users Paying the Same Tuition Concurrently

This one-time demonstration uses:

| Setting | Default Value |
|---|---|
| First user | `user01` |
| Second user | `user04` |
| Student ID | `524H0004` |
| Initial tuition status required | `UNPAID` |

The test:

1. Logs in both users.
2. Checks that both users have different accounts.
3. Checks that both accounts have enough balance.
4. Creates two payment transactions for the same tuition bill.
5. Requests an OTP for each transaction.
6. Confirms both payments concurrently.
7. Verifies that only one payment succeeds.

**Expected result:**

- One payment returns HTTP `200`.
- The other payment returns HTTP `409`.
- One transaction becomes `SUCCESS`.
- The other transaction becomes `FAILED`.
- Only one account is debited.
- The tuition bill becomes `PAID`.

**Warning:** This test uses the local demo MySQL database and leaves the winning tuition bill in `PAID` status. Use only with disposable local demo data.

Run in PowerShell:

```powershell
$env:IBANKING_DEMO_CONCURRENCY_APPROVAL = "YES"

python -m pytest -v -s tests/payment_service/test_demo_two_payer_concurrency.py::test_two_demo_accounts_concurrently_pay_the_same_tuition

Remove-Item Env:IBANKING_DEMO_CONCURRENCY_APPROVAL
```

The approval variable is required because this test performs a real payment in the local demo environment.

To change the demo users or student ID, configure:

```text
IBANKING_DEMO_FIRST_USERNAME
IBANKING_DEMO_SECOND_USERNAME
IBANKING_DEMO_STUDENT_ID
```

The test requires the selected tuition bill to be `UNPAID` and both accounts to have sufficient balances.

---

## 11. Stop, Restart and Reset

### Stop the System

**Windows:**

```bat
stop.bat
```

**Linux / macOS / Git Bash:**

```bash
./stop.sh
```

Stopping the system does not delete database records or `.env.docker`.

### Start or Restart the System

**Windows:**

```bat
setup.bat
```

**Linux / macOS / Git Bash:**

```bash
./setup.sh
```

The setup process preserves existing MySQL data.

### Reset All Demo Databases

Resetting the databases is a destructive operation.

It removes all three databases, including:

- User and account data.
- Tuition bills.
- Payment transactions.
- OTP records and payment history.

**Only reset when you are sure that you do not need the current data.**

From the project root, run:

**Step 1. Stop the Compose project**

```powershell
docker compose --env-file .env.docker -p ibanking-demo down
```

**Step 2. Check the Docker volumes**

```powershell
docker volume ls
```

**Step 3. Remove the MySQL data volume**

```powershell
docker volume rm ibanking-demo_mysql_data
```

Make sure the volume name is correct before removing it.

**Step 4. Start the system again**

```powershell
.\setup.bat
```

The fresh MySQL volume will be initialized using the database initialization files configured in Docker Compose.

**Important:**

- Do not use `docker compose down -v`.
- Do not use global Docker prune commands.
- Do not remove unrelated Docker volumes.
- The database setup and seed scripts are still needed for fresh installation and database initialization.

---

## 12. Project Structure

```text
iBanking-Tuition-Payment/
│
├── backend/
│   ├── user_service/
│   ├── tuition_service/
│   └── payment_service/
│
├── db/
│   ├── docker-init/
│   ├── user/
│   ├── tuition/
│   └── payment/
│
├── diagram/
├── docs/
├── frontend/
├── nginx/
├── tests/
│
├── docker-compose.yml
├── setup.bat
├── setup.sh
├── setup-menu.ps1
├── setup-db.ps1
├── stop.bat
├── stop.sh
└── README.md
```

### Important Setup Files

| File | Purpose |
|---|---|
| `setup.bat` / `setup.sh` | Start the system and perform setup checks. |
| `setup-menu.ps1` | Display the interactive setup menu and configure email. |
| `setup-db.ps1` | Set up or validate database structures and migrations. |
| `docker-compose.yml` | Define containers, services, networks, and volumes. |
| `stop.bat` / `stop.sh` | Stop the Compose project without deleting database data. |

---

## 13. Troubleshooting

| Problem | What to do |
|---|---|
| Docker Desktop is not running | Start Docker Desktop and run setup again. |
| A container is unhealthy | Check Docker Compose status and logs. |
| Frontend cannot open | Check Nginx and port `8080`. |
| Mailpit cannot open | Check the Mailpit container and port `8025`. |
| MySQL connection fails | Check MySQL health and logs. |
| Demo data is missing | Check the current database. Existing volumes are not automatically reseeded. |
| OTP email is missing | Confirm Mailpit mode and check the selected user's email. |
| Gmail authentication fails | Check the sender address, App Password, port `587`, and STARTTLS. |
| Gmail OTP is not received | Check the paying user's registered email. Seeded `example.com` addresses are placeholders. |
| Payment Service is unhealthy | Check Payment Service logs and SMTP configuration. |

### Useful Docker Commands

Check service status:

```bash
docker compose --env-file .env.docker -p ibanking-demo ps
```

View all service logs:

```bash
docker compose --env-file .env.docker -p ibanking-demo logs --tail=80
```

View logs for one service:

```bash
docker compose --env-file .env.docker -p ibanking-demo logs payment-service --tail=80
```

---

**End of README**