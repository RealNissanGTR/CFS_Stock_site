param(
    [switch]$InstallPython,
    [switch]$SkipPythonInstall
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$backendDir = Join-Path $repoRoot "Webapp\Backend"
$requirementsPath = Join-Path $repoRoot "requirements.txt"
$venvDir = Join-Path $backendDir "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

function Find-Python {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return @{ Exe = $pythonCmd.Source; UsePyLauncher = $false }
    }

    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        return @{ Exe = $pyCmd.Source; UsePyLauncher = $true }
    }

    return $null
}

function Ensure-Python {
    $pythonInfo = Find-Python
    if ($pythonInfo) {
        return $pythonInfo
    }

    Write-Host "Python was not found on this machine."

    $shouldInstall = $false
    if ($InstallPython) {
        $shouldInstall = $true
    }
    elseif ($SkipPythonInstall) {
        $shouldInstall = $false
    }
    else {
        $answer = Read-Host "Install Python automatically now using winget? (Y/N)"
        $shouldInstall = $answer -match "^(?i)y(es)?$"
    }

    if (-not $shouldInstall) {
        throw "Python is required. Install Python from https://www.python.org/downloads/ and rerun this script."
    }

    $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $wingetCmd) {
        throw "winget was not found. Install Python manually from https://www.python.org/downloads/ and rerun this script."
    }

    Write-Host "Installing Python with winget..."
    & $wingetCmd.Source install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements

    $pythonInfo = Find-Python
    if ($pythonInfo) {
        return $pythonInfo
    }

    $candidatePaths = @(
        "$env:LocalAppData\Programs\Python\Python312\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:LocalAppData\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python311\python.exe"
    )

    foreach ($candidate in $candidatePaths) {
        if (Test-Path $candidate) {
            return @{ Exe = $candidate; UsePyLauncher = $false }
        }
    }

    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        return @{ Exe = $pyCmd.Source; UsePyLauncher = $true }
    }

    throw "Python installation completed, but Python was not found in this terminal session. Open a new PowerShell window and rerun .\\Scripts\\First_setup.ps1."
}

if (-not (Test-Path $backendDir)) {
    throw "Backend folder not found: $backendDir"
}

if (-not (Test-Path $requirementsPath)) {
    throw "requirements.txt not found: $requirementsPath"
}

$existingPython = Find-Python
if ($existingPython) {
    Write-Host "Python is already installed on this device: $($existingPython.Exe)"
    Write-Host "Skipping setup and exiting without changes."
    exit 0
}

$pythonInfo = Ensure-Python

Push-Location $backendDir
try {
    if (-not (Test-Path $venvDir)) {
        Write-Host "Creating virtual environment..."
        if ($pythonInfo.UsePyLauncher) {
            & $pythonInfo.Exe -3 -m venv venv
        }
        else {
            & $pythonInfo.Exe -m venv venv
        }
    }
    else {
        Write-Host "Using existing virtual environment at: $venvDir"
    }

    if (-not (Test-Path $venvPython)) {
        throw "Virtual environment python executable not found: $venvPython"
    }

    Write-Host "Installing/upgrading dependencies..."
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r $requirementsPath
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "To start the app:"
Write-Host "1) cd \"$backendDir\""
Write-Host "2) .\venv\Scripts\Activate.ps1"
Write-Host "3) uvicorn main:app --host 0.0.0.0 --port 8000 --reload"