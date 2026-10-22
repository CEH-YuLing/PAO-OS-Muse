$ErrorActionPreference='Stop'
& "$PSScriptRoot\.venv\Scripts\python.exe" -B "$PSScriptRoot\scripts\muse_sandbox.py" stop
if ($LASTEXITCODE -ne 0) { throw 'Dừng chưa hoàn tất; không tự kill process khác.' }
