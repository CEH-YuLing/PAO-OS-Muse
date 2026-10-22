# Narrow fallback for a broken CIM account/SID lookup; never repairs Windows identity.
$ErrorActionPreference='Stop'
$agyRoot='F:\PAO-ACOS'
. (Join-Path $PSScriptRoot 'get_acos_python.ps1')
$agyPython=Get-AcosPython $agyRoot
$agyRecordsPath=Join-Path $agyRoot '.runtime\acos-processes.json'
$agyRecords=Get-Content -LiteralPath $agyRecordsPath -Raw | ConvertFrom-Json
if($agyRecords.telegram -or $agyRecords.studio){throw 'Additional worker requires review'}
$env:PAO_ROOT=$agyRoot
$env:PYTHONPATH=@((Join-Path $agyRoot 'apps\api'),(Join-Path $agyRoot 'packages\cli-runtime')) -join [IO.Path]::PathSeparator
$env:PYTHONDONTWRITEBYTECODE='1';$env:PYTHONUTF8='1'
Push-Location $agyRoot
try {
 & $agyPython -B scripts/check_acos_idle.py
 if($LASTEXITCODE -ne 0){throw 'Idle gate failed'}
 $agyIdentityJson=& $agyPython -I -B scripts/read_owned_pao_processes.py
 if($LASTEXITCODE -ne 0){throw 'Native query identity guard failed'}
 $agyIdentities=$agyIdentityJson | ConvertFrom-Json
 if($agyIdentities.untracked_scoped_worker -ne $false){throw 'Scoped worker inventory failed'}
 foreach($agyKind in @('api','worker')){
  $agyRecord=$agyRecords.$agyKind;$agyIdentity=$agyIdentities.$agyKind;$agyProcess=Get-Process -Id $agyRecord.id -ErrorAction Stop
  if($agyIdentity.id -ne $agyRecord.id -or $agyIdentity.started -ne $agyRecord.started -or $agyIdentity.exe -ne $agyPython -or $agyProcess.StartTime.ToUniversalTime().Ticks -ne $agyRecord.started -or $agyProcess.Path -ne $agyPython){throw 'Exact process identity changed'}
 }
 foreach($agyKind in @('api','worker')){
  $agyRecord=$agyRecords.$agyKind;$agyProcess=Get-Process -Id $agyRecord.id -ErrorAction Stop
  if($agyProcess.StartTime.ToUniversalTime().Ticks -ne $agyRecord.started -or $agyProcess.Path -ne $agyPython){throw 'Process identity changed at stop boundary'}
  Stop-Process -Id $agyRecord.id -ErrorAction Stop;$agyProcess.WaitForExit(10000) | Out-Null
  if(-not $agyProcess.HasExited){throw 'Owned process did not exit'}
 }
 foreach($agyKind in @('api','worker')){
  $agyArgs=if($agyKind -eq 'api'){@('-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','8100','--no-access-log')}else{@('-m','arq','pao.runtime.WorkerSettings')}
  $agyProcess=Start-Process -FilePath $agyPython -ArgumentList $agyArgs -WorkingDirectory $agyRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $agyRoot ".runtime\antigravity-$agyKind.stdout.log") -RedirectStandardError (Join-Path $agyRoot ".runtime\antigravity-$agyKind.stderr.log")
  $agyRecords.$agyKind=@{id=$agyProcess.Id;started=$agyProcess.StartTime.ToUniversalTime().Ticks}
  $agyRecords | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $agyRecordsPath
 }
 & $agyPython -B scripts/check_acos_health.py
 if($LASTEXITCODE -ne 0){throw 'Installed health not verified'}
} finally {Pop-Location}
