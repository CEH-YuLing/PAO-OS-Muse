# One-time local security release only, not a public deployment or database migration.
param([Parameter(Mandatory=$true)][string]$BrowserReceipt)
$ErrorActionPreference='Stop'
$p3Root=Split-Path $PSScriptRoot -Parent
if((Resolve-Path -LiteralPath $p3Root).Path -ne 'F:\PAO-ACOS'){throw 'Wrong local release target'}
$p3Candidate='F:\Apex\phase3-candidate'
$p3ReceiptPath=(Resolve-Path -LiteralPath $BrowserReceipt).Path
if(-not $p3ReceiptPath.StartsWith('F:\PAO-ACOS\.runtime\phase3-browser-runs\')){throw 'Wrong browser evidence scope'}
$p3Proof=Get-Content -Raw -LiteralPath $p3ReceiptPath | ConvertFrom-Json
if(-not $p3Proof.pass -or $p3Proof.next_version -ne '15.5.28'){throw 'Patched browser gate required'}
$p3Baseline=Get-Content -Raw -LiteralPath 'F:\PAO-ACOS\.runtime\checkpoints\p0-20261017T061447-61ce95cf\manifest.json' | ConvertFrom-Json
$p3Files=@('package.json','package-lock.json','apps/web/package.json')
foreach($p3File in $p3Files){
 $p3Expected=$p3Baseline.source.files.PSObject.Properties[$p3File].Value
 if((Get-FileHash -LiteralPath (Join-Path $p3Root $p3File)).Hash.ToLower() -ne $p3Expected){throw 'Manifest changed since approved baseline; preserve it'}
 if($p3File -ne 'apps/web/package.json' -and (Get-FileHash -LiteralPath (Join-Path $p3Candidate $p3File)).Hash.ToLower() -ne $p3Proof.root_dependency_hashes.PSObject.Properties[$p3File].Value){throw 'Candidate dependency proof changed'}
}
$p3RecordsPath=Join-Path $p3Root '.runtime/acos-processes.json'
$p3Records=Get-Content -Raw -LiteralPath $p3RecordsPath | ConvertFrom-Json
$p3Old=$p3Records.web
$p3Process=Get-Process -Id $p3Old.id -ErrorAction Stop
$p3Node=(Get-Command node).Source
if($p3Process.StartTime.ToUniversalTime().Ticks -ne $p3Old.started -or $p3Process.Path -ne $p3Node){throw 'Web process identity mismatch'}
$p3Modules=Join-Path $p3Root 'node_modules'
$p3Item=Get-Item -LiteralPath $p3Modules
if($p3Item.LinkType -or $p3Item.FullName -ne 'F:\PAO-ACOS\node_modules'){throw 'Unexpected dependency target'}
$p3Backup=Join-Path $p3Root ('.runtime/phase3-web-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $p3Backup | Out-Null
foreach($p3File in $p3Files){Copy-Item -LiteralPath (Join-Path $p3Root $p3File) -Destination (Join-Path $p3Backup ($p3File.Replace('/','_')))}
$p3OldModules=Join-Path $p3Backup 'node_modules-before'
if(-not [IO.Path]::GetFullPath($p3OldModules).StartsWith('F:\PAO-ACOS\.runtime\phase3-web-')){throw 'Unsafe rollback path'}
$p3Moved=$false
$script:p3StartedWeb=$null
function Start-P3Web([string]$p3Label){
 $env:PAO_API_URL='http://127.0.0.1:8100';$env:PAO_BUILD_CHECK='0';$env:NEXT_TELEMETRY_DISABLED='1'
 $p3New=Start-Process -FilePath $p3Node -ArgumentList @('node_modules/next/dist/bin/next','dev','apps/web','--hostname','127.0.0.1','--port','3200') -WindowStyle Hidden -PassThru -WorkingDirectory $p3Root -RedirectStandardOutput (Join-Path $p3Backup ($p3Label+'.stdout.log')) -RedirectStandardError (Join-Path $p3Backup ($p3Label+'.stderr.log'))
 $script:p3StartedWeb=$p3New
 $p3Records.web=@{id=$p3New.Id;started=$p3New.StartTime.ToUniversalTime().Ticks}
 $p3Records | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $p3RecordsPath
 $p3Secondary=Join-Path $p3Root '.runtime/acos-web-process.json'
 if(Test-Path -LiteralPath $p3Secondary){$p3Saved=Get-Content -Raw -LiteralPath $p3Secondary | ConvertFrom-Json;if($p3Saved.id -eq $p3Old.id){$p3Records.web | ConvertTo-Json | Set-Content -LiteralPath $p3Secondary}}
 for($p3Probe=0;$p3Probe -lt 80;$p3Probe++){
  if($p3New.HasExited){throw 'Web launcher exited; inspect retained release log'}
  try{if((Invoke-WebRequest -Uri 'http://127.0.0.1:3200/' -TimeoutSec 3).StatusCode -eq 200){return}}catch{}
  Start-Sleep -Milliseconds 500
 };throw 'Web startup not verified'
}
try{
 & taskkill /PID $p3Process.Id /T /F | Out-Null
 if($LASTEXITCODE -ne 0){throw 'Unable to stop verified web tree'}
 Start-Sleep -Milliseconds 500
 if(Get-NetTCPConnection -State Listen -LocalPort 3200 -ErrorAction SilentlyContinue){throw 'Port3200 still occupied; refuse duplicate start'}
 Move-Item -LiteralPath $p3Modules -Destination $p3OldModules
 $p3Moved=$true
 foreach($p3File in $p3Files){Copy-Item -LiteralPath (Join-Path $p3Candidate $p3File) -Destination (Join-Path $p3Root $p3File)}
 Push-Location $p3Root
 try{& $p3Node (Join-Path (Split-Path $p3Node -Parent) 'node_modules/npm/bin/npm-cli.js') ci --no-audit --no-fund --registry=https://registry.npmjs.org *> (Join-Path $p3Backup 'npm-ci.log');if($LASTEXITCODE -ne 0){throw 'Candidate dependency installation failed'}}finally{Pop-Location}
 Start-P3Web 'patched'
 @{pass=$true;next='15.5.28';rollback_directory=$p3Backup;database_changed=$false;backend_changed=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $p3Root '.runtime/phase3-web-release.json')
 Write-Output ('Patched local Web3200 ready; rollback preserved at '+$p3Backup)
}catch{
 # Never delete a partial dependency tree or restore database/schema to recover Web.
 if($script:p3StartedWeb){$p3Owned=Get-Process -Id $script:p3StartedWeb.Id -ErrorAction SilentlyContinue;if($p3Owned -and $p3Owned.Path -eq $p3Node -and $p3Owned.StartTime.ToUniversalTime().Ticks -eq $script:p3StartedWeb.StartTime.ToUniversalTime().Ticks){& taskkill /PID $p3Owned.Id /T /F | Out-Null}}
 if($p3Moved){
  if(Test-Path -LiteralPath $p3Modules){Move-Item -LiteralPath $p3Modules -Destination (Join-Path $p3Backup 'node_modules-incomplete')}
  Move-Item -LiteralPath $p3OldModules -Destination $p3Modules
  foreach($p3File in $p3Files){Copy-Item -LiteralPath (Join-Path $p3Backup ($p3File.Replace('/','_'))) -Destination (Join-Path $p3Root $p3File)}
 }
 if(-not (Get-NetTCPConnection -State Listen -LocalPort 3200 -ErrorAction SilentlyContinue)){Start-P3Web 'rollback'}
 throw 'Patched release did not complete; old manifests/dependencies preserved or restored. Inspect release logs; no database rollback was attempted.'
}
