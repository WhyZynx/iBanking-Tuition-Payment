
param(
    [ValidateSet('Prepare', 'Run')]
    [string]$Mode = 'Run'
)

$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$toolsDir = Join-Path $root '.tools'
$uvBin = Join-Path $toolsDir 'uv.exe'
$venvDir = Join-Path $root '.venv-ibanking-tests'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$requirements = Join-Path $root 'requirements-test.txt'

# Keep uv-managed Python and cache inside the project
$env:UV_PYTHON_INSTALL_DIR = Join-Path $toolsDir 'python'
$env:UV_CACHE_DIR = Join-Path $root '.cache\uv'

function Install-LocalUv {
    if (-not (Test-Path -LiteralPath $uvBin)) {
        Write-Host 'Installing uv locally...'

        New-Item -ItemType Directory -Force -Path $toolsDir |
            Out-Null

        $env:UV_INSTALL_DIR = $toolsDir

        try {
            Invoke-RestMethod 'https://astral.sh/uv/install.ps1' |
                Invoke-Expression
        }
        finally {
            Remove-Item Env:UV_INSTALL_DIR -ErrorAction SilentlyContinue
        }
    }

    if (-not (Test-Path -LiteralPath $uvBin)) {
        throw 'uv installation failed.'
    }
}

function Prepare-TestEnvironment {
    if (-not (Test-Path -LiteralPath $requirements)) {
        throw 'requirements-test.txt not found.'
    }

    Install-LocalUv

    # Install Python 3.13 independently of system Python
    Write-Host 'Installing Python 3.13...'
    & $uvBin python install 3.13

    if ($LASTEXITCODE -ne 0) {
        throw 'Could not install Python 3.13.'
    }

    # Check existing virtual environment
    if (Test-Path -LiteralPath $venvPython) {
        $version = & $venvPython -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'

        if ($LASTEXITCODE -ne 0 -or $version.Trim() -ne '3.13') {
            Write-Host 'Existing environment is incompatible. Recreating...'
            Remove-Item -LiteralPath $venvDir -Recurse -Force
        }
    }
    elseif (Test-Path -LiteralPath $venvDir) {
        throw '.venv-ibanking-tests exists but is incomplete; inspect it before retrying.'
    }

    # Create virtual environment
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host 'Creating virtual environment...'

        & $uvBin venv --python 3.13 $venvDir

        if ($LASTEXITCODE -ne 0) {
            throw 'Could not create the isolated test virtual environment.'
        }
    }

    # Install test dependencies
    Write-Host 'Installing test dependencies...'

    & $uvBin pip install `
        --python $venvPython `
        -r $requirements

    if ($LASTEXITCODE -ne 0) {
        throw 'Could not install test dependencies.'
    }

    $venvVersion = & $venvPython --version

    Write-Host "Prepared isolated pytest environment: $venvVersion"
}

function Run-Tests {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        throw 'The test environment is not prepared. Open the Setup Menu and choose Tests > Prepare test environment.'
    }

    & $venvPython -m pytest -q

    if ($LASTEXITCODE -ne 0) {
        throw 'Default safe pytest suite failed; see the report above.'
    }
}

if ($Mode -eq 'Prepare') {
    Prepare-TestEnvironment
    return
}

Run-Tests
