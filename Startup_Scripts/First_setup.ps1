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
$minimumPythonVersion = [version]"3.10"

function Find-Python {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return @{ Exe = $pythonCmd.Source; UsePyLauncher = $false }
    }

    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        return @{ Exe = $pyCmd.Source; UsePyLauncher = $true }
    }

    # Fallback for machines where Python is installed but not on PATH.
    $installRoots = @(
        (Join-Path $env:LocalAppData "Programs\Python"),
        "${env:ProgramFiles}\Python",
        "${env:ProgramFiles(x86)}\Python"
    )

    foreach ($root in $installRoots) {
        if (-not $root -or -not (Test-Path $root)) {
            continue
        }

        $pythonDirs = Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^Python\d+' } |
            Sort-Object Name -Descending

        foreach ($dir in $pythonDirs) {
            $candidate = Join-Path $dir.FullName "python.exe"
            if (Test-Path $candidate) {
                Write-Host "Detected Python at $candidate (not on PATH)."
                return @{ Exe = $candidate; UsePyLauncher = $false }
            }
        }
    }

    return $null
}

function Get-PythonVersion([hashtable]$pythonInfo) {
    try {
        if ($pythonInfo.UsePyLauncher) {
            $versionText = & $pythonInfo.Exe -3 -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}')"
        }
        else {
            $versionText = & $pythonInfo.Exe -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}')"
        }

        if (-not $versionText) {
            return $null
        }

        return [version]($versionText.Trim())
    }
    catch {
        return $null
    }
}

function Ensure-Python {
    $pythonInfo = Find-Python
    if ($pythonInfo) {
        $detectedVersion = Get-PythonVersion $pythonInfo
        if ($detectedVersion -and $detectedVersion -ge $minimumPythonVersion) {
            Write-Host "Detected Python $detectedVersion (meets minimum $minimumPythonVersion)."
            return $pythonInfo
        }

        if ($detectedVersion) {
            Write-Host "Detected Python $detectedVersion, but version $minimumPythonVersion or higher is required."
        }
        else {
            Write-Host "Python was detected, but its version could not be verified."
        }
    }

    if (-not $pythonInfo) {
        Write-Host "Python was not found on this machine."
    }

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
            $candidateInfo = @{ Exe = $candidate; UsePyLauncher = $false }
            $candidateVersion = Get-PythonVersion $candidateInfo
            if ($candidateVersion -and $candidateVersion -ge $minimumPythonVersion) {
                return $candidateInfo
            }
        }
    }

    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        $launcherInfo = @{ Exe = $pyCmd.Source; UsePyLauncher = $true }
        $launcherVersion = Get-PythonVersion $launcherInfo
        if ($launcherVersion -and $launcherVersion -ge $minimumPythonVersion) {
            return $launcherInfo
        }
    }

    throw "Python $minimumPythonVersion or higher is required. Open a new PowerShell window and rerun .\\Startup_Scripts\\First_setup.ps1."
}

if (-not (Test-Path $backendDir)) {
    throw "Backend folder not found: $backendDir"
}

if (-not (Test-Path $requirementsPath)) {
    throw "requirements.txt not found: $requirementsPath"
}

$existingPython = Find-Python
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