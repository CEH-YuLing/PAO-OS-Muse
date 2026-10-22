$ErrorActionPreference='Stop'
& "$PSScriptRoot\.venv\Scripts\python.exe" -B "$PSScriptRoot\scripts\test_muse_sandbox.py"
if ($LASTEXITCODE -ne 0) { throw 'Test failed; retained .runtime/sandbox-test-* evidence. Do not restore primary.' }
