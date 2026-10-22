$ErrorActionPreference='Stop';$paoRoot=Split-Path $PSScriptRoot -Parent;Push-Location $paoRoot
try{$python=Join-Path $paoRoot '.venv\Scripts\python.exe';& $python scripts/deploy_phase16.py --check;if($LASTEXITCODE -ne 0){throw 'PAO has active work'};$records=Get-Content .runtime/processes.json -Raw|ConvertFrom-Json -AsHashtable
foreach($name in @('web','telegram','api','worker')){$old=$records[$name];if(-not $old){continue};$running=Get-Process -Id $old.id -ErrorAction SilentlyContinue;if($running -and $running.StartTime.ToUniversalTime().Ticks -eq $old.started){taskkill /PID $old.id /T /F;if($LASTEXITCODE -ne 0){throw "Could not stop $name"}}}
& $python scripts/deploy_phase16.py;if($LASTEXITCODE -ne 0){throw 'Migration failed; inspect backup'};& (Join-Path $PSScriptRoot 'start_local.ps1')
}finally{Pop-Location}
