param()
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'get_acos_python.ps1')
$taskPython = Get-AcosPython $taskRoot
$taskRecordsPath = Join-Path $taskRoot '.runtime/acos-processes.json'
$taskRecords = Get-Content -LiteralPath $taskRecordsPath -Raw | ConvertFrom-Json
foreach ($taskKind in @('api','worker')) {
    if (Get-Process -Id $taskRecords.$taskKind.id -ErrorAction SilentlyContinue) {
        throw 'Recorded process exists; use verified ordinary recovery instead.'
    }
}
if (Get-NetTCPConnection -State Listen -LocalPort 8100 -ErrorAction SilentlyContinue) {
    throw 'API port occupied; refuse to start or stop unknown process.'
}
$env:PAO_ROOT = $taskRoot
$env:PYTHONPATH = @((Join-Path $taskRoot 'apps/api'),(Join-Path $taskRoot 'packages/cli-runtime'),$PSScriptRoot) -join [IO.Path]::PathSeparator
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
Push-Location $taskRoot
try {
    & $taskPython -B scripts/verify_missing_ai_services.py
    if ($LASTEXITCODE -ne 0) { throw 'Missing-service preflight failed; no process started.' }
    $taskRecovery = Join-Path $taskRoot ('.runtime/ai-service-recovery-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $taskRecovery | Out-Null
    foreach ($taskKind in @('api','worker')) {
        $taskArgs = if ($taskKind -eq 'api') { @('-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','8100','--no-access-log') } else { @('-m','arq','pao.runtime.WorkerSettings') }
        $taskProcess = Start-Process -FilePath $taskPython -ArgumentList $taskArgs -WindowStyle Hidden -PassThru -WorkingDirectory $taskRoot -RedirectStandardOutput (Join-Path $taskRecovery "$taskKind.stdout.log") -RedirectStandardError (Join-Path $taskRecovery "$taskKind.stderr.log")
        $taskRecords.$taskKind = @{id=$taskProcess.Id; started=$taskProcess.StartTime.ToUniversalTime().Ticks}
        $taskRecords | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $taskRecordsPath
    }
    # Health must not capture a cold-import race as the final endpoint result.
    # Bounded wait only; process creation and a worker lease are not API readiness.
    $taskApiReady = $false
    for ($taskAttempt=0; $taskAttempt -lt 30; $taskAttempt++) {
        try {
            # Never invoke the Windows PowerShell HTML/IE parser or its prompt.
            if ((Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8100/health' -TimeoutSec 1).StatusCode -eq 200) { $taskApiReady=$true; break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $taskApiReady) { throw "API readiness deadline exceeded; logs retained at $taskRecovery" }
    & $taskPython -B scripts/check_acos_health.py
    if ($LASTEXITCODE -ne 0) { throw "Services not healthy; logs retained at $taskRecovery" }
    Write-Output "Recovered existing API/worker without migration: $taskRecovery"
} finally { Pop-Location }
