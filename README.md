# iBanking Tuition Payment System

## Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Run with Docker](#run-with-docker)
- [Demo Data](#demo-data)
- [Demo Workflow](#demo-workflow)
- [Testing](#testing)
- [Stop and Restart](#stop-and-restart)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)

## Project Overview

iBanking Tuition Payment System is a demo online banking application for paying university tuition. A user can sign in, check an account, find a tuition bill, confirm a payment by email OTP, and view payment history.

## Features

- User login with JWT authentication.
- Account information and balance lookup.
- Tuition lookup by student ID.
- OTP verification by email.
- Tuition payment from an account.
- Transaction history.
- Protection against duplicate payments and duplicate account debits.

## System Architecture

```text
Browser
  |
  v
Nginx (frontend and API routing)
  |---------------- User Service ---- account_db
  |---------------- Tuition Service -- ibanking_tuition
  |---------------- Payment Service -- payment_db
                         |
                         +---- Gmail SMTP
```

- **Frontend and Nginx:** Nginx serves the static frontend and routes browser API requests to the correct backend service.
- **User Service:** Handles login, JWTs, user information, accounts, and safe account debits.
- **Tuition Service:** Looks up tuition bills and protects them from simultaneous payment claims.
- **Payment Service:** Creates transactions, sends OTP email, confirms payments, and provides history.
- **MySQL:** Stores separate data for User, Tuition, and Payment services.

## Technology Stack

Versions below come from the Docker image tags and service requirements in this repository. Some image tags and Python package ranges are not pinned to a patch version.

- Python 3.12 container base image.
- FastAPI `>=0.115,<1.0` for User and Tuition; Payment pins FastAPI `0.141.1`.
- MySQL `8.4`.
- Nginx `alpine` image tag.
- HTML, CSS, and browser JavaScript.
- Pytest `>=8,<9` for automated tests.

## Project Structure

```text
backend/
  user_service/
  tuition_service/
  payment_service/
db/
  docker-init/       # Fresh Docker database schemas
  user/              # User schema, migrations, and demo seed
  tuition/           # Tuition schema and demo seed
  payment/           # Payment schema and migrations
  demo_reset_*.sql   # Guarded local demo reset scripts
docs/                # Demo data, E2E testing, and database review notes
frontend/            # HTML, CSS, and JavaScript
nginx/               # Nginx routing configuration
tests/               # Unit, service, database, and opt-in E2E tests
docker-compose.yml
pytest.ini
```

## Prerequisites

- Docker Desktop running with Linux containers enabled.
- Git.
- A Gmail account with 2-Step Verification and an App Password if you want OTP email sent through Gmail.
- Git Bash on Windows for the commands below.

## Environment Setup

Copy the example file and edit the local copy:

```bash
cp .env.docker.example .env.docker
```

Set these values in `.env.docker`:

| Variable | Purpose |
| --- | --- |
| `MYSQL_ROOT_PASSWORD` | Password for the local MySQL root account. Use letters and numbers so it is safe in the service connection URLs. |
| `MYSQL_PORT` | Host port mapped to MySQL. The default is `3307`; change it if another program already uses that port. |
| `JWT_SECRET_KEY` | Secret used to sign and verify access tokens. Use a new random value. |
| `INTERNAL_API_KEY` | Shared key for private calls between backend services. Use a new random value. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime in minutes. The default is `30`. |
| `SMTP_HOST` | Gmail SMTP server, normally `smtp.gmail.com`. |
| `SMTP_PORT` | Gmail SMTP port, normally `587` with STARTTLS. |
| `SMTP_USERNAME` | Gmail address used to send messages. |
| `SMTP_PASSWORD` | Gmail App Password. Do not use your regular Gmail password. |
| `SMTP_FROM_EMAIL` | Sender address shown on OTP messages, usually the configured Gmail address. |

Generate random local secrets in Git Bash with `openssl rand -hex 32`, then paste the output into the matching fields. Do not share or commit those values.

To use Gmail, enable 2-Step Verification in the Google Account and create an App Password if the account offers that option. See [Google's App Password guide](https://support.google.com/accounts/answer/185833). Some work or school accounts, security-key-only setups, or Advanced Protection accounts may not offer App Passwords. Put the App Password in `SMTP_PASSWORD`. The sender settings above control who sends the OTP. The recipient is the email address stored for the paying user in `account_db`; these are separate settings.

## Run with Docker

Run these commands from the repository root:

```bash
docker compose --env-file .env.docker -p ibanking-demo config --quiet
docker compose --env-file .env.docker -p ibanking-demo up --build -d
docker compose --env-file .env.docker -p ibanking-demo ps
```

Open the frontend at <http://localhost:8080>. Nginx routes `/api/v1/tuition` to Tuition, `/api/v1/payments` and `/api/v1/transactions` to Payment, and other `/api/v1/` requests to User.

The backend ports are private to the Docker network. There is no API docs URL exposed on the host. Each FastAPI service provides `/docs` inside Docker for internal debugging.

Check service logs with:

```bash
docker compose --env-file .env.docker -p ibanking-demo logs --tail=100
```

If MySQL port `3307` is already allocated, edit `MYSQL_PORT` in `.env.docker` to a free host port, such as `3308`. The services still connect to MySQL at `mysql:3306` inside Docker.

The Compose file has fixed container names (`ibanking-mysql`, `ibanking-user-service`, `ibanking-tuition-service`, and `ibanking-payment-service`). Only one project using these names can run at a time. If there is a name conflict, inspect `docker ps -a` and stop the other iBanking Compose project before starting this one. Do not remove its volume.

## Demo Data

Docker init scripts create the three schemas and tables on the first initialization of the MySQL volume. They do not add demo users or tuition bills. Seed data is optional. Run these commands once after MySQL is healthy:

```bash
docker compose --env-file .env.docker -p ibanking-demo exec -T mysql \
  sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' < db/user/demo_seed.sql
docker compose --env-file .env.docker -p ibanking-demo exec -T mysql \
  sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' < db/tuition/demo_seed.sql
```

The user names, password hash, demo email addresses, accounts, and initial balances are defined in `db/user/demo_seed.sql`. Tuition bills are in `db/tuition/demo_seed.sql`. The source seed and `docs/DEMO_DATA.md` identify the demo logins as `user01` through `user08`, all with password `password123`. Payment data does not need a seed.

The seeded recipient addresses use `example.com`, so they cannot receive Gmail messages. To receive OTP at an address you control, update only the matching user in this **demo database**. First inspect the row:

```bash
docker compose --env-file .env.docker -p ibanking-demo exec mysql mysql -uroot -p
```

Enter the MySQL root password when prompted, then run:

```sql
USE account_db;
SELECT username, student_id, email FROM users WHERE username = 'user01';
UPDATE users
SET email = 'your-address@example.net'
WHERE username = 'user01' AND student_id = '524H0001';
SELECT username, student_id, email FROM users WHERE username = 'user01';
```

Use your own inbox address. Confirm the selected row before updating it. Do not change an account in a shared or production database for this demo.

## Demo Workflow

1. Open the frontend and log in as a seeded demo user.
2. Open **Accounts** to view the account and balance.
3. Open **Tuition** and search by student ID.
4. Request an OTP and check the paying user's email inbox.
5. Enter the OTP and confirm the payment.
6. Open **History** to see the completed transaction.

## Testing

From the repository root, run the automated tests with:

```bash
python -m pytest tests -q
```

Latest recorded result: **107 passed, 14 skipped**. The skipped tests are conditional: two require a separate MySQL database named `account_db_test`; real HTTP E2E tests require explicitly configured disposable databases and approval; OTP scenarios also need a local test email reader. One fault-injection E2E scenario remains skipped because the repository has no controlled fault-injection proxy. See `docs/E2E_TESTING.md` before setting up those tests.

`pytest.ini` adds the repository root to Python's import path. Keep it when running the tests from the repository root.

## Stop and Restart

Stop the services without removing containers or database data:

```bash
docker compose --env-file .env.docker -p ibanking-demo stop
```

Start the same project again:

```bash
docker compose --env-file .env.docker -p ibanking-demo up -d
```

MySQL data is stored in the named volume `ibanking-demo_mysql_data`. `docker compose down` without `-v` also keeps the named volume. **Do not use `docker compose down -v` when you need to keep the database.**

## Troubleshooting

- **Docker Engine unavailable:** Start Docker Desktop, wait until it reports that the engine is running, then check `docker info`.
- **MySQL port already allocated:** Change `MYSQL_PORT` in `.env.docker` to another free host port and run Compose again.
- **Container name conflict:** The Compose file uses fixed `ibanking-*` names. Stop the other iBanking project that owns the names; do not delete its volume.
- **Gmail SMTP error:** Check the sender address, port `587`, Gmail App Password, and 2-Step Verification. Check that `SMTP_FROM_EMAIL` matches the sending account.
- **OTP does not arrive:** Check the email stored for the paying user in `account_db`; it is the recipient and can differ from the SMTP sender.
- **Database volume already initialized:** MySQL init SQL runs only when its data directory is empty. Editing an init script does not update an existing database. Keep the volume; review the applicable forward-only migration and back up the intended database before applying it.

## Security Notes

- Never commit `.env.docker`, any `.env` file, Gmail App Passwords, `JWT_SECRET_KEY`, or `INTERNAL_API_KEY`.
- Keep real credentials out of README files, logs, screenshots, and chat.
- Use fictional demo data and a local demo database. Do not run demo seeds or reset scripts against a shared or production database.
