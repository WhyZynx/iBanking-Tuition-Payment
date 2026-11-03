# User Service – Payment Service Integration Report

## Result

**READY AFTER PAYMENT OWNER COORDINATION**

User Service now returns explicit error codes for confirmed rollback versus unknown debit outcome. Payment Service does not currently inspect those codes, so the two services are not fully behaviorally aligned yet. Payment business logic was not changed because it belongs to another owner.

## 1. Initial issue

User Service returned HTTP 503 with only a prose `detail` for both a confirmed MySQL lock-error rollback and an unconfirmed transaction result. Payment Service treated every debit response other than HTTP 200, 404, or 409 as a reconciliation case. Consequently, it could not distinguish a debit that certainly rolled back from one that might have committed.

## 2. Existing flow

1. The client asks Payment Service to create a payment. Payment validates account ownership and tuition, creates a Payment transaction with a UUID, and returns it as `PENDING`.
2. Payment confirmation claims the Payment transaction (`PROCESSING`), validates the OTP, rechecks Tuition and User account state, then requests a Tuition claim using the Payment transaction ID.
3. Payment marks the OTP used and calls User Service `POST /api/v1/internal/accounts/{account_number}/debit`, sending the same ID as `transactionId`.
4. User Service creates an `AccountDebit` keyed by that transaction ID and conditionally updates the balance in the same DB transaction. A matching existing debit record returns its prior result without another debit.
5. On User HTTP 200, Payment updates Tuition to paid, marks the Payment transaction successful, and sends a confirmation email.
6. On User 404/409, Payment attempts to release the Tuition claim and marks the transaction failed. On a timeout or any other User response, Payment marks `RECONCILIATION_REQUIRED` and does not release the Tuition claim. No automatic debit retry or reconciliation worker/status query to User Service was identified.

Payment's own `GET /api/v1/payments/{transaction_id}` reports Payment transaction state; it does not query the User Service debit ledger.

## 3. Files changed in this task

| File | Change |
|---|---|
| `backend/user_service/services/account_service.py` | Adds stable `DEBIT_ROLLED_BACK` and `DEBIT_OUTCOME_UNKNOWN` codes in 503 response details. The first is returned only after a pre-commit rollback succeeds. Commit exceptions and failed rollback remain outcome-unknown. A refresh error after successful commit still returns the known committed balance. |
| `tests/user_service/test_user_service.py` | Asserts both response codes; tests rollback failure, commit acknowledgement loss, post-commit refresh failure, MySQL 1205/1213 handling, and idempotent retry behavior using isolated SQLite and simulated SQLAlchemy errors. |
| `docs/USER_SERVICE_PAYMENT_INTEGRATION_REPORT.md` | Adds this report and the coordination proposal below. |

No Payment Service, Tuition Service, database schema, or Docker configuration was changed in this task. Other pre-existing worktree changes are listed under Git below and were preserved.

## 4. Response contract

The request remains unchanged. Payment must send the payment transaction ID as `transactionId`:

```http
POST /api/v1/internal/accounts/1012345678/debit
X-Internal-API-Key: <internal key>
Content-Type: application/json
```

```json
{
  "amount": 5000000.00,
  "transactionId": "the-payment-transaction-uuid"
}
```

Success remains HTTP 200 with the existing response:

```json
{
  "success": true,
  "accountNumber": "1012345678",
  "remainingBalance": 10000000
}
```

For a MySQL 1205/1213 before commit, after rollback succeeds:

```http
HTTP/1.1 503 Service Unavailable
```

```json
{
  "detail": {
    "code": "DEBIT_ROLLED_BACK",
    "message": "Database is temporarily unavailable; debit was rolled back. Retry with the same transaction ID"
  }
}
```

If commit or rollback outcome cannot be confirmed:

```http
HTTP/1.1 503 Service Unavailable
```

```json
{
  "detail": {
    "code": "DEBIT_OUTCOME_UNKNOWN",
    "message": "Debit outcome could not be confirmed; reconcile before retrying with the same transaction ID"
  }
}
```

The new error body uses FastAPI's standard `detail` envelope, but `detail` changes from a string to an object for these two 503 cases. Payment currently ignores the error body; any other internal client must be checked before release.

## 5. Payment owner changes required

1. Parse `response.json()["detail"]["code"]` for User debit 503 responses.
2. For `DEBIT_ROLLED_BACK`, do not call Tuition `/pay`; release the Tuition claim and follow the agreed safe Payment transaction policy. If the transaction is made terminal `FAILED`, the user can create a new Payment transaction after the claim is released. Ensure claim-release failure is observable and does not silently leave a claim held.
3. For `DEBIT_OUTCOME_UNKNOWN`, keep the Payment transaction in `RECONCILIATION_REQUIRED`, do not release the Tuition claim, and do not send another debit with a new transaction ID.
4. Keep timeouts, malformed responses, and unrecognized error codes on the conservative reconciliation path.
5. Confirm the lifecycle for later reconciliation. Reposting with the same transaction ID cannot double-debit an already-recorded debit, but it is **not a read-only status check**: if no debit record exists, the User endpoint will perform a debit. Payment has no current recovery operation for a transaction already in `RECONCILIATION_REQUIRED`.

### Suggested message to Payment owner

> User Service is adding two explicit codes to its debit 503 responses: `DEBIT_ROLLED_BACK` means a pre-commit error was rolled back successfully; `DEBIT_OUTCOME_UNKNOWN` means commit/rollback outcome cannot be confirmed. Please parse `detail.code`: for the first, do not mark payment as reconciliation-required by default—do not pay Tuition, release the claim, then apply the agreed terminal/retry policy. For the second, preserve `RECONCILIATION_REQUIRED` and the Tuition claim; do not retry automatically or create a new transaction ID. Reposting the same ID is duplicate-safe if a debit record exists, but it can execute a debit if no record exists, so it is not a status query. Please confirm the intended Payment status and recovery flow before integrating this branch.

## 6. Idempotency and status lookup

- `transactionId` is the primary key of User Service's debit record. A matching retry returns the saved `balance_after`; a reused ID for a different account or amount returns conflict.
- This protects against a second debit when the first debit committed.
- If an ambiguous first attempt actually rolled back, replaying the same ID can perform the debit once. This is a safe idempotent operation retry only when Payment deliberately decides to retry; it is not a way to ask “did it commit?” without side effects.
- No User debit-status endpoint or automatic reconciliation worker exists. For automated, read-only reconciliation, the owners should agree on a narrowly scoped internal status endpoint and its result semantics. Do not treat “record absent” as conclusive while the original request may still be executing.

## 7. Tests

### PASS

- `python -m pytest --basetemp <task-temp-dir> -q tests/user_service/test_user_service.py`: **22 passed, 2 skipped**. Runs against fixture-managed temporary SQLite, not demo databases.
- `python -m pytest -q tests/payment_service/test_payment_confirmation.py` with `PAYMENT_DATABASE_URL=sqlite:///:memory:` and test-only keys: **32 passed**. Its fixture uses `FakeSession` and mocked service HTTP calls. This verifies current Payment behavior, not support for the new error codes; no Payment code has been changed.
- `python -m py_compile backend/user_service/services/account_service.py tests/user_service/test_user_service.py`: passed.
- `git diff --check`: passed.

### SKIP / NOT VERIFIED

- Two User Service MySQL concurrency cases were skipped because `USER_SERVICE_TEST_DATABASE_URL` is not configured. No MySQL test database was created or contacted.
- Real MySQL 1205/1213 handling and network/commit ambiguity have not been tested against MySQL.
- Payment's interpretation of `DEBIT_ROLLED_BACK` and `DEBIT_OUTCOME_UNKNOWN` is **not verified** because Payment has no parser/branch for these codes.
- No demo database, live payment endpoint, or demo container was used.

The first Payment confirmation test collection attempt lacked `PAYMENT_DATABASE_URL` and stopped before running tests. It was rerun successfully with in-memory SQLite and test-only credentials; no Payment database was accessed.

## 8. Remaining risks

- Payment does not yet parse either response code; a known rollback currently remains conservatively marked for reconciliation and its Tuition claim is not released.
- There is no automatic/manual tooling documented here to resolve `RECONCILIATION_REQUIRED` by checking User debit state.
- Same-ID replay is safe against duplicate debit but can perform a debit if the record is absent; Payment must not treat it as a status-only request.
- The structured `detail` shape is new for these 503 responses. Confirm no other internal clients assume that `detail` is always a string.
- MySQL-specific behavior remains simulated rather than verified on an isolated MySQL test DB.

## 9. Git state and re-check instructions

- Branch: `fix/user-service-integration`.
- Upstream: `origin/fix/system-audit-and-stabilization` (unchanged).
- This task's modifications: `backend/user_service/services/account_service.py`, `tests/user_service/test_user_service.py`, and this report.
- Pre-existing uncommitted files preserved: `docker-compose.yml`, `docs/FULL_SYSTEM_AUDIT_BY_SERVICE.md`, and `docs/USER_SERVICE_INTEGRATION_FIX_REPORT.md`.
- No commit, push, merge, stage, or branch switch was performed.

After Payment owner confirms the response handling, add Payment tests for both codes (including claim release/retention), then run the service unit tests and the integration tests only against explicitly isolated databases.
