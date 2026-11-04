# Existing database migration plan

Setup never renames, drops, imports into, or modifies an existing database or Docker volume. MySQL's initialization files run only for an empty data directory. Keep the old databases until the application has been verified against the new names.

| Existing database | New database |
| --- | --- |
| `account_db` | `ibanking_account_db` |
| `ibanking_tuition` | `ibanking_tuition_db` |
| `payment_db` | `ibanking_payment_db` |

## Before migration

1. Schedule downtime and stop only the iBanking Compose project with `stop.sh` or `stop.bat`.
2. Confirm the MySQL server and the three source databases are the intended targets. Never run these commands against a shared or production server without its approved change process.
3. Make a tested, access-controlled backup of all three databases. Store it outside the repository and do not paste credentials into shell history or commit the backup.
4. Review schema differences and the forward-only SQL under `db/user`, `db/tuition`, and `db/payment`. Init scripts and demo seed scripts are not migrations for populated databases.
5. Before deploying Payment Service changes to an existing Payment database, back it up and run the canonical, guarded schema script [`payment_init.sql`](../db/payment/payment_init.sql) against the intended `ibanking_payment_db`. It creates missing tables, adds missing nullable Payment fields, and checks existing required values before applying constraints. Inspect and resolve any preflight error instead of bypassing it. Fresh Docker databases use this same file.

The Compose setup runners verify migration structure before recording a version in each database's `schema_migrations` table. They check the relevant columns, keys, indexes, foreign keys, and checks. The PowerShell runner's `-ValidateOnly` mode is read-only and can be used to inspect an existing Compose database before a reset; it does not create migration tables or apply SQL:

```powershell
powershell.exe -NoProfile -File .\setup-db.ps1 -ComposeProject ibanking-demo -ValidateOnly
```

Normal setup mode applies migrations and seed scripts and is not a read-only inspection. Do not use it to bypass a failed validation or without the required backup and approval.

## Migration approach

For a separately approved migration, create the three new schemas on the intended MySQL server, then copy each source database's schema and rows into its corresponding new name. Use a reviewed migration tool or a controlled `mysqldump`/restore process with credentials supplied securely. Apply only the forward migrations that match the source schema, and verify primary keys, foreign keys, indexes, checks, row counts, balances, tuition statuses, debit ledger rows, payment statuses, and OTP references.

Update the application's `DATABASE_URL` values to the new names only after the copies have been checked. Start the services and verify login, account lookup, tuition lookup, payment history, and a deliberately selected test payment before reopening normal use. Retain the old databases and backup until the owner approves their later archival or removal.

Local ignored service `.env` files are preserved by setup and are not part of a public clone. If you run services directly from the repository instead of Compose, update their database names only after completing this migration. The Docker Compose demo already points to the new database names.

This repository intentionally does not provide a one-command copy script: the correct source server, schema version, ownership, and data-retention approval must be confirmed for each existing installation. No migration has been run as part of project setup.
