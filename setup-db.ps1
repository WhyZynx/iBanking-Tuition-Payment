param(
    [string]$ComposeProject = 'ibanking-demo'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$envFile = Join-Path $root '.env.docker'

function Invoke-MySql([string]$sql) {
    $output = $sql | & docker compose --env-file $envFile -p $ComposeProject exec -T mysql sh -c 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql -uroot --batch --skip-column-names'
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "MySQL schema preparation failed (exit $exitCode). No volume reset was attempted."
    }
    return ($output -join "`n").Trim()
}

$databaseCount = [int](Invoke-MySql @'
SELECT COUNT(*)
FROM information_schema.schemata
WHERE schema_name IN ('ibanking_account_db', 'ibanking_tuition_db', 'ibanking_payment_db');
'@)
if ($databaseCount -ne 3) {
    throw 'Expected all three iBanking databases. Existing volumes are not initialized again; preserve data and follow the migration guide before retrying.'
}

Invoke-MySql @'
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
);
'@ | Out-Null

$migrations = @(
    @{ Database = 'ibanking_account_db'; Version = '001-user-student-id'; File = 'db/user/add_user_student_id.sql' },
    @{ Database = 'ibanking_account_db'; Version = '002-account-debits'; File = 'db/user/add_account_debits.sql' },
    @{ Database = 'ibanking_tuition_db'; Version = '001-tuition-payment-claims'; File = 'db/tuition/tuition_payment_claims.sql' },
    @{ Database = 'ibanking_payment_db'; Version = '001-payment-integrity'; File = 'db/payment/payment_init.sql' }
)

foreach ($migration in $migrations) {
    $version = $migration.Version.Replace("'", "''")
    $applied = [int](Invoke-MySql "SELECT COUNT(*) FROM $($migration.Database).schema_migrations WHERE version='$version';")
    if ($applied -ne 0) { continue }

    $filePath = Join-Path $root $migration.File
    if (-not (Test-Path -LiteralPath $filePath)) {
        throw "Required schema migration is missing: $($migration.File)"
    }
    $sql = [System.IO.File]::ReadAllText($filePath, [System.Text.Encoding]::UTF8)
    Invoke-MySql $sql | Out-Null
    Invoke-MySql "INSERT INTO $($migration.Database).schema_migrations (version) VALUES ('$version');" | Out-Null
    Write-Host "Applied schema migration $($migration.Version)"
}

foreach ($seed in @('db/docker-init/05-user-demo-seed.sql', 'db/docker-init/06-tuition-demo-seed.sql')) {
    $seedPath = Join-Path $root $seed
    if (-not (Test-Path -LiteralPath $seedPath)) { throw "Required seed script is missing: $seed" }
    $sql = [System.IO.File]::ReadAllText($seedPath, [System.Text.Encoding]::UTF8)
    Invoke-MySql $sql | Out-Null
}

$tableCount = [int](Invoke-MySql @'
SELECT COUNT(*)
FROM information_schema.tables
WHERE (table_schema='ibanking_account_db' AND table_name IN ('users', 'accounts', 'account_debits'))
   OR (table_schema='ibanking_tuition_db' AND table_name IN ('tuition_bills', 'tuition_payment_claims'))
   OR (table_schema='ibanking_payment_db' AND table_name IN ('transactions', 'otps'));
'@)
if ($tableCount -ne 7) { throw 'Schema verification failed: one or more service tables are missing.' }

$columnCount = [int](Invoke-MySql @'
SELECT COUNT(*)
FROM information_schema.columns
WHERE (table_schema='ibanking_account_db' AND table_name='users' AND column_name='student_id')
   OR (table_schema='ibanking_account_db' AND table_name='account_debits' AND column_name='transaction_id')
   OR (table_schema='ibanking_tuition_db' AND table_name='tuition_payment_claims' AND column_name='transaction_id')
   OR (table_schema='ibanking_payment_db' AND table_name='transactions' AND column_name IN ('student_name', 'reconciliation_code'))
   OR (table_schema='ibanking_payment_db' AND table_name='otps' AND column_name='otp_code');
'@)
if ($columnCount -ne 6) { throw 'Schema verification failed: one or more required service columns are missing.' }

Write-Host 'Schema checks, guarded migrations, and idempotent demo seeds completed.'
