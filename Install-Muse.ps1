# Reproducible local setup. Never modifies the protected F: installation.
$ErrorActionPreference='Stop'
if ($PSScriptRoot -ne 'G:\PAO OS Muse') { throw 'Chỉ cài trong G:\PAO OS Muse.' }
Set-Location -LiteralPath $PSScriptRoot
if (Test-Path -LiteralPath '.runtime\muse-processes.json') {
    $museExisting=Get-Content -LiteralPath '.runtime\muse-processes.json' -Raw | ConvertFrom-Json
    foreach ($museExistingEntry in $museExisting.PSObject.Properties) {
        if (Get-Process -Id $museExistingEntry.Value.pid -ErrorAction SilentlyContinue) {
            throw 'Bản Muse đang chạy hoặc PID chưa xác minh. Dừng bằng Stop-Muse.ps1 trước khi cài/build.'
        }
    }
}
$env:PYTHONUTF8='1'
$env:PAO_API_URL='http://127.0.0.1:8200'
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & python -c 'import sys; assert sys.version_info[:2] == (3,12), "Use Python 3.12"'
    if ($LASTEXITCODE -ne 0) { throw 'Cần Python3.12 trong PATH; không tự cài/thay Python máy.' }
    & python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Tạo .venv thất bại.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Cài dependency Python thất bại.' }
& '.\.venv\Scripts\python.exe' -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Cài backend package thất bại.' }
& npm.cmd ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Cài dependency frontend thất bại.' }
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Build frontend thất bại.' }
& '.\.venv\Scripts\python.exe' -B scripts\muse_sandbox.py setup
if ($LASTEXITCODE -ne 0) { throw 'Setup sandbox thất bại.' }
$museSetupSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
foreach ($museSetupFile in @('.env','.runtime\first-login.txt')) {
    & icacls.exe $museSetupFile '/inheritance:r' '/grant:r' "*${museSetupSid}:(F)" '*S-1-5-18:(F)'
    if ($LASTEXITCODE -ne 0) { throw 'Không giới hạn được quyền đọc file cấu hình riêng.' }
}
Write-Host 'Đã chuẩn bị bản Muse; chạy Start-Muse.ps1. Không có provider tự đăng nhập.'
