#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
PROJECT="${1:-ibanking-demo}"

mysql_exec() {
  docker compose --env-file "$ROOT_DIR/.env.docker" \
    --file "$ROOT_DIR/docker-compose.yml" \
    --project-directory "$ROOT_DIR" --project-name "$PROJECT" exec -T mysql \
    sh -c 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql --protocol=socket -uroot --batch --raw --skip-column-names'
}

mysql_query() {
  printf '%s\n' "$1" | mysql_exec
}

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

database_count="$(mysql_query "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('ibanking_account_db','ibanking_tuition_db','ibanking_payment_db');")"
[[ "$database_count" == 3 ]] || fail "Expected all three iBanking databases in Compose project $PROJECT."

service_table_count="$(mysql_query "SELECT COUNT(*) FROM information_schema.tables WHERE (table_schema='ibanking_account_db' AND table_name IN ('users','accounts','account_debits')) OR (table_schema='ibanking_tuition_db' AND table_name IN ('tuition_bills','tuition_payment_claims')) OR (table_schema='ibanking_payment_db' AND table_name IN ('transactions','otps'));")"
[[ "$service_table_count" == 7 ]] || fail "Schema validation failed: expected all 7 service tables before migrations (found $service_table_count)."

base_schema_validation_sql() {
  cat <<'SQL'
SELECT IF(
    EXISTS (SELECT 1 FROM information_schema.statistics
            WHERE table_schema='ibanking_account_db' AND table_name='users'
              AND non_unique=0
            GROUP BY index_name
            HAVING COUNT(*)=1 AND MAX(column_name)='username' AND MAX(sub_part) IS NULL)
    AND EXISTS (SELECT 1 FROM information_schema.tables
                WHERE table_schema='ibanking_account_db' AND table_name='accounts'
                  AND engine='InnoDB')
    AND (SELECT COUNT(*) FROM information_schema.columns
         WHERE table_schema='ibanking_account_db' AND table_name='accounts'
           AND ((column_name='account_number' AND data_type='varchar'
                 AND character_maximum_length=20 AND is_nullable='NO')
             OR (column_name='user_id' AND data_type='bigint' AND is_nullable='NO')
             OR (column_name='balance' AND data_type='decimal'
                 AND numeric_precision=15 AND numeric_scale=2 AND is_nullable='NO')
             OR (column_name='is_default' AND data_type='tinyint' AND is_nullable='NO')
             OR (column_name='status' AND data_type='varchar'
                 AND character_maximum_length=20 AND is_nullable='NO'))) = 5
    AND EXISTS (SELECT 1 FROM information_schema.statistics
                WHERE table_schema='ibanking_account_db' AND table_name='accounts'
                  AND index_name='PRIMARY' AND column_name='account_number'
                  AND seq_in_index=1 AND non_unique=0
                GROUP BY index_name
                HAVING COUNT(*)=1 AND MAX(sub_part) IS NULL)
    AND EXISTS (SELECT 1 FROM information_schema.key_column_usage
                WHERE table_schema='ibanking_account_db' AND table_name='accounts'
                  AND constraint_name='fk_accounts_user' AND column_name='user_id'
                  AND referenced_table_schema='ibanking_account_db'
                  AND referenced_table_name='users' AND referenced_column_name='user_id')
    AND EXISTS (SELECT 1 FROM information_schema.check_constraints
                WHERE constraint_schema='ibanking_account_db'
                  AND constraint_name IN ('chk_accounts_balance','chk_accounts_balance_nonnegative')
                  AND LOWER(REPLACE(REPLACE(REPLACE(REPLACE(check_clause,'`',''),' ',''),'(',''),')',''))='balance>=0')
    AND EXISTS (SELECT 1 FROM information_schema.tables
                WHERE table_schema='ibanking_tuition_db' AND table_name='tuition_bills'
                  AND engine='InnoDB')
    AND (SELECT COUNT(*) FROM information_schema.columns
         WHERE table_schema='ibanking_tuition_db' AND table_name='tuition_bills'
           AND ((column_name='student_id' AND data_type='varchar'
                 AND character_maximum_length=20 AND is_nullable='NO')
             OR (column_name='student_name' AND data_type='varchar'
                 AND character_maximum_length=100 AND is_nullable='NO')
             OR (column_name='amount' AND data_type='decimal'
                 AND numeric_precision=15 AND numeric_scale=2 AND is_nullable='NO')
             OR (column_name='status' AND data_type='varchar'
                 AND character_maximum_length=20 AND is_nullable='NO'))) = 4
    AND EXISTS (SELECT 1 FROM information_schema.statistics
                WHERE table_schema='ibanking_tuition_db' AND table_name='tuition_bills'
                  AND index_name='PRIMARY' AND column_name='student_id'
                  AND seq_in_index=1 AND non_unique=0
                GROUP BY index_name
                HAVING COUNT(*)=1 AND MAX(sub_part) IS NULL)
    AND EXISTS (SELECT 1 FROM information_schema.check_constraints
                WHERE constraint_schema='ibanking_tuition_db'
                  AND constraint_name='chk_tuition_amount'
                  AND LOWER(REPLACE(REPLACE(REPLACE(REPLACE(check_clause,'`',''),' ',''),'(',''),')',''))='amount>0')
    AND EXISTS (SELECT 1 FROM information_schema.check_constraints
                WHERE constraint_schema='ibanking_tuition_db'
                  AND constraint_name='chk_tuition_status'
                  AND LOWER(check_clause) LIKE '%status%in%unpaid%paid%'),
    1, 0
);
SQL
}

base_schema_valid="$(mysql_query "$(base_schema_validation_sql)")"
[[ "$base_schema_valid" == 1 ]] || fail 'Schema validation failed: base account or tuition columns, indexes, foreign keys, or checks are missing or incorrect.'

migration_validation_sql() {
  case "$1" in
    001-user-student-id)
      cat <<'SQL'
SELECT IF(
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema='ibanking_account_db' AND table_name='users'
       AND column_name='student_id' AND data_type='varchar'
       AND character_maximum_length=20 AND is_nullable='YES') = 1
    AND EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema='ibanking_account_db' AND table_name='users'
          AND non_unique=0
        GROUP BY index_name
        HAVING COUNT(*)=1 AND MAX(column_name)='student_id' AND MAX(sub_part) IS NULL
    ),
    1, 0
);
SQL
      ;;
    002-account-debits)
      cat <<'SQL'
SELECT IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema='ibanking_account_db' AND table_name='account_debits'
              AND engine='InnoDB')
    AND (SELECT COUNT(*) FROM information_schema.columns
         WHERE table_schema='ibanking_account_db' AND table_name='account_debits'
           AND ((column_name='transaction_id' AND data_type='varchar'
                 AND character_maximum_length=100 AND is_nullable='NO')
             OR (column_name='account_number' AND data_type='varchar'
                 AND character_maximum_length=20 AND is_nullable='NO')
             OR (column_name='amount' AND data_type='decimal'
                 AND numeric_precision=15 AND numeric_scale=2 AND is_nullable='NO')
             OR (column_name='balance_after' AND data_type='decimal'
                 AND numeric_precision=15 AND numeric_scale=2 AND is_nullable='NO')
             OR (column_name='created_at' AND data_type='timestamp'
                 AND is_nullable='NO'))) = 5
    AND EXISTS (SELECT 1 FROM information_schema.statistics
                WHERE table_schema='ibanking_account_db' AND table_name='account_debits'
                  AND index_name='PRIMARY' AND column_name='transaction_id'
                  AND seq_in_index=1 AND non_unique=0
                GROUP BY index_name
                HAVING COUNT(*)=1 AND MAX(sub_part) IS NULL)
    AND EXISTS (SELECT 1 FROM information_schema.statistics
                WHERE table_schema='ibanking_account_db' AND table_name='account_debits'
                  AND index_name='ix_account_debits_account_number'
                  AND column_name='account_number' AND seq_in_index=1 AND non_unique=1
                GROUP BY index_name
                HAVING COUNT(*)=1 AND MAX(sub_part) IS NULL)
    AND EXISTS (SELECT 1 FROM information_schema.key_column_usage
                WHERE table_schema='ibanking_account_db' AND table_name='account_debits'
                  AND constraint_name='fk_account_debits_account'
                  AND column_name='account_number'
                  AND referenced_table_schema='ibanking_account_db'
                  AND referenced_table_name='accounts'
                  AND referenced_column_name='account_number')
    AND EXISTS (SELECT 1 FROM information_schema.check_constraints
                WHERE constraint_schema='ibanking_account_db'
                  AND constraint_name='chk_account_debits_amount'
                  AND LOWER(REPLACE(REPLACE(REPLACE(REPLACE(check_clause,'`',''),' ',''),'(',''),')',''))='amount>0')
    AND EXISTS (SELECT 1 FROM information_schema.check_constraints
                WHERE constraint_schema='ibanking_account_db'
                  AND constraint_name='chk_account_debits_balance'
                  AND LOWER(REPLACE(REPLACE(REPLACE(REPLACE(check_clause,'`',''),' ',''),'(',''),')',''))='balance_after>=0'),
    1, 0
);
SQL
      ;;
    001-tuition-payment-claims)
      cat <<'SQL'
SELECT IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema='ibanking_tuition_db' AND table_name='tuition_payment_claims'
              AND engine='InnoDB')
    AND (SELECT COUNT(*) FROM information_schema.columns
         WHERE table_schema='ibanking_tuition_db' AND table_name='tuition_payment_claims'
           AND ((column_name='student_id' AND data_type='varchar'
                 AND character_maximum_length=20 AND is_nullable='NO')
             OR (column_name='transaction_id' AND data_type='varchar'
                 AND character_maximum_length=36 AND is_nullable='NO')
             OR (column_name='claimed_at' AND data_type='timestamp'
                 AND is_nullable='NO'))) = 3
    AND EXISTS (SELECT 1 FROM information_schema.statistics
                WHERE table_schema='ibanking_tuition_db' AND table_name='tuition_payment_claims'
                  AND index_name='PRIMARY' AND column_name='student_id'
                  AND seq_in_index=1 AND non_unique=0
                GROUP BY index_name
                HAVING COUNT(*)=1 AND MAX(sub_part) IS NULL)
    AND EXISTS (SELECT 1 FROM information_schema.statistics
                WHERE table_schema='ibanking_tuition_db' AND table_name='tuition_payment_claims'
                  AND non_unique=0
                GROUP BY index_name
                HAVING COUNT(*)=1 AND MAX(column_name)='transaction_id'
                   AND MAX(sub_part) IS NULL)
    AND EXISTS (SELECT 1 FROM information_schema.key_column_usage
                WHERE table_schema='ibanking_tuition_db' AND table_name='tuition_payment_claims'
                  AND constraint_name='fk_tuition_payment_claim_student'
                  AND column_name='student_id'
                  AND referenced_table_schema='ibanking_tuition_db'
                  AND referenced_table_name='tuition_bills'
                  AND referenced_column_name='student_id'),
    1, 0
);
SQL
      ;;
    001-payment-integrity)
      cat <<'SQL'
SELECT IF(
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema='ibanking_payment_db' AND table_name='transactions'
       AND ((column_name='payer_user_id' AND data_type='bigint' AND is_nullable='NO')
         OR (column_name='source_account_number' AND data_type='varchar'
             AND character_maximum_length=20 AND is_nullable='NO')
         OR (column_name='student_id' AND data_type='varchar'
             AND character_maximum_length=20 AND is_nullable='NO')
         OR (column_name='student_name' AND data_type='varchar'
             AND character_maximum_length=255 AND is_nullable='YES')
         OR (column_name='status' AND data_type='varchar'
             AND character_maximum_length=32 AND is_nullable='NO')
         OR (column_name='reconciliation_code' AND data_type='varchar'
             AND character_maximum_length=64 AND is_nullable='YES')
         OR (column_name='created_at' AND data_type='timestamp' AND is_nullable='NO'))) = 7
    AND (SELECT COUNT(*) FROM information_schema.columns
         WHERE table_schema='ibanking_payment_db' AND table_name='otps'
           AND ((column_name='transaction_id' AND data_type='varchar'
                 AND character_maximum_length=36 AND is_nullable='NO')
             OR (column_name='otp_code' AND data_type='varchar'
                 AND character_maximum_length=10 AND is_nullable='NO')
             OR (column_name='expires_at' AND data_type='timestamp' AND is_nullable='NO')
             OR (column_name='is_used' AND data_type='tinyint' AND is_nullable='NO'))) = 4
    AND EXISTS (SELECT 1 FROM information_schema.statistics
                WHERE table_schema='ibanking_payment_db' AND table_name='transactions'
                  AND index_name='PRIMARY' AND column_name='transaction_id'
                  AND seq_in_index=1 AND non_unique=0
                GROUP BY index_name
                HAVING COUNT(*)=1 AND MAX(sub_part) IS NULL)
    AND EXISTS (SELECT 1 FROM information_schema.statistics
                WHERE table_schema='ibanking_payment_db' AND table_name='otps'
                  AND index_name='PRIMARY' AND column_name='otp_id'
                  AND seq_in_index=1 AND non_unique=0
                GROUP BY index_name
                HAVING COUNT(*)=1 AND MAX(sub_part) IS NULL)
    AND EXISTS (SELECT 1 FROM information_schema.statistics
                WHERE table_schema='ibanking_payment_db' AND table_name='otps'
                  AND non_unique=1
                GROUP BY index_name
                HAVING COUNT(*)=1 AND MAX(column_name)='transaction_id'
                   AND MAX(sub_part) IS NULL)
    AND EXISTS (SELECT 1 FROM information_schema.key_column_usage
                WHERE table_schema='ibanking_payment_db' AND table_name='otps'
                  AND constraint_name='fk_otps_transaction'
                  AND column_name='transaction_id'
                  AND referenced_table_schema='ibanking_payment_db'
                  AND referenced_table_name='transactions'
                  AND referenced_column_name='transaction_id'),
    1, 0
);
SQL
      ;;
    *)
      fail "No schema validator is defined for migration $1."
      ;;
  esac
}

migration_is_valid() {
  local result
  result="$(mysql_query "$(migration_validation_sql "$1")")"
  [[ "$result" == 1 ]]
}

assert_migration_tracking_schema() {
  local result
  result="$(mysql_query "$(cat <<'SQL'
SELECT IF(
    (SELECT COUNT(*) FROM information_schema.tables
     WHERE table_schema IN ('ibanking_account_db','ibanking_tuition_db','ibanking_payment_db')
       AND table_name='schema_migrations' AND engine='InnoDB') = 3
    AND (SELECT COUNT(*) FROM information_schema.columns
         WHERE table_schema IN ('ibanking_account_db','ibanking_tuition_db','ibanking_payment_db')
           AND table_name='schema_migrations'
           AND ((column_name='version' AND data_type='varchar'
                 AND character_maximum_length=100 AND is_nullable='NO')
             OR (column_name='applied_at' AND data_type='timestamp' AND is_nullable='NO'))) = 6
    AND (SELECT COUNT(*) FROM (
             SELECT table_schema, table_name
             FROM information_schema.statistics
             WHERE table_schema IN ('ibanking_account_db','ibanking_tuition_db','ibanking_payment_db')
               AND table_name='schema_migrations' AND index_name='PRIMARY'
               AND non_unique=0
             GROUP BY table_schema, table_name
             HAVING COUNT(*)=1 AND MAX(column_name)='version'
                AND MAX(sub_part) IS NULL
         ) AS migration_primary_keys) = 3,
    1, 0
);
SQL
  )")"
  [[ "$result" == 1 ]] || fail 'Migration tracking schema is missing or malformed in one or more target databases.'
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
assert_migration_tracking_schema

migrations=(
  'ibanking_account_db|001-user-student-id|db/user/add_user_student_id.sql'
  'ibanking_account_db|002-account-debits|db/user/add_account_debits.sql'
  'ibanking_tuition_db|001-tuition-payment-claims|db/tuition/tuition_payment_claims.sql'
  'ibanking_payment_db|001-payment-integrity|db/payment/payment_init.sql'
)

for migration in "${migrations[@]}"; do
  IFS='|' read -r database version file <<<"$migration"
  applied="$(mysql_query "SELECT COUNT(*) FROM ${database}.schema_migrations WHERE version='${version}';")"
  [[ "$applied" =~ ^[01]$ ]] || fail "Migration tracking contains an invalid count for $version."

  if migration_is_valid "$version"; then
    if [[ "$applied" == 1 ]]; then
      continue
    fi
  else
    if [[ "$applied" == 1 ]]; then
      fail "Migration $version is recorded but its required schema is missing or incorrect."
    fi
    [[ -f "$ROOT_DIR/$file" ]] || fail "Required schema migration is missing: $file"
    if ! mysql_exec < "$ROOT_DIR/$file"; then
      fail "Migration $version in $database failed; it was not recorded."
    fi
    migration_is_valid "$version" || fail "Migration $version in $database did not produce the required schema; it was not recorded."
  fi

  mysql_query "INSERT INTO ${database}.schema_migrations (version) VALUES ('${version}');" >/dev/null
  applied="$(mysql_query "SELECT COUNT(*) FROM ${database}.schema_migrations WHERE version='${version}';")"
  [[ "$applied" == 1 ]] || fail "Migration $version schema was verified but its tracking record could not be verified."
  printf 'Verified and recorded schema migration %s\n' "$version"
done

for seed in db/docker-init/05-user-demo-seed.sql db/docker-init/06-tuition-demo-seed.sql; do
  [[ -f "$ROOT_DIR/$seed" ]] || fail "Required seed script is missing: $seed"
  mysql_exec < "$ROOT_DIR/$seed"
done

for migration in "${migrations[@]}"; do
  IFS='|' read -r database version _ <<<"$migration"
  migration_is_valid "$version" || fail "Final schema validation failed for migration $version in $database."
  applied="$(mysql_query "SELECT COUNT(*) FROM ${database}.schema_migrations WHERE version='${version}';")"
  [[ "$applied" == 1 ]] || fail "Final migration tracking verification failed for $version."
done

printf 'Schema checks, verified migration tracking, and idempotent demo seed scripts completed.\n'
