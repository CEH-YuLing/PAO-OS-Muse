param([ValidateSet('api','worker','studio','web','ollama')][string[]]$Components = @('api','worker','studio','web','ollama'))
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$runtime = Join-Path $repoRoot '.runtime'
. (Join-Path $PSScriptRoot 'get_acos_python.ps1')
$pythonExe = Get-AcosPython $repoRoot
$records = @{}
if ($Components -contains 'studio' -or $Components -contains 'worker' -or $Components -contains 'api') {
    $env:PAO_ROOT = $repoRoot
    $env:PYTHONPATH = Join-Path $repoRoot 'apps\api'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $pythonExe (Join-Path $repoRoot 'scripts\check_acos_idle.py')
    if ($LASTEXITCODE -ne 0) { throw 'Jobs are active or idle cannot be verified. Cancel/reconcile and drain before stopping workers.' }
}
foreach ($file in @('acos-processes.json','acos-web-process.json','acos-ollama-process.json')) {
    $path = Join-Path $runtime $file
    if (-not (Test-Path -LiteralPath $path)) { continue }
    $data = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    if ($file -eq 'acos-processes.json') {
        foreach ($name in @('api','worker','studio','web','ollama')) {
            if ($data.$name) { $records[$name] = $data.$name }
        }
    } else {
        $name = if ($file -eq 'acos-web-process.json') { 'web' } else { 'ollama' }
        if (-not $records.ContainsKey($name)) { $records[$name] = $data }
    }
}
foreach ($name in $Components) {
    if (-not $records.ContainsKey($name)) { continue }
    $item = $records[$name]
    $p = Get-Process -Id $item.id -ErrorAction SilentlyContinue
    if (-not $p -or $p.StartTime.ToUniversalTime().Ticks -ne $item.started) {
        Write-Host "$name recorded process is no longer alive; skipped"
        continue
    }
    $expected = switch ($name) {
        'api' { 'python.exe' }
        'worker' { 'python.exe' }
        'studio' { 'python.exe' }
        'web' { 'node.exe' }
        'ollama' { 'ollama.exe' }
    }
    if ([IO.Path]::GetFileName($p.Path) -ne $expected) { throw "$name process identity changed; refusing to stop." }
    if ($name -in @('api','worker','studio') -and -not [string]::Equals($p.Path, $pythonExe, [StringComparison]::OrdinalIgnoreCase)) {
        throw "$name executable is outside the ACOS runtime; refusing to stop."
    }
    & taskkill.exe /PID $item.id /T /F
    if ($LASTEXITCODE -ne 0) { throw "Failed to stop $name process tree." }
    Write-Host "Stopped $name and its children"
}
# Preserve containers, volumes, credentials, and all runtime records for recovery.
