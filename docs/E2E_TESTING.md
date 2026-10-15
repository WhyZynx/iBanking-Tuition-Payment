# Real HTTP E2E preparation

This guide prepares the opt-in test suite in `tests/e2e/test_real_http_e2e.py`. It validates all three MySQL targets first, then starts its own local service subprocesses with those exact database URLs and sends real HTTP requests. It never creates databases, initializes schemas, seeds rows, or cleans up data.

## Safety boundary

The suite only accepts these three distinct databases:

| Service | Required database |
| --- | --- |
| User | `account_db_e2e_test` |
| Tuition | `ibanking_tuition_e2e_test` |
| Payment | `payment_db_e2e_test` |

It rejects `account_db`, `account_db_test`, `account_db_demo_test`, `ibanking_tuition`, `ibanking_tuition_demo_test`, and `payment_db`. The existing demo test databases are not targets for this suite. Each database URL must use `mysql+pymysql`, loopback networking, and configured credentials. The test checks `DATABASE()`, MySQL server hostname, port, and data directory against separately configured expected values before sending any API request.

Creating and initializing the three E2E databases is outside this phase. Do not start User Service until the dedicated database exists: its FastAPI lifespan calls `Base.metadata.create_all()` at startup. The suite first requires the expected table names, but the operator should also confirm complete columns and constraints. Grant service users no `CREATE`, `ALTER`, or `DROP` privileges so startup cannot create or change a schema. Use separate least-privilege users for each service, and run only after the database writes have been explicitly approved.

For a future approved setup, start from the fresh schema scripts `db/user/init.sql`, `db/tuition/tuition.sql`, and `db/payment/payment_init.sql`; make temporary copies that replace their hard-coded database names with the three E2E names above. The first two services also need temporary copies of their optional demo seeds with the matching database names substituted. Payment has no demo seed. These fresh schemas already contain the current account debit, tuition claim, payment student-name, and reconciliation status structures, so no legacy migration is needed for a fresh E2E database. Do not run the migration scripts against the test schemas unless an existing schema has been reviewed individually.

## Required environment

Set these variables in the shell that will run pytest and use matching values when starting each service. Do not put credentials in this document or in tracked files.

```text
IBANKING_E2E_USER_DATABASE_URL=mysql+pymysql://<test-user>:<test-password>@127.0.0.1:<port>/account_db_e2e_test
IBANKING_E2E_TUITION_DATABASE_URL=mysql+pymysql://<test-user>:<test-password>@127.0.0.1:<port>/ibanking_tuition_e2e_test
IBANKING_E2E_PAYMENT_DATABASE_URL=mysql+pymysql://<test-user>:<test-password>@127.0.0.1:<port>/payment_db_e2e_test
IBANKING_E2E_MYSQL_SERVER_HOSTNAME=<expected @@hostname>
IBANKING_E2E_MYSQL_SERVER_PORT=<expected @@port>
IBANKING_E2E_MYSQL_DATADIR=<expected @@datadir>
IBANKING_E2E_PRIMARY_USERNAME=<demo user>
IBANKING_E2E_PRIMARY_PASSWORD=<demo password>
IBANKING_E2E_SECOND_USERNAME=<different demo user>
IBANKING_E2E_SECOND_PASSWORD=<demo password>
IBANKING_E2E_JWT_SECRET=<test-only shared secret>
IBANKING_E2E_INTERNAL_API_KEY=<same test key used by all three services>
IBANKING_E2E_ISOLATION_CONFIRMED=YES
IBANKING_E2E_APPROVAL=I_APPROVE_WRITES_TO_THE_ISOLATED_E2E_DATABASES
```

The approval variable is an execution guard; setting it authorizes the suite to make payment, debit, OTP, and tuition-state changes in the three named E2E databases. It does not authorize use of the existing application or demo databases.

OTP-only optional values are `IBANKING_E2E_LOCAL_SMTP_READY=YES`, `IBANKING_E2E_SMTP_HOST`, `IBANKING_E2E_SMTP_PORT`, `IBANKING_E2E_SMTP_USERNAME`, `IBANKING_E2E_SMTP_PASSWORD`, `IBANKING_E2E_SMTP_FROM_EMAIL`, and `IBANKING_E2E_OTP_READER_URL`. Set them only for a local sink and reader. The test runner blanks SMTP settings in its Payment Service subprocess unless these explicit values are supplied, so it cannot fall back to a real account in the local `.env`.

Optional IDs/accounts default to the documented Phase 4.2 demo records. The primary login should map to account `6201000001`; the second login should own `6201000005`. Both users need sufficient initial balances for the shared-bill scenario. Use a fresh database set for a complete run because successful payment and concurrency scenarios intentionally mark bills PAID. The duplicate-debit scenario uses an idempotency key so rerunning it does not debit again.

## OTP and fault scenarios

Payment sends OTP by SMTP and has no API that returns the code. The repository has no safe OTP inbox/retrieval service. OTP scenarios are skipped unless a local test-only reader is configured with:

```text
IBANKING_E2E_OTP_READER_URL=http://127.0.0.1:<local-reader-port>/otp
```

The reader must return JSON `{"otp_code":"123456"}` for `GET` with query parameter `transaction_id`. It must read only from a local SMTP sink used by the disposable E2E environment. Do not point it at a real email account. The expired-OTP test moves that test transaction's expiration timestamp into the past in the verified Payment E2E database, then checks rejection through HTTP.

E2E-10 is explicitly skipped. There is no controlled fault-injection proxy or service recovery harness in the repository to safely force the partial-side-effect states needed to verify `RECONCILIATION_REQUIRED`.

## HTTP contracts exercised

| Service | Route | Request/response contract |
| --- | --- | --- |
| User | `POST /api/v1/auth/login` | JSON `{username,password}` → `{access_token,token_type}` |
| User | `GET /api/v1/users/me` | Bearer JWT → user fields including `user_id` and nullable `student_id` |
| User | `GET /api/v1/accounts/me` | Bearer JWT → account fields serialized as `accountNumber`, `balance`, `isDefault`, `status` |
| User internal | `GET /api/v1/internal/accounts/{account_number}` | `X-Internal-API-Key` → account plus `userId` |
| User internal | `POST /api/v1/internal/accounts/{account_number}/debit` | Internal key and `{amount,transactionId}` → `{success,accountNumber,remainingBalance}` |
| Tuition | `GET /api/v1/tuition/{student_id}` | Public lookup → `{student_id,student_name,amount,status}` |
| Tuition internal | `POST /api/v1/tuition/{student_id}/claim` | Internal key and `{transaction_id}` → claim (201) |
| Tuition internal | `DELETE /api/v1/tuition/{student_id}/claim/{transaction_id}` | Internal key → release result |
| Tuition internal | `PUT /api/v1/tuition/{student_id}/pay` | Internal key → updated tuition bill |
| Payment | `POST /api/v1/payments` | Bearer JWT and `{student_id,account_number}` → pending transaction (201) |
| Payment | `POST /api/v1/payments/{transaction_id}/otp` | Bearer JWT → delivery message and 300-second lifetime; OTP is not returned |
| Payment | `POST /api/v1/payments/confirm` | Bearer JWT and `{transactionId,otpCode}` → transaction result |
| Payment | `GET /api/v1/payments/{transaction_id}` | Bearer JWT → owned transaction status |
| Payment | `GET /api/v1/transactions/me` | Bearer JWT → `{items:[...]}` history |
| Payment | `POST /api/v1/payments/cancel-pending` | Bearer JWT → cancelled count |

The README API overview omits the Payment status and cancel-pending routes even though the controller exposes them and the frontend polls/cancels through them. This is a documentation gap; the paths and request contracts align with the current frontend.

## Start the services on Windows

For manual API inspection, start each service in a separate PowerShell terminal from the repository root. Populate the `IBANKING_E2E_*` variables first, then copy them into the names each service reads. These are process environment overrides; do not edit real `.env` files. Stop manually started services before pytest: the E2E fixture checks ports 8001–8003 are free and starts isolated subprocesses itself after MySQL identity checks.

User Service terminal:

```powershell
$env:DATABASE_URL = $env:IBANKING_E2E_USER_DATABASE_URL
$env:JWT_SECRET_KEY = $env:IBANKING_E2E_JWT_SECRET
$env:JWT_ALGORITHM = 'HS256'
$env:INTERNAL_API_KEY = $env:IBANKING_E2E_INTERNAL_API_KEY
python -m uvicorn backend.user_service.main:app --host 127.0.0.1 --port 8001
```

Tuition Service terminal:

```powershell
$env:DATABASE_URL = $env:IBANKING_E2E_TUITION_DATABASE_URL
$env:INTERNAL_API_KEY = $env:IBANKING_E2E_INTERNAL_API_KEY
python -m uvicorn backend.tuition_service.main:app --host 127.0.0.1 --port 8002
```

Payment Service terminal:

```powershell
$env:PAYMENT_DATABASE_URL = $env:IBANKING_E2E_PAYMENT_DATABASE_URL
$env:USER_SERVICE_URL = 'http://127.0.0.1:8001'
$env:TUITION_SERVICE_URL = 'http://127.0.0.1:8002'
$env:JWT_SECRET_KEY = $env:IBANKING_E2E_JWT_SECRET
$env:JWT_ALGORITHM = 'HS256'
$env:INTERNAL_API_KEY = $env:IBANKING_E2E_INTERNAL_API_KEY
if ($env:IBANKING_E2E_LOCAL_SMTP_READY -eq 'YES') {
    $env:SMTP_HOST = $env:IBANKING_E2E_SMTP_HOST
    $env:SMTP_PORT = $env:IBANKING_E2E_SMTP_PORT
    $env:SMTP_USERNAME = $env:IBANKING_E2E_SMTP_USERNAME
    $env:SMTP_PASSWORD = $env:IBANKING_E2E_SMTP_PASSWORD
    $env:SMTP_FROM_EMAIL = $env:IBANKING_E2E_SMTP_FROM_EMAIL
} else {
    # Explicit empty overrides prevent a local .env from supplying a real SMTP account.
    $env:SMTP_HOST = ''
    $env:SMTP_PORT = ''
    $env:SMTP_USERNAME = ''
    $env:SMTP_PASSWORD = ''
    $env:SMTP_FROM_EMAIL = ''
}
python -m uvicorn backend.payment_service.main:app --host 127.0.0.1 --port 8003
```

The shared JWT secret and internal key must be test-only values. Payment OTP scenarios require the local SMTP sink and the reader described above. Do not copy credentials into command history; set them through a protected local shell environment.

## Readiness and execution

Check each service before running tests:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8002/health
Invoke-RestMethod http://127.0.0.1:8003/health
```

After the dedicated databases are initialized and seeded, and after explicit approval for writes to them, run:

```powershell
pytest -q tests/e2e/test_real_http_e2e.py -rs
```

Without the approval and isolation variables, the suite skips before connecting to MySQL or sending requests. It checks database identity and required tables before starting any service. Never use the repository's standard `.env.example` database names for this suite.

## Scenario coverage

| ID | Scenario | Verification |
| --- | --- | --- |
| E2E-01 | Demo login and JWT validation | User profile and Payment history accept the same JWT |
| E2E-02 | Tuition lookup | HTTP response includes the expected student, positive amount, and UNPAID status |
| E2E-03 | Successful payment | Payment response, one debit ledger row, exact balance reduction, and PAID bill |
| E2E-04 | Insufficient balance | HTTP 409 and unchanged account balance |
| E2E-05 | Already-paid tuition | HTTP 409 and bill remains PAID |
| E2E-06 | Invalid OTP | HTTP 400, transaction remains PENDING, no debit row |
| E2E-07 | Expired OTP | Expired code rejected over HTTP; no debit row |
| E2E-08 | Duplicate debit/retry | Same idempotency key returns same balance and one ledger row |
| E2E-09 | Two payers, one bill | Concurrent confirmations produce one success, one conflict, one debit, and a PAID bill |
| E2E-10 | Service failure/reconciliation | SKIP until a safe fault-injection harness exists |
| E2E-11 | Transaction history | Successful runtime transaction appears once in the payer's history |
| E2E-12 | Unauthorized access | Protected User, Payment, and internal endpoints return HTTP 401 |

The suite does not delete or reset data. Successful payment scenarios consume their tuition bills. To repeat the full suite, provision a new isolated database set from the schemas and optional seeds after approval; do not reset a used database.

## Verify state after a run

Use a MySQL client connected only to the three E2E database names. The suite avoids printing transaction IDs, tokens, OTPs, passwords, or database URLs. Useful read-only checks include:

```sql
SELECT username, student_id FROM account_db_e2e_test.users WHERE username LIKE 'demo_%';
SELECT account_number, balance FROM account_db_e2e_test.accounts ORDER BY account_number;
SELECT student_id, status FROM ibanking_tuition_e2e_test.tuition_bills ORDER BY student_id;
SELECT transaction_id, student_id, amount, status FROM payment_db_e2e_test.transactions ORDER BY created_at DESC;
SELECT transaction_id, account_number, amount, balance_after FROM account_db_e2e_test.account_debits ORDER BY created_at DESC;
```

Stop each service with `Ctrl+C`. This phase does not run real HTTP tests or make payment transactions.
