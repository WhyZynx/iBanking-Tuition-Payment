$ErrorActionPreference = 'Stop'
$target = Join-Path $PSScriptRoot '.env.docker'
if (Test-Path -LiteralPath $target) { exit 0 }

function New-Secret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
}

$templatePath = Join-Path $PSScriptRoot '.env.docker.example'
if (-not (Test-Path -LiteralPath $templatePath)) { throw '.env.docker.example template is missing' }
$content = [System.IO.File]::ReadAllText($templatePath)
$content = $content.Replace('MYSQL_ROOT_PASSWORD=GENERATE_WITH_SETUP_SCRIPT', "MYSQL_ROOT_PASSWORD=$(New-Secret)")
$content = $content.Replace('JWT_SECRET_KEY=GENERATE_WITH_SETUP_SCRIPT', "JWT_SECRET_KEY=$(New-Secret)")
$content = $content.Replace('INTERNAL_API_KEY=GENERATE_WITH_SETUP_SCRIPT', "INTERNAL_API_KEY=$(New-Secret)")
Set-Content -LiteralPath $target -Value $content -Encoding ascii -NoNewline
if (-not (Test-Path -LiteralPath $target)) { throw 'Could not create .env.docker' }
