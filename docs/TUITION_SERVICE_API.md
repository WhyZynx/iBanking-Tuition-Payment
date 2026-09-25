# Tuition Service API

## Responsibility

The Tuition Service manages student tuition information, tuition lookup, and tuition payment status.

Authentication, account balances, payment processing, OTP verification, notifications, and transaction history remain handled by other services.

## Run Configuration

- Framework: FastAPI
- Default port: `8002`
- Database: MySQL `ibanking_tuition`
- Swagger: `http://localhost:8002/docs`
- Frontend: `http://localhost:3000/pages/tuition.html`

## APIs

### `GET /api/v1/tuition`

Returns all tuition records.

Success `200`:

```json
[
  {
    "student_id": "524H0012",
    "student_name": "Nguyen Minh Anh",
    "amount": 18500000.00,
    "status": "UNPAID"
  },
  {
    "student_id": "524H0078",
    "student_name": "Le Hoang Phuc",
    "amount": 19750000.00,
    "status": "PAID"
  }
]
```

### `GET /api/v1/tuition/{student_id}`

Returns tuition information for a student.

Example:

```text
GET /api/v1/tuition/524H0012
```

Success `200`:

```json
{
  "student_id": "524H0012",
  "student_name": "Nguyen Minh Anh",
  "amount": 18500000.00,
  "status": "UNPAID"
}
```

Returns `404` if the student or tuition information does not exist.

```json
{
  "detail": "Tuition information not found"
}
```

### `PUT /api/v1/tuition/{student_id}/pay`

Marks an unpaid tuition bill as paid.

This endpoint is intended to be called by the Payment Service after the payment and OTP verification process has completed successfully.

Example:

```text
PUT /api/v1/tuition/524H0104/pay
```

Success `200`:

```json
{
  "student_id": "524H0104",
  "student_name": "Pham Ngoc Han",
  "amount": 17300000.00,
  "status": "PAID"
}
```

Returns `404` if the tuition information does not exist and `409` if the tuition has already been paid.

Already paid example:

```json
{
  "detail": "Tuition has already been paid"
}
```

## Tuition Payment Interface

The Tuition Payment page contains three information groups:

- Payer Information
- Tuition Information
- Payment Information

Payer information is automatically loaded from the authenticated user's account and is read-only.

The user enters a Student ID to retrieve the student's name, tuition amount, and payment status.

The payment amount is always the full tuition amount. Partial payment is not supported.

The Confirm Transaction button is enabled only when the tuition is unpaid, the available balance is sufficient, and the terms and conditions have been accepted.

The frontend does not directly update the tuition status. Payment processing and OTP verification are handled by the Payment Service.

## Payment Status Safety

Tuition status is updated using one conditional SQL statement:

```sql
UPDATE tuition_bills
SET status = 'PAID'
WHERE student_id = ?
  AND status = 'UNPAID';
```

The affected-row count determines whether the update succeeds.

Therefore, if two requests attempt to mark the same tuition bill as paid, only the first request can change the status from `UNPAID` to `PAID`. Later requests receive `409 Conflict`.

The complete payment transaction, account debit, OTP verification, transaction idempotency, and rollback remain the responsibility of the Payment Service.

## Running

Install dependencies:

```bash
python -m pip install -r backend/requirements.txt
```

Create a `.env` file in the project root:

```env
TUITION_DB_HOST=localhost
TUITION_DB_PORT=3306
TUITION_DB_USER=root
TUITION_DB_PASSWORD=
TUITION_DB_NAME=ibanking_tuition
```

Import the database:

```bash
mysql -u root < db/tuition.sql
```

If MySQL requires a password:

```bash
mysql -u root -p < db/tuition.sql
```

Run the Tuition Service:

```bash
python -m uvicorn backend.controllers.tuition_controller:app --reload --port 8002
```

Swagger is available at:

```text
http://localhost:8002/docs
```

## Running the Web

Keep the Tuition Service running and open another terminal.

Run the frontend:

```bash
python3 -m http.server 3000 --directory frontend
```

On Windows:

```powershell
python -m http.server 3000 --directory frontend
```

Open:

```text
http://localhost:3000/pages/tuition.html
```

The Tuition Service must be running on port `8002` for Student ID lookup to work.

The User & Account Service must also be running on port `8001` for the logged-in user's payer information and available balance to be loaded automatically.

## Manual Testing

Test all tuition records:

```text
GET /api/v1/tuition
```

Expected: `200 OK`.

Test an existing unpaid tuition:

```text
GET /api/v1/tuition/524H0012
```

Expected: `200 OK` with `"status": "UNPAID"`.

Test a paid tuition:

```text
GET /api/v1/tuition/524H0078
```

Expected: `200 OK` with `"status": "PAID"`.

Test a non-existing student:

```text
GET /api/v1/tuition/524H9999
```

Expected: `404 Not Found`.

Test updating an unpaid tuition:

```text
PUT /api/v1/tuition/524H0104/pay
```

Expected: `200 OK` with `"status": "PAID"`.

Call the same request again:

```text
PUT /api/v1/tuition/524H0104/pay
```

Expected: `409 Conflict`.
