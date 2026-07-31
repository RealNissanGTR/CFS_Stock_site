param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000,
    [switch]$UseHttps,
    [string]$SslCertFile = "",
    [string]$SslKeyFile = ""
)

$mutexName = "Global\CFS_Stock_Uvicorn_Launcher"
$scriptMutex = New-Object System.Threading.Mutex($false, $mutexName)
$hasMutex = $false

try {
    $hasMutex = $scriptMutex.WaitOne(0, $false)
}
catch {
    $hasMutex = $false
}

if (-not $hasMutex) {
    Write-Host "Another start_uvicorn.ps1 instance is already running. Exiting to avoid duplicate servers and log spam."
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$backendDir = Join-Path $repoRoot "Webapp\Backend"
$venvPython = Join-Path $backendDir "venv\Scripts\python.exe"
$logDir = Join-Path $backendDir "logs"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$firewallRuleName = "CFS Stock TCP $Port"
try {
    $existingRule = Get-NetFirewallRule -DisplayName $firewallRuleName -ErrorAction SilentlyContinue
    if (-not $existingRule) {
        New-NetFirewallRule `
            -DisplayName $firewallRuleName `
            -Direction Inbound `
            -Action Allow `
            -Protocol TCP `
            -LocalPort $Port `
            -Profile Private | Out-Null
        Write-Host ("Added Windows Firewall rule for TCP {0} on Private networks" -f $Port)
    }
}
catch {
    Write-Host "Could not add Windows Firewall rule automatically (run PowerShell as Administrator to allow this)."
}

$lanIps = @()
try {
    $lanIps = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -and
            $_.IPAddress -ne "127.0.0.1" -and
            (
                $_.IPAddress.StartsWith("192.168.") -or
                $_.IPAddress.StartsWith("10.") -or
                $_.IPAddress -match '^172\.(1[6-9]|2[0-9]|3[0-1])\.'
            )
        } |
        Select-Object -ExpandProperty IPAddress -Unique
}
catch {
    $lanIps = @()
}

$pythonCmd = $null
$pythonArgs = @()

if (Test-Path $venvPython) {
    $pythonCmd = $venvPython
    $pythonArgs = @("-m", "uvicorn", "main:app", "--host", $BindHost, "--port", $Port.ToString())
}
else {
    throw "Virtual environment Python not found at '$venvPython'. Run .\\Startup_Scripts\\First_setup.ps1 from the repository root to create the environment and install requirements."
}

$scheme = "http"
if ($UseHttps) {
    if ([string]::IsNullOrWhiteSpace($SslCertFile) -or [string]::IsNullOrWhiteSpace($SslKeyFile)) {
        throw "HTTPS enabled but certificate or key path is missing. Provide -SslCertFile and -SslKeyFile."
    }

    if (-not (Test-Path $SslCertFile)) {
        throw "SSL certificate file not found: $SslCertFile"
    }

    if (-not (Test-Path $SslKeyFile)) {
        throw "SSL key file not found: $SslKeyFile"
    }

    $resolvedCert = (Resolve-Path $SslCertFile).Path
    $resolvedKey = (Resolve-Path $SslKeyFile).Path
    $pythonArgs += @("--ssl-certfile", $resolvedCert, "--ssl-keyfile", $resolvedKey)
    $scheme = "https"
}

function Get-ListeningProcessOnPort {
    param([int]$LocalPort)

    try {
        $listener = Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction Stop |
            Select-Object -First 1
        if ($listener) {
            return Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
        }
    }
    catch {
        return $null
    }

    return $null
}

$existingPortOwner = Get-ListeningProcessOnPort -LocalPort $Port
if ($existingPortOwner) {
    Write-Host ("Port {0} is already in use by PID {1} ({2}). Exiting to prevent restart loops." -f $Port, $existingPortOwner.Id, $existingPortOwner.ProcessName)
    if ($hasMutex) {
        $scriptMutex.ReleaseMutex() | Out-Null
        $scriptMutex.Dispose()
    }
    exit 0
}

try {
    while ($true) {
        $dateTag = Get-Date -Format "yyyyMMdd"
        $logFile = Join-Path $logDir "uvicorn-$dateTag.log"
        $errFile = Join-Path $logDir "uvicorn-$dateTag.err.log"
        $startedAt = Get-Date

        Write-Host ("Starting uvicorn on {0}://{1}:{2}" -f $scheme, $BindHost, $Port)
        Write-Host ("Log file: {0}" -f $logFile)
        if ($lanIps.Count -gt 0) {
            foreach ($ip in $lanIps) {
                Write-Host ("Try from other devices: {0}://{1}:{2}" -f $scheme, $ip, $Port)
            }
        }
        else {
            Write-Host "No LAN IPv4 address detected. Ensure this PC is connected to your local network."
        }

        $proc = Start-Process -FilePath $pythonCmd `
            -ArgumentList $pythonArgs `
            -WorkingDirectory $backendDir `
            -RedirectStandardOutput $logFile `
            -RedirectStandardError $errFile `
            -PassThru

        $proc.WaitForExit()
        $runSeconds = ((Get-Date) - $startedAt).TotalSeconds
        $hasAddressInUseError = $false

        if (Test-Path $errFile) {
            $errContent = Get-Content $errFile -ErrorAction SilentlyContinue
            if ($errContent) {
                Add-Content -Path $logFile -Value ""
                Add-Content -Path $logFile -Value "----- STDERR -----"
                Add-Content -Path $logFile -Value $errContent
                $joinedErr = ($errContent -join "`n")
                if ($joinedErr -match "10048|Only one usage of each socket address") {
                    $hasAddressInUseError = $true
                }
            }
            Remove-Item $errFile -Force -ErrorAction SilentlyContinue
        }

        if ($hasAddressInUseError) {
            Write-Host ("Detected socket bind error on port {0} (Errno 10048). Another process is already bound. Exiting launcher to prevent infinite log creation." -f $Port)
            break
        }

        if ($runSeconds -lt 10) {
            Write-Host "uvicorn exited quickly. Restarting in 30 seconds to reduce log noise..."
            Start-Sleep -Seconds 30
        }
        else {
            Write-Host "uvicorn stopped. Restarting in 3 seconds..."
            Start-Sleep -Seconds 3
        }
    }
}
finally {
    if ($hasMutex) {
        $scriptMutex.ReleaseMutex() | Out-Null
    }
    $scriptMutex.Dispose()
}