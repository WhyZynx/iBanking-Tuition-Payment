$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$project = 'ibanking-demo'
$envFile = Join-Path $root '.env.docker'
$composeFile = Join-Path $root 'docker-compose.yml'
$resetConfirmation = 'RESET ibanking-demo'
$requiredServices = @('mysql', 'user-service', 'tuition-service', 'payment-service', 'nginx', 'mailpit')
$servicesToStop = @('payment-service', 'tuition-service', 'user-service')
$servicesToStart = @('user-service', 'tuition-service', 'payment-service')
$databases = @('ibanking_account_db', 'ibanking_tuition_db', 'ibanking_payment_db')
$databasePhases = [ordered]@{
    'ibanking_account_db' = 'Original'
    'ibanking_tuition_db' = 'Original'
    'ibanking_payment_db' = 'Original'
}
$servicePhases = [ordered]@{
    'mysql' = 'Not checked'
    'user-service' = 'Not checked'
    'tuition-service' = 'Not checked'
    'payment-service' = 'Not checked'
    'nginx' = 'Not checked'
    'mailpit' = 'Not checked'
}
$stoppedServices = [System.Collections.Generic.List[string]]::new()
$destructiveStarted = $false

function Invoke-NativeCommand([string]$Executable, [string[]]$Arguments) {
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $lines = @(& $Executable @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    $text = ($lines | ForEach-Object { [string]$_ }) -join "`n"
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = $text.Trim()
    }
}

function Get-ComposeArguments([string[]]$Arguments) {
    return @(
        'compose',
        '--env-file', $envFile,
        '--file', $composeFile,
        '--project-directory', $root,
        '--project-name', $project
    ) + $Arguments
}

function Invoke-Compose([string[]]$Arguments) {
    return Invoke-NativeCommand 'docker' (Get-ComposeArguments $Arguments)
}

function Invoke-ComposeChecked([string[]]$Arguments, [string]$FailureMessage) {
    $result = Invoke-Compose $Arguments
    if ($result.ExitCode -ne 0) {
        $detail = if ($result.Output) { " Output: $($result.Output)" } else { '' }
        throw "$FailureMessage (exit $($result.ExitCode)).$detail"
    }
    return $result.Output
}

function Invoke-MySql([string]$Sql) {
    $arguments = Get-ComposeArguments @(
        'exec', '-T', 'mysql',
        'sh', '-c',
        'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql --protocol=socket -uroot --batch --raw --skip-column-names'
    )
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $lines = @($Sql | & docker @arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    $output = ($lines | ForEach-Object { [string]$_ }) -join "`n"
    if ($exitCode -ne 0) {
        throw "MySQL command failed (exit $exitCode). $($output.Trim())"
    }
    return $output.Trim()
}

function Get-ProjectContainer([string]$Service) {
    $listing = Invoke-Compose @('ps', '--all', '--quiet', $Service)
    if ($listing.ExitCode -ne 0) {
        throw "Could not list $Service containers in Compose project $project (exit $($listing.ExitCode))."
    }
    $containerIds = @(
        $listing.Output -split "`r?`n" |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    )
    if ($containerIds.Count -ne 1) {
        throw "Expected exactly one $Service container in Compose project $project; found $($containerIds.Count)."
    }

    $containerId = $containerIds[0]
    if ($containerId -notmatch '^[0-9a-fA-F]{64}$') {
        throw "Docker Compose returned an invalid full container ID for $Service."
    }
    $inspection = Invoke-NativeCommand 'docker' @('inspect', $containerId)
    if ($inspection.ExitCode -ne 0) {
        throw "Could not inspect the full container ID returned for $Service (exit $($inspection.ExitCode))."
    }
    try {
        $containers = @($inspection.Output | ConvertFrom-Json)
    }
    catch {
        throw "Docker returned invalid inspection data for $Service."
    }
    if ($containers.Count -ne 1 -or $containers[0].Id -ne $containerId) {
        throw "Docker inspection did not resolve exactly the requested full container ID for $Service."
    }

    $container = $containers[0]
    $labels = $container.Config.Labels
    if (
        $labels.'com.docker.compose.project' -ne $project -or
        $labels.'com.docker.compose.service' -ne $Service
    ) {
        throw "Refusing to use a $Service container outside Compose project $project."
    }
    return $container
}

function Get-ContainerEnvironmentValue($Container, [string]$Name) {
    $matches = @(
        $Container.Config.Env |
            Where-Object { $_.StartsWith("$Name=") }
    )
    if ($matches.Count -ne 1) {
        throw "Container configuration for $($Container.Config.Labels.'com.docker.compose.service') has a missing or ambiguous $Name."
    }
    return $matches[0].Substring($Name.Length + 1)
}

function Assert-ContainerHealthy([string]$Service) {
    $container = Get-ProjectContainer $Service
    if ($container.State.Status -ne 'running') {
        throw "$Service is not running (current state: $($container.State.Status))."
    }
    if (-not $container.State.Health -or $container.State.Health.Status -ne 'healthy') {
        throw "$Service does not report healthy (current state: $($container.State.Health.Status))."
    }
    $servicePhases[$Service] = 'Running and healthy'
    return $container
}

function Get-ExpectedSeedData {
    $userSeedPath = Join-Path $root 'db/docker-init/05-user-demo-seed.sql'
    $tuitionSeedPath = Join-Path $root 'db/docker-init/06-tuition-demo-seed.sql'
    $userSeed = [System.IO.File]::ReadAllText($userSeedPath)
    $tuitionSeed = [System.IO.File]::ReadAllText($tuitionSeedPath)

    $userPattern = "SELECT\s+'([^']+)'\s*,\s*'[^']+'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'"
    $userRows = @(
        foreach ($match in [regex]::Matches($userSeed, $userPattern)) {
            [pscustomobject]@{
                Username = $match.Groups[1].Value
                FullName = $match.Groups[2].Value
                Email = $match.Groups[4].Value
                StudentId = $match.Groups[5].Value
            }
        }
    )

    $accountPattern = "SELECT '([^']+)', u\.user_id, ([0-9]+(?:\.[0-9]+)?), TRUE, 'ACTIVE' FROM users AS u\s+WHERE u\.username = '([^']+)' AND u\.student_id = '([^']+)'"
    $accountRows = @(
        foreach ($match in [regex]::Matches($userSeed, $accountPattern)) {
            [pscustomobject]@{
                AccountNumber = $match.Groups[1].Value
                Balance = [decimal]::Parse(
                    $match.Groups[2].Value,
                    [System.Globalization.CultureInfo]::InvariantCulture
                )
                Username = $match.Groups[3].Value
                StudentId = $match.Groups[4].Value
            }
        }
    )

    $tuitionPattern = "SELECT '([^']+)', '([^']+)', ([0-9]+(?:\.[0-9]+)?), '(UNPAID|PAID)'"
    $tuitionRows = @(
        foreach ($match in [regex]::Matches($tuitionSeed, $tuitionPattern)) {
            [pscustomobject]@{
                StudentId = $match.Groups[1].Value
                StudentName = $match.Groups[2].Value
                Amount = [decimal]::Parse(
                    $match.Groups[3].Value,
                    [System.Globalization.CultureInfo]::InvariantCulture
                )
                Status = $match.Groups[4].Value
            }
        }
    )

    if ($userRows.Count -ne 8 -or $accountRows.Count -ne 8 -or $tuitionRows.Count -ne 8) {
        throw 'Seed pre-check failed: expected 8 parseable users, accounts, and tuition bills in the current SQL files.'
    }
    return [pscustomobject]@{
        Users = $userRows
        Accounts = $accountRows
        TuitionBills = $tuitionRows
    }
}

function Assert-SeedRows([pscustomobject]$SeedData) {
    $actualUsers = Invoke-MySql @'
SELECT username, full_name, email, student_id
FROM ibanking_account_db.users
ORDER BY username;
'@
    $expectedUsers = @(
        $SeedData.Users |
            Sort-Object Username |
            ForEach-Object { "$($_.Username)`t$($_.FullName)`t$($_.Email)`t$($_.StudentId)" }
    )
    if ($actualUsers -cne ($expectedUsers -join "`n")) {
        throw 'User seed verification failed: database rows do not exactly match the current user seed SQL.'
    }

    $actualAccounts = Invoke-MySql @'
SELECT u.username, a.account_number, CAST(a.balance AS CHAR), CAST(a.is_default AS UNSIGNED), a.status
FROM ibanking_account_db.accounts a
JOIN ibanking_account_db.users u ON u.user_id = a.user_id
ORDER BY u.username, a.account_number;
'@
    $expectedAccounts = @(
        $SeedData.Accounts |
            Sort-Object Username, AccountNumber |
            ForEach-Object {
                "$($_.Username)`t$($_.AccountNumber)`t$($_.Balance.ToString('0.00', [System.Globalization.CultureInfo]::InvariantCulture))`t1`tACTIVE"
            }
    )
    if ($actualAccounts -cne ($expectedAccounts -join "`n")) {
        throw 'Account seed verification failed: database rows do not exactly match the current user seed SQL.'
    }

    $actualTuition = Invoke-MySql @'
SELECT student_id, student_name, CAST(amount AS CHAR), status
FROM ibanking_tuition_db.tuition_bills
ORDER BY student_id;
'@
    $expectedTuition = @(
        $SeedData.TuitionBills |
            Sort-Object StudentId |
            ForEach-Object {
                "$($_.StudentId)`t$($_.StudentName)`t$($_.Amount.ToString('0.00', [System.Globalization.CultureInfo]::InvariantCulture))`t$($_.Status)"
            }
    )
    if ($actualTuition -cne ($expectedTuition -join "`n")) {
        throw 'Tuition seed verification failed: database rows do not exactly match the current tuition seed SQL.'
    }
}

function Assert-DatabaseReset([pscustomobject]$SeedData) {
    $schemas = Invoke-MySql @'
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name IN ('ibanking_account_db','ibanking_tuition_db','ibanking_payment_db')
ORDER BY schema_name;
'@
    if ($schemas -cne (($databases | Sort-Object) -join "`n")) {
        throw 'Post-reset schema verification failed: one or more target databases are missing.'
    }

    $tableCount = Invoke-MySql @'
SELECT COUNT(*)
FROM information_schema.tables
WHERE (table_schema='ibanking_account_db' AND table_name IN ('users','accounts','account_debits','schema_migrations'))
   OR (table_schema='ibanking_tuition_db' AND table_name IN ('tuition_bills','tuition_payment_claims','schema_migrations'))
   OR (table_schema='ibanking_payment_db' AND table_name IN ('transactions','otps','schema_migrations'));
'@
    if ($tableCount -ne '10') {
        throw 'Post-reset schema verification failed: expected all 10 service and migration tables.'
    }

    $migrationRows = Invoke-MySql @'
SELECT 'ibanking_account_db', version FROM ibanking_account_db.schema_migrations ORDER BY version;
SELECT 'ibanking_payment_db', version FROM ibanking_payment_db.schema_migrations ORDER BY version;
SELECT 'ibanking_tuition_db', version FROM ibanking_tuition_db.schema_migrations ORDER BY version;
'@
    $expectedMigrations = @(
        "ibanking_account_db`t001-user-student-id",
        "ibanking_account_db`t002-account-debits",
        "ibanking_payment_db`t001-payment-integrity",
        "ibanking_tuition_db`t001-tuition-payment-claims"
    ) -join "`n"
    if ($migrationRows -cne $expectedMigrations) {
        throw 'Post-reset migration verification failed: applied versions do not match setup-db.ps1.'
    }

    $rowCounts = Invoke-MySql @'
SELECT
    (SELECT COUNT(*) FROM ibanking_account_db.users),
    (SELECT COUNT(*) FROM ibanking_account_db.accounts),
    (SELECT COUNT(*) FROM ibanking_tuition_db.tuition_bills),
    (SELECT COUNT(*) FROM ibanking_payment_db.transactions),
    (SELECT COUNT(*) FROM ibanking_payment_db.otps),
    (SELECT COUNT(*) FROM ibanking_account_db.account_debits),
    (SELECT COUNT(*) FROM ibanking_tuition_db.tuition_payment_claims);
'@
    if ($rowCounts -cne "8`t8`t8`t0`t0`t0`t0") {
        throw 'Post-reset data verification failed: expected 8 users/accounts/bills and no transactions, OTPs, debits, or claims.'
    }
    Assert-SeedRows $SeedData
}

function Get-ConfiguredPort([string]$Name, [int]$DefaultValue) {
    $matches = @(
        [System.IO.File]::ReadAllLines($envFile) |
            Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s*=\s*(\d{1,5})\s*$" } |
            ForEach-Object { [int]$Matches[1] }
    )
    if ($matches.Count -gt 1) { throw "$Name is configured more than once in .env.docker." }
    if ($matches.Count -eq 0) { return $DefaultValue }
    if ($matches[0] -lt 1 -or $matches[0] -gt 65535) { throw "$Name is outside the valid TCP port range." }
    return $matches[0]
}

function Test-LocalHttpEndpoint([string]$Name, [int]$Port) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/" -TimeoutSec 10
    }
    catch {
        $httpResponse = $_.Exception.Response
        if ($null -ne $httpResponse -and $null -ne $httpResponse.StatusCode) {
            throw "$Name returned HTTP $([int]$httpResponse.StatusCode)."
        }
        throw "$Name did not respond at http://127.0.0.1:$Port/."
    }
    if ([int]$response.StatusCode -lt 200 -or [int]$response.StatusCode -ge 400) {
        throw "$Name returned HTTP $($response.StatusCode)."
    }
}

function Start-ApplicationService([string]$Service) {
    $result = Invoke-Compose @(
        'up', '--detach', '--no-deps', '--wait', '--wait-timeout', '240', $Service
    )
    if ($result.ExitCode -ne 0) {
        $detail = if ($result.Output) { " Output: $($result.Output)" } else { '' }
        throw "Could not start $Service (exit $($result.ExitCode)).$detail"
    }
    [void](Assert-ContainerHealthy $Service)
    $servicePhases[$Service] = 'Restarted and healthy'
}

function Write-FailureState {
    Write-Host 'Database reset state (last confirmed phase):' -ForegroundColor Yellow
    foreach ($database in $databases) {
        Write-Host "  ${database}: $($databasePhases[$database])"
    }
    Write-Host 'Service state (last confirmed phase):' -ForegroundColor Yellow
    foreach ($service in $requiredServices) {
        Write-Host "  ${service}: $($servicePhases[$service])"
    }
}

try {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        throw 'The reset script project directory is unavailable.'
    }
    foreach ($requiredPath in @(
        $envFile,
        $composeFile,
        (Join-Path $root 'setup-db.ps1'),
        (Join-Path $root 'db/docker-init/01-user-init.sql'),
        (Join-Path $root 'db/docker-init/02-tuition-init.sql'),
        (Join-Path $root 'db/docker-init/03-tuition-claims.sql'),
        (Join-Path $root 'db/payment/payment_init.sql'),
        (Join-Path $root 'db/docker-init/05-user-demo-seed.sql'),
        (Join-Path $root 'db/docker-init/06-tuition-demo-seed.sql'),
        (Join-Path $root 'db/user/add_user_student_id.sql'),
        (Join-Path $root 'db/user/add_account_debits.sql'),
        (Join-Path $root 'db/tuition/tuition_payment_claims.sql')
    )) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Required project, migration, or seed file is missing: $requiredPath"
        }
    }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker CLI is not installed or is not available on PATH.'
    }

    Set-Location -LiteralPath $root
    $config = Invoke-Compose @('config', '--quiet')
    if ($config.ExitCode -ne 0) {
        throw "Compose configuration is invalid (exit $($config.ExitCode)). Check .env.docker without sharing its values."
    }
    $serviceList = Invoke-ComposeChecked @('config', '--services') 'Could not read Compose services'
    foreach ($service in $requiredServices) {
        if ($serviceList -notmatch "(?m)^$([regex]::Escape($service))$") {
            throw "Compose project $project does not define the required $service service."
        }
    }

    $jsonResult = Invoke-Compose @('config', '--format', 'json')
    if ($jsonResult.ExitCode -ne 0) {
        throw "Could not resolve Compose configuration (exit $($jsonResult.ExitCode))."
    }
    try {
        $composeConfiguration = $jsonResult.Output | ConvertFrom-Json
    }
    catch {
        throw 'Compose returned invalid JSON configuration.'
    }
    $rootPasswordProperty = $composeConfiguration.services.mysql.environment.PSObject.Properties['MYSQL_ROOT_PASSWORD']
    if (-not $rootPasswordProperty -or [string]::IsNullOrWhiteSpace([string]$rootPasswordProperty.Value)) {
        throw 'MYSQL_ROOT_PASSWORD is missing or empty in the resolved Compose configuration.'
    }
    $seedData = Get-ExpectedSeedData
    $mysql = Get-ProjectContainer 'mysql'
    if ($mysql.Config.Image -notmatch '^mysql:8\.4(?:@|$)') {
        throw 'The mysql container does not use the expected mysql:8.4 image.'
    }
    foreach ($service in $requiredServices) {
        [void](Assert-ContainerHealthy $service)
    }

    $databaseTargets = @(
        @{ Service = 'user-service'; Variable = 'DATABASE_URL'; Database = 'ibanking_account_db' },
        @{ Service = 'tuition-service'; Variable = 'DATABASE_URL'; Database = 'ibanking_tuition_db' },
        @{ Service = 'payment-service'; Variable = 'PAYMENT_DATABASE_URL'; Database = 'ibanking_payment_db' }
    )
    foreach ($target in $databaseTargets) {
        $container = Get-ProjectContainer $target.Service
        $databaseUrl = [Uri](Get-ContainerEnvironmentValue $container $target.Variable)
        if (
            $databaseUrl.Scheme -ne 'mysql+pymysql' -or
            $databaseUrl.Host -ne 'mysql' -or
            $databaseUrl.Port -ne 3306 -or
            $databaseUrl.AbsolutePath -ne "/$($target.Database)"
        ) {
            throw "$($target.Service) is not configured for its expected database in Compose project $project."
        }
    }

    $mysqlRootPassword = Get-ContainerEnvironmentValue $mysql 'MYSQL_ROOT_PASSWORD'
    if ([string]::IsNullOrWhiteSpace($mysqlRootPassword)) {
        throw 'MYSQL_ROOT_PASSWORD is missing from the running project MySQL container.'
    }
    if ($mysqlRootPassword -cne [string]$rootPasswordProperty.Value) {
        throw 'MYSQL_ROOT_PASSWORD in the running MySQL container does not match the resolved project configuration.'
    }
    $mysqlRootPassword = $null

    $serverIdentity = Invoke-MySql 'SELECT VERSION(), @@port;'
    $serverIdentityParts = @($serverIdentity -split "`t")
    if ($serverIdentityParts.Count -ne 2 -or $serverIdentityParts[0] -notmatch '^8\.4' -or $serverIdentityParts[1] -ne '3306') {
        throw 'MySQL connection or identity check failed; expected MySQL 8.4 on port 3306.'
    }
    $existingSchemas = Invoke-MySql @'
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name IN ('ibanking_account_db','ibanking_tuition_db','ibanking_payment_db')
ORDER BY schema_name;
'@
    $expectedSchemaList = ($databases | Sort-Object) -join "`n"
    if ($existingSchemas -cne $expectedSchemaList) {
        throw 'Pre-check failed: all three target databases must exist in the verified project MySQL server.'
    }
    $existingTableCount = Invoke-MySql @'
SELECT COUNT(*)
FROM information_schema.tables
WHERE (table_schema='ibanking_account_db' AND table_name IN ('users','accounts','account_debits','schema_migrations'))
   OR (table_schema='ibanking_tuition_db' AND table_name IN ('tuition_bills','tuition_payment_claims','schema_migrations'))
   OR (table_schema='ibanking_payment_db' AND table_name IN ('transactions','otps','schema_migrations'));
'@
    if ($existingTableCount -ne '10') {
        throw 'Pre-check failed: current database schemas do not contain the expected 10 service and migration tables.'
    }

    Write-Host 'Pre-check passed. Verified Compose project, MySQL 8.4 connection, three target schemas, schema files, seeds, and healthy services.'
    Write-Host 'This reset permanently replaces data only in:'
    foreach ($database in $databases) { Write-Host "  $database" }
    Write-Host 'MySQL volume mysql_data, MySQL server, Mailpit, and Docker projects outside ibanking-demo are not reset.'
    $confirmation = Read-Host "Type $resetConfirmation to continue"
    if ($confirmation -cne $resetConfirmation) {
        Write-Host 'Reset cancelled; no database or service state was changed.' -ForegroundColor Yellow
        exit 2
    }

    foreach ($service in $servicesToStop) {
        $container = Get-ProjectContainer $service
        if ($container.State.Status -ne 'running') {
            throw "$service changed state after pre-check; refusing to begin the reset."
        }
        $stopResult = Invoke-Compose @('stop', '--timeout', '60', $service)
        $containerState = $container.State.Status
        $deadline = [DateTime]::UtcNow.AddSeconds(75)
        do {
            $container = Get-ProjectContainer $service
            $containerState = $container.State.Status
            if ($containerState -eq 'exited') { break }
            Start-Sleep -Seconds 1
        } while ([DateTime]::UtcNow -lt $deadline)
        if ($containerState -ne 'running') {
            $stoppedServices.Add($service)
            $servicePhases[$service] = "Not running after stop request ($containerState)"
        }
        if ($stopResult.ExitCode -ne 0) {
            $detail = if ($stopResult.Output) { " Output: $($stopResult.Output)" } else { '' }
            throw "docker compose stop failed for $service (exit $($stopResult.ExitCode), final state $containerState).$detail"
        }
        if ($containerState -ne 'exited') {
            $detail = if ($stopResult.Output) { " Output: $($stopResult.Output)" } else { '' }
            throw "$service did not finish stopping within 75 seconds (final state $containerState).$detail"
        }
    }
    [void](Assert-ContainerHealthy 'mysql')

    $destructiveStarted = $true
    foreach ($database in $databases) {
        [void](Invoke-MySql "DROP DATABASE ``$database``;")
        $databasePhases[$database] = 'Dropped'
    }

    $schemaFiles = @(
        @{ Database = 'ibanking_account_db'; File = 'db/docker-init/01-user-init.sql' },
        @{ Database = 'ibanking_tuition_db'; File = 'db/docker-init/02-tuition-init.sql' },
        @{ Database = 'ibanking_tuition_db'; File = 'db/docker-init/03-tuition-claims.sql' },
        @{ Database = 'ibanking_payment_db'; File = 'db/payment/payment_init.sql' }
    )
    foreach ($schema in $schemaFiles) {
        $sqlPath = Join-Path $root $schema.File
        $sql = [System.IO.File]::ReadAllText($sqlPath)
        [void](Invoke-MySql $sql)
        $databasePhases[$schema.Database] = 'Schema created from init SQL'
    }

    foreach ($database in $databases) {
        $databasePhases[$database] = 'Migration/seed runner in progress; data may be partial'
    }
    $migrationScript = Join-Path $root 'setup-db.ps1'
    try {
        & $migrationScript -ComposeProject $project
    }
    catch {
        throw "setup-db.ps1 migration/seed runner failed: $($_.Exception.Message)"
    }
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "setup-db.ps1 migration/seed runner failed (exit $LASTEXITCODE)."
    }
    foreach ($database in $databases) {
        $databasePhases[$database] = 'Schema, migrations, and seed runner completed'
    }

    Assert-DatabaseReset $seedData
    foreach ($database in $databases) {
        $databasePhases[$database] = 'Schema, migrations, seeds, and data verified; service startup pending'
    }
    Write-Host 'Post-reset database, migration-version, seed-row, and empty transaction/debit/claim verification passed.'

    [void](Assert-ContainerHealthy 'mysql')
    foreach ($service in $servicesToStart) {
        Start-ApplicationService $service
    }
    [void](Assert-ContainerHealthy 'nginx')
    [void](Assert-ContainerHealthy 'mailpit')

    $frontendPort = Get-ConfiguredPort 'FRONTEND_PORT' 8080
    $mailpitPort = Get-ConfiguredPort 'MAILPIT_WEB_PORT' 8025
    Test-LocalHttpEndpoint 'Frontend' $frontendPort
    Test-LocalHttpEndpoint 'Mailpit' $mailpitPort

    foreach ($database in $databases) {
        $databasePhases[$database] = 'Reset and verified'
    }
    Write-Host 'Reset completed successfully.'
    Write-Host "Frontend verified at http://localhost:$frontendPort/"
    Write-Host "Mailpit verified at http://localhost:$mailpitPort/"
    Write-Host 'The mysql_data volume was preserved.'
}
catch {
    Write-Host "RESET FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-FailureState
    if (-not $destructiveStarted -and $stoppedServices.Count -gt 0) {
        Write-Host 'The reset did not begin. Attempting one service recovery for the services stopped by this run.' -ForegroundColor Yellow
        foreach ($service in $servicesToStart) {
            if (-not $stoppedServices.Contains($service)) { continue }
            try {
                Start-ApplicationService $service
            }
            catch {
                $servicePhases[$service] = 'Recovery failed; manual start required'
                Write-Host "Recovery failed for ${service}: $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    }
    elseif ($destructiveStarted) {
        Write-Host 'The database reset started and may be partial. Application services were not automatically restarted.' -ForegroundColor Yellow
        Write-Host "After reviewing the database phases, use: docker compose --env-file .env.docker -f docker-compose.yml --project-directory `"$root`" -p $project up -d user-service tuition-service payment-service nginx"
    }
    exit 1
}
