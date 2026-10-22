param([Parameter(Mandatory=$true)][string]$ReleaseManifest)
$ErrorActionPreference='Stop'
$uiRoot='F:\PAO-ACOS';$uiCandidate='F:\Apex\local-cycle-candidate'
$uiManifestPath=(Resolve-Path -LiteralPath $ReleaseManifest).Path
if($uiManifestPath -ne "$uiCandidate\.runtime\local-cycle-release.json"){throw 'Unexpected release manifest'}
$uiProof=Get-Content -LiteralPath $uiManifestPath -Raw | ConvertFrom-Json
if(-not $uiProof.pass -or $uiProof.backend_changed -or $uiProof.database_changed -or $uiProof.env_changed){throw 'UI-only proof required'}
foreach($entry in $uiProof.changes.PSObject.Properties){
 if(-not $entry.Name.StartsWith('apps/web/') -or $entry.Name.Contains('..')){throw 'Source scope refused'}
 $source=Join-Path $uiCandidate $entry.Name;$target=Join-Path $uiRoot $entry.Name
 if((Get-FileHash -LiteralPath $source).Hash.ToLower() -ne $entry.Value.after){throw 'Candidate changed after verification'}
 if($entry.Value.before){if((Get-FileHash -LiteralPath $target).Hash.ToLower() -ne $entry.Value.before){throw 'Installed source changed; preserve user edits'}}
 elseif(Test-Path -LiteralPath $target){throw 'New file already exists; refuse overwrite'}
}
$uiRecordsPath=Join-Path $uiRoot '.runtime\acos-processes.json';$uiRecords=Get-Content -LiteralPath $uiRecordsPath -Raw | ConvertFrom-Json
$uiOld=$uiRecords.web;$uiOwned=Get-Process -Id $uiOld.id -ErrorAction Stop
$uiNode='C:\Program Files\nodejs\node.exe'
if($uiOwned.StartTime.ToUniversalTime().Ticks -ne $uiOld.started -or $uiOwned.Path -ne $uiNode){throw 'Web process identity mismatch'}
$uiNative=Get-CimInstance Win32_Process -Filter ('ProcessId='+$uiOld.id)
if($uiNative.CommandLine -notmatch 'node_modules/next/dist/bin/next.+apps/web.+--port.+3200'){throw 'Unexpected Web command'}
$uiBackup=Join-Path $uiRoot ('.runtime\local-cycle-install-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $uiBackup | Out-Null
Copy-Item -LiteralPath $uiManifestPath -Destination (Join-Path $uiBackup 'release.json')
foreach($entry in $uiProof.changes.PSObject.Properties){if($entry.Value.before){$old=Join-Path $uiBackup ('before\'+$entry.Name);New-Item -ItemType Directory -Path (Split-Path $old -Parent) -Force | Out-Null;Copy-Item -LiteralPath (Join-Path $uiRoot $entry.Name) -Destination $old}}
$uiNew=$null
function Start-UxWeb([string]$label){
 $env:PAO_API_URL='http://127.0.0.1:8100';$env:PAO_BUILD_CHECK='0';$env:NEXT_TELEMETRY_DISABLED='1'
 $script:uiNew=Start-Process -FilePath $uiNode -ArgumentList @('node_modules/next/dist/bin/next','dev','apps/web','--hostname','127.0.0.1','--port','3200') -WorkingDirectory $uiRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $uiBackup "$label.stdout.log") -RedirectStandardError (Join-Path $uiBackup "$label.stderr.log")
 $uiRecords.web=@{id=$script:uiNew.Id;started=$script:uiNew.StartTime.ToUniversalTime().Ticks}
 $uiRecords | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $uiRecordsPath
 $uiRecords.web | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $uiRoot '.runtime\acos-web-process.json')
 for($i=0;$i -lt 60;$i++){if($script:uiNew.HasExited){throw 'Owned Web exited'};try{if((Invoke-WebRequest -Uri 'http://127.0.0.1:3200/' -TimeoutSec 3).StatusCode -eq 200){return}}catch{};Start-Sleep -Milliseconds 500};throw 'Web did not become ready'
}
$uiCache=Join-Path $uiRoot 'apps\web\.pao-next';$uiOldCache=Join-Path $uiBackup 'cache-before'
try{
 & taskkill.exe /PID $uiOwned.Id /T /F | Out-Null;if($LASTEXITCODE -ne 0){throw 'Stop verified Web failed'}
 if(Get-NetTCPConnection -State Listen -LocalPort 3200 -ErrorAction SilentlyContinue){throw 'Port3200 remains owned by another process'}
 if(Test-Path -LiteralPath $uiCache){if((Resolve-Path -LiteralPath $uiCache).Path -ne 'F:\PAO-ACOS\apps\web\.pao-next' -or ((Get-Item -LiteralPath $uiCache).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Unexpected generated cache'};Move-Item -LiteralPath $uiCache -Destination $uiOldCache}
 foreach($entry in $uiProof.changes.PSObject.Properties){$target=Join-Path $uiRoot $entry.Name;New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null;Copy-Item -LiteralPath (Join-Path $uiCandidate $entry.Name) -Destination $target}
 Start-UxWeb 'installed'
 @{pass=$true;backup=$uiBackup;browser_receipt=$uiProof.browser_receipt;frontend_sha256=$uiProof.frontend_sha256;backend_changed=$false;database_changed=$false;env_changed=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $uiRoot '.runtime\local-cycle-installed.json')
 Write-Output ('UI installed; rollback preserved: '+$uiBackup)
}catch{
 $uiError=$_.Exception.Message
 if($script:uiNew){$p=Get-Process -Id $script:uiNew.Id -ErrorAction SilentlyContinue;if($p -and $p.Path -eq $uiNode -and $p.StartTime.ToUniversalTime().Ticks -eq $script:uiNew.StartTime.ToUniversalTime().Ticks){& taskkill.exe /PID $p.Id /T /F | Out-Null}}
 foreach($entry in $uiProof.changes.PSObject.Properties){$target=Join-Path $uiRoot $entry.Name;if($entry.Value.before){Copy-Item -LiteralPath (Join-Path $uiBackup ('before\'+$entry.Name)) -Destination $target -Force}else{if(Test-Path -LiteralPath $target){$saved=Join-Path $uiBackup ('new-source\'+$entry.Name);New-Item -ItemType Directory -Path (Split-Path $saved -Parent) -Force | Out-Null;Move-Item -LiteralPath $target -Destination $saved}}}
 if(Test-Path -LiteralPath $uiOldCache){if(Test-Path -LiteralPath $uiCache){Move-Item -LiteralPath $uiCache -Destination (Join-Path $uiBackup 'failed-cache')};Move-Item -LiteralPath $uiOldCache -Destination $uiCache}
 if(-not (Get-NetTCPConnection -State Listen -LocalPort 3200 -ErrorAction SilentlyContinue)){Start-UxWeb 'rollback'}
 throw "UI release failed; recoverable files retained. $uiError"
}
