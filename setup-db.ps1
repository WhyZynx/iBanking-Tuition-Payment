param(
    [string]$ComposeProject = 'ibanking-demo',
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$envFile = Join-Path $root '.env.docker'
$composeFile = Join-Path $root 'docker-compose.yml'

function Get-ComposeArguments([string[]]$Arguments) {
    return @(
        'compose',
        '--env-file', $envFile,
        '--file', $composeFile,
        '--project-directory', $root,
        '--project-name', $ComposeProject
    ) + $Arguments
}

function Invoke-MySql([string]$Sql) {
    $arguments = Get-ComposeArguments @(
        'exec', '-T', 'mysql',
        'sh', '-c',
        'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql --protocol=socket -uroot --batch --raw --skip-column-names'
    )
    $output = $Sql | & docker @arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "MySQL command failed for Compose project $ComposeProject (exit $exitCode)."
    }
    return ($output -join "`n").Trim()
}

function Get-MigrationValidationQuery([string]$Version) {
    switch ($Version) {
        '001-user-student-id' {
            return @'
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
'@
        }
        '002-account-debits' {
            return @'
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
'@
        }
        '001-tuition-payment-claims' {
            return @'
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
'@
        }
        '001-payment-integrity' {
            return @'
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
'@
        }
        default { throw "No schema validator is defined for migration $Version." }
    }
}

function Test-MigrationSchema([string]$Version) {
    return (Invoke-MySql (Get-MigrationValidationQuery $Version)) -eq '1'
}

function Assert-MigrationTrackingSchema {
    $valid = Invoke-MySql @'
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
'@
    if ($valid -ne '1') {
        throw 'Migration tracking schema is missing or malformed in one or more target databases.'
    }
}

function Assert-ServiceTables {
    $tableCount = [int](Invoke-MySql @'
SELECT COUNT(*)
FROM information_schema.tables
WHERE (table_schema='ibanking_account_db' AND table_name IN ('users','accounts','account_debits'))
   OR (table_schema='ibanking_tuition_db' AND table_name IN ('tuition_bills','tuition_payment_claims'))
   OR (table_schema='ibanking_payment_db' AND table_name IN ('transactions','otps'));
'@)
    if ($tableCount -ne 7) {
        throw 'Schema validation failed: expected all 7 service tables before migrations.'
    }

    $valid = Invoke-MySql @'
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
'@
    if ($valid -ne '1') {
        throw 'Schema validation failed: base account or tuition columns, indexes, foreign keys, or checks are missing or incorrect.'
    }
}

function Assert-MigrationSchemas($Migrations) {
    foreach ($migration in $Migrations) {
        if (-not (Test-MigrationSchema $migration.Version)) {
            throw "Schema validation failed for migration $($migration.Version) in $($migration.Database)."
        }
    }
}

if ([string]::IsNullOrWhiteSpace($ComposeProject)) {
    throw 'Compose project name is required.'
}
if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw 'Required .env.docker file is missing.'
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker CLI is not installed or is not available on PATH.'
}

$databaseCount = [int](Invoke-MySql @'
SELECT COUNT(*)
FROM information_schema.schemata
WHERE schema_name IN ('ibanking_account_db', 'ibanking_tuition_db', 'ibanking_payment_db');
'@)
if ($databaseCount -ne 3) {
    throw "Expected all three iBanking databases in Compose project $ComposeProject."
}

$migrations = @(
    @{ Database = 'ibanking_account_db'; Version = '001-user-student-id'; File = 'db/user/add_user_student_id.sql' },
    @{ Database = 'ibanking_account_db'; Version = '002-account-debits'; File = 'db/user/add_account_debits.sql' },
    @{ Database = 'ibanking_tuition_db'; Version = '001-tuition-payment-claims'; File = 'db/tuition/tuition_payment_claims.sql' },
    @{ Database = 'ibanking_payment_db'; Version = '001-payment-integrity'; File = 'db/payment/payment_init.sql' }
)

Assert-ServiceTables

if ($ValidateOnly) {
    Assert-MigrationSchemas $migrations
    $trackingTableCount = [int](Invoke-MySql @'
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema IN ('ibanking_account_db','ibanking_tuition_db','ibanking_payment_db')
  AND table_name='schema_migrations';
'@)
    if ($trackingTableCount -notin @(0, 3)) {
        throw 'Migration tracking pre-check failed: schema_migrations exists in only some target databases.'
    }
    if ($trackingTableCount -eq 3) {
        Assert-MigrationTrackingSchema
        foreach ($migration in $migrations) {
            $version = $migration.Version.Replace("'", "''")
            $applied = [int](Invoke-MySql "SELECT COUNT(*) FROM $($migration.Database).schema_migrations WHERE version='$version';")
            if ($applied -gt 1) {
                throw "Migration tracking contains duplicate version $($migration.Version)."
            }
        }
    }
    Write-Host 'Read-only schema pre-check passed for all service migrations.'
    return
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
Assert-MigrationTrackingSchema

foreach ($migration in $migrations) {
    $version = $migration.Version.Replace("'", "''")
    $applied = [int](Invoke-MySql "SELECT COUNT(*) FROM $($migration.Database).schema_migrations WHERE version='$version';")
    if ($applied -gt 1) {
        throw "Migration tracking contains duplicate version $($migration.Version)."
    }

    $schemaValid = Test-MigrationSchema $migration.Version
    if ($applied -eq 1) {
        if (-not $schemaValid) {
            throw "Migration $($migration.Version) is recorded but its required schema is missing or incorrect."
        }
        continue
    }

    if (-not $schemaValid) {
        $filePath = Join-Path $root $migration.File
        if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
            throw "Required schema migration is missing: $($migration.File)"
        }
        try {
            $sql = [System.IO.File]::ReadAllText($filePath, [System.Text.Encoding]::UTF8)
            Invoke-MySql $sql | Out-Null
        }
        catch {
            throw "Migration $($migration.Version) in $($migration.Database) failed; it was not recorded. $($_.Exception.Message)"
        }
    }

    if (-not (Test-MigrationSchema $migration.Version)) {
        throw "Migration $($migration.Version) in $($migration.Database) did not produce the required schema; it was not recorded."
    }
    Invoke-MySql "INSERT INTO $($migration.Database).schema_migrations (version) VALUES ('$version');" | Out-Null
    $applied = [int](Invoke-MySql "SELECT COUNT(*) FROM $($migration.Database).schema_migrations WHERE version='$version';")
    if ($applied -ne 1) {
        throw "Migration $($migration.Version) schema was verified but its tracking record could not be verified."
    }
    Write-Host "Verified and recorded schema migration $($migration.Version)"
}

Assert-MigrationSchemas $migrations

foreach ($seed in @('db/docker-init/05-user-demo-seed.sql', 'db/docker-init/06-tuition-demo-seed.sql')) {
    $seedPath = Join-Path $root $seed
    if (-not (Test-Path -LiteralPath $seedPath -PathType Leaf)) {
        throw "Required seed script is missing: $seed"
    }
    $sql = [System.IO.File]::ReadAllText($seedPath, [System.Text.Encoding]::UTF8)
    Invoke-MySql $sql | Out-Null
}

$expectedMigrations = @(
    "ibanking_account_db`t001-user-student-id",
    "ibanking_account_db`t002-account-debits",
    "ibanking_tuition_db`t001-tuition-payment-claims",
    "ibanking_payment_db`t001-payment-integrity"
) -join "`n"
$actualMigrations = Invoke-MySql @'
SELECT CONCAT('ibanking_account_db', CHAR(9), version)
FROM ibanking_account_db.schema_migrations
WHERE version IN ('001-user-student-id','002-account-debits')
UNION ALL
SELECT CONCAT('ibanking_tuition_db', CHAR(9), version)
FROM ibanking_tuition_db.schema_migrations
WHERE version='001-tuition-payment-claims'
UNION ALL
SELECT CONCAT('ibanking_payment_db', CHAR(9), version)
FROM ibanking_payment_db.schema_migrations
WHERE version='001-payment-integrity'
ORDER BY 1;
'@
if ($actualMigrations -cne $expectedMigrations) {
    throw 'Migration verification failed: expected schema versions are missing or duplicated.'
}

Write-Host 'Schema checks, verified migration tracking, and idempotent demo seed scripts completed.'
