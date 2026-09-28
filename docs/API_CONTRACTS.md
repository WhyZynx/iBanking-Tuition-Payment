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

- `POST /api/v1/payments` creates a `PENDING` transaction from `student_id` and `account_number`; payer identity comes from JWT and amount comes from Tuition Service.
- `POST /api/v1/payments/{transaction_id}/otp` requires a Bearer JWT and an owned `PENDING` transaction. It sends a six-digit OTP to the authenticated user's registered email; the code expires after five minutes. A newer request invalidates the previous active OTP for that transaction.
- `POST /api/v1/payments/confirm` accepts `{ "transactionId": "...", "otpCode": "..." }`, requires a Bearer JWT, verifies ownership and `PENDING` status, then consumes a valid OTP. It does not debit an account, update tuition, or change transaction status in the current step.
- `GET /api/v1/transactions/me` requires a Bearer JWT and filters by the JWT `sub`; response is `{ "items": [...] }` with existing frontend fields `transactionId`, `studentId`, `studentName`, `amount`, `status`, `createdAt`.
- Payment transaction columns include `transaction_id`, `payer_user_id`, `source_account_number`, `student_id`, `student_name`, `amount`, `status`, `created_at`, and `completed_at`. Existing PaymentDB installations need the `student_name` migration from `db/payment/payment_add_student_name.sql`.
- OTP rows use the existing `otps` table and its `transaction_id`, `otp_code`, `expires_at`, and `is_used` columns.
- `/health` returns `{ "status": "ok", "service": "payment" }`.

## Service configuration

User and Payment must use the same `JWT_SECRET_KEY` and `JWT_ALGORITHM`; internal account calls also share `INTERNAL_API_KEY`. Payment configuration is read from `backend/payment_service/.env` (copy `.env.example` locally): `PAYMENT_DATABASE_URL`, `USER_SERVICE_URL`, `TUITION_SERVICE_URL`, `INTERNAL_API_KEY`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, and `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`. User config is read from `backend/user_service/.env`; Tuition DB variables (`TUITION_DB_HOST`, `TUITION_DB_PORT`, `TUITION_DB_USER`, `TUITION_DB_PASSWORD`, `TUITION_DB_NAME`) are read from `backend/tuition_service/.env`.

`change-this-secret` and `change-this-internal-key` are development defaults only. Configure private local values consistently; do not commit `.env` files. SMTP credentials must also be set locally to deliver OTP emails.

## Known integration gaps for the next workflow step

1. Payment confirmation currently verifies OTP only; account debit and Tuition status update are subsequent workflow work.
2. Payment does not yet update Tuition Service.
3. Payment does not yet debit User Service or implement cross-service rollback/idempotency.
