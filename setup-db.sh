#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
PROJECT="${1:-ibanking-demo}"

mysql_exec() {
  docker compose --env-file .env.docker -p "$PROJECT" exec -T mysql \
    sh -c 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql -uroot --batch --skip-column-names'
}

mysql_query() {
  printf '%s\n' "$1" | mysql_exec
}

database_count="$(mysql_query "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('ibanking_account_db', 'ibanking_tuition_db', 'ibanking_payment_db');")"
[[ "$database_count" == 3 ]] || {
  printf 'Expected all three iBanking databases. Existing volumes are not initialized again; preserve data and follow the migration guide before retrying.\n' >&2
  exit 1
}

mysql_query "
CREATE TABLE IF NOT EXISTS ibanking_account_db.schema_migrations (
    version VARCHAR(100) PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ibanking_tuition_db.schema_migrations (
    version VARCHAR(100) PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ibanking_payment_db.schema_migrations (
    version VARCHAR(100) PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);" >/dev/null

while IFS='|' read -r database version file; do
  [[ -n "$database" ]] || continue
  applied="$(mysql_query "SELECT COUNT(*) FROM ${database}.schema_migrations WHERE version='${version}';")"
  if [[ "$applied" == 0 ]]; then
    mysql_exec < "$ROOT_DIR/$file"
    mysql_query "INSERT INTO ${database}.schema_migrations (version) VALUES ('${version}');" >/dev/null
    printf 'Applied schema migration %s\n' "$version"
  fi
done <<'MIGRATIONS'
ibanking_account_db|001-user-student-id|db/user/add_user_student_id.sql
ibanking_account_db|002-account-debits|db/user/add_account_debits.sql
ibanking_tuition_db|001-tuition-payment-claims|db/tuition/tuition_payment_claims.sql
ibanking_payment_db|001-payment-integrity|db/payment/payment_init.sql
MIGRATIONS

mysql_exec < "$ROOT_DIR/db/docker-init/05-user-demo-seed.sql"
mysql_exec < "$ROOT_DIR/db/docker-init/06-tuition-demo-seed.sql"

table_count="$(mysql_query "SELECT COUNT(*) FROM information_schema.tables WHERE (table_schema='ibanking_account_db' AND table_name IN ('users','accounts','account_debits')) OR (table_schema='ibanking_tuition_db' AND table_name IN ('tuition_bills','tuition_payment_claims')) OR (table_schema='ibanking_payment_db' AND table_name IN ('transactions','otps'));")"
[[ "$table_count" == 7 ]] || { printf 'Schema verification failed: required service tables are missing.\n' >&2; exit 1; }

column_count="$(mysql_query "SELECT COUNT(*) FROM information_schema.columns WHERE (table_schema='ibanking_account_db' AND table_name='users' AND column_name='student_id') OR (table_schema='ibanking_account_db' AND table_name='account_debits' AND column_name='transaction_id') OR (table_schema='ibanking_tuition_db' AND table_name='tuition_payment_claims' AND column_name='transaction_id') OR (table_schema='ibanking_payment_db' AND table_name='transactions' AND column_name IN ('student_name','reconciliation_code')) OR (table_schema='ibanking_payment_db' AND table_name='otps' AND column_name='otp_code');")"
[[ "$column_count" == 6 ]] || { printf 'Schema verification failed: required service columns are missing.\n' >&2; exit 1; }

printf 'Schema checks, guarded migrations, and idempotent demo seeds completed.\n'
