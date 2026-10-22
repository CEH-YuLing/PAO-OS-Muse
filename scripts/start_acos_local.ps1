param([string]$PythonExe)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'get_acos_python.ps1')
if (-not $PythonExe) { $PythonExe = Get-AcosPython $repoRoot }
if (-not (Test-Path -LiteralPath $PythonExe)) { throw 'Install the local .venv before starting PAO-ACOS.' }
$ollamaExe = Join-Path $repoRoot '.runtime\ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $ollamaExe)) { throw 'Install Ollama CPU runtime under .runtime/ollama first.' }
Push-Location $repoRoot
try {
    if (-not (Test-Path -LiteralPath '.env')) { throw 'Run scripts/init_acos_local.py first.' }
    if (-not (Select-String -LiteralPath '.env' -Pattern ':15432/pao_acos_local$' -Quiet)) {
        throw 'This launcher requires the isolated ACOS database configuration.'
    }
    $env:PAO_ROOT = $repoRoot
    $env:PYTHONPATH = @((Join-Path $repoRoot 'apps\api'), (Join-Path $repoRoot 'packages\cli-runtime')) -join [IO.Path]::PathSeparator
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PAO_API_URL = 'http://127.0.0.1:8100'
    & docker compose --env-file .env -f infra/compose.acos-local.yaml up -d --wait
    if ($LASTEXITCODE -ne 0) { throw 'Isolated Docker services failed.' }
    # Startup is read-only with respect to schema. A release needs its own verified
    # checkpoint + clone restore + reviewed rollout; never follow Alembic head here.
    & $PythonExe -B scripts/check_acos_startup_schema.py --expected 0077
    if ($LASTEXITCODE -ne 0) { throw 'Schema release required. Startup did not migrate the database; see docs/GD00-BASELINE-AND-RECOVERY-2026-10-21.vi.md.' }
    $runtimeDir = Join-Path $repoRoot '.runtime'
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    $pidFile = Join-Path $runtimeDir 'acos-processes.json'
    $records = @{}
    $ollamaPidFile = Join-Path $runtimeDir 'acos-ollama-process.json'
    if (Test-Path -LiteralPath $ollamaPidFile) {
        $item = Get-Content -LiteralPath $ollamaPidFile -Raw | ConvertFrom-Json
        $p = Get-Process -Id $item.id -ErrorAction SilentlyContinue
        if ($p -and $p.StartTime -and $p.StartTime.ToUniversalTime().Ticks -eq $item.started) {
            $records['ollama'] = $item
        }
    }
    $webPidFile = Join-Path $runtimeDir 'acos-web-process.json'
    if (Test-Path -LiteralPath $webPidFile) {
        $item = Get-Content -LiteralPath $webPidFile -Raw | ConvertFrom-Json
        $p = Get-Process -Id $item.id -ErrorAction SilentlyContinue
        if ($p -and $p.StartTime -and $p.StartTime.ToUniversalTime().Ticks -eq $item.started) {
            $records['web'] = $item
        }
    }
    if (Test-Path -LiteralPath $pidFile) {
        $old = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
        foreach ($name in @('api','worker','telegram','studio','web','ollama')) {
            $item = $old.$name
            if ($item) {
                $p = Get-Process -Id $item.id -ErrorAction SilentlyContinue
                if ($p -and $p.StartTime -and $p.StartTime.ToUniversalTime().Ticks -eq $item.started) {
                    $records[$name] = $item
                }
            }
        }
    }
    function Start-AcosProcess($name, $file, $arguments) {
        if ($records.ContainsKey($name)) {
            $running = Get-Process -Id $records[$name].id -ErrorAction Stop
            if (-not [string]::Equals($running.Path, (Resolve-Path -LiteralPath $file).Path, [StringComparison]::OrdinalIgnoreCase)) {
                throw "$name uses a different executable; stop the recorded ACOS process before switching runtime."
            }
            Write-Host "$name already running"; return
        }
        $ports = @{ollama=11434; api=8100; web=3200}
        if ($ports.ContainsKey($name) -and (Get-NetTCPConnection -State Listen -LocalPort $ports[$name] -ErrorAction SilentlyContinue)) {
            throw "$name port is occupied but no verified process record exists; refuse duplicate start or stopping an unknown process."
        }
        $p = Start-Process -FilePath $file -ArgumentList $arguments -WindowStyle Hidden -PassThru -WorkingDirectory $repoRoot `
            -RedirectStandardOutput (Join-Path $runtimeDir "acos-$name.stdout.log") `
            -RedirectStandardError (Join-Path $runtimeDir "acos-$name.stderr.log")
        $records[$name] = @{id=$p.Id; started=$p.StartTime.ToUniversalTime().Ticks}
        Write-Host "Started $name PID $($p.Id)"
    }
    $env:OLLAMA_HOST = '127.0.0.1:11434'
    $env:OLLAMA_MODELS = Join-Path $runtimeDir 'models'
    $env:OLLAMA_NO_CLOUD = '1'
    $env:OLLAMA_NUM_PARALLEL = '1'
    $env:OLLAMA_MAX_LOADED_MODELS = '1'
    $env:CUDA_VISIBLE_DEVICES = '-1'
    $env:GGML_VK_VISIBLE_DEVICES = '-1'
    $env:OLLAMA_VULKAN = '0'
    Start-AcosProcess 'ollama' $ollamaExe @('serve')
    $records | ConvertTo-Json | Set-Content -LiteralPath $pidFile
    Start-AcosProcess 'api' $PythonExe @('-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','8100','--no-access-log')
    $records | ConvertTo-Json | Set-Content -LiteralPath $pidFile
    Start-AcosProcess 'worker' $PythonExe @('-m','arq','pao.runtime.WorkerSettings')
    $records | ConvertTo-Json | Set-Content -LiteralPath $pidFile
    $telegramScopedEnabled = & $PythonExe -c 'from pao.config import settings; c=settings(); print(int(c.telegram_scoped_runtime_enabled and not c.telegram_enabled and c.channels_enabled))'
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read scoped Telegram worker gate.' }
    if ($telegramScopedEnabled -eq '1') {
        Start-AcosProcess 'telegram' $PythonExe @('-m','arq','pao.modules.channels.telegram_worker.WorkerSettings')
        $records | ConvertTo-Json | Set-Content -LiteralPath $pidFile
    } else { Write-Host 'Telegram theo doanh nghiep dang tat; khong khoi dong worker hoac goi bot.' }
    $studioEnabled = & $PythonExe -c 'from pao.config import settings; print(int(settings().workflow_worker_enabled))'
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read Studio worker gate.' }
    if ($studioEnabled -eq '1') {
        Start-AcosProcess 'studio' $PythonExe @('scripts/studio_temporal_worker.py')
        $records | ConvertTo-Json | Set-Content -LiteralPath $pidFile
    } else { Write-Host 'Studio durable worker disabled; no model or external tool execution.' }
    $nodeExe = (Get-Command node).Source
    Start-AcosProcess 'web' $nodeExe @('node_modules/next/dist/bin/next','dev','apps/web','--hostname','127.0.0.1','--port','3200')
    $records | ConvertTo-Json | Set-Content -LiteralPath $pidFile
    Write-Host 'ACOS local web: http://127.0.0.1:3200'
} finally { Pop-Location }
