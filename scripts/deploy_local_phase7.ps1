$ErrorActionPreference = 'Stop'
$paoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $paoRoot
try {
    $paoPython = Join-Path $paoRoot '.venv\Scripts\python.exe'
    & $paoPython scripts/deploy_phase7.py --check
    if ($LASTEXITCODE -ne 0) { throw 'PAO has active work; deployment stopped.' }
    $paoRecords = Get-Content .runtime/processes.json -Raw | ConvertFrom-Json -AsHashtable
    foreach ($paoName in @('web','telegram','api','worker')) {
        $paoOld = $paoRecords[$paoName]
        if (-not $paoOld) { continue }
        $paoRunning = Get-Process -Id $paoOld.id -ErrorAction SilentlyContinue
        if ($paoRunning -and $paoRunning.StartTime.ToUniversalTime().Ticks -eq $paoOld.started) {
            taskkill /PID $paoOld.id /T /F
            if ($LASTEXITCODE -ne 0) { throw "Could not stop verified PAO service: $paoName" }
        }
    }
    & $paoPython scripts/deploy_phase7.py
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed. Inspect the backup before restarting.' }
    & (Join-Path $PSScriptRoot 'start_local.ps1')
} finally { Pop-Location }
