# Demo data guide

This guide describes fictional data for local demonstrations. The SQL seeds are optional, insert-only scripts. Apply them only after initializing schemas in a fresh, disposable local MySQL environment. Never run them against shared or production databases.

## Demo logins

The four `demo_` users added by `db/user/demo_seed.sql` share this demo-only password:

```text
CampusDemo!2026
```

Their stored hashes use bcrypt cost 12, which matches the User Service `bcrypt.checkpw` verification. The legacy `user01` record is retained with its old hash for compatibility; its password is not specified by this guide.

| Username | Fictional name | Mapped student ID | Demo email |
| --- | --- | --- | --- |
| `demo_minh` | Minh Nguyen | `DEMO24001` | `demo.minh@example.test` |
| `demo_linh` | Linh Tran | `DEMO24002` | `demo.linh@example.test` |
| `demo_khoa` | Khoa Le | `DEMO24003` | `demo.khoa@example.test` |
| `demo_hanh` | Hanh Pham | `DEMO24004` | `demo.hanh@example.test` |

The `.test` email domain is reserved and will not receive public email. To demonstrate OTP and successful confirmation, configure Payment Service to use a local SMTP sink/inbox and ensure it accepts these recipients. The account and tuition lookup flows do not require SMTP.

## Bank accounts

| Owner | Account number | Initial balance | Notes |
| --- | --- | ---: | --- |
| Legacy `user01` | `1012345678` | 15,000,000 | Existing default demo account; mapped to `524H0104` |
| Legacy `user01` | `1012345679` | 5,000,000 | Existing secondary demo account |
| `demo_minh` | `6201000001` | 25,000,000 | Sufficient for its own bill and shared scenario |
| `demo_minh` | `6201000002` | 4,000,000 | Insufficient for its own bill |
| `demo_linh` | `6201000003` | 13,000,000 | Insufficient for its own bill |
| `demo_khoa` | `6201000004` | 8,000,000 | Sufficient for its own bill |
| `demo_hanh` | `6201000005` | 26,000,000 | Sufficient for its own bill and shared scenario |

The service links a payer to bank accounts through `accounts.user_id → users.user_id`. The optional `users.student_id` profile mapping is used by the frontend's “Pay for me” flow. A payer may search for another student's tuition bill without owning that student mapping.

## Tuition bills

The tuition seed retains the six existing fictional records and adds six `DEMO` records. A bill's primary key is `student_id`; no database relationship is created from a User row to a Tuition row because those services own separate databases.

| Student ID | Student | Amount | Initial status | User mapping |
| --- | --- | ---: | --- | --- |
| `524H0012` | Nguyen Minh Anh | 18,500,000 | UNPAID | None |
| `524H0035` | Tran Gia Huy | 16,250,000 | UNPAID | None |
| `524H0078` | Le Hoang Phuc | 19,750,000 | PAID | None |
| `524H0104` | Pham Ngoc Han | 17,300,000 | UNPAID | Legacy `user01` |
| `524H0126` | Vo Minh Khang | 21,000,000 | UNPAID | None |
| `524H0159` | Bui Thanh Truc | 15,800,000 | PAID | None |
| `DEMO24001` | Minh Nguyen | 12,000,000 | UNPAID | `demo_minh` |
| `DEMO24002` | Linh Tran | 18,000,000 | UNPAID | `demo_linh` |
| `DEMO24003` | Khoa Le | 7,500,000 | UNPAID | `demo_khoa` |
| `DEMO24004` | Hanh Pham | 24,000,000 | UNPAID | `demo_hanh` |
| `DEMO24005` | Shared Scenario Student | 15,000,000 | UNPAID | No owner; searched by payers |
| `DEMO24006` | Paid Scenario Student | 11,000,000 | PAID | No owner |

Amounts and balances are fictional VND values. Applying the seed never changes an existing bill's amount, name, or status.

## Scenario walkthroughs

Each scenario starts from the initial seeded state unless stated otherwise. Successful payment, OTP, debit-ledger, and history records are created only by runtime API actions.

1. **Profile-linked payment:** Log in as `demo_minh`, use “Pay for me,” and select account `6201000001`. The profile maps to `DEMO24001`; the 25,000,000 balance covers its 12,000,000 bill. Expected: a PENDING payment and OTP request; after OTP confirmation, the balance becomes 13,000,000, tuition becomes PAID, and Payment history contains SUCCESS.
2. **Low-balance account choice:** As `demo_minh`, select secondary account `6201000002` for `DEMO24001`. Expected: payment creation rejects insufficient balance; no debit occurs.
3. **Insufficient own bill:** Log in as `demo_linh` and use “Pay for me.” Its 13,000,000 account cannot cover `DEMO24002` at 18,000,000. Expected: insufficient-balance rejection and no debit.
4. **Successful smaller bill:** Log in as `demo_khoa` and pay `DEMO24003` for 7,500,000 from `6201000004`. Expected after runtime OTP confirmation: SUCCESS and a 500,000 remaining balance.
5. **Other-payer success:** Log in as `demo_hanh`, search for `DEMO24002`, and pay Linh's 18,000,000 bill from `6201000005`. Expected after runtime OTP confirmation: SUCCESS and an 8,000,000 remaining balance. The mapping does not restrict search-and-pay to the payer's own student ID.
6. **Already-paid rejection:** Search for `DEMO24006` or `524H0078`. Expected: Payment Service rejects the bill before debit; no payment confirmation is needed.
7. **Two payers competing for one bill:** From a fresh seeded state, create a payment for `DEMO24005` as `demo_minh` and another as `demo_hanh`, request both OTPs, then confirm both close together. Both accounts initially cover the bill. Expected: Tuition's claim permits at most one payment to proceed; at most one debit/payment succeeds. This is a runtime concurrency demonstration, not guaranteed by loading seed data alone.
8. **Existing-payment history:** Complete any one successful scenario above, then open transaction history for that payer. Expected: the runtime-created SUCCESS transaction appears with its student, account, and amount.
9. **Wrong or reused OTP:** Create a pending payment and request an OTP through the configured local SMTP sink. Submit an incorrect code, then try the valid code and try reusing it after success. Expected: invalid/reused codes are rejected and a consumed OTP cannot authorize another payment.
10. **Legacy record compatibility:** Log in to `user01` only if its local demo password is already known. The seed preserves legacy account/student records without changing their balances; the documented shared password is for `demo_` users only.

Paid bills and balances change during successful runtime demos. Use a fresh disposable setup when replaying scenarios that depend on the initial UNPAID status or balance. The seed deliberately does not reset them.

## Safe local setup

1. Create a fresh, disposable local MySQL environment and the service-owned databases `account_db`, `ibanking_tuition`, and `payment_db`.
2. Initialize each schema using the existing service setup scripts. Do not point the service URLs at a shared/current application database.
3. Run `db/user/demo_seed.sql` while `account_db` is selected and `db/tuition/demo_seed.sql` while `ibanking_tuition` is selected. Do not execute either seed against a database containing non-demo data.
4. Configure local service `.env` files with the matching database names, a shared test JWT secret/internal API key, and a local SMTP sink if demonstrating OTP.
5. Start User and Tuition Services before Payment Service, then use the scenario walkthroughs above.

Seeds are sequentially repeatable: they insert only absent usernames, account numbers, or student IDs. They never update an existing row and do not insert Payment transactions, OTPs, or debit-ledger rows. If a reserved demo identifier already exists with unexpected data, inspect it manually rather than deleting or overwriting it.
