# User & Account Service API

## Responsibility

Student 1 owns authentication, users, accounts, and account balances. Tuition, payment workflow, OTP, notifications, and transaction history remain owned by other services.

## Run Configuration

- Framework: FastAPI
- Default port: `8001`
- Database: MySQL `account_db`
- Swagger: `http://localhost:8001/docs`
- Internal API authentication: `X-Internal-API-Key`

## Public APIs

### `POST /api/v1/auth/login`

No authentication.

Request:

```json
{"username": "user01", "password": "123456"}
```

Success `200`:

```json
{"access_token": "JWT", "token_type": "bearer"}
```

Invalid credentials return `401`.

### `GET /api/v1/users/me`

Requires `Authorization: Bearer <JWT>`.

Success `200`:

```json
{
  "userId": 1,
  "username": "user01",
  "fullName": "Nguyen Van A",
  "phone": "0901234567",
  "email": "user01@example.com"
}
```

### `GET /api/v1/accounts/me`

Requires `Authorization: Bearer <JWT>`. Returns only accounts owned by the authenticated user.

## Internal APIs for Payment Service

Both endpoints require `X-Internal-API-Key` and must be called service-to-service, not by the frontend.

### `GET /api/v1/internal/accounts/{account_number}`

Returns `200` with account number, owner ID, balance, and status. Missing accounts return `404`.

### `POST /api/v1/internal/accounts/{account_number}/debit`

Request:

```json
{"amount": 8500000, "transactionId": "TX-001"}
```

Success `200`:

```json
{"success": true, "accountNumber": "1012345678", "remainingBalance": 6500000}
```

Returns `404` for a missing account, `409` for an inactive account or insufficient balance, and `422` for invalid input. The `transactionId` is accepted for integration tracing; transaction ownership and idempotency remain the responsibility of Payment Service.

## Debit Safety

Debit uses one atomic SQL update with predicates for `ACTIVE` status and `balance >= amount`. The affected-row count determines success. Therefore two concurrent debits cannot both spend the same available balance, and the database check constraint also prevents negative balances.

## Running

```powershell
python -m pip install -r backend/requirements.txt
mysql -u root -p < db/init.sql
Copy-Item backend/.env.example backend/.env
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

Run tests with:

```powershell
python -m pytest -q
```

The tests use a local SQLite file only for isolated automated testing; production configuration remains MySQL.

Transaction History is not backed by a User Service endpoint. Its ownership and frontend integration point are described in [USER_SERVICE_INTEGRATION.md](USER_SERVICE_INTEGRATION.md). No transaction table or PaymentDB access is added to User Service.
