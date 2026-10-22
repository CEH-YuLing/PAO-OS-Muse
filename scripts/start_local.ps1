param([int]$Port = 3100)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$env:PAO_ROOT = $repoRoot
$env:PYTHONPATH = @((Join-Path $repoRoot 'apps\api'), (Join-Path $repoRoot 'packages\cli-runtime')) -join [IO.Path]::PathSeparator
if (Test-Path -LiteralPath (Join-Path $repoRoot '.runtime\acos-python-runtime.json')) {
    throw 'A reviewed ACOS runtime release is active. Use scripts/start_acos_local.ps1; legacy launcher is not the release entrypoint.'
}
$runtimeDir = Join-Path $repoRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
$nodeExe = (Get-Command node -ErrorAction Stop).Source
$dockerExe = (Get-Command docker -ErrorAction SilentlyContinue).Source
if (-not $dockerExe) { $dockerExe = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe' }
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Run the setup in docs/LOCAL-DEVELOPMENT.md first.' }
Push-Location $repoRoot
try {
    & $pythonExe scripts/setup_search.py
    if ($LASTEXITCODE -ne 0) { throw "Search setup failed." }
    & $dockerExe compose --env-file .env -f infra/compose.yaml --profile search up -d --wait postgres redis search
    if ($LASTEXITCODE -ne 0) { throw 'Docker is not ready. See docs/ENVIRONMENT-NOTES.md; no data was reset.' }
    $temporalEnabled = Select-String -LiteralPath (Join-Path $repoRoot '.env') -Pattern '^TEMPORAL_ENABLED=true\s*$' -Quiet
    if ($temporalEnabled) {
        & $dockerExe compose --env-file .env -f infra/compose.yaml --profile automation up -d temporal-namespace
        if ($LASTEXITCODE -ne 0) { throw 'Temporal failed to start; PAO processes were not launched.' }
    }
    # Legacy entrypoint cannot perform an implicit schema rollout either.
    & $pythonExe -B scripts/check_acos_startup_schema.py --expected 0077
    if ($LASTEXITCODE -ne 0) { throw 'Schema must be prepared by a checkpoint-bound release; startup did not migrate it.' }
    $pidFile = Join-Path $runtimeDir 'processes.json'
    $previous = @{}
    if (Test-Path $pidFile) { $previous = Get-Content $pidFile -Raw | ConvertFrom-Json }
    $records = @{}
    function Start-PaoProcess($name, $file, $arguments) {
        $old = $previous.$name
        if ($old) {
            $running = Get-Process -Id $old.id -ErrorAction SilentlyContinue
            $sameProcess = $false
            if ($running) {
                try { $sameProcess = $running.StartTime.ToUniversalTime().Ticks -eq $old.started } catch { $sameProcess = $false }
            }
            if ($sameProcess) {
                $records[$name] = $old
                Write-Host "$name already running (PID $($old.id))"
                return
            }
        }
        $process = Start-Process -FilePath $file -ArgumentList $arguments -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $runtimeDir "$name.stdout.log") -RedirectStandardError (Join-Path $runtimeDir "$name.stderr.log")
        $records[$name] = @{id=$process.Id; started=$process.StartTime.ToUniversalTime().Ticks}
        Write-Host "Started $name (PID $($process.Id))"
    }
    # Explicit CPU profile: no cloud fallback and no dependency on the current GPU driver.
    $env:OLLAMA_HOST='127.0.0.1:11434'
    $env:OLLAMA_MODELS=Join-Path $runtimeDir 'models'
    $env:OLLAMA_NO_CLOUD='1'
    $env:OLLAMA_NUM_PARALLEL='1'
    $env:OLLAMA_MAX_LOADED_MODELS='1'
    $env:CUDA_VISIBLE_DEVICES='-1'
    $env:GGML_VK_VISIBLE_DEVICES='-1'
    $env:OLLAMA_VULKAN='0'
    Start-PaoProcess 'ollama' (Join-Path $runtimeDir 'ollama\ollama.exe') @('serve')
    Start-PaoProcess 'api' $pythonExe @('-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','8000')
    Start-PaoProcess 'worker' $pythonExe @('-m','arq','pao.runtime.WorkerSettings')
    if ($temporalEnabled) {
        Start-PaoProcess 'temporal-worker' $pythonExe @('scripts/temporal_worker.py')
    }
    Start-PaoProcess 'web' $nodeExe @(('"' + (Join-Path $repoRoot 'node_modules\next\dist\bin\next') + '"'),'start',('"' + (Join-Path $repoRoot 'apps\web') + '"'),'--hostname','127.0.0.1','--port',"$Port")
    Start-PaoProcess 'telegram' $pythonExe @('scripts/telegram_bridge.py')
    $records | ConvertTo-Json | Set-Content $pidFile
    Write-Host "PAO: http://127.0.0.1:$Port - logs in .runtime (allow startup time)."
} finally { Pop-Location }
