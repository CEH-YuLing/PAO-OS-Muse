# Local source-only additive release; no migrations, configuration or database restore.
param([Parameter(Mandatory=$true)][string]$ReleaseManifest)
$ErrorActionPreference='Stop'
$orgRoot='F:\PAO-ACOS';$orgCandidate='F:\Apex\enterprise-knowledge-candidate'
if((Resolve-Path -LiteralPath $ReleaseManifest).Path -ne "$orgCandidate\.runtime\organization-release.json"){throw 'Unexpected release manifest'}
$orgProof=Get-Content -Raw -LiteralPath $ReleaseManifest | ConvertFrom-Json
if(-not $orgProof.pass -or $orgProof.schema -ne '0071' -or $orgProof.environment_changed){throw 'Local verification proof required'}
. (Join-Path $orgRoot 'scripts\get_acos_python.ps1')
$orgPython=(Resolve-Path -LiteralPath (Get-AcosPython $orgRoot)).Path;$orgNode='C:\Program Files\nodejs\node.exe'
$env:PAO_ROOT=$orgRoot;$env:PYTHONPATH=Join-Path $orgRoot 'apps\api';$env:PYTHONDONTWRITEBYTECODE='1';$env:PYTHONUTF8='1';$env:PAO_API_URL='http://127.0.0.1:8100';$env:PAO_BUILD_CHECK='0'
foreach($e in $orgProof.changes.PSObject.Properties){
 if($e.Name.Contains('..') -or $e.Name.Contains(':') -or $e.Name.StartsWith('/')){throw 'Invalid source path'}
 $src=Join-Path $orgCandidate $e.Name;$dst=Join-Path $orgRoot $e.Name
 if((Get-FileHash -LiteralPath $src).Hash.ToLower() -ne $e.Value.after){throw 'Candidate changed after verification'}
 if($e.Value.before){if((Get-FileHash -LiteralPath $dst).Hash.ToLower() -ne $e.Value.before){throw 'Installed file changed; preserve user work'}}elseif(Test-Path -LiteralPath $dst){throw 'New source target already exists'}
}
$orgRecordsPath=Join-Path $orgRoot '.runtime\acos-processes.json';$orgRecords=Get-Content -Raw -LiteralPath $orgRecordsPath | ConvertFrom-Json
if($orgRecords.telegram -or $orgRecords.studio){throw 'Additional workers require separate verified restart scope'}
$orgPatterns=@{api='-m\s+uvicorn\s+pao.main:app.+--port\s+8100';worker='-m\s+arq\s+pao.runtime.WorkerSettings';web='node_modules/next/dist/bin/next.+apps/web.+--port.+3200'}
function Assert-OrgProcess([string]$name){$r=$orgRecords.$name;if(-not $r){throw 'Missing process record'};$p=Get-Process -Id $r.id -ErrorAction Stop;$native=Get-CimInstance Win32_Process -Filter ('ProcessId='+$r.id);$exe=if($name -eq 'web'){$orgNode}else{$orgPython};if($p.StartTime.ToUniversalTime().Ticks -ne $r.started -or $p.Path -ne $exe -or $native.CommandLine -notmatch $orgPatterns[$name]){throw "Process identity mismatch: $name"};return $p}
foreach($name in @('web','api','worker')){$null=Assert-OrgProcess $name}
Push-Location $orgRoot
try{& $orgPython scripts/check_acos_idle.py;if($LASTEXITCODE -ne 0){throw 'Idle gate failed; nothing stopped'}}finally{Pop-Location}
$orgBackup=Join-Path $orgRoot ('.runtime\organization-install-'+[guid]::NewGuid().ToString('N'));New-Item -ItemType Directory -Path $orgBackup | Out-Null
Copy-Item -LiteralPath $ReleaseManifest -Destination (Join-Path $orgBackup 'release.json');Copy-Item -LiteralPath $orgRecordsPath -Destination (Join-Path $orgBackup 'processes-before.json')
foreach($e in $orgProof.changes.PSObject.Properties){if($e.Value.before){$saved=Join-Path $orgBackup ('source-before\'+$e.Name);New-Item -ItemType Directory -Path (Split-Path $saved -Parent) -Force | Out-Null;Copy-Item -LiteralPath (Join-Path $orgRoot $e.Name) -Destination $saved}}
$orgCache=Join-Path $orgRoot 'apps\web\.pao-next';$orgOldCache=Join-Path $orgBackup 'cache-before';$orgStarted=@{}
function Start-OrgServices([string]$label){
 foreach($name in @('api','worker','web')){
  $exe=if($name -eq 'web'){$orgNode}else{$orgPython};$orgArguments=if($name -eq 'api'){@('-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','8100','--no-access-log')}elseif($name -eq 'worker'){@('-m','arq','pao.runtime.WorkerSettings')}else{@('node_modules/next/dist/bin/next','dev','apps/web','--hostname','127.0.0.1','--port','3200')}
  $existing=Get-Process -Id $orgRecords.$name.id -ErrorAction SilentlyContinue
  if($existing){$null=Assert-OrgProcess $name;continue}
  $orgPort=if($name -eq 'web'){3200}elseif($name -eq 'api'){8100}else{0}
  if($orgPort -and (Get-NetTCPConnection -State Listen -LocalPort $orgPort -ErrorAction SilentlyContinue)){throw 'Refuse starting into an unowned port'}
  $p=Start-Process -FilePath $exe -ArgumentList $orgArguments -WorkingDirectory $orgRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $orgBackup "$label-$name.stdout.log") -RedirectStandardError (Join-Path $orgBackup "$label-$name.stderr.log")
  $orgStarted[$name]=@{id=$p.Id;started=$p.StartTime.ToUniversalTime().Ticks};$orgRecords.$name=$orgStarted[$name];$orgRecords | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $orgRecordsPath
 }
 $orgRecords.web | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $orgRoot '.runtime\acos-web-process.json')
 for($i=0;$i -lt 80;$i++){try{if((Invoke-WebRequest -Uri 'http://127.0.0.1:8100/ready' -TimeoutSec 2).StatusCode -eq 200 -and (Invoke-WebRequest -Uri 'http://127.0.0.1:3200/' -TimeoutSec 3).StatusCode -eq 200){return}}catch{};Start-Sleep -Milliseconds 500};throw 'New services did not become ready'
}
try{
 foreach($name in @('web','api','worker')){$p=Assert-OrgProcess $name;if($name -eq 'web'){& taskkill.exe /PID $p.Id /T /F | Out-Null;if($LASTEXITCODE -ne 0){throw 'Verified Web stop failed'}}else{Stop-Process -Id $p.Id -ErrorAction Stop;$p.WaitForExit(10000)|Out-Null;if(-not $p.HasExited){throw 'Verified backend stop failed'}}}
 foreach($port in @(3200,8100)){if(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue){throw 'Expected local port still occupied'}}
 if(Test-Path -LiteralPath $orgCache){if((Resolve-Path -LiteralPath $orgCache).Path -ne 'F:\PAO-ACOS\apps\web\.pao-next' -or ((Get-Item -LiteralPath $orgCache).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Cache path refused'};Move-Item -LiteralPath $orgCache -Destination $orgOldCache}
 foreach($e in $orgProof.changes.PSObject.Properties){$dst=Join-Path $orgRoot $e.Name;New-Item -ItemType Directory -Path (Split-Path $dst -Parent) -Force|Out-Null;Copy-Item -LiteralPath (Join-Path $orgCandidate $e.Name) -Destination $dst}
 Start-OrgServices 'installed'
 Push-Location $orgRoot;try{& $orgPython scripts/check_acos_health.py;if($LASTEXITCODE -ne 0){throw 'Installed health/worker gate failed'}}finally{Pop-Location}
 @{pass=$true;backup=$orgBackup;source_manifest=$ReleaseManifest;schema_changed=$false;env_changed=$false;production_accepted=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $orgRoot '.runtime\organization-installed.json')
 Write-Output ('Local source installed; recoverable backup: '+$orgBackup)
}catch{
 $orgFailure=$_.Exception.Message
 foreach($name in @($orgStarted.Keys)){$r=$orgStarted[$name];$p=Get-Process -Id $r.id -ErrorAction SilentlyContinue;if($p -and $p.StartTime.ToUniversalTime().Ticks -eq $r.started -and $p.Path -eq $(if($name -eq 'web'){$orgNode}else{$orgPython})){if($name -eq 'web'){& taskkill.exe /PID $p.Id /T /F|Out-Null}else{Stop-Process -Id $p.Id;$p.WaitForExit(10000)|Out-Null}}}
 foreach($e in $orgProof.changes.PSObject.Properties){$dst=Join-Path $orgRoot $e.Name;if($e.Value.before){Copy-Item -LiteralPath (Join-Path $orgBackup ('source-before\'+$e.Name)) -Destination $dst -Force}elseif(Test-Path -LiteralPath $dst){$saved=Join-Path $orgBackup ('failed-source\'+$e.Name);New-Item -ItemType Directory -Path (Split-Path $saved -Parent) -Force|Out-Null;Move-Item -LiteralPath $dst -Destination $saved}}
 if(Test-Path -LiteralPath $orgOldCache){if(Test-Path -LiteralPath $orgCache){if((Resolve-Path -LiteralPath $orgCache).Path -ne 'F:\PAO-ACOS\apps\web\.pao-next' -or ((Get-Item -LiteralPath $orgCache).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Rollback cache path refused'};Move-Item -LiteralPath $orgCache -Destination (Join-Path $orgBackup 'failed-cache')};Move-Item -LiteralPath $orgOldCache -Destination $orgCache}
 Start-OrgServices 'rollback'
 throw "Local release failed; source/cache retained, no database restore performed: $orgFailure"
}
