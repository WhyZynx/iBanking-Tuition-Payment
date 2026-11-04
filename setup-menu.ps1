$ErrorActionPreference = 'Stop'
$project = 'ibanking-demo'
$envPath = Join-Path $PSScriptRoot '.env.docker'
$sqlPath = Join-Path $PSScriptRoot 'db/demo-data-view.sql'

function Get-EnvValues {
    $values = @{}
    foreach ($line in [System.IO.File]::ReadAllLines($envPath)) {
        if ($line -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { $values[$Matches[1]] = $Matches[2] }
    }
    return $values
}

function Get-SmtpMode {
    $values = Get-EnvValues
    if ($values['SMTP_HOST'] -eq 'smtp.gmail.com') { return 'Gmail SMTP' }
    if ($values['SMTP_HOST'] -eq 'mailpit') { return 'Mailpit' }
    return 'Custom SMTP'
}

function Get-LocalUrl([string]$portName, [string]$defaultPort) {
    $values = Get-EnvValues
    $port = $values[$portName]
    if ($port -notmatch '^\d{1,5}$') { $port = $defaultPort }
    return "http://localhost:$port"
}

function Restart-PaymentService {
    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & docker compose --env-file $envPath -p $project up -d --no-deps --wait --wait-timeout 120 payment-service *> $null
        return ($LASTEXITCODE -eq 0)
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
}

function Set-SmtpConfig([hashtable]$settings) {
    $oldBytes = [System.IO.File]::ReadAllBytes($envPath)
    $lines = [System.IO.File]::ReadAllLines($envPath)
    $remaining = @{}
    foreach ($key in $settings.Keys) { $remaining[$key] = $settings[$key] }
    $updated = foreach ($line in $lines) {
        if ($line -match '^([A-Za-z_][A-Za-z0-9_]*)=') {
            $key = $Matches[1]
            if ($remaining.ContainsKey($key)) {
                $value = [string]$remaining[$key]
                $remaining.Remove($key)
                "$key=$value"
                continue
            }
        }
        $line
    }
    foreach ($key in $remaining.Keys) { $updated += "$key=$($remaining[$key])" }

    $tempPath = "$envPath.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        if ($IsWindows -or $env:OS -eq 'Windows_NT') {
            [System.IO.File]::WriteAllText($tempPath, '', [System.Text.UTF8Encoding]::new($false))
            $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
            & icacls.exe $tempPath /inheritance:r /grant:r "${identity}:F" 'SYSTEM:F' 'BUILTIN\Administrators:F' *> $null
            if ($LASTEXITCODE -ne 0) { throw 'Could not restrict .env.docker file permissions.' }
        }
        else {
            [System.IO.File]::WriteAllText($tempPath, '', [System.Text.UTF8Encoding]::new($false))
            & chmod 600 $tempPath
            if ($LASTEXITCODE -ne 0) { throw 'Could not restrict .env.docker file permissions.' }
        }
        [System.IO.File]::WriteAllLines($tempPath, [string[]]$updated, [System.Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $tempPath -Destination $envPath -Force

        if (-not (Restart-PaymentService)) {
            [System.IO.File]::WriteAllBytes($envPath, $oldBytes)
            [void](Restart-PaymentService)
            Write-Host 'SMTP configuration was not applied. The previous configuration was restored.' -ForegroundColor Yellow
            return $false
        }
        return $true
    }
    catch {
        [System.IO.File]::WriteAllBytes($envPath, $oldBytes)
        Write-Host 'SMTP configuration could not be saved or applied. The previous configuration was restored.' -ForegroundColor Yellow
        return $false
    }
    finally {
        if (Test-Path -LiteralPath $tempPath) { Remove-Item -LiteralPath $tempPath -Force }
    }
}

function Set-Mailpit {
    $settings = @{
        SMTP_HOST = 'mailpit'; SMTP_PORT = '1025'; SMTP_USERNAME = '';
        SMTP_PASSWORD = ''; SMTP_FROM_EMAIL = 'ibanking@example.test'; SMTP_STARTTLS = 'false'
    }
    if (Set-SmtpConfig $settings) { Write-Host 'Mailpit configuration applied to Payment Service.' -ForegroundColor Green }
}

function Set-Gmail {
    Write-Host 'Gmail requires Google 2-Step Verification and a Google App Password.'
    Write-Host 'The App Password is stored only in the ignored .env.docker file and is never displayed.'
    $address = (Read-Host 'Gmail sender address').Trim()
    if ($address -notmatch '^[^\s@]+@gmail\.com$') {
        Write-Host 'Enter a valid @gmail.com sender address.' -ForegroundColor Yellow
        return
    }
    $securePassword = Read-Host 'Gmail App Password' -AsSecureString
    $pointer = [IntPtr]::Zero
    $plainPassword = $null
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
        $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) -replace '\s', ''
        if ([string]::IsNullOrWhiteSpace($plainPassword)) {
            Write-Host 'An App Password is required.' -ForegroundColor Yellow
            return
        }
        $settings = @{
            SMTP_HOST = 'smtp.gmail.com'; SMTP_PORT = '587'; SMTP_USERNAME = $address;
            SMTP_PASSWORD = $plainPassword; SMTP_FROM_EMAIL = $address; SMTP_STARTTLS = 'true'
        }
        if (Set-SmtpConfig $settings) {
            Write-Host 'Gmail SMTP configuration applied to Payment Service. Delivery has not been tested.' -ForegroundColor Green
            Write-Host 'OTP still goes to the email address registered on the paying user.'
        }
    }
    finally {
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
        $plainPassword = $null
        $securePassword.Dispose()
    }
}

function Show-EmailMenu {
    while ($true) {
        Write-Host ''
        Write-Host '========================================'
        Write-Host ' Email Delivery Configuration'
        Write-Host '========================================'
        Write-Host "Current Mode: $(Get-SmtpMode)"
        Write-Host '[1] Use Mailpit (Local Testing)'
        Write-Host '[2] Use Gmail SMTP (Real Email)'
        Write-Host '[0] Back to Main Menu'
        $choice = Read-Host 'Choose an option'
        switch ($choice.Trim()) {
            '1' { Set-Mailpit; return }
            '2' { Set-Gmail; return }
            '0' { return }
            default { Write-Host 'Please enter 1, 2, or 0.' -ForegroundColor Yellow }
        }
    }
}

function Show-DemoData {
    if (-not (Test-Path -LiteralPath $sqlPath)) {
        Write-Host 'Demo data query file is missing.' -ForegroundColor Yellow
    }
    else {
        try {
            $sql = [System.IO.File]::ReadAllText($sqlPath)
            $composeArgs = @('compose', '--env-file', $envPath, '-p', $project, 'exec', '-T', 'mysql', 'sh', '-c', 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql -uroot --table')
            $sql | & docker @composeArgs
            if ($LASTEXITCODE -ne 0) {
                Write-Host 'Could not read current demo data. Check that MySQL is running and initialized.' -ForegroundColor Yellow
                Write-Host "Troubleshooting: docker compose --env-file .env.docker -p $project logs --tail=80 mysql"
            }
        }
        catch {
            Write-Host 'Could not read current demo data. Check Docker Compose and MySQL availability.' -ForegroundColor Yellow
            Write-Host "Troubleshooting: docker compose --env-file .env.docker -p $project ps"
        }
    }
    [void](Read-Host 'Press Enter to return to the menu')
}


function Invoke-ConcurrencyTest([string]$testPath) {
    Write-Host ''
    Write-Host 'WARNING: This test may modify the demo database.' -ForegroundColor Yellow
    Write-Host 'It can create real transactions and mark tuition as PAID.' -ForegroundColor Yellow

    $approval = Read-Host 'Continue? (Y/N)'
    if ($approval.Trim().ToUpper() -ne 'Y') {
        Write-Host 'Test cancelled.' -ForegroundColor Yellow
        return
    }

    $pythonPath = Join-Path $PSScriptRoot '.venv-ibanking-tests\Scripts\python.exe'

    if (-not (Test-Path -LiteralPath $pythonPath)) {
        $pythonPath = 'python'
    }

    $previousApproval = $env:IBANKING_DEMO_CONCURRENCY_APPROVAL

    try {
        $env:IBANKING_DEMO_CONCURRENCY_APPROVAL = 'YES'

        Write-Host ''
        Write-Host "Running: $testPath" -ForegroundColor Cyan
        Write-Host '----------------------------------------'

        & $pythonPath -m pytest $testPath -m demo_live -v -s

        $exitCode = $LASTEXITCODE

        Write-Host ''
        if ($exitCode -eq 0) {
            Write-Host 'Test completed successfully.' -ForegroundColor Green
        }
        else {
            Write-Host "Test finished with exit code $exitCode." -ForegroundColor Red
        }
    }
    finally {
        $env:IBANKING_DEMO_CONCURRENCY_APPROVAL = $previousApproval
    }

    [void](Read-Host 'Press Enter to return to the menu')
}

function Show-ConcurrencyMenu {
    while ($true) {
        Write-Host ''
        Write-Host '========================================'
        Write-Host ' Concurrency Testing'
        Write-Host '========================================'
        Write-Host '[1] Same Account - Two Students'
        Write-Host '[2] Two Payer - Same Student'
        Write-Host '[3] Run Both Tests'
        Write-Host '[0] Back to Main Menu'

        $choice = Read-Host 'Choose an option'

        switch ($choice.Trim()) {
            '1' {
                Invoke-ConcurrencyTest `
                    'tests/payment_service/test_payment_concurrency_same_account.py'
            }
            '2' {
                Invoke-ConcurrencyTest `
                    'tests/payment_service/test_demo_two_payer_concurrency.py'
            }
            '3' {
                Invoke-ConcurrencyTest `
                    'tests/payment_service/test_payment_concurrency_same_account.py'

                Invoke-ConcurrencyTest `
                    'tests/payment_service/test_demo_two_payer_concurrency.py'
            }
            '0' { return }
            default {
                Write-Host 'Please enter 1, 2, 3, or 0.' -ForegroundColor Yellow
            }
        }
    }
}


while ($true) {
    Write-Host ''
    Write-Host '[1] View current demo data'
    Write-Host '[2] Open iBanking frontend'
    Write-Host '[3] Open Mailpit inbox'
    Write-Host '[4] Configure email delivery'
    Write-Host '[5] Run concurrency tests'
    Write-Host '[0] Exit setup (keep services running)'
    $choice = Read-Host 'Choose an option'
    switch ($choice.Trim()) {
        '1' { Show-DemoData }
        '2' { Start-Process (Get-LocalUrl 'FRONTEND_PORT' '8080') }
        '3' { Start-Process (Get-LocalUrl 'MAILPIT_WEB_PORT' '8025') }
        '4' { Show-EmailMenu }
        '5' { Show-ConcurrencyMenu }
        '0' { exit 0 }
        default { Write-Host 'Please enter 1, 2, 3, 4, 5, or 0.' -ForegroundColor Yellow }
    }
}
