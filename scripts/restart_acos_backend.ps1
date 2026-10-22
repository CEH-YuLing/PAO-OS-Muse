# S1.1: replace only owned idle API/ARQ processes; no Docker/Web/flags/schema changes.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Split-Path $PSScriptRoot -Parent)).Path
if ($repoRoot -ne 'F:\PAO-ACOS') { throw 'ACOS checkout required.' }
$runtime = Join-Path $repoRoot '.runtime'
$recordsPath = Join-Path $runtime 'acos-processes.json'
. (Join-Path $PSScriptRoot 'get_acos_python.ps1')
$pythonExe = (Resolve-Path -LiteralPath (Get-AcosPython $repoRoot)).Path
$records = Get-Content -LiteralPath $recordsPath -Raw | ConvertFrom-Json
$env:PAO_ROOT = $repoRoot
$env:PYTHONPATH = @((Join-Path $repoRoot 'apps\api'), (Join-Path $repoRoot 'packages\cli-runtime')) -join [IO.Path]::PathSeparator
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
Push-Location $repoRoot
try {
    & $pythonExe -B scripts/check_acos_startup_schema.py --expected 0077
    if ($LASTEXITCODE -ne 0) { throw 'Schema gate failed; nothing stopped or migrated.' }
    $telegramEnabled = & $pythonExe -c 'from pao.config import settings; c=settings(); print(int(c.telegram_scoped_runtime_enabled and not c.telegram_enabled and c.channels_enabled))'
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read scoped Telegram worker gate.' }
    $ownedNames = @('api','worker')
    if ($records.telegram) { $ownedNames += 'telegram' }
    $scopedWorkers = @(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $pythonExe -and $_.CommandLine -match '-m\s+arq\s+pao.modules.channels.telegram_worker.WorkerSettings' })
    foreach ($candidate in $scopedWorkers) {
        if (-not $records.telegram -or $candidate.ProcessId -ne $records.telegram.id) { throw 'Untracked scoped Telegram worker; nothing stopped. Verify its owner before restarting.' }
    }
    & $pythonExe scripts/check_acos_idle.py --safe-repair
    if ($LASTEXITCODE -ne 0) { throw 'Idle/safety gate failed; nothing stopped.' }
    # Validate both identities before stopping either. No guessed PIDs or broad kill.
    foreach ($name in $ownedNames) {
        $record = $records.$name
        if (-not $record) { throw "Missing $name process record." }
        $process = Get-Process -Id $record.id -ErrorAction Stop
        $native = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $record.id)
        $pattern = if ($name -eq 'api') {'-m\s+uvicorn\s+pao.main:app.+--port\s+8100'} elseif ($name -eq 'telegram') {'-m\s+arq\s+pao.modules.channels.telegram_worker.WorkerSettings'} else {'-m\s+arq\s+pao.runtime.WorkerSettings'}
        if ($process.StartTime.ToUniversalTime().Ticks -ne $record.started -or
            -not [string]::Equals($process.Path, $pythonExe, [StringComparison]::OrdinalIgnoreCase) -or
            $native.CommandLine -notmatch $pattern) { throw "$name process identity mismatch." }
    }
    foreach ($name in $ownedNames) {
        # Recheck start time at the stop boundary to defend against PID reuse.
        $record = $records.$name
        $process = Get-Process -Id $record.id -ErrorAction Stop
        if ($process.StartTime.ToUniversalTime().Ticks -ne $record.started) { throw "$name identity changed." }
        Stop-Process -Id $record.id -ErrorAction Stop
        $process.WaitForExit(10000) | Out-Null
        if (-not $process.HasExited) { throw "$name did not exit." }
    }
    $startNames = @('api','worker')
    if ($telegramEnabled -eq '1') { $startNames += 'telegram' } elseif ($records.telegram) { $records.PSObject.Properties.Remove('telegram') }
    foreach ($name in $startNames) {
        $arguments = if ($name -eq 'api') {@('-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','8100','--no-access-log')} elseif ($name -eq 'telegram') {@('-m','arq','pao.modules.channels.telegram_worker.WorkerSettings')} else {@('-m','arq','pao.runtime.WorkerSettings')}
        $process = Start-Process -FilePath $pythonExe -ArgumentList $arguments -WindowStyle Hidden -PassThru -WorkingDirectory $repoRoot -RedirectStandardOutput (Join-Path $runtime "acos-$name.stdout.log") -RedirectStandardError (Join-Path $runtime "acos-$name.stderr.log")
        if ($records.PSObject.Properties[$name]) { $records.$name = @{id=$process.Id; started=$process.StartTime.ToUniversalTime().Ticks} } else { $records | Add-Member -NotePropertyName $name -NotePropertyValue @{id=$process.Id; started=$process.StartTime.ToUniversalTime().Ticks} }
        $records | ConvertTo-Json | Set-Content -LiteralPath $recordsPath
        Write-Host "Replaced only owned ACOS $name PID $($process.Id)"
    }
    # Process creation is not readiness: allow a bounded cold import/startup.
    $ready = $false
    for ($attempt=0; $attempt -lt 16; $attempt++) {
        try {
            if ((Invoke-WebRequest -Uri 'http://127.0.0.1:8100/health' -TimeoutSec 1).StatusCode -eq 200) { $ready=$true; break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw 'API cold-start readiness deadline exceeded.' }
    & $pythonExe scripts/check_acos_health.py
    if ($LASTEXITCODE -ne 0) { throw 'Replacement runtime readiness failed; inspect retained logs.' }
} finally { Pop-Location }
