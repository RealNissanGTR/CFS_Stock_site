param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000,
    [switch]$UseHttps,
    [string]$SslCertFile = "",
    [string]$SslKeyFile = ""
)

$backendDir = "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
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
    $pythonResult = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonResult) {
        throw "Python was not found. Install Python and try again."
    }
    $pythonCmd = $pythonResult.Source
    $pythonArgs = @("-m", "uvicorn", "main:app", "--host", $BindHost, "--port", $Port.ToString())
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

while ($true) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $logFile = Join-Path $logDir "uvicorn-$timestamp.log"
    $errFile = Join-Path $logDir "uvicorn-$timestamp.err.log"

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

    if (Test-Path $errFile) {
        $errContent = Get-Content $errFile -ErrorAction SilentlyContinue
        if ($errContent) {
            Add-Content -Path $logFile -Value ""
            Add-Content -Path $logFile -Value "----- STDERR -----"
            Add-Content -Path $logFile -Value $errContent
        }
        Remove-Item $errFile -Force -ErrorAction SilentlyContinue
    }

    Write-Host "uvicorn stopped. Restarting in 3 seconds..."
    Start-Sleep -Seconds 3
}


<# 
cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r "..\..\requirements.txt"
powershell -ExecutionPolicy Bypass -File "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend\start_uvicorn.ps1"
#>