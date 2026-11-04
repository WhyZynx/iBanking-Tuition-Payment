# iBanking Tuition Payment System

A university Service-Oriented Architecture (SOA) demo for paying tuition from simulated bank accounts.

The system consists of **3 FastAPI microservices**, **3 separate MySQL databases**, and **email OTP verification**.

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
9. [Gmail Configuration](#9-gmail-configuration)
10. [Automated Tests](#10-automated-tests)
11. [Stop, Restart and Reset](#11-stop-restart-and-reset)
12. [Project Structure](#12-project-structure)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Project Overview

The system allows users to:

- Log in to their accounts.
- View their profiles and bank account balances.
- Check unpaid tuition bills.
- Pay tuition using a simulated bank account.
- Confirm payments using an email OTP.
- View payment history and updated account balances.

## 2. System Architecture

### Architecture Overview

```text
                         Browser
                            |
                          Nginx
                            |
          +-----------------+-----------------+
          |                 |                 |
     User Service     Tuition Service   Payment Service
          |                 |                 |
   Account Database   Tuition Database   Payment Database
                            |
                       Email Delivery
                       Mailpit / Gmail
```

### Main Services

| Component | Responsibility |
|---|---|
| User Service | Login, user profiles, bank accounts, and account balance operations. |
| Tuition Service | Student information and tuition bills. |
| Payment Service | Payment transactions, OTP generation, OTP verification, and payment coordination. |
| Nginx | Frontend hosting and API routing. |
| MySQL | Stores data in 3 separate databases. |
| Mailpit | Captures demo emails locally. |

### Databases

| Database | Purpose |
|---|---|
| `ibanking_account_db` | User information and bank accounts. |
| `ibanking_tuition_db` | Student information and tuition bills. |
| `ibanking_payment_db` | Payment transactions and OTP records. |

**Timezone:** The system uses Vietnam time (UTC+7).

**Note:** Some older diagrams in the `diagram/` folder may show an external tuition system. The current Docker Compose setup uses the three services listed above.

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

Install:

- Git
- Docker Desktop
- Docker Compose V2

Make sure Docker Desktop is running before starting the project.

**Windows:** Use PowerShell or Command Prompt.

No local MySQL or Python installation is required for the default Docker demo.

---

## 5. Quick Start

### Step 1. Clone the repository

```bash
git clone https://github.com/WhyZynx/iBanking-Tuition-Payment.git
cd iBanking-Tuition-Payment
```

### Step 2. Start Docker Desktop

Open Docker Desktop and wait until it is running.

### Step 3. Start the project

**Windows PowerShell:**

```bat
.\setup.bat
```

**Linux / macOS / Git Bash:**

```bash
./setup.sh
```

The setup script will:

1. Create `.env.docker` if it does not exist.
2. Start the Docker containers.
3. Wait for the services to become healthy.
4. Initialize databases on a fresh installation.
5. Check the frontend and Mailpit.
6. Verify demo login.
7. Open the setup menu.

**Important:**

- Existing `.env.docker` settings are preserved.
- Existing database records are not automatically deleted.
- Running setup again does not reset the database.

### Step 4. Open the application

| Application | URL |
|---|---|
| iBanking Frontend | [http://localhost:8080](http://localhost:8080) |
| Mailpit Inbox | [http://localhost:8025](http://localhost:8025) |

---

## 6. Setup Menu

After setup finishes, the interactive menu provides:

| Option | Function |
|---|---|
| `1` | View current demo data |
| `2` | Open the frontend |
| `3` | Open the Mailpit inbox |
| `4` | Configure email delivery |
| `5` | Run concurrency tests |
| `0` | Exit the setup menu |

Choosing `0` only exits the menu. Docker containers continue running.

### Email Configuration

Choose option `4` to configure email delivery.

| Option | Email Mode | Configuration |
|---|---|---|
| `1` | Mailpit | `mailpit:1025` |
| `2` | Gmail SMTP | `smtp.gmail.com:587` |
| `0` | Back | Return to the main menu |

**Mailpit** is the default mode and is recommended for local testing.

Changing the email mode updates `.env.docker` and recreates Payment Service. Database records are not reset.

For Gmail, the App Password is stored locally in the Git-ignored `.env.docker`.

### Concurrency Testing

Choose option `5` to open the concurrency testing menu.

| Option | Test |
|---|---|
| `1` | Same Account - Two Students |
| `2` | Two Payer - Same Student |
| `3` | Run Both Tests |
| `0` | Back to Main Menu |

The menu asks for confirmation before running tests because they can modify demo data.

---

## 7. Demo Accounts

All demo accounts use the password:

```text
password123
```

### Initial Demo Data

The following table shows the **initial seed data**. Current balances and tuition statuses may be different after testing.

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

Choose option `1` in the setup menu to view current balances and tuition statuses.

Examples:

- Successful payment: `user04` has enough initial balance for `524H0004`.
- Insufficient balance: `user03` does not have enough initial balance for `524H0003`.

Always check the current data before testing because previous tests may have changed it.

---

## 8. Manual Payment Test

Use Mailpit to test the payment process without sending real emails.

### Steps

1. Start the project using `setup.bat` or `./setup.sh`.
2. Make sure the email mode is **Mailpit**.
3. Choose menu option `1` to check current demo data.
4. Select a user with an unpaid tuition bill and sufficient balance.
5. Open [http://localhost:8080](http://localhost:8080).
6. Log in using the selected username and `password123`.
7. Open the Tuition section and start a payment.
8. Open Mailpit at [http://localhost:8025](http://localhost:8025).
9. Find the OTP email sent to the selected user's registered email.
10. Enter the OTP and confirm the payment.
11. Check the updated balance, tuition status, and payment history.

### Expected Result

After a successful payment:

- Tuition status becomes `PAID`.
- The bank account is debited by the tuition amount.
- The payment transaction is recorded as `SUCCESS`.
- The OTP is verified successfully.

---

## 9. Gmail Configuration

The default setup uses Mailpit. Gmail is optional for demonstrating real email delivery.

### Step 1. Create a Gmail App Password

1. Enable Google 2-Step Verification.
2. Open [Google App Passwords](https://myaccount.google.com/apppasswords).
3. Create an App Password for this project.

### Step 2. Configure Gmail

1. Start the project.
2. Choose menu option `4`.
3. Select option `2` for Gmail SMTP.
4. Enter the Gmail sender address and App Password.

SMTP settings:

```text
SMTP Host: smtp.gmail.com
SMTP Port: 587
Security: STARTTLS
```

### Step 3. Update a Demo User's Email

Seeded addresses such as `user04@example.com` are placeholders and cannot receive real emails.

To receive a real OTP, temporarily update the selected demo user's email in the local database.

**Use this procedure only with local demo data.**

Open the MySQL client:

```bash
docker compose --env-file .env.docker -p ibanking-demo exec mysql mysql -uroot -p ibanking_account_db
```

Check the user's current email:

```sql
SELECT username, email
FROM users
WHERE username = 'user04';
```

Record the original email before changing it.

To update the email, replace the placeholders with the actual values:

```sql
START TRANSACTION;

UPDATE users
SET email = 'YOUR_CONTROLLED_EMAIL'
WHERE username = 'user04'
  AND email = 'ORIGINAL_EMAIL_FROM_SELECT';

SELECT ROW_COUNT() AS updated_rows;

SELECT username, email
FROM users
WHERE username = 'user04';
```

Commit only if `updated_rows` is exactly `1` and the email is correct:

```sql
COMMIT;
```

Otherwise, run:

```sql
ROLLBACK;
```

### Step 4. Test Gmail OTP

1. Log in as the selected demo user.
2. Start a payment.
3. Check the controlled Gmail inbox.
4. Enter the OTP and confirm the payment.

### Step 5. Restore the Original Email

After testing, restore the original email address:

```sql
START TRANSACTION;

UPDATE users
SET email = 'ORIGINAL_EMAIL_FROM_SELECT'
WHERE username = 'user04'
  AND email = 'YOUR_CONTROLLED_EMAIL';

SELECT ROW_COUNT() AS restored_rows;

SELECT username, email
FROM users
WHERE username = 'user04';
```

Commit only if `restored_rows` is exactly `1` and the original email is restored:

```sql
COMMIT;
```

Otherwise:

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

### Run the Full Test Suite

```bash
python -m pytest tests -q
```

Some MySQL integration tests require an isolated test database.

The two concurrency tests below use the actual local demo stack and modify demo data.

### 10.1 Same Account - Two Students

Test file:

```text
tests/payment_service/test_payment_concurrency_same_account.py
```

This test checks whether one bank account can safely handle simultaneous payments for two different students.

**Test scenario:**

- Initial account balance: `25,000,000 VND`.
- Student `524H0001`: `18,500,000 VND`.
- Student `524H0002`: `16,500,000 VND`.
- Both payment confirmations are sent concurrently.

**Expected result:**

- One confirmation succeeds with HTTP `200`.
- The other is rejected with HTTP `409`.
- Only one account debit is recorded.
- The account balance does not become negative.
- Only one tuition bill becomes `PAID`.

**Latest test result: PASSED**

| Item | Result |
|---|---|
| Concurrent confirmation results | `[200, 409]` |
| Successful debits | `1` |
| Final account balance | `8,500,000 VND` |
| `524H0001` | UNPAID |
| `524H0002` | PAID |

### 10.2 Two Payer - Same Student

Test file:

```text
tests/payment_service/test_demo_two_payer_concurrency.py
```

Test function:

```text
test_two_demo_accounts_concurrently_pay_the_same_tuition
```

This test checks whether two different bank accounts can pay the same tuition bill at the same time.

**Default test scenario:**

| Setting | Value |
|---|---|
| First user | `user01` |
| Second user | `user04` |
| Student ID | `524H0004` |
| Required initial tuition status | `UNPAID` |

**Expected result:**

- One payment returns HTTP `200`.
- The other payment returns HTTP `409`.
- One transaction becomes `SUCCESS`.
- The other transaction becomes `FAILED`.
- Only one account is debited.
- The tuition bill becomes `PAID`.

**Latest test result: PASSED**

| Account | Initial Balance | Final Balance | Result |
|---|---:|---:|---|
| `6202000008` | 35,000,000 | 35,000,000 | FAILED |
| `6202000004` | 30,000,000 | 12,500,000 | SUCCESS |

The tuition bill for `524H0004` was paid only once.

### 10.3 Run Concurrency Tests from the Setup Menu

The recommended way to run these tests:

1. Open PowerShell in the project root.
2. Activate the test environment if it is not already active.
3. Run:

```powershell
.\setup-menu.ps1
```

4. Choose option `5`.
5. Select:
   - `1`: Same Account - Two Students.
   - `2`: Two Payer - Same Student.
   - `3`: Run Both Tests.
6. Confirm the warning when prompted.

### Important Warning

Concurrency tests use the local demo database. They can:

- Create payment transactions.
- Debit bank accounts.
- Change tuition statuses to `PAID`.
- Add records to payment and account debit history.

**Check the current demo data before running tests.** Do not run them repeatedly without resetting or preparing suitable test data.

---

## 11. Stop, Restart and Reset

### Stop the System

**Windows PowerShell:**

```bat
.\stop.bat
```

**Linux / macOS / Git Bash:**

```bash
./stop.sh
```
**Note**: When using PowerShell, add .\ before the script filename to run a file from the current directory.
Stopping the system does not delete database records or `.env.docker`.

### Start or Restart the System

**Windows PowerShell:**

```bat
setup.bat
```

**Linux / macOS / Git Bash:**

```bash
./setup.sh
```

Existing MySQL data is preserved.

### Reset All Demo Databases

Resetting the databases is destructive. It removes:

- User and account data.
- Tuition bills.
- Payment transactions.
- OTP records and payment history.

**Only reset when you are sure that you no longer need the current data.**

From the project root:

**Step 1. Stop the Compose project**

```powershell
docker compose --env-file .env.docker -p ibanking-demo down
```

**Step 2. Check Docker volumes**

```powershell
docker volume ls
```

**Step 3. Remove the MySQL data volume**

```powershell
docker volume rm ibanking-demo_mysql_data
```

Check the volume name carefully before removing it.

**Step 4. Start the project again**

```powershell
.\setup.bat
```

The fresh MySQL volume will be initialized using the database initialization files configured in Docker Compose.

**Important:**

- Do not use `docker compose down -v`.
- Do not use global Docker prune commands.
- Do not remove unrelated Docker volumes.

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
| `setup-menu.ps1` | Display the interactive menu and configure email and concurrency tests. |
| `setup-db.ps1` | Set up or validate database structures and migrations. |
| `docker-compose.yml` | Define containers, services, networks, and volumes. |
| `stop.bat` / `stop.sh` | Stop the Compose project without deleting database data. |

---

## 13. Troubleshooting

| Problem | Solution |
|---|---|
| Docker Desktop is not running | Start Docker Desktop and run setup again. |
| A container is unhealthy | Check Docker Compose status and logs. |
| Frontend cannot open | Check Nginx and port `8080`. |
| Mailpit cannot open | Check Mailpit and port `8025`. |
| MySQL connection fails | Check MySQL health and logs. |
| Demo data is missing | Check the database and existing Docker volumes. |
| OTP email is missing | Check the email mode and the user's registered email. |
| Gmail authentication fails | Check the Gmail address, App Password, port `587`, and STARTTLS. |
| Payment Service is unhealthy | Check Payment Service logs and SMTP configuration. |
| Concurrency test cannot run | Check whether the tuition bill is `UNPAID` and the accounts have sufficient balances. |

### Useful Docker Commands

Check service status:

```bash
docker compose --env-file .env.docker -p ibanking-demo ps
```

View all service logs:

```bash
docker compose --env-file .env.docker -p ibanking-demo logs --tail=80
```

View Payment Service logs:

```bash
docker compose --env-file .env.docker -p ibanking-demo logs payment-service --tail=80
```

---

**End of README**
