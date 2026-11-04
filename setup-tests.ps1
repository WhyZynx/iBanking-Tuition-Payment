param(
    [ValidateSet('Prepare', 'Run')]
    [string]$Mode = 'Run'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$venvPython = Join-Path $root '.venv-ibanking-tests\Scripts\python.exe'

function Find-SupportedPython {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        $installedRuntimes = & $launcher.Source -0p 2>$null
        if ($LASTEXITCODE -eq 0) {
            foreach ($runtime in $installedRuntimes) {
                if ($runtime -match '^\s*-V:(3\.(?:12|13))\s+.*?\s{2,}(.+\.exe)\s*$') {
                    return [pscustomobject]@{ Path = $Matches[2] }
                }
            }
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $versionText = & $pythonCommand.Source -c 'import sys; print(sys.version_info[0], sys.version_info[1], sep=chr(46))'
        if ($LASTEXITCODE -eq 0 -and $versionText -in @('3.12', '3.13')) {
            return [pscustomobject]@{ Path = $pythonCommand.Source }
        }
    }
    throw 'Python 3.12 or 3.13 is required. Install one from python.org and retry; no global packages were changed.'
}

if ($Mode -eq 'Prepare') {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        if (Test-Path -LiteralPath (Split-Path -Parent $venvPython)) {
            throw '.venv-ibanking-tests exists but is incomplete; preserve it and inspect it before retrying.'
        }
        $pythonCommand = Find-SupportedPython
        & $pythonCommand.Path -m venv (Join-Path $root '.venv-ibanking-tests')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated test virtual environment.' }
    }
    $venvVersion = & $venvPython -c 'import sys; print(sys.version_info[0], sys.version_info[1], sep=chr(46))'
    if ($LASTEXITCODE -ne 0 -or $venvVersion -notin @('3.12', '3.13')) {
        throw '.venv-ibanking-tests must use Python 3.12 or 3.13; it was not replaced.'
    }
    & $venvPython -m pip install --disable-pip-version-check -r (Join-Path $root 'requirements-test.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Could not install test dependencies into .venv-ibanking-tests.' }
    Write-Host "Prepared isolated pytest environment: $venvVersion"
    return
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'The test environment is not prepared. Open the Setup Menu and choose Tests > Prepare test environment.'
}
& $venvPython -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Default safe pytest suite failed; see the report above.' }
