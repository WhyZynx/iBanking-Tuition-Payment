# API contracts (current implementation)

Local ports: User `8001`, Tuition `8002`, Payment `8003`; frontend `5500`. Each backend reads only its own database. Payment-to-service traffic uses HTTP and does not open another service's database.

## User Service (`http://localhost:8001`)

- `POST /api/v1/auth/login`, no auth. Request `{ "username": "user01", "password": "..." }`; response `{ "access_token": "...", "token_type": "bearer" }`.
- JWT claims: `sub` is the authenticated user ID as a string, plus `username` and `exp`. The same `JWT_SECRET_KEY` and `JWT_ALGORITHM` must be configured in Payment Service to verify this token.
- `GET /api/v1/users/me`, Bearer JWT. JSON uses existing aliases `userId`, `fullName`; DB/model names are `user_id`, `full_name`.
- `GET /api/v1/accounts/me`, Bearer JWT; returns `accountNumber`, `balance`, `isDefault`, `status` for the authenticated user's accounts.
- `GET /api/v1/internal/accounts/{account_number}` and `POST /api/v1/internal/accounts/{account_number}/debit` require `X-Internal-API-Key`. Debit body uses `{ "amount": 8500000, "transactionId": "TX-001" }`; success fields are `success`, `accountNumber`, `remainingBalance`. 404 means account missing; 409 means inactive or insufficient balance; validation errors are 422.
- `GET /health` returns `{ "status": "ok" }`.

## Tuition Service (`http://localhost:8002`)

- `GET /api/v1/tuition` returns a list; `GET /api/v1/tuition/{student_id}` returns one record with `student_id`, `student_name`, `amount`, `status`.
- `student_id` maps to `tuition_bills.student_id`, `student_name` to `student_name`, `amount` is VND, and `status` is `UNPAID` or `PAID`. These snake_case names match the existing database and frontend lookup code.
- Missing records return 404. `PUT /api/v1/tuition/{student_id}/pay` returns the updated record, 404 if missing, 409 if already paid. This existing route currently has no service credential check; add that protection before enabling Payment to call it.
- `GET /health` returns `{ "service": "tuition-service", "status": "UP" }`.

## Payment Service (`http://localhost:8003`)

- `POST /api/v1/payments/confirm` currently accepts `{ "transactionId": "...", "otpCode": "..." }`. It refers to an already stored transaction and OTP; there is no payment creation endpoint in this step. It now requires a Bearer JWT and only permits the transaction's `payer_user_id` to confirm it. Success is `{ "message": "..." }`; failed verification/debit uses an HTTP error.
- `GET /api/v1/transactions/me` requires a Bearer JWT and filters by the JWT `sub`; response is `{ "items": [...] }` with existing frontend fields `transactionId`, `studentId`, `studentName`, `amount`, `status`, `createdAt`.
- Payment DB columns are `transaction_id`, `payer_user_id`, `source_account_number`, `student_id`, `amount`, `status`, `created_at`, `completed_at`. `source_account_number` is the current DB name for the payer account number. Stored statuses written by current code are `PENDING`, `SUCCESS`, `FAILED`; no DB enum/check constraint restricts this field.
- Existing stored transactions/OTP rows are prerequisites for confirm. The service does not yet create them or call Tuition Service; transaction IDs therefore originate outside the currently implemented API surface.
- `/health` returns `{ "status": "ok", "service": "payment" }`.

## Service configuration

User and Payment must use the same `JWT_SECRET_KEY`, `JWT_ALGORITHM`, and `INTERNAL_API_KEY`. Payment configuration is read from `backend/payment_service/.env` (copy `.env.example` locally): `PAYMENT_DATABASE_URL`, `USER_SERVICE_URL`, `TUITION_SERVICE_URL`, `INTERNAL_API_KEY`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`. User config is read from `backend/user_service/.env`; Tuition DB variables (`TUITION_DB_HOST`, `TUITION_DB_PORT`, `TUITION_DB_USER`, `TUITION_DB_PASSWORD`, `TUITION_DB_NAME`) are read from `backend/tuition_service/.env`.

`change-this-secret` and `change-this-internal-key` are development defaults only. Configure private local values consistently; do not commit `.env` files. Payment's `TUITION_SERVICE_URL` is prepared for the next workflow step and is not called yet.

## Known integration gaps for the next workflow step

1. No API currently creates a PaymentDB transaction or OTP, so confirm only works for a transaction/OTP that already exists.
2. Payment does not yet update Tuition Service. The current tuition pay route is not internal-key protected.
3. The existing Payment confirmation operation spans PaymentDB and User Service; cross-service rollback/idempotency is not implemented here.
