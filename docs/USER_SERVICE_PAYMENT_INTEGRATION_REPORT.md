# Payment ↔ User Service Integration Handoff

## Current status

Payment consumes the User Service API contract documented in [`USER_SERVICE_PAYMENT_API_CONTRACT.md`](./USER_SERVICE_PAYMENT_API_CONTRACT.md).

Payment branch: `fix/payment-service-integration`

Latest Payment commits:

- `b523910` — reconciliation endpoint and initial behavior
- `ccced86` — User debit contract integration
- `55ce6a9` — consolidate Payment schema SQL

## What Payment now handles

| User Service result | Payment behavior |
|---|---|
| Debit HTTP 200 | Continue to Tuition `/pay`, then finalize Payment as `SUCCESS`. |
| `DEBIT_ROLLED_BACK` | Do not call Tuition `/pay`; mark Payment `FAILED` and attempt to release this transaction's Tuition claim. |
| `ACCOUNT_NOT_FOUND`, `ACCOUNT_INACTIVE`, `INSUFFICIENT_BALANCE` | Treat as a confirmed pre-debit rejection; mark `FAILED`, then attempt to release the claim. |
| `DEBIT_OUTCOME_UNKNOWN`, timeout, malformed response, unknown code | Mark `RECONCILIATION_REQUIRED`; retain the claim; do not retry debit. |
| `TRANSACTION_ID_CONFLICT` | Set `reconciliation_code=TRANSACTION_ID_CONFLICT`; retain the claim; do not auto-finalize, fail, release, or replay. Requires manual review. |

Payment adds the authenticated endpoint:

```http
POST /api/v1/payments/{transaction_id}/reconcile
```

It calls User Service's read-only `GET /api/v1/internal/debits/{transaction_id}`:

- `DEBITED`: for ordinary reconciliation cases, continue tuition completion without calling debit again.
- `NOT_FOUND`: keep `RECONCILIATION_REQUIRED` and the Tuition claim. This is only a point-in-time observation and is not proof that the original debit request cannot still commit.
- `TRANSACTION_ID_CONFLICT`: automatic reconciliation is blocked; Payment asks for manual review.

The tuition page exposes a “Check debit status” action for reconcilable transactions and explicitly tells users not to retry manual-review conflicts.

## What User Service should consider next

No User Service change is required for Payment to consume the current contract safely. The following additions would enable stronger automated recovery:

1. **Return debit identity fields in the read-only status response.** For `DEBITED`, include at least `account_number` and `amount` (and optionally `balance_after`). Payment can compare those values to its stored source account and amount before completing Tuition. Today the endpoint returns only the transaction ID and `DEBITED`, so Payment cannot independently verify a `TRANSACTION_ID_CONFLICT`; it deliberately leaves that case for manual review.
2. **Define how to establish that a debit attempt is no longer in flight.** `NOT_FOUND` can race an uncommitted POST. If automatic recovery from `NOT_FOUND` is needed, agree on a durable attempt state/protocol (for example `IN_PROGRESS`, `DEBITED`, and a terminal confirmed-no-debit result) with crash recovery semantics. Do not make a single `NOT_FOUND` mean safe-to-retry.
3. If User Service adopts either response enhancement, update the API contract and tests together, then Payment can consume the revised contract on its branch.

## Payment database

Payment continues to own a separate `ibanking_payment_db`; only its SQL initialization/migration files were consolidated. The canonical schema is [`db/payment/payment_init.sql`](../db/payment/payment_init.sql), mounted by Docker for both fresh initialization and reviewed schema upgrades.

For an existing Payment database, back it up and run that canonical script against the intended database before deploying this Payment version. It adds missing nullable fields and checks required data / orphan OTP rows before tightening constraints. Stop and investigate if its preflight signals an error; do not bypass the guard.

## Validation

- Safe Payment Service tests: **90 passed**. The two demo/real-database integration tests were excluded.
- Python compile check, `node --check frontend/js/tuition.js`, `git diff --check`, and Docker Compose configuration validation with test-only required variables passed.
- User Service MySQL lock/deadlock behavior and Payment's live cross-service flow have not been tested against an isolated MySQL environment.

## Handoff note

The Payment branch has not been pushed from this environment because GitHub authentication was unavailable. The commits above are present locally; after authentication, push with:

```bash
git push origin fix/payment-service-integration
```

The requested User Service follow-up is to review items 1–2 above and decide whether to extend the status contract. No one should use the debit POST as a status-only smoke test against demo accounts.
