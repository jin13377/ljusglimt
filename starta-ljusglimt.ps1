$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$healthUrl = "http://127.0.0.1:4173/api/health"
$siteUrl = "http://127.0.0.1:4173"

try {
    $health = Invoke-RestMethod $healthUrl -TimeoutSec 2
} catch {
    Start-Process -FilePath "python" -ArgumentList "server.py" -WorkingDirectory $root -WindowStyle Hidden
    Start-Sleep -Milliseconds 900
    $health = Invoke-RestMethod $healthUrl -TimeoutSec 5
}

if (-not $health.ok) {
    throw "Ljusglimt-servern svarade inte korrekt."
}

Start-Process $siteUrl
Write-Host "Ljusglimt kör på $siteUrl" -ForegroundColor Green
