$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\python.exe" -B "$PSScriptRoot\scripts\muse_sandbox.py" start
if ($LASTEXITCODE -ne 0) { throw 'Không khởi động được; xem .runtime trong bản Muse.' }
Write-Host 'PAO OS Muse: http://127.0.0.1:3300/'
