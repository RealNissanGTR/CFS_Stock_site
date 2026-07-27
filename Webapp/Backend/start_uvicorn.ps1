param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000
)

$backendDir = "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
$venvPython = Join-Path $backendDir "venv\Scripts\python.exe"
$logDir = Join-Path $backendDir "logs"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

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

while ($true) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $logFile = Join-Path $logDir "uvicorn-$timestamp.log"
    $errFile = Join-Path $logDir "uvicorn-$timestamp.err.log"

    Write-Host ("Starting uvicorn on {0}:{1}" -f $BindHost, $Port)
    Write-Host ("Log file: {0}" -f $logFile)

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