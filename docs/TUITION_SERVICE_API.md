# Tuition Service API

## Responsibility

Student 2 owns tuition lookup and tuition payment status management.

The Tuition Service stores student tuition information and provides internal APIs for the Payment Service to retrieve tuition details and mark tuition as paid.

Authentication, account balances, payment workflow, OTP, notifications, and transaction history remain owned by other services.

## Run Configuration

- Framework: FastAPI
- Default port: `8002`
- Database: MySQL `ibanking_tuition`
- Swagger: `http://localhost:8002/docs`

## Tuition APIs

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

Example:

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

Returns:

- `404` if the tuition information does not exist.
- `409` if the tuition has already been paid.

Already paid example:

```json
{
  "detail": "Tuition has already been paid"
}
```

## Payment Status Safety

Tuition status is updated using a conditional SQL statement:

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

Create and activate a virtual environment.

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
python -m pip install fastapi uvicorn pymysql python-dotenv
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

If the MySQL root account requires a password:

```bash
mysql -u root -p < db/tuition.sql
```

Run the service:

```bash
python -m uvicorn backend.controllers.tuition_controller:app --host 0.0.0.0 --port 8002
```

Swagger is available at:

```text
http://localhost:8002/docs
```

## Manual Testing

Test an existing unpaid tuition:

```text
GET /api/v1/tuition/524H0012
```

Expected: `200 OK`.

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