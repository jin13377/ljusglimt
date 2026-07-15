$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$localConfig = Join-Path $root "config\local.env"
if (Test-Path $localConfig) {
    Get-Content $localConfig | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

function Test-LjusglimtApi([string]$Url) {
    try {
        $health = Invoke-RestMethod $Url -TimeoutSec 1
        return ($health.ok -and $health.service -eq "ljusglimt")
    } catch {
        return $false
    }
}

function Test-WebUrl([string]$Url) {
    try {
        $response = Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 1
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    } catch {
        return $false
    }
}

$apiPort = if ($env:GLIMT_API_PORT) { $env:GLIMT_API_PORT } else { "4173" }
$webPort = if ($env:GLIMT_WEB_PORT) { $env:GLIMT_WEB_PORT } else { "5173" }
$healthUrl = "http://127.0.0.1:$apiPort/api/health"
$distIndex = Join-Path $root "dist\index.html"
$packageFile = Join-Path $root "package.json"

if (Test-Path $distIndex) {
    $siteUrl = "http://127.0.0.1:$apiPort"
    if (-not (Test-LjusglimtApi $healthUrl)) {
        Start-Process -FilePath "python" -ArgumentList "server.py" -WorkingDirectory $root -WindowStyle Hidden
    }
} elseif (Test-Path $packageFile) {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        throw "Node.js saknas. Installera Node.js och kör sedan startfilen igen."
    }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm saknas. Installera Node.js med npm och försök igen."
    }
    $siteUrl = "http://127.0.0.1:$webPort"
    if (-not (Test-WebUrl $siteUrl)) {
        Start-Process -FilePath "node" -ArgumentList "scripts/dev.mjs" -WorkingDirectory $root -WindowStyle Hidden
    } elseif (-not (Test-LjusglimtApi $healthUrl)) {
        Start-Process -FilePath "python" -ArgumentList "server.py" -WorkingDirectory $root -WindowStyle Hidden
    }
} else {
    # Bakåtkompatibelt läge för den äldre, beroendefria frontendversionen.
    $siteUrl = "http://127.0.0.1:$apiPort"
    if (-not (Test-LjusglimtApi $healthUrl)) {
        Start-Process -FilePath "python" -ArgumentList "server.py" -WorkingDirectory $root -WindowStyle Hidden
    }
}

for ($attempt = 0; $attempt -lt 20; $attempt++) {
    if ((Test-LjusglimtApi $healthUrl) -and (Test-WebUrl $siteUrl)) { break }
    Start-Sleep -Milliseconds 500
}
if (-not (Test-LjusglimtApi $healthUrl)) { throw "Ljusglimt-API:t startade inte på $healthUrl." }
if (-not (Test-WebUrl $siteUrl)) { throw "Webbgränssnittet startade inte på $siteUrl." }

Start-Process $siteUrl
Write-Host "Ljusglimt kör på $siteUrl" -ForegroundColor Green
