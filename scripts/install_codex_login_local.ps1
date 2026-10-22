# Install only an exact tested local auth slice. No migration or primary restore.
param([Parameter(Mandatory=$true)][string]$InstallFolder)
$ErrorActionPreference='Stop'
$cxRoot='F:\PAO-ACOS'
if([IO.Path]::GetFullPath($InstallFolder) -notmatch '^F:\\PAO-ACOS\\\.runtime\\codex-login-install-[a-f0-9]{32}$'){throw 'Install folder scope denied'}
if((Get-Item -LiteralPath $InstallFolder).Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)){throw 'Linked install folder denied'}
$cxPlan=Get-Content -LiteralPath (Join-Path $InstallFolder 'source-plan.json') -Raw|ConvertFrom-Json
if(-not $cxPlan.source_plan_ready -or $cxPlan.primary_installed -or $cxPlan.schema -ne '0072' -or $cxPlan.operations -ne 416){throw 'Plan gate failed'}
$cxEnv=Join-Path $cxRoot '.env'
$cxBefore=Join-Path $InstallFolder 'env-before.private'
if((Get-FileHash -LiteralPath $cxBefore).Hash.ToLowerInvariant() -ne $cxPlan.env_before_sha256){throw 'Environment preimage mismatch'}
$cxOldText=[IO.File]::ReadAllText($cxBefore).Replace("`r`n","`n")
$cxNewText=[IO.File]::ReadAllText($cxEnv).Replace("`r`n","`n")
if(($cxNewText -replace '(?m)^CLI_BROWSER_LOGIN_ENABLED=true\n','') -cne $cxOldText){throw 'Unexpected environment change'}
. (Join-Path $cxRoot 'scripts\get_acos_python.ps1')
$cxPython=(Resolve-Path -LiteralPath (Get-AcosPython $cxRoot)).Path
$cxRecordsPath=Join-Path $cxRoot '.runtime\acos-processes.json'
$cxRecords=Get-Content -LiteralPath $cxRecordsPath -Raw|ConvertFrom-Json
if($cxRecords.telegram -or $cxRecords.studio){throw 'Additional worker requires review'}
$env:PAO_ROOT=$cxRoot
$env:PYTHONPATH=@((Join-Path $cxRoot 'apps\api'),(Join-Path $cxRoot 'packages\cli-runtime')) -join [IO.Path]::PathSeparator
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
function Assert-CxOwned([string]$name){
 $record=$cxRecords.$name;$process=Get-Process -Id $record.id -ErrorAction Stop
 $native=Get-CimInstance Win32_Process -Filter ('ProcessId='+$record.id)
 $pattern=if($name -eq 'api'){'-m\s+uvicorn\s+pao.main:app.+--host\s+127\.0\.0\.1.+--port\s+8100'}else{'-m\s+arq\s+pao.runtime.WorkerSettings'}
 if($process.StartTime.ToUniversalTime().Ticks -ne $record.started -or $process.Path -ne $cxPython -or $native.CommandLine -notmatch $pattern){throw 'Process identity changed'}
 return $process
}
function Start-CxOwned {
 foreach($name in @('api','worker')){
  $record=$cxRecords.$name
  $running=Get-Process -Id $record.id -ErrorAction SilentlyContinue
  if($running -and $running.StartTime.ToUniversalTime().Ticks -eq $record.started){$null=Assert-CxOwned $name;continue}
  if($name -eq 'api' -and (Get-NetTCPConnection -State Listen -LocalPort 8100 -ErrorAction SilentlyContinue)){throw 'Unowned API port occupied'}
  $arguments=if($name -eq 'api'){@('-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','8100','--no-access-log')}else{@('-m','arq','pao.runtime.WorkerSettings')}
  $process=Start-Process -FilePath $cxPython -ArgumentList $arguments -WindowStyle Hidden -PassThru -WorkingDirectory $cxRoot -RedirectStandardOutput (Join-Path $InstallFolder "$name.stdout.log") -RedirectStandardError (Join-Path $InstallFolder "$name.stderr.log")
  $cxRecords.$name=@{id=$process.Id;started=$process.StartTime.ToUniversalTime().Ticks}
  $cxRecords|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $cxRecordsPath
 }
}
$cxChanges=@{}
foreach($entry in $cxPlan.changes.PSObject.Properties){
 $name=$entry.Name;$change=$entry.Value
 if($name -notmatch '^[a-zA-Z0-9_./-]+$' -or $name.Contains('..') -or $name.StartsWith('/')){throw 'Invalid source path'}
 foreach($path in @($change.source,(Join-Path $cxRoot $name))){
  $cursor=[IO.Path]::GetFullPath($path)
  if(-not $cursor.StartsWith($cxRoot+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Path outside checkout'}
  while($cursor -ne $cxRoot){if((Test-Path -LiteralPath $cursor) -and (Get-Item -LiteralPath $cursor).Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)){throw 'Linked source denied'};$cursor=Split-Path $cursor -Parent}
 }
 if((Get-FileHash -LiteralPath $change.source).Hash.ToLowerInvariant() -ne $change.after){throw 'Tested source changed'}
 $target=Join-Path $cxRoot $name
 if($change.before){
  if((Get-FileHash -LiteralPath $target).Hash.ToLowerInvariant() -ne $change.before){throw 'Preserve overlapping source changes'}
  $saved=Join-Path $InstallFolder ('source-before\'+$name);New-Item -ItemType Directory -Path (Split-Path $saved -Parent) -Force|Out-Null;Copy-Item -LiteralPath $target -Destination $saved
 }elseif(Test-Path -LiteralPath $target){throw 'New source target exists'}
 $cxChanges[$name]=$change
}
Push-Location $cxRoot
$cxStopped=$false
try{
 & $cxPython -B scripts/check_acos_idle.py
 if($LASTEXITCODE -ne 0){throw 'Idle gate failed'}
 & $cxPython -B scripts/check_codex_login_installed.py before --folder $InstallFolder
 if($LASTEXITCODE -ne 0){throw 'Snapshot/CLI idle gate failed'}
 foreach($name in @('api','worker')){$null=Assert-CxOwned $name}
 $cxStopped=$true
 foreach($name in @('api','worker')){$process=Assert-CxOwned $name;Stop-Process -Id $process.Id -ErrorAction Stop;$process.WaitForExit(10000)|Out-Null;if(-not $process.HasExited){throw 'Owned process did not exit'}}
 foreach($name in $cxChanges.Keys){$target=Join-Path $cxRoot $name;New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force|Out-Null;Copy-Item -LiteralPath $cxChanges[$name].source -Destination $target}
 Start-CxOwned
 $cxStopped=$false
 $cxReady=$false
 for($attempt=0;$attempt -lt 30;$attempt++){try{if((Invoke-WebRequest -Uri 'http://127.0.0.1:8100/ready' -TimeoutSec 1).StatusCode -eq 200){$cxReady=$true;break}}catch{};Start-Sleep -Milliseconds 500}
 if(-not $cxReady){throw 'Installed API readiness deadline exceeded'}
 & $cxPython -B scripts/check_acos_health.py *> (Join-Path $InstallFolder 'health.log')
 if($LASTEXITCODE -ne 0){throw 'Installed health/worker gate failed'}
 & $cxPython -B scripts/check_codex_login_installed.py after --folder $InstallFolder *> (Join-Path $InstallFolder 'installed-check.log')
 if($LASTEXITCODE -ne 0){throw 'Installed source/data/contract/archive gate failed'}
 Write-Output ('Codex local browser login installed and checked: '+$InstallFolder)
}catch{
 if($cxStopped){
  foreach($name in @('api','worker')){
   $record=$cxRecords.$name;$running=Get-Process -Id $record.id -ErrorAction SilentlyContinue
   if($running -and $running.StartTime.ToUniversalTime().Ticks -eq $record.started){$process=Assert-CxOwned $name;Stop-Process -Id $process.Id -ErrorAction Stop;$process.WaitForExit(10000)|Out-Null;if(-not $process.HasExited){throw 'Rollback process stop failed'}}
  }
  # Source-only recovery; preserve new files in a named rollback folder.
  foreach($name in $cxChanges.Keys){
   $target=Join-Path $cxRoot $name;$change=$cxChanges[$name]
   if(Test-Path -LiteralPath $target){$hash=(Get-FileHash -LiteralPath $target).Hash.ToLowerInvariant();if($hash -ne $change.after -and $hash -ne $change.before){throw 'Preserve unexpected source change during rollback'}}
   if($change.before){Copy-Item -LiteralPath (Join-Path $InstallFolder ('source-before\'+$name)) -Destination $target -Force}
   elseif(Test-Path -LiteralPath $target){$saved=Join-Path $InstallFolder ('rejected-source\'+$name);New-Item -ItemType Directory -Path (Split-Path $saved -Parent) -Force|Out-Null;Move-Item -LiteralPath $target -Destination $saved}
  }
  Copy-Item -LiteralPath $cxBefore -Destination $cxEnv -Force
  Start-CxOwned
 }
 throw
}finally{Pop-Location}
