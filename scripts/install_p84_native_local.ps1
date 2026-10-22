# One reviewed local install, not a provider/business runner. Never restore primary DB.
param([Parameter(Mandatory=$true)][string]$InstallFolder,
      [Parameter(Mandatory=$true)][string]$CheckpointManifest)
$ErrorActionPreference='Stop'
$p84Root='F:\PAO-ACOS'
$p84Candidate=Join-Path $p84Root '.runtime\p84-native-candidate-20261018'
if([IO.Path]::GetFullPath($InstallFolder) -notmatch '^F:\\PAO-ACOS\\\.runtime\\p84-native-install-[a-f0-9]{32}$'){throw 'Install folder scope denied'}
if((Get-Item -LiteralPath $InstallFolder).Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)){throw 'Linked install folder denied'}
$p84Plan=Get-Content -LiteralPath (Join-Path $InstallFolder 'source-plan.json') -Raw|ConvertFrom-Json
$p84Before=Get-Content -LiteralPath (Join-Path $InstallFolder 'database-before.json') -Raw|ConvertFrom-Json
if(-not $p84Plan.source_plan_ready -or $p84Plan.primary_installed -or $p84Plan.schema_before -ne '0071' -or $p84Plan.schema_target -ne '0072'){throw 'Source plan gate failed'}
if([IO.Path]::GetFullPath($CheckpointManifest) -notmatch '^F:\\PAO-ACOS\\\.runtime\\checkpoints\\p0-[a-zA-Z0-9-]+\\manifest.json$'){throw 'Checkpoint scope denied'}
$p84Checkpoint=Get-Content -LiteralPath $CheckpointManifest -Raw|ConvertFrom-Json
if($p84Checkpoint.database.revision_before -ne '0071' -or $p84Checkpoint.database.table_count -ne 153 -or $p84Checkpoint.database.artifact_count -ne 3){throw 'Verified checkpoint required'}
if((Get-FileHash -LiteralPath $p84Checkpoint.source.path).Hash.ToLowerInvariant() -ne $p84Checkpoint.source.sha256 -or
   (Get-FileHash -LiteralPath $p84Checkpoint.database.backup).Hash.ToLowerInvariant() -ne $p84Checkpoint.database.sha256){throw 'Checkpoint integrity failed'}
$p84EnvPath=Join-Path $p84Root '.env'
$p84OldEnv=Get-Content -LiteralPath (Join-Path $InstallFolder 'env-before.private') -Raw
$p84NewEnv=Get-Content -LiteralPath $p84EnvPath -Raw
if(($p84NewEnv.Replace("`r`n","`n") -replace '(?m)^CLI_CONNECTIONS_ENABLED=true\n','') -cne $p84OldEnv.Replace("`r`n","`n")){throw 'Unexpected environment change; preserve for review'}
if((Get-FileHash -LiteralPath (Join-Path $InstallFolder 'env-before.private')).Hash.ToLowerInvariant() -ne $p84Before.env_sha256){throw 'Original environment backup changed'}
$p84Registry=Get-Content -LiteralPath (Join-Path $p84Root '.runtime\cli-device.json') -Raw|ConvertFrom-Json
. (Join-Path $p84Root 'scripts\get_acos_python.ps1')
$p84Python=(Resolve-Path -LiteralPath (Get-AcosPython $p84Root)).Path
$env:PAO_ROOT=$p84Root
$env:PYTHONPATH=@((Join-Path $p84Root 'apps\api'),(Join-Path $p84Root 'packages\cli-runtime')) -join [IO.Path]::PathSeparator
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$p84RecordsPath=Join-Path $p84Root '.runtime\acos-processes.json'
$p84Records=Get-Content -LiteralPath $p84RecordsPath -Raw|ConvertFrom-Json
if($p84Records.telegram -or $p84Records.studio){throw 'Additional worker scope not reviewed'}
$p84Changes=@{}
foreach($entry in $p84Plan.changes.PSObject.Properties){
 if($entry.Name -notmatch '^[a-zA-Z0-9_./-]+$' -or $entry.Name.Contains('..') -or $entry.Name.StartsWith('/')){throw 'Invalid source path'}
 $p84Changes[$entry.Name]=@{source=(Join-Path $p84Candidate $entry.Name);before=$entry.Value.before;after=$entry.Value.after}
}
$p84Derived=$p84Plan.derived_contract
if($p84Derived.target -ne 'packages/contracts/schema.d.ts' -or [IO.Path]::GetFullPath($p84Derived.source) -notmatch '^F:\\PAO-ACOS\\\.runtime\\p84-frontend-[a-f0-9]{32}\\source\\packages\\contracts\\schema.d.ts$'){throw 'Derived contract scope denied'}
$p84Changes[$p84Derived.target]=@{source=$p84Derived.source;before=$p84Derived.before;after=$p84Derived.after}
foreach($name in $p84Changes.Keys){
 $change=$p84Changes[$name];$target=Join-Path $p84Root $name
 foreach($path in @($change.source,$target)){
  $cursor=[IO.Path]::GetFullPath($path)
  if(-not $cursor.StartsWith($p84Root+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Source outside checkout'}
  while($cursor -ne $p84Root){if((Test-Path -LiteralPath $cursor) -and (Get-Item -LiteralPath $cursor).Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)){throw 'Linked source denied'};$cursor=Split-Path $cursor -Parent}
 }
 if((Get-FileHash -LiteralPath $change.source).Hash.ToLowerInvariant() -ne $change.after){throw 'Tested source changed'}
 if($change.before){
  if((Get-FileHash -LiteralPath $target).Hash.ToLowerInvariant() -ne $change.before){throw 'Preserve overlapping source changes'}
  $saved=Join-Path $InstallFolder ('source-before\'+$name)
  New-Item -ItemType Directory -Path (Split-Path $saved -Parent) -Force|Out-Null
  Copy-Item -LiteralPath $target -Destination $saved
 }elseif(Test-Path -LiteralPath $target){throw 'New source target already exists'}
}
function Assert-P84Owned([string]$name){
 $record=$p84Records.$name;$process=Get-Process -Id $record.id -ErrorAction Stop
 $native=Get-CimInstance Win32_Process -Filter ('ProcessId='+$record.id)
 $pattern=if($name -eq 'api'){'-m\s+uvicorn\s+pao.main:app.+--port\s+8100'}else{'-m\s+arq\s+pao.runtime.WorkerSettings'}
 if($process.StartTime.ToUniversalTime().Ticks -ne $record.started -or $process.Path -ne $p84Python -or $native.CommandLine -notmatch $pattern){throw 'Process identity changed'}
 return $process
}
function Start-P84Owned {
 foreach($name in @('api','worker')){
  $running=Get-Process -Id $p84Records.$name.id -ErrorAction SilentlyContinue
  if($running -and $running.StartTime.ToUniversalTime().Ticks -eq $p84Records.$name.started){$null=Assert-P84Owned $name;continue}
  if($name -eq 'api' -and (Get-NetTCPConnection -State Listen -LocalPort 8100 -ErrorAction SilentlyContinue)){throw 'Unowned API port occupied'}
  $arguments=if($name -eq 'api'){@('-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','8100','--no-access-log')}else{@('-m','arq','pao.runtime.WorkerSettings')}
  $process=Start-Process -FilePath $p84Python -ArgumentList $arguments -WindowStyle Hidden -PassThru -WorkingDirectory $p84Root -RedirectStandardOutput (Join-Path $InstallFolder "$name.stdout.log") -RedirectStandardError (Join-Path $InstallFolder "$name.stderr.log")
  $p84Records.$name=@{id=$process.Id;started=$process.StartTime.ToUniversalTime().Ticks}
  $p84Records|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $p84RecordsPath
 }
}
Push-Location $p84Root
$p84Stopped=$false;$p84Copied=$false;$p84Migrated=$false
try{
 & $p84Python -B scripts/check_acos_idle.py
 if($LASTEXITCODE -ne 0){throw 'Idle gate failed; nothing stopped'}
 foreach($name in @('api','worker')){$null=Assert-P84Owned $name}
 @{version=1;env_after_sha256=(Get-FileHash -LiteralPath $p84EnvPath).Hash.ToLowerInvariant();device_registry=$p84Registry;selected_workspace='ef221310-5afc-4c21-9f9e-4aa9bf4b3e79';checkpoint=$CheckpointManifest}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $InstallFolder 'install-intent.json')
 foreach($operator in @('install_p84_native_local.ps1','check_p84_native_installed.py')){$saved=Join-Path $InstallFolder ('operator-source\'+$operator);New-Item -ItemType Directory -Path (Split-Path $saved -Parent) -Force|Out-Null;Copy-Item -LiteralPath (Join-Path $p84Root ('scripts\'+$operator)) -Destination $saved}
 $p84Stopped=$true
 foreach($name in @('api','worker')){$process=Assert-P84Owned $name;Stop-Process -Id $process.Id -ErrorAction Stop;$process.WaitForExit(10000)|Out-Null;if(-not $process.HasExited){throw 'Verified process did not exit'}}
 $p84Copied=$true
 foreach($name in $p84Changes.Keys){$target=Join-Path $p84Root $name;New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force|Out-Null;Copy-Item -LiteralPath $p84Changes[$name].source -Destination $target}
 & $p84Python -B -m alembic upgrade 0072 *> (Join-Path $InstallFolder 'migration.log')
 if($LASTEXITCODE -ne 0){throw 'Migration failed; inspect retained log'}
 $p84Migrated=$true
 Start-P84Owned
 $p84Ready=$false
 for($attempt=0;$attempt -lt 30;$attempt++){try{if((Invoke-WebRequest -Uri 'http://127.0.0.1:8100/ready' -TimeoutSec 1).StatusCode -eq 200){$p84Ready=$true;break}}catch{};Start-Sleep -Milliseconds 500}
 if(-not $p84Ready){throw 'Installed API cold-start deadline exceeded'}
 & $p84Python -B scripts/check_acos_health.py *> (Join-Path $InstallFolder 'health.log')
 if($LASTEXITCODE -ne 0){throw 'Installed readiness failed'}
 & $p84Python -B scripts/check_p84_native_installed.py after --install-folder $InstallFolder *> (Join-Path $InstallFolder 'installed-check.log')
 if($LASTEXITCODE -ne 0){throw 'Installed source/contract/data/replay checks failed'}
 Write-Output ('P8.4 native metadata backend installed and verified: '+$InstallFolder)
}catch{
 $failure=$_.Exception.Message
 if($p84Stopped -and -not $p84Migrated){
  # Restore source only after confirming transactional migration did not advance.
  $revision=& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' --host npipe:////./pipe/dockerDesktopLinuxEngine exec pao-acos-local-postgres-1 psql -U pao -d pao_acos_local -Atc 'SELECT version_num FROM alembic_version'
  if($LASTEXITCODE -eq 0 -and $revision -eq '0071'){
   if($p84Copied){foreach($name in $p84Changes.Keys){$target=Join-Path $p84Root $name;if($p84Changes[$name].before){Copy-Item -LiteralPath (Join-Path $InstallFolder ('source-before\'+$name)) -Destination $target -Force}elseif(Test-Path -LiteralPath $target){$saved=Join-Path $InstallFolder ('rejected-source\'+$name);New-Item -ItemType Directory -Path (Split-Path $saved -Parent) -Force|Out-Null;Move-Item -LiteralPath $target -Destination $saved}}}
   if((Get-FileHash -LiteralPath $p84EnvPath).Hash.ToLowerInvariant() -eq (Get-Content -LiteralPath (Join-Path $InstallFolder 'install-intent.json') -Raw|ConvertFrom-Json).env_after_sha256){Copy-Item -LiteralPath (Join-Path $InstallFolder 'env-before.private') -Destination $p84EnvPath -Force}
   Start-P84Owned
  }
 }
 throw ('Install gate failed; no primary DB restore/downgrade performed. Evidence retained: '+$failure)
}finally{Pop-Location}
