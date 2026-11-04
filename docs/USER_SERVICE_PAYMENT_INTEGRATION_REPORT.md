# User Service – Payment Service Integration Report

## Result

**Payment integration implemented on `fix/payment-service-integration`; see the Payment owner implementation note below.**

Sections 1–10 contain the User Service implementation report and its point-in-time findings. The Payment owner follow-up below supersedes the earlier statements that Payment had not yet integrated the contract.

User Service returns explicit error codes for confirmed rollback versus unknown debit outcome and exposes a read-only debit status endpoint. Payment Service now consumes that contract. The status endpoint's `NOT_FOUND` race remains unresolved by the two-service API alone, so Payment does not fail or retry based on a single `NOT_FOUND`.

## 1. Initial issue

User Service returned HTTP 503 with only a prose `detail` for both a confirmed MySQL lock-error rollback and an unconfirmed transaction result. Payment Service treated every debit response other than HTTP 200, 404, or 409 as a reconciliation case. Consequently, it could not distinguish a debit that certainly rolled back from one that might have committed.

## 2. Existing flow

1. The client asks Payment Service to create a payment. Payment validates account ownership and tuition, creates a Payment transaction with a UUID, and returns it as `PENDING`.
2. Payment confirmation claims the Payment transaction (`PROCESSING`), validates the OTP, rechecks Tuition and User account state, then requests a Tuition claim using the Payment transaction ID.
3. Payment marks the OTP used and calls User Service `POST /api/v1/internal/accounts/{account_number}/debit`, sending the same ID as `transactionId`.
4. User Service creates an `AccountDebit` keyed by that transaction ID and conditionally updates the balance in the same DB transaction. A matching existing debit record returns its prior result without another debit.
5. On User HTTP 200, Payment updates Tuition to paid, marks the Payment transaction successful, and sends a confirmation email.
6. On User 404/409, Payment currently attempts to release the Tuition claim and marks the transaction failed. That generic 409 branch must be refined for `TRANSACTION_ID_CONFLICT`, because a debit ledger row for the ID already exists. On a timeout or any other User response, Payment marks `RECONCILIATION_REQUIRED` and does not release the Tuition claim. No automatic debit retry or reconciliation worker/status query to User Service was identified before this task.

Payment's own `GET /api/v1/payments/{transaction_id}` reports Payment transaction state; it does not query the User Service debit ledger. User Service now exposes a read-only endpoint for that ledger, with the race limitations below.

## 3. Files changed in this task

| File | Change |
|---|---|
| `backend/user_service/services/account_service.py` | Adds stable codes for debit business errors, confirmed rollback, and unknown outcome, plus a SELECT-only status lookup by transaction ID. `DEBIT_ROLLED_BACK` is returned only for a pre-commit lock error after rollback succeeds. Commit exceptions and failed rollback remain outcome-unknown. A refresh error after successful commit still returns the known committed balance. |
| `backend/user_service/controllers/account_controller.py` | Adds an internal status route protected by the existing internal API key dependency. |
| `backend/user_service/schemas/account_schema.py` | Defines the minimal status response schema. |
| `backend/user_service/main.py` | Registers the internal debit-status router. |
| `tests/user_service/test_user_service.py` | Tests structured business error codes, rollback failure (including duplicate-insert recovery cleanup), commit acknowledgement loss, post-commit refresh failure, MySQL 1205/1213 handling, idempotency, and status lookup/auth/database-error/no-side-effect behavior using isolated SQLite and simulated SQLAlchemy errors. |
| `docs/USER_SERVICE_PAYMENT_API_CONTRACT.md` | Documents the implemented HTTP contract and the race limits of `NOT_FOUND`. |
| `docs/USER_SERVICE_PAYMENT_INTEGRATION_REPORT.md` | Updates the integration findings and coordination proposal. |

No Payment Service, Tuition Service, database schema, or Docker configuration was changed in this task. Existing uncommitted changes were preserved.

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
    "message": "Debit was rolled back successfully."
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
    "message": "Debit outcome could not be confirmed."
  }
}
```

The new error body uses FastAPI's standard `detail` envelope, but `detail` changes from a string to an object for these two 503 cases. Payment currently ignores the error body; any other internal client must be checked before release.

## 5. Payment owner implementation

1. Parse `response.json()["detail"]["code"]` for User debit 503 responses.
2. For `DEBIT_ROLLED_BACK`, do not call Tuition `/pay`; release the Tuition claim and follow the agreed safe Payment transaction policy. If the transaction is made terminal `FAILED`, the user can create a new Payment transaction after the claim is released. Ensure claim-release failure is observable and does not silently leave a claim held.
3. For `DEBIT_OUTCOME_UNKNOWN`, keep the Payment transaction in `RECONCILIATION_REQUIRED`, do not release the Tuition claim, and do not send another debit with a new transaction ID.
4. Keep timeouts, malformed responses, and unrecognized error codes on the conservative reconciliation path.
5. Handle `TRANSACTION_ID_CONFLICT` separately from insufficient balance. The ID is already present in the debit ledger, so Payment must not mark the transaction failed and release the Tuition claim without reconciling the recorded debit.
6. Use `GET /api/v1/internal/debits/{transaction_id}` only as a read-only observation. A `NOT_FOUND` response can race an in-flight debit and is not proof that the request will not commit. Do not retry POST automatically based on one `NOT_FOUND`.

Payment now parses structured debit codes. Confirmed rollback marks the transaction failed and attempts to release the Tuition claim. Unknown outcomes keep `RECONCILIATION_REQUIRED` and retain the claim. A transaction ID conflict is recorded with a dedicated reconciliation code, keeps the claim, and is excluded from automatic reconciliation because User's status endpoint does not expose the account and amount needed to prove that the existing debit matches this tuition payment.

Payment's authenticated `POST /api/v1/payments/{transaction_id}/reconcile` endpoint looks up debit status. `DEBITED` can resume tuition completion for non-conflict transactions; `NOT_FOUND` remains `RECONCILIATION_REQUIRED` and keeps the claim, without resending the debit. Conflicts require manual review.

The Tuition owner should confirm that release by transaction ID is safe to call for a confirmed rollback and cannot release another payment's claim. No Tuition behavior was changed.

### Suggested message to Payment owner

> User Service returns two explicit codes in debit 503 responses: `DEBIT_ROLLED_BACK` means a pre-commit error was rolled back successfully; `DEBIT_OUTCOME_UNKNOWN` means commit/rollback outcome cannot be confirmed. Please parse `detail.code`: for the first, do not pay Tuition and release the claim only under the agreed Payment failure policy. For the second, preserve `RECONCILIATION_REQUIRED` and the Tuition claim. The new GET `/api/v1/internal/debits/{transaction_id}` endpoint is read-only, but one `NOT_FOUND` can race an in-flight debit and must not trigger an automatic retry. Please confirm Payment status and recovery behavior before integrating this branch.

## 6. Idempotency and status lookup

- `transactionId` is the primary key of User Service's debit record. A matching retry returns the saved `balance_after`; a reused ID for a different account or amount returns conflict.
- This protects against a second debit when the first debit committed.
- If an ambiguous first attempt actually rolled back, replaying the same ID can perform the debit once. This is a safe idempotent operation retry only when Payment deliberately decides to retry; it is not a way to ask “did it commit?” without side effects.
- `GET /api/v1/internal/debits/{transaction_id}` SELECTs the committed debit record and returns `DEBITED` or `NOT_FOUND`; it does not mutate data or call debit logic. Database errors propagate as server errors instead of being reported as `NOT_FOUND`.
- Because the POST inserts the ledger row and updates the account in one transaction, a concurrent GET cannot see an uncommitted row. A `NOT_FOUND` response is only a point-in-time observation; the POST may still commit. There is no automatic reconciliation worker.

## 7. Tests

### PASS

- `python -m pytest tests/user_service --basetemp <unique-writable-temp-dir>`: **27 passed, 2 skipped**. Runs against fixture-managed temporary SQLite, not demo databases. The default pytest temp root was inaccessible in this environment, so the passing run used a unique `--basetemp` directory.
- `python -m pytest -q tests/payment_service/test_payment_confirmation.py` with `PAYMENT_DATABASE_URL=sqlite:///:memory:` and test-only keys: **32 passed**. Its fixture uses `FakeSession` and mocked service HTTP calls. This verifies current Payment behavior, not support for the new error codes; no Payment code has been changed.
- `python -m py_compile backend/user_service/services/account_service.py backend/user_service/controllers/account_controller.py backend/user_service/schemas/account_schema.py backend/user_service/main.py tests/user_service/test_user_service.py`: passed after the final typing changes.
- `git diff --check`: passed.

### Pylance type checking

- Checked with the workspace-selected Python 3.13 interpreter and `python.analysis.typeCheckingMode=basic`.
- Workspace diagnostics reported **0 severity 1–3 diagnostics** in `backend/user_service` and `tests/user_service`. The remaining User Service entries are severity-4 unused-variable hints (including model imports used for metadata registration and test-fixture parameters); no typing errors remain in the checked files.
- The debit-status service now returns `Literal["DEBITED", "NOT_FOUND"]`, matching its response schema.
- The atomic UPDATE uses the Session's transaction-bound connection so Pylance exposes the returned cursor's `rowcount`; this remains in the same Session transaction. Lock-error tests now inject failures at that connection execution boundary.
- Pylance reported no diagnostics for the typed ORM model files or database `Base`. The previously supplied ORM self-dependency and class/instance attribute errors were not reproduced by current workspace diagnostics.
- Pylance is available; a standalone `pyright` executable is not installed. No dependency was installed.

### SKIP / NOT VERIFIED

- Two User Service MySQL concurrency cases were skipped because `USER_SERVICE_TEST_DATABASE_URL` is not configured. No MySQL test database was created or contacted.
- Real MySQL 1205/1213 handling and network/commit ambiguity have not been tested against MySQL.
- Payment's interpretation of `DEBIT_ROLLED_BACK` and `DEBIT_OUTCOME_UNKNOWN` is **not verified** because Payment has no parser/branch for these codes. The Payment confirmation suite passes with mocked HTTP but does not test the new code branches.
- No demo database, live payment endpoint, or demo container was used.

The first Payment confirmation test collection attempt lacked `PAYMENT_DATABASE_URL` and stopped before running tests. It was rerun successfully with in-memory SQLite and test-only credentials; no Payment database was accessed.

## 8. Remaining risks

- Payment does not yet parse either response code; a known rollback currently remains conservatively marked for reconciliation and its Tuition claim is not released.
- The new GET status endpoint provides point-in-time information only and cannot alone resolve a race with a still-running POST.
- Same-ID replay is safe against duplicate debit but can perform a debit if the record is absent; Payment must not treat it as a status-only request.
- The structured `detail` shape is new for these 503 responses. Confirm no other internal clients assume that `detail` is always a string.
- MySQL-specific behavior remains simulated rather than verified on an isolated MySQL test DB.

## 9. Git state and re-check instructions

- Branch: `fix/user-service-integration`.
- Upstream: `origin/fix/user-service-integration` (unchanged during this task).
- Scoped integration files: `backend/user_service/services/account_service.py`, `backend/user_service/controllers/account_controller.py`, `backend/user_service/schemas/account_schema.py`, `backend/user_service/main.py`, `tests/user_service/test_user_service.py`, `docs/USER_SERVICE_PAYMENT_API_CONTRACT.md`, and this report.
- Pre-existing uncommitted files preserved: `docker-compose.yml`, `docs/FULL_SYSTEM_AUDIT_BY_SERVICE.md`, and `docs/USER_SERVICE_INTEGRATION_FIX_REPORT.md`.
- The finalization commit must include only the scoped integration files above; the pre-existing unrelated files must remain unstaged. No merge into `main` is intended.

After Payment owner confirms the response handling, add Payment tests for both codes (including claim release/retention), then run the service unit tests and the integration tests only against explicitly isolated databases.

## 10. Safe re-check commands

Run User Service tests with the fixture-managed SQLite database:

```powershell
$testTemp = Join-Path $env:TEMP ("user-service-tests-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $testTemp | Out-Null
python -m pytest tests/user_service --basetemp $testTemp
```

Run Payment confirmation unit tests with mocked service calls and an in-memory Payment database:

```powershell
$env:PAYMENT_DATABASE_URL = "sqlite:///:memory:"
$env:INTERNAL_API_KEY = "test-only-key"
$env:JWT_SECRET_KEY = "test-only-secret"
python -m pytest -q tests/payment_service/test_payment_confirmation.py
```

Read-only status endpoint smoke check (User Service must already be running in an approved test environment):

```powershell
$headers = @{ "X-Internal-API-Key" = $env:INTERNAL_API_KEY }
Invoke-RestMethod -Method Get `
  -Uri "http://localhost:8001/api/v1/internal/debits/TXN123" `
  -Headers $headers
```

Equivalent curl command:

```powershell
curl.exe -H "X-Internal-API-Key: $env:INTERNAL_API_KEY" `
  "http://localhost:8001/api/v1/internal/debits/TXN123"
```

Do not use the POST debit endpoint as a smoke test against demo data. MySQL concurrency/debit tests require an explicitly isolated test database and must not point at demo schemas.

## 11. Payment owner follow-up

- Parses `detail.code`: confirmed rollback fails the Payment transaction and releases the Tuition claim; unknown/malformed outcomes preserve reconciliation and the claim.
- `TRANSACTION_ID_CONFLICT` is persisted as `reconciliation_code`, keeps the claim, and is excluded from automatic reconciliation because User's read endpoint does not expose amount/account for comparison. The UI instructs the payer not to retry and requires manual review.
- Adds the authenticated Payment reconciliation endpoint. `DEBITED` can resume tuition completion without replaying the debit; `NOT_FOUND` preserves reconciliation and the claim because it is only a point-in-time observation.
- Fresh and existing Payment databases use the single canonical script `db/payment/payment_init.sql`; it includes `reconciliation_code` and guarded upgrades for the older Payment schema.
- Payment tests cover rollback, unknown outcome, ID conflict, claim handling, read-only status lookup, and the migration. MySQL-specific production behavior still requires validation against an approved isolated MySQL environment.
- Safe Payment Service test run: **90 passed**; the two opt-in/demo database integration tests were excluded. Python/JavaScript syntax checks and `git diff --check` passed.
