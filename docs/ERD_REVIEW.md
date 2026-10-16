# iBanking ERD and Database Review

## Scope and method

This is a source-level review of the seven listed tables, their SQL initialization/migrations, ORM or raw SQL access, and payment workflow. No code or schema was changed. The repository has no editable source for the existing ERD raster; `docs/diagrams/erd.puml` is the repository's proposed replacement from the preceding diagram task and is used as the “Current ERD” comparison where applicable. The root-level `erd_ibanking.png` is not an auditable relational model source.

The installed SQL is authoritative for physical constraints. Application checks and mocked SQLite tests are separately identified; they do not imply MySQL production constraints.

## Decision table

| Component | Current Code/SQL | Current ERD | Real-world Assessment | Decision | Priority | Required Changes |
| --- | --- | --- | --- | --- | --- | --- |
| `users` identity and student mapping | `user_id` PK; unique non-null username; password/name/phone/email NOT NULL; `student_id` nullable UNIQUE (`db/user/init.sql:4-13`, migration `db/user/add_user_student_id.sql:3-5`, model `backend/user_service/models/user.py:14-39`) | Correctly shows optional unique `student_id` | A bank payer need not be a student. Nullable user student ID is appropriate for “pay for self”; other-student payments use entered Tuition student ID (`frontend/js/tuition.js:80-106`). `student_id` is a logical cross-service link, not a physical FK. | KEEP | LOW | Keep optional mapping, label dashed logical association to Tuition bill. No schema change. |
| `accounts.user_id → users.user_id` | NOT NULL physical FK (`db/user/init.sql:15-23`, `backend/user_service/models/account.py:25-41`) | Solid FK shown | Correct ownership relation; payment code validates account belongs to authenticated payer (`backend/payment_service/services/paymentService.py:132-164,357-365`). | KEEP | LOW | No change. |
| `account_debits.account_number → accounts.account_number` | NOT NULL physical FK, account index, amount/balance CHECK (`db/user/init.sql:25-35`; model `backend/user_service/models/account.py:43-65`) | Solid FK shown | Correct account-local debit ledger. The row stores the account, amount, resulting balance and transaction idempotency key. | KEEP | LOW | No change. |
| `account_debits.transaction_id → transactions.transaction_id` | User DB PK `VARCHAR(100)`; no FK. Payment passes its UUID transaction ID to User debit API (`backend/user_service/services/paymentService.py:419-435`); duplicate key returns original debit (`backend/user_service/services/account_service.py:24-45`). | Dashed logical/idempotency reference shown | Correct cross-database association; physical FK would couple independently-owned service DBs. Primary key enforces one debit per ID within User DB, and retry checks same account and amount. | KEEP | LOW | Keep dashed, explicitly label idempotency key; optionally align to `VARCHAR(36)` after validating all stored IDs and API contract. No FK. |
| Tuition bills | `student_id` PK; student name/amount/status NOT NULL; amount/status CHECK; `updated_at` has default/update behavior (`db/tuition/tuition.sql:7-20`) | Correct table/columns and checks represented | A single current bill per student is what this schema supports. Current system cannot model multiple terms/invoices for one student; whether that is required is not established by repository evidence. | KEEP | LOW | No change for evidenced one-bill-per-student scope. If multiple invoices/terms are a confirmed requirement, new invoice key and migration would be a separate scope decision. |
| `tuition_payment_claims.student_id → tuition_bills.student_id` | PK and NOT NULL physical FK; `transaction_id` NOT NULL UNIQUE (`db/tuition/tuition.sql:22-28`) | Solid physical FK shown | One claim per bill and one bill per transaction; atomic `INSERT IGNORE ... SELECT ... status='UNPAID'` prevents concurrent claim for same bill (`backend/tuition_service/services/tuition_service.py:173-205`). Appropriate as an in-progress lock. | KEEP | LOW | No structural change. Claim recovery after process crash is a lifecycle concern: add explicit expiry/cleanup only if operationally needed; current row has no lease expiry. |
| `tuition_payment_claims.transaction_id → transactions.transaction_id` | NOT NULL UNIQUE, no FK; transaction ID is passed by Payment; database is separate (`db/tuition/tuition.sql:22-28`, `backend/payment_service/services/paymentService.py:367-380`) | Dashed logical reference shown | Correct cross-service reference; unique constraint prevents a transaction claiming multiple bills in Tuition DB. Retain no physical FK. | KEEP | LOW | No change; retain dashed reference. |
| `transactions.payer_user_id → users.user_id` | Nullable BIGINT, no FK (`db/payment/payment_init.sql:6-16`). Runtime create path supplies JWT subject (`backend/payment_service/controllers/paymentController.py:75-89`, `backend/payment_service/models/transactionModel.py:8-39`) and history scopes by payer ID (`.../transactionModel.py:172-205`). | Dashed logical ref shown | Payer identity is essential transaction audit/history data. In the normal workflow it is available, so NULL is inconsistent and can create unowned history rows if another writer bypasses the controller. Cross-service FK is not appropriate. | FIX CODE / DATABASE | HIGH | Make required transaction facts NOT NULL (at least payer, source account, student ID, amount, status, created_at) after preflight for legacy NULLs; application already supplies these on creation. Migration required; cross-DB reference remains logical. Tests: reject missing fields and verify history ownership. |
| `transactions.source_account_number → accounts.account_number` | Nullable VARCHAR(20), no FK; create path verifies account exists/owned and passes it to transaction insert (`backend/payment_service/services/paymentService.py:132-164,219-230`) | Dashed logical ref shown | Needed to identify funding source and reconcile debits; NULL is not valid for this payment flow. Do not add cross-DB FK. | FIX CODE / DATABASE | HIGH | Require NOT NULL after checking historical NULL rows. Add app invariant/tests that every new payment persists chosen validated account. Keep logical dashed edge. |
| `transactions.student_id → tuition_bills.student_id` | Nullable VARCHAR(20), no FK; lookup validates bill and stores student ID (`backend/payment_service/services/paymentService.py:166-230`) | Dashed logical ref shown | Identifies beneficiary; essential for business audit. It need not equal payer's optional user student ID. NULL is invalid for the supported tuition payment flow. | FIX CODE / DATABASE | HIGH | Require NOT NULL after data preflight; keep logical dashed edge. No cross-DB FK. |
| `transactions.student_name` snapshot | Nullable VARCHAR(255); fetched from Tuition and required by application before creation (`db/payment/payment_add_student_name.sql:3-4`, `backend/payment_service/services/paymentService.py:205-230`) | Nullable field shown | Snapshot preserves the name seen at payment time if upstream student data changes. NOT NULL is a possible data-quality improvement but current code explicitly rejects missing name before insert. | FIX CODE / DATABASE (optional tightening) | MEDIUM | Consider NOT NULL after confirming no legacy nulls; low functional risk after validation. Not required to establish payer/beneficiary identity because student ID is the stable identifier. |
| `transactions.amount` | Nullable DECIMAL(15,2); assigned from current tuition bill during create and revalidated at confirmation (`db/payment/payment_init.sql:12`, `backend/payment_service/services/paymentService.py:194-230,300-307`); `TransactionModel.complete` writes amount on success (`backend/payment_service/models/transactionModel.py:172-196`) | Nullable field shown | Current implementation intentionally creates pending transaction with amount NULL, then sets final amount on success. Do not simply add NOT NULL without changing transaction lifecycle or persisting amount at creation. The revalidation means successful amount is the amount paid at confirm time, while original quote is not snapshotted. | KEEP for now; optional FIX CODE / DATABASE | MEDIUM | Safer design: persist validated quoted amount at create (and define policy if tuition amount changes before confirm), then require NOT NULL and CHECK amount > 0. Requires migration plus behavior decision and tests. Minimal safe route is keep nullable until lifecycle is revised; ERD should explain nullable pending amount. |
| `transactions.status` | Nullable VARCHAR(32); status migration explicitly modifies column to NULL (`db/payment/payment_reconciliation_status.sql:3-4`); code uses PENDING, PROCESSING, SUCCESS, FAILED, RECONCILIATION_REQUIRED (`backend/payment_service/models/transactionModel.py:40-170`) | Nullable status shown; state values not constrained | A transaction without status is not operationally interpretable. App writes PENDING at creation, and all code paths use a finite known set. NULL and arbitrary values weaken reconciliation and reporting. | FIX CODE / DATABASE | HIGH | Preflight/fix legacy NULL or unknown status; make NOT NULL with DEFAULT only if creation semantics permit; add CHECK or reference/enum strategy for allowed statuses (ensure deployed MySQL version enforces CHECK). Migration required. Test invalid status rejection and state transition paths. |
| `transactions.created_at` / `completed_at` | created_at nullable with default; completed_at nullable (`db/payment/payment_init.sql:14-15`). Code inserts created_at and sets completed_at on terminal state (`backend/payment_service/models/transactionModel.py:8-39,40-170`). | Nullable created_at and completed_at shown | Every transaction needs creation timestamp; completed_at is correctly nullable while pending/processing/reconciliation. | FIX CODE / DATABASE | MEDIUM | `created_at NOT NULL DEFAULT CURRENT_TIMESTAMP`; retain nullable `completed_at`. Backfill null creation dates using a defensible migration timestamp only after backup/review. Add history ordering test. |
| `otps.transaction_id → transactions.transaction_id` | Nullable `VARCHAR(36)`, no FK; code always inserts transaction ID and verifies by both transaction ID and code (`db/payment/payment_init.sql:19-25`, `backend/payment_service/models/otpModel.py:18-81`) | ERD currently marks dashed logical association | Logical ownership is right, but unlike service-to-service links, both tables are in the same Payment DB. A physical FK is technically safe and would prevent orphan OTPs; deletion behavior must be chosen (no transaction deletes observed). The user's list calls this physical FK, but current SQL does not declare one. | FIX CODE / DATABASE (recommended) | MEDIUM | Add FK `otps.transaction_id → transactions.transaction_id`, make transaction_id NOT NULL, and add index if not provided by FK implementation. Preflight orphan/null rows. Migration required. Retain OTP records as history; avoid cascade delete unless retention policy explicitly allows it. |
| `otps.otp_code`, `expires_at`, `is_used` | All nullable in SQL; `is_used` default FALSE. App creates with transaction/code/expiry and checks code, transaction, unused, and expiry (`backend/payment_service/models/otpModel.py:18-81`). | Nullable attributes represented | The runtime invariant is stronger than DDL. NULL expiry/code cannot authenticate, but NULL `is_used` creates three-valued SQL behavior and an incomplete row is possible from other writers. OTP must be bound to transaction, expire, and be single-use. | FIX CODE / DATABASE | HIGH | Make transaction_id, otp_code, expires_at, is_used NOT NULL; retain default false for is_used. Enforce code/expiry validation in service; add DB CHECK for expiry not a past-relative constraint (not portable/meaningful), code format if supported. Tests for wrong transaction, expiry, replay, parallel confirmation. |
| OTP one-time consumption ordering | `OtpModel.verify` SELECTs valid code, then `mark_as_used` separately commits after Tuition claim (`backend/payment_service/services/paymentService.py:249-259,407-417`; OTP SQL in `backend/payment_service/models/otpModel.py:69-91`) | ERD only models association, no behavioral detail | Atomic transaction claim prevents two payment confirmations from proceeding concurrently for one transaction. However verify and consume are separate DB operations; transaction status guard prevents repeat debit after status changes, and OTP is marked used before debit. A crash after consuming OTP/claim but before debit can strand the transaction and require support/manual recovery. | KEEP current protections; optional FIX CODE | MEDIUM | Prefer atomic consume (`UPDATE ... WHERE transaction_id=? AND otp_code=? AND is_used=FALSE AND expires_at>CURRENT_TIMESTAMP`) checking exactly one affected row, ideally coordinated with `PROCESSING` claim. Add fault-injection and concurrent replay tests. This is code hardening, not an ERD edge change. |
| No duplicate debit for one transaction | `account_debits.transaction_id` is PK; debit records insert before atomic guarded balance update; duplicate same payload returns prior balance, conflicting payload rejects (`backend/user_service/services/account_service.py:24-105`) | ERD shows debit row keyed by logical transaction id | Strong per-transaction idempotency and no-overdraft condition. The operation commits debit record and balance in same account DB transaction. | KEEP | LOW | Keep. Preserve DB-backed idempotency; add/retain MySQL concurrency test because SQLite/mock alone is not production-engine proof. |
| No successful double payment for one tuition bill | `tuition_payment_claims.student_id` PK; claim insert only for UNPAID; `mark_tuition_as_paid` updates only UNPAID and returns conflict if already paid (`backend/tuition_service/services/tuition_service.py:95-152,173-205`) | ERD shows one claim per bill and FK to bill | Prevents two concurrent claims and second successful status update, subject to preserving claim through the flow. It is an in-progress lock, not a durable payment ledger. | KEEP with recovery caveat | MEDIUM | No schema change required for double-success prevention. Add expiry/lease or reconciliation cleanup for claims left after process death only if operational recovery is desired; test timeout/crash recovery if implemented. |
| Cross-service partial failure after debit | Debit timeout is marked `RECONCILIATION_REQUIRED`; Tuition update failure after debit also marked reconciliation (`backend/payment_service/services/paymentService.py:429-499`). README states there is no automatic refund (`README.md:180`). | ERD shows status and cross-service refs but not recovery guarantee | Failures are detected and retained, avoiding false SUCCESS, but do not automatically finish Tuition update or refund. The bank debit can exist while tuition remains UNPAID; this is a material manual-reconciliation state. No schema alone solves distributed atomicity. | KEEP current conservative behavior; optional FIX CODE / operations | HIGH | Do not mark failed or retry debit blindly. Define reconciliation operation/runbook using account debit ledger and tuition claim/status. Optional durable outbox/saga/retry is a larger architecture change and needs idempotent Tuition finalize and explicit policy. Test lost responses at each boundary. |
| `account_debits` relationship to transactions in ERD | PK value is Payment transaction ID but SQL has no cross-DB FK | Dashed logical reference | Correct and deliberate for service DB isolation. Account DB still guarantees one debit per transaction ID locally. | KEEP | LOW | No cross-database FK. ERD label should state logical idempotency reference, not FK. |
| Relationship `users.student_id → tuition_bills.student_id` | Nullable unique mapping in Account DB; no FK; UI uses mapping for own payment; manual entry supports others (`frontend/js/tuition.js:80-106,184-216`) | Dashed logical reference | Correct optional convenience mapping. Do not infer payer=beneficiary. | KEEP | LOW | Retain optional/dashed; no schema change. |

## 1. Correct ERD elements

- Physical FKs `accounts.user_id → users.user_id`, `account_debits.account_number → accounts.account_number`, and `tuition_payment_claims.student_id → tuition_bills.student_id` match the SQL and ownership boundaries.
- Cross-database references from Payment to User/Tuition and Tuition claim to Payment transaction are logical references. They must remain dashed and must not become cross-database FKs.
- `account_debits.transaction_id` is correctly modeled as a logical idempotency association, not an FK. Its primary key is the actual duplicate-debit control.
- Optional `users.student_id` is correct because a bank user may not be a student. It must not be treated as the transaction beneficiary identity.
- Tuition claim table's PK on student ID and unique transaction ID correctly permits one active claim per bill and one claimed bill per transaction.
- `completed_at` and `tuition_payment_claims` are appropriately nullable/short-lived in meaning: completed time is absent for open transactions; a claim is removed when bill is marked paid.

## 2. ERD changes recommended

1. Correct the relationship notation for `otps.transaction_id`: current SQL has no FK, so current ERD's dashed logical line is factually accurate. The recommended database hardening below would change it to a solid physical FK within Payment DB.
2. Mark `transactions` pending `amount` as nullable-by-lifecycle in the ERD; current create flow inserts a PENDING transaction before final amount is stored at completion.
3. Annotate `account_debits.transaction_id` as “logical idempotency key; primary key in Account DB” and annotate claims as an in-progress lock, not a permanent payment record.
4. Show `transactions` required business identity fields as intended NOT NULL only after the migration is approved/applied. Until then the ERD must report actual nullable SQL as current.
5. Do not add speculative term/invoice tables or student/account entities not evidenced in the present system.

## 3. Code/database changes recommended

### Required integrity hardening

- `payment_db.transactions`: make `payer_user_id`, `source_account_number`, `student_id`, `status`, and `created_at` NOT NULL after handling legacy rows. Consider `amount` separately because it is intentionally NULL during pending creation. Add an allowed-status CHECK/constraint after auditing existing values and supported MySQL version.
- `payment_db.otps`: make transaction_id, otp_code, expires_at, is_used NOT NULL; add same-database FK to transactions. Preserve OTP history; do not cascade delete without retention approval.
- Evaluate `transactions.student_name NOT NULL` as a lower-priority consistency constraint. Application currently validates name before transaction creation, but old rows may lack it.
- Database-side checks for positive transaction amount should accompany a lifecycle change that persists amount at create. User debit schema already checks positive amount and balance.

### Required payment-process safety follow-up

- Add operational recovery for `RECONCILIATION_REQUIRED` and expired tuition claims. Existing code records uncertainty but README explicitly says there is no automatic refund. Do not add a blind retry/refund without reconciling `account_debits` and Tuition state.
- Make OTP consumption a single conditional update, and test process interruption after claim/OTP consumption. Current separate verify and consume operations are guarded by Payment transaction status, but may leave a transaction requiring manual recovery.
- Keep current atomic per-account debit and Tuition claim/paid guards; these are stronger and safer than relying on ERD relationships alone.

## 4. Mandatory vs optional

**Mandatory before treating database as robust against malformed direct writes:** tighten transaction identity/status/timestamp nullability; tighten OTP nullability and add its same-database FK; preflight and migrate data safely; add SQL constraint tests against MySQL.

**Optional, behavior-affecting improvement:** persist the tuition quote amount at creation and make it NOT NULL. This requires choosing whether confirmation pays the originally quoted amount or refreshes the current tuition bill amount. Today confirmation uses the current amount, so this must be a product/business decision before changing behavior.

**Optional operations hardening:** claim lease/expiry and automated reconciliation/outbox. These add lifecycle states and operational ownership; avoid them unless the system is expected to recover unattended from process death or service outages.

## 5. Files to change if implementation fixes are approved

No files changed in this audit. For the recommended integrity changes:

- SQL canonical schema: `db/payment/payment_init.sql`.
- New forward-only migrations: add one for `transactions` nullability/status constraints and one for OTP nullability/FK (or combine with clearly separated, reversible preflight/alter sections).
- Payment insertion/transition logic if amount lifecycle is revised: `backend/payment_service/models/transactionModel.py`, `backend/payment_service/services/paymentService.py`.
- OTP persistence/consume: `backend/payment_service/models/otpModel.py`; orchestration `backend/payment_service/services/paymentService.py`.
- Tuition claim recovery only if approved: `db/tuition/tuition.sql`, a migration, `backend/tuition_service/services/tuition_service.py`, plus authenticated internal route in `backend/tuition_service/controllers/tuition_controller.py`.
- Tests: `tests/payment_service/test_payment_creation.py`, `test_payment_otp.py`, `test_payment_confirmation.py`, `test_payment_database_concurrency.py`, `test_payment_concurrency.py`, and isolated MySQL/E2E coverage in `tests/e2e/test_real_http_e2e.py`.
- Update `docs/diagrams/erd.puml` and the audit/report docs after schema decisions are implemented; never depict proposed constraints as current before migration.

## 6. Migration and test plan

1. Back up target DBs; query counts for NULL transaction payer/account/student/status/created_at/amount/name and OTP transaction/code/expiry/is_used; query unknown status values, orphan OTPs, duplicate/invalid amounts, and existing FK metadata.
2. Do not guess missing payer, beneficiary, amount, or timestamps. Resolve each malformed historical row from authoritative payment/debit/tuition evidence or leave migration blocked for manual review. For missing `is_used`, only default false where provenance confirms the OTP is valid; otherwise invalidate it.
3. Add forward-only migration after preflight: clean/resolve rows, alter transaction columns, add status/positive amount constraints as approved, alter OTP columns, create OTP FK/index. Validate migration on a disposable copy and on the production MySQL major version.
4. Test database rejects NULL required fields, invalid statuses/amounts, and orphan OTP references. Test normal create → OTP → confirm; wrong transaction/code, expiry, resend, replay and concurrent confirmations; duplicate debit retry and conflicting replay; concurrent tuition claim and second paid attempt; lost debit response and Tuition failure after debit; reconciliation does not claim SUCCESS or cause a second debit.
5. Keep unit tests with mocks, but use isolated MySQL integration tests for actual DDL/FK/check/concurrency guarantees. Never point destructive migration or E2E tests at demo/production data.

## 7. Proposed final ERD

Target model after the recommended integrity migration (not current deployed SQL until applied):

```text
ACCOUNT DB
users(user_id PK, username UQ NOT NULL, ..., student_id NULL UQ)
  1 ───< accounts(account_number PK, user_id FK NOT NULL, balance NOT NULL CHECK >= 0, ...)
accounts 1 ───< account_debits(transaction_id PK, account_number FK NOT NULL,
                               amount NOT NULL CHECK > 0, balance_after NOT NULL, ...)

TUITION DB
tuition_bills(student_id PK, student_name NOT NULL, amount NOT NULL CHECK > 0,
              status NOT NULL CHECK in UNPAID/PAID, ...)
tuition_bills 1 ─── 0..1 tuition_payment_claims(student_id PK/FK,
                    transaction_id UQ NOT NULL, claimed_at NOT NULL)

PAYMENT DB
transactions(transaction_id PK, payer_user_id NOT NULL, source_account_number NOT NULL,
              student_id NOT NULL, student_name, amount NULL while PENDING under current lifecycle,
              status NOT NULL, created_at NOT NULL, completed_at NULL)
transactions 1 ───< otps(otp_id PK, transaction_id FK NOT NULL, otp_code NOT NULL,
                          expires_at NOT NULL, is_used NOT NULL DEFAULT FALSE)

Dashed logical references across databases:
transactions.payer_user_id      ..> ACCOUNT.users.user_id
transactions.source_account_number ..> ACCOUNT.accounts.account_number
transactions.student_id         ..> TUITION.tuition_bills.student_id
TUITION.claims.transaction_id    ..> PAYMENT.transactions.transaction_id
ACCOUNT.account_debits.transaction_id ..> PAYMENT.transactions.transaction_id (idempotency key)
ACCOUNT.users.student_id        ..> TUITION.tuition_bills.student_id (optional self-payment mapping)
```

`otps.transaction_id` becomes a solid FK only after the same-database FK migration. All cross-database associations remain logical. If quoted amount is made immutable at transaction creation, target ERD should change `transactions.amount` to NOT NULL and code must stop overwriting the quote at confirmation.

## Final recommendation

Choose **B for the current ERD's existing relationships**, and **A for several database integrity gaps**. Keep the distributed logical references and current per-account debit / per-bill claim protections. Do not add cross-database FKs. Before changing nullability, run the data preflight because SQL currently permits incomplete transaction and OTP rows. The OTP FK and required-field constraints improve integrity with modest scope; changing amount timing or adding an automated saga is a separate, more behavior-sensitive decision. This sequence keeps existing successful flows intact while making schema guarantees match the normal payment lifecycle.
