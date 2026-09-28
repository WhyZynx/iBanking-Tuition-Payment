# User Service Integration Guide

This guide explains how Student 2 (Tuition Service) and Student 3 (Payment Service) can connect to Student 1's User Service.

## What User Service owns

- User authentication and JWT creation
- Current user's profile
- User-owned payment accounts and simulated balances
- Internal account lookup and atomic debit

User Service does not own tuition data, payment transactions, OTP, email, or the payment workflow. Account data is stored in `AccountDB`; transaction data belongs to Payment Service/PaymentDB.

## Project files

- `backend/main.py`: creates the FastAPI app, registers routers and CORS, and exposes `/health`.
- `backend/database.py`: SQLAlchemy engine, session factory, and database dependency.
- `backend/config.py`: loads database, JWT, and internal API key settings from environment configuration.
- `backend/security.py`: password hashing/checking and JWT encode/decode.
- `backend/dependencies.py`: authenticated-user and bearer-token dependency.
- `backend/models/`: SQLAlchemy `User` and `Account` models.
- `backend/schemas/`: request and response validation/serialization.
- `backend/controllers/`: FastAPI route definitions.
- `backend/services/`: authentication, account listing, lookup, and debit logic.
- `frontend/index.html`: public landing page.
- `frontend/login.html`: login form and User Service login call.
- `frontend/dashboard.html` and `frontend/js/dashboard.js`: authenticated overview and account summary.
- `frontend/profile.html` and `frontend/js/profile.js`: current user profile.
- `frontend/accounts.html` and `frontend/js/accounts.js`: simulated account list and balances.
- `frontend/history.html` and `frontend/js/history.js`: Payment Service history integration point; host is not configured yet.
- `frontend/tuition.html` and `frontend/js/tuition.js`: browser integration with Tuition Service.
- `frontend/js/auth.js`: shared `sessionStorage` token handling, API helper, navigation, logout, and page guard.
- `frontend/css/style.css`: shared responsive styles.
- `frontend/assets/ibanking-hero.png`: homepage illustration.
- `tests/`: User Service API, account scoping, debit, and concurrency tests.
- `db/init.sql`: MySQL `users` and `accounts` schema and demo seed data.

## Current service endpoints

User Service local development base URL: `http://localhost:8001`.

| Feature | Frontend / caller | Service | Endpoint |
| --- | --- | --- | --- |
| Sign in | `login.html` | User Service | `POST /api/v1/auth/login` |
| Current profile | `profile.html`, `dashboard.html` | User Service | `GET /api/v1/users/me` |
| User accounts | `accounts.html`, `dashboard.html`, `tuition.html` | User Service | `GET /api/v1/accounts/me` |
| Internal account lookup | Payment Service only | User Service internal | `GET /api/v1/internal/accounts/{account_number}` |
| Internal debit | Payment Service only | User Service internal | `POST /api/v1/internal/accounts/{account_number}/debit` |
| Tuition lookup | `tuition.html` | Tuition Service | Current UI calls `GET /api/v1/tuition/{student_id}`; Student 2/team must confirm the service contract. |
| Transaction history | `history.html` | Payment Service | Endpoint and host/port are **TBD by Student 3**. |

The application-level architecture may place an API Gateway in front of these services:

```text
Frontend -> API Gateway -> User Service / Tuition Service / Payment Service
```

This repository currently configures the frontend to call User Service directly at port `8001` and Tuition Service at port `8002`. No API Gateway implementation or route configuration is present here. Agree gateway routes and browser CORS settings with the team before changing frontend base URLs.

## User authentication

The login request is:

```http
POST /api/v1/auth/login
Content-Type: application/json
```

```json
{"username":"user01","password":"123456"}
```

The response contains `access_token` and `token_type`. The JWT claims are `sub` (user ID as a string), `username`, and `exp`. The current default lifetime is 30 minutes. The frontend stores the token in `sessionStorage` under `ibanking_access_token` and sends authenticated public requests as:

```http
Authorization: Bearer <JWT>
```

`GET /api/v1/users/me` returns `userId`, `username`, `fullName`, `phone`, and `email`. `GET /api/v1/accounts/me` returns only the authenticated user's accounts, with `accountNumber`, `balance`, `isDefault`, and `status`.

The internal account lookup returns `accountNumber`, `balance`, `isDefault`, `status`, and `userId`. For example:

```json
{"accountNumber":"1012345678","balance":15000000,"isDefault":true,"status":"ACTIVE","userId":1}
```

## Student 2: Tuition Service connection

Student 2 owns tuition records and its database. Tuition Service must not read User Service's `AccountDB` or copy User Service tables. Student 1's current user profile endpoint is protected by the user's JWT:

```http
GET /api/v1/users/me
Authorization: Bearer <user JWT>
```

If Tuition Service needs payer profile data, use an agreed REST/API Gateway flow that forwards the authenticated user's JWT. The current User Service does not provide a separate service credential for calling `/users/me`; do not invent another authentication mechanism. The existing internal API key is only for internal account routes. There is no User-to-Student ID mapping in User Service, so do not assume that a profile contains an MSSV.

The current tuition page calls `http://localhost:8002/api/v1/tuition/{student_id}` without a JWT because the lookup is by student ID. Student 2/team should confirm the endpoint, response fields, and CORS/API Gateway behavior before final integration.

## Student 3: Payment Service connection

Payment Service owns payment records, transaction state, OTP validation, idempotency, and calls to Notification Service. It must not connect directly to `AccountDB`. After validating a payment request and OTP, Payment Service calls the User Service internal debit route:

```http
POST /api/v1/internal/accounts/{account_number}/debit
X-Internal-API-Key: <internal-key>
Content-Type: application/json
```

Request body:

```json
{"amount":8500000,"transactionId":"TX-001"}
```

`amount` must be greater than zero. `transactionId` is required and is accepted for tracing; User Service does not store it or provide transaction idempotency.

Successful response (`200`):

```json
{"success":true,"accountNumber":"1012345678","remainingBalance":6500000}
```

Relevant failures are `401` for a missing/invalid internal API key, `404` for a missing account, `409` for an inactive account or insufficient balance, and `422` for invalid request fields/amount. Payment Service should handle the response and decide whether its own payment can continue or must fail.

`INTERNAL_API_KEY` is configured in the User Service environment (`backend/.env`, based on `backend/.env.example`). Share the secret through the team's approved private configuration channel; never place it in HTML, browser JavaScript, or frontend build settings. The frontend must never call either `/api/v1/internal/accounts/...` route.

### Debit sequence

1. Payment Service validates its payment request and OTP.
2. Payment Service calls the User Service internal debit endpoint with the account number, amount, transaction ID, and internal API key.
3. User Service checks the internal API key and account status.
4. User Service executes one conditional database update requiring an active account and sufficient balance.
5. User Service returns success or an HTTP error; Payment Service continues its own workflow based on that result.

Debit uses an atomic update equivalent to:

```sql
UPDATE accounts
SET balance = balance - :amount
WHERE account_number = :account_number
  AND status = 'ACTIVE'
  AND balance >= :amount;
```

Only a request that changes one row succeeds. For example, if two concurrent requests each try to debit 4,000,000 from a 5,000,000 balance, at most one can succeed. Payment Service must call the debit endpoint rather than `GET balance -> calculate -> update`; the read-then-write pattern can overspend under concurrency. Payment Service remains responsible for payment idempotency and coordination with Tuition Service.

## History integration

`history.html` and `frontend/js/history.js` are UI/integration only. The Payment Service host/port and history API are **TBD by Student 3**; the frontend intentionally has no guessed default host. The existing proposal is:

```http
GET /api/v1/transactions/me
Authorization: Bearer <user JWT>
```

Proposed response shape for team review:

```json
{
  "items": [
    {
      "transactionId": "TX-001",
      "studentId": "20260001",
      "studentName": "Nguyen Van B",
      "amount": 5000000,
      "status": "SUCCESS",
      "createdAt": "2026-09-25T10:30:00Z"
    }
  ]
}
```

Student 3 must confirm the route, host/port, response fields, authorization behavior, and CORS/API Gateway configuration. The UI supports loading, empty, unconfigured, and unavailable states. Do not add transaction tables or transaction data to User Service.

## Environment and local run

| Component | Local port |
| --- | --- |
| User Service | `8001` |
| Frontend static server | `5500` |
| Tuition Service | `8002` (current frontend setting; confirm with Student 2) |
| Payment Service | **TBD by Student 3** |

Set local values in `backend/.env` using `backend/.env.example` as a template. Do not commit secrets.

**Terminal 1 — from the repository root:**

```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

**Terminal 2 — from the repository root:**

```powershell
python -m http.server 5500 --directory frontend
```

Open `http://localhost:5500`. User Service health: `http://localhost:8001/health`; Swagger: `http://localhost:8001/docs`.

## Integration checklist

- [ ] User Service runs on port 8001.
- [ ] `GET /health` returns `{"status":"ok"}`.
- [ ] Login API issues a JWT.
- [ ] JWT-protected profile API works.
- [ ] Account API returns only the current user's accounts.
- [ ] Internal API key is configured for service-to-service calls.
- [ ] Payment Service can call the internal debit API.
- [ ] Payment Service does not access AccountDB directly.
- [ ] Tuition Service does not access AccountDB directly.
- [ ] Frontend does not call the internal debit API.
- [ ] Student 3 confirms the History API contract and Payment Service host/port.
- [ ] History UI calls the confirmed Payment Service API.
