# User Service – Payment Service API Contract

This document describes the internal User Service endpoints used by Payment Service. All examples use the existing internal API key header.

## Authentication

Send the internal key on both endpoints:

```http
X-Internal-API-Key: <shared internal API key>
```

Missing or invalid keys return HTTP `401`. Do not send this key from the browser.

## Debit an account

```http
POST /api/v1/internal/accounts/{account_number}/debit
Content-Type: application/json
X-Internal-API-Key: <shared internal API key>
```

Request:

```json
{
  "amount": 5000000.00,
  "transactionId": "payment-transaction-uuid"
}
```

Use the Payment transaction ID as `transactionId`. Reuse it for an intentional retry of that same debit; do not generate a new ID to retry an unknown result.

### Success — HTTP 200

```json
{
  "success": true,
  "accountNumber": "1012345678",
  "remainingBalance": 10000000
}
```

### Debit response mapping

| Case | HTTP | `detail.code` | `detail.message` | Meaning / commit certainty |
|---|---:|---|---|---|
| Account does not exist | `404` | `ACCOUNT_NOT_FOUND` | `Account not found.` | No debit was started for a new attempt. For a retry, check status if the same ID could already have a record. |
| Insufficient balance | `409` | `INSUFFICIENT_BALANCE` | `Insufficient available balance.` | Conditional update affected no row and rollback succeeded; this request did not commit. If rollback fails, response is `DEBIT_OUTCOME_UNKNOWN`. |
| Inactive account | `409` | `ACCOUNT_INACTIVE` | `Account is inactive.` | No debit was started for this attempt. |
| Same transaction ID and same account/amount, already debited | `200` | Not applicable | Not applicable | Idempotent success; returns the stored debit result without debiting again. The debit with this ID was previously committed. |
| Same transaction ID but different account or amount | `409` | `TRANSACTION_ID_CONFLICT` | `Transaction ID was already used for a different debit.` | A debit ledger record for this ID exists. Do not treat this as “no debit”; reconcile and do not release the tuition claim automatically. |
| MySQL lock timeout `1205` before commit | `503` | `DEBIT_ROLLED_BACK` | `Debit was rolled back successfully.` | Lock timeout occurred before commit and rollback succeeded; this request did not commit. |
| MySQL deadlock `1213` before commit | `503` | `DEBIT_ROLLED_BACK` | `Debit was rolled back successfully.` | Deadlock occurred before commit and rollback succeeded; this request did not commit. |
| Rollback fails | `503` | `DEBIT_OUTCOME_UNKNOWN` | `Debit outcome could not be confirmed.` | User Service could not confirm whether the transaction was rolled back. |
| Commit raises an exception | `503` | `DEBIT_OUTCOME_UNKNOWN` | `Debit outcome could not be confirmed.` | Commit outcome cannot be confirmed, even if a later rollback call returns. |
| Debit succeeds | `200` | Not applicable | Not applicable | Debit and ledger record committed. |
| Invalid request | `422` | FastAPI validation body; no debit `detail.code` | FastAPI validation message | Request was rejected before debit logic, for example invalid amount or transaction ID; no debit was attempted. |

Business errors use the same structure:

```json
{
  "detail": {
    "code": "INSUFFICIENT_BALANCE",
    "message": "Insufficient available balance."
  }
}
```

For example, `ACCOUNT_NOT_FOUND`, `ACCOUNT_INACTIVE`, and `TRANSACTION_ID_CONFLICT` use the same `detail.code` and `detail.message` shape. A matching existing transaction ID returns the normal HTTP 200 success response; a mismatched reuse returns `TRANSACTION_ID_CONFLICT`.

### Confirmed rollback — HTTP 503

```json
{
  "detail": {
    "code": "DEBIT_ROLLED_BACK",
    "message": "Debit was rolled back successfully."
  }
}
```

This code is used for MySQL lock timeout `1205` or deadlock `1213` only when rollback succeeds. It confirms the debit transaction was rolled back by User Service. A Payment client can distinguish it from business rejection and from an unknown commit result using both HTTP status and `detail.code`.

### Unknown transaction outcome — HTTP 503

Returned when commit fails, or rollback cannot be confirmed:

```json
{
  "detail": {
    "code": "DEBIT_OUTCOME_UNKNOWN",
    "message": "Debit outcome could not be confirmed."
  }
}
```

Payment must not mark the payment as definitely failed or release its tuition claim based only on this response. Do not retry automatically.

All debit business `HTTPException` responses above use a structured `detail` object with a stable `code` and a human-readable `message`. FastAPI's request-validation `422` response remains its standard validation format.

## Read a debit status

```http
GET /api/v1/internal/debits/{transaction_id}
X-Internal-API-Key: <shared internal API key>
```

If a committed debit record exists, HTTP `200`:

```json
{
  "transaction_id": "payment-transaction-uuid",
  "status": "DEBITED"
}
```

If no record is visible to the query, HTTP `200`:

```json
{
  "transaction_id": "payment-transaction-uuid",
  "status": "NOT_FOUND"
}
```

The endpoint performs a SELECT only. It does not debit an account, change a balance, or create a record. Database query failures are returned as server errors; they are not converted to `NOT_FOUND`.

### Race and reconciliation limits

The debit row is inserted in the same database transaction as the balance update and is not visible to a separate read until commit. Therefore, a GET that returns `NOT_FOUND` can race with a debit POST that is still running and may commit later. `NOT_FOUND` means only “no committed debit row was visible at the time of this query”; it does not prove a pending request will not commit.

The POST endpoint is idempotent for a committed debit row: repeating the same transaction ID, account, and amount returns the stored debit result without debiting again. However, the POST is not a read-only status check. If the original request did not commit, replaying it may perform the debit. User Service does not automatically retry, poll, or reconcile ambiguous requests.

Payment should retain `RECONCILIATION_REQUIRED` for unknown outcomes. It should use the GET result only as one piece of evidence, and must account for in-flight requests (for example, wait for the original request to be known quiescent and check again) before deciding that a payment can safely fail or be retried. A dedicated reconciliation protocol may be needed for stronger guarantees.

## Payment Service coordination

The Payment integration on `fix/payment-service-integration` parses `detail.code` and applies these policies:

1. `DEBIT_ROLLED_BACK` and known pre-debit business rejections fail the Payment transaction without calling Tuition `/pay`, then attempt to release the claim.
2. `DEBIT_OUTCOME_UNKNOWN`, timeout, malformed response, and unknown codes keep `RECONCILIATION_REQUIRED` and retain the Tuition claim.
3. `TRANSACTION_ID_CONFLICT` is handled separately: Payment records the conflict reason, keeps the reconciliation status and claim, and requires manual review. The debit status endpoint does not expose account/amount, so Payment does not automatically treat the conflicting ledger row as the debit for this tuition.
4. Payment's `POST /api/v1/payments/{transaction_id}/reconcile` uses the GET status endpoint. `DEBITED` may resume tuition completion for non-conflict transactions; `NOT_FOUND` remains under reconciliation and does not trigger a retry or claim release.

The Payment database requires the nullable `reconciliation_code` column. For an existing database, apply `db/payment/payment_reconciliation_code.sql` before deploying the Payment code. The GET status endpoint remains point-in-time evidence: a single `NOT_FOUND` does not prove that an in-flight debit will not commit.
