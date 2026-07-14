$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$healthUrl = "http://127.0.0.1:4173/api/health"
$siteUrl = "http://127.0.0.1:4173"

$localConfig = Join-Path $root "config\local.env"
if (Test-Path $localConfig) {
    Get-Content $localConfig | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

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
