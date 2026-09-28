# Tuition Service API

## Responsibility

The Tuition Service manages student tuition information, tuition lookup, and tuition payment status.

Authentication, account balances, payment processing, OTP verification, notifications, and transaction history are handled by other services.

## Run Configuration

- Framework: FastAPI
- Default port: `8002`
- Database: MySQL `ibanking_tuition`
- Swagger: `http://localhost:8002/docs`
- Frontend: `http://localhost:5500/tuition.html`

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

Returns `404 Not Found` if the tuition information does not exist.

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

Returns `404 Not Found` if the tuition information does not exist.

Returns `409 Conflict` if the tuition has already been paid.

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

The Confirm Transaction button is enabled only when:

- Tuition information exists
- Tuition status is `UNPAID`
- Available account balance is sufficient
- Terms and conditions have been accepted

The frontend does not directly update the tuition status.

Payment processing, OTP verification, account debit, and transaction processing are handled by the Payment Service.

## Payment Status Safety

Tuition status is updated using a conditional SQL statement:

```sql
UPDATE tuition_bills
SET status = 'PAID'
WHERE student_id = ?
  AND status = 'UNPAID';
```

The affected-row count determines whether the update succeeds.

If two requests attempt to mark the same tuition bill as paid, only one request can change the status from `UNPAID` to `PAID`.

Later attempts receive `409 Conflict`.

This protects the tuition payment status from being updated successfully more than once.

The complete payment transaction, account debit, OTP verification, transaction idempotency, and rollback remain the responsibility of the Payment Service.

## Running

### 1. Activate the Virtual Environment

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows:

```powershell
.venv\Scripts\activate
```

### 2. Install Dependencies

```bash
python -m pip install -r backend/tuition_service/requirements.txt
```

### 3. Configure the Database

Create `backend/tuition_service/.env` for local settings:

```env
TUITION_DB_HOST=localhost
TUITION_DB_PORT=3306
TUITION_DB_USER=root
TUITION_DB_PASSWORD=
TUITION_DB_NAME=ibanking_tuition
```

Import the Tuition database:

```bash
mysql -u root < db/tuition/tuition.sql
```

If MySQL requires a password:

```bash
mysql -u root -p < db/tuition/tuition.sql
```

### 4. Run the Tuition Service

```bash
python -m uvicorn backend.tuition_service.main:app --reload --port 8002
```

Swagger:

```text
http://localhost:8002/docs
```

Health check:

```text
http://localhost:8002/health
```

## Running the Web

Keep the backend services running and open another terminal.

Run the frontend:

```bash
python3 -m http.server 5500 --directory frontend
```

On Windows:

```powershell
python -m http.server 5500 --directory frontend
```

Open:

```text
http://localhost:5500/tuition.html
```

The following services are required for the integrated Tuition Payment page:

```text
User & Account Service: http://localhost:8001
Tuition Service:        http://localhost:8002
Frontend:               http://localhost:5500
```

The User & Account Service provides the authenticated user's payer information and account balance.

The Tuition Service provides tuition lookup and tuition payment status.

The Payment Service will handle the final payment workflow, OTP verification, account debit, and transaction processing.

## Automated Testing

The automated tests are located at:

```text
tests/tuition_service/test_tuition_service.py
```

Install the required dependencies:

```bash
python -m pip install -r backend/tuition_service/requirements.txt
```

Run the Tuition Service tests:

```bash
python -m pytest tests/tuition_service/test_tuition_service.py -v
```

Or run all tests inside the `tests` directory:

```bash
python -m pytest tests -v
```

The Tuition Service test suite covers:

- Retrieving all tuition records
- Retrieving tuition by Student ID
- Student ID normalization
- Non-existing tuition lookup
- Updating unpaid tuition to `PAID`
- Preventing duplicate tuition payment
- Handling non-existing tuition during payment
- Concurrent payment status updates

Expected result:

```text
8 passed
```

The automated tests use mocked database connections and do not modify the production MySQL tuition data.

## Manual Testing

The APIs can also be tested through Swagger:

```text
http://localhost:8002/docs
```

### Get All Tuition Records

```text
GET /api/v1/tuition
```

Expected:

```text
200 OK
```

### Get an Existing Unpaid Tuition

```text
GET /api/v1/tuition/524H0012
```

Expected:

```text
200 OK
status: UNPAID
```

### Get a Paid Tuition

```text
GET /api/v1/tuition/524H0078
```

Expected:

```text
200 OK
status: PAID
```

### Get a Non-existing Student

```text
GET /api/v1/tuition/524H9999
```

Expected:

```text
404 Not Found
```

### Update an Unpaid Tuition

```text
PUT /api/v1/tuition/524H0104/pay
```

Expected:

```text
200 OK
status: PAID
```

Call the same request again:

```text
PUT /api/v1/tuition/524H0104/pay
```

Expected:

```text
409 Conflict
```

After manual payment testing, reset the sample tuition status if the record is required as `UNPAID` for later demonstrations.
