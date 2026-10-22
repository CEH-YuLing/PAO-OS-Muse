param([Parameter(Mandatory=$true)][string]$CiManifest,
      [Parameter(Mandatory=$true)][string]$WindowsReceipt,
      [Parameter(Mandatory=$true)][string]$PrivateReceipt,
      [Parameter(Mandatory=$true)][string]$ColdReceipt)
$ErrorActionPreference='Stop'
$root='F:\PAO-ACOS'
$candidate='F:\Apex\phase3-candidate'
$oldPython=Join-Path $root '.venv\Scripts\python.exe'
$env:PAO_ROOT=$root
$env:PYTHONPATH=Join-Path $root 'apps\api'
$env:PYTHONDONTWRITEBYTECODE='1'
& $oldPython (Join-Path $candidate 'scripts\check_phase3_candidate_release.py') $CiManifest $WindowsReceipt $PrivateReceipt $ColdReceipt
if($LASTEXITCODE -ne 0){throw 'Exact candidate gates did not pass; no runtime change.'}
$proof=Get-Content -LiteralPath (Join-Path $root '.runtime\phase3-candidate-release.json') -Raw | ConvertFrom-Json
$releaseId=[guid]::NewGuid().ToString('N')
$folder=Join-Path $root ('.runtime\phase3-backend-'+$releaseId)
$venv=Join-Path $root ('.runtime\python-releases\'+$releaseId)
New-Item -ItemType Directory -Path $folder | Out-Null
& $oldPython -m venv $venv
if($LASTEXITCODE -ne 0){throw 'Release venv creation failed; old runtime still serving.'}
$newPython=Join-Path $venv 'Scripts\python.exe'
$env:PYTHONPATH=''
& $newPython -m pip install --only-binary=:all: -r (Join-Path $candidate 'requirements.lock') *> (Join-Path $folder 'pip-install.log')
if($LASTEXITCODE -ne 0){throw 'Release dependency install failed; old runtime still serving.'}
$wheelSource=Join-Path $candidate '.runtime\backend-wheel-metadata\new'
$wheel=Join-Path $wheelSource 'pao_backend-0.1.0-py3-none-any.whl'
if((Get-FileHash -LiteralPath $wheel -Algorithm SHA256).Hash.ToLowerInvariant() -ne $proof.wheel_hashes.new.'pao_backend-0.1.0-py3-none-any.whl'){throw 'Release wheel changed.'}
& $newPython -m pip install --no-index --no-deps $wheel *> (Join-Path $folder 'metadata-install.log')
if($LASTEXITCODE -ne 0){throw 'Release metadata install failed; old runtime still serving.'}
& $newPython -m pip check *> (Join-Path $folder 'pip-check.log')
if($LASTEXITCODE -ne 0){throw 'Release dependency check failed.'}
& $newPython (Join-Path $candidate 'scripts\test_phase3_crypto_compat.py') *> (Join-Path $folder 'crypto-compat.log')
if($LASTEXITCODE -ne 0){throw 'Release crypto compatibility failed.'}
& $newPython -c 'import platform;from importlib.metadata import version;assert platform.python_version()=="3.12.14";assert version("PyJWT")=="2.15.1";assert version("cryptography")=="50.0.2"'
if($LASTEXITCODE -ne 0){throw 'Unexpected release runtime versions.'}
$env:PYTHONPATH=Join-Path $root 'apps\api'
& $oldPython (Join-Path $root 'scripts\backup_acos_checkpoint.py') | Out-File -LiteralPath (Join-Path $folder 'pre-checkpoint.json') -Encoding utf8
if($LASTEXITCODE -ne 0){throw 'Pre-cutover checkpoint failed; old runtime still serving.'}
& $oldPython (Join-Path $root 'scripts\check_acos_idle.py') *> (Join-Path $folder 'idle.log')
if($LASTEXITCODE -ne 0){throw 'Active jobs detected; old runtime still serving.'}
& $oldPython (Join-Path $candidate 'scripts\check_phase3_candidate_release.py') $CiManifest $WindowsReceipt $PrivateReceipt $ColdReceipt *> (Join-Path $folder 'pre-stop-gates.log')
if($LASTEXITCODE -ne 0){throw 'Source/evidence changed during preparation; old runtime still serving.'}
$changed=@($proof.changed_files)+@($proof.operator_changed_files)
$newFiles=@($proof.new_files)+@('scripts/get_acos_python.ps1','scripts/test_phase3_crypto_compat.py')
foreach($relative in $changed){
    $target=Join-Path $folder ('source-before\'+$relative)
    New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $root $relative) -Destination $target
}
$pinPath=Join-Path $root '.runtime\acos-python-runtime.json'
if(Test-Path -LiteralPath $pinPath){throw 'An active release pin already exists; review instead of overriding.'}
$envHash=(Get-FileHash -LiteralPath (Join-Path $root '.env') -Algorithm SHA256).Hash
$stopped=$false
$sourceChanged=$false
$metadataMoved=$false
$metadataPath=Join-Path $root 'apps\api\pao_backend.egg-info'
if(Test-Path -LiteralPath $metadataPath){
    if((Resolve-Path -LiteralPath $metadataPath).Path -ne 'F:\PAO-ACOS\apps\api\pao_backend.egg-info' -or
       (Get-Item -LiteralPath $metadataPath).Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)){throw 'Unexpected generated metadata path.'}
    foreach($item in Get-ChildItem -LiteralPath $metadataPath -Force){
        if($item.PSIsContainer -or $item.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint) -or
           $item.Name -notin @('PKG-INFO','SOURCES.txt','dependency_links.txt','requires.txt','top_level.txt')){throw 'Unrecognized package metadata; preserve for review.'}
    }
}
try{
    # Existing stop verifies idle, recorded executable and process start-time.
    $stopped=$true
    & (Join-Path $root 'scripts\stop_acos_local.ps1') -Components @('api','worker')
    if(Test-Path -LiteralPath $metadataPath){
        $preservedMetadata=Join-Path $folder 'generated-metadata-before'
        if(-not ([IO.Path]::GetFullPath($preservedMetadata)).StartsWith('F:\PAO-ACOS\.runtime\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe metadata preservation path.'}
        Move-Item -LiteralPath $metadataPath -Destination $preservedMetadata
        $metadataMoved=$true
    }
    $sourceChanged=$true
    foreach($relative in ($changed+$newFiles)){
        Copy-Item -LiteralPath (Join-Path $candidate $relative) -Destination (Join-Path $root $relative)
    }
    @{version=1; relative_path=('.runtime/python-releases/'+$releaseId+'/Scripts/python.exe');
      python_sha256=(Get-FileHash -LiteralPath $newPython -Algorithm SHA256).Hash.ToLowerInvariant();
      ci_manifest=$CiManifest; requirements_sha256=(Get-FileHash -LiteralPath (Join-Path $root 'requirements.lock') -Algorithm SHA256).Hash.ToLowerInvariant()} |
        ConvertTo-Json | Set-Content -LiteralPath $pinPath
    & (Join-Path $root 'scripts\start_acos_local.ps1') *> (Join-Path $folder 'start.log')
    $healthy=$false
    for($attempt=0;$attempt -lt 12;$attempt++){
        & $newPython (Join-Path $root 'scripts\check_acos_health.py') *> (Join-Path $folder 'health.log')
        if($LASTEXITCODE -eq 0){$healthy=$true;break}
        Start-Sleep -Seconds 1
    }
    if(-not $healthy){throw 'Release API/Web/worker health failed.'}
    & $newPython (Join-Path $root 'scripts\check_s62_live.py') *> (Join-Path $folder 'live.log')
    if($LASTEXITCODE -ne 0){throw 'Installed live contract/replay verification failed.'}
    if((Get-FileHash -LiteralPath (Join-Path $root '.env') -Algorithm SHA256).Hash -ne $envHash){throw 'Configuration changed during cutover.'}
    @{pass=$true;release_id=$releaseId;python=$newPython;old_venv_preserved=$true;env_unchanged=$true;
      binding_changed=$false;production_accepted=$false;evidence=$folder} | ConvertTo-Json |
        Set-Content -LiteralPath (Join-Path $root '.runtime\phase3-backend-installed.json')
    Write-Output 'Backend security release installed; API/Web/worker and archive replay verified. Production remains pending.'
}catch{
    $failure=$_.Exception.Message
    if($stopped){
        # If restart created children, stop only records matching this release path.
        $records=Get-Content -LiteralPath (Join-Path $root '.runtime\acos-processes.json') -Raw | ConvertFrom-Json
        foreach($name in @('api','worker')){
            $record=$records.$name
            if(-not $record){continue}
            $process=Get-Process -Id $record.id -ErrorAction SilentlyContinue
            if($process -and $process.StartTime.ToUniversalTime().Ticks -eq $record.started -and
               [string]::Equals($process.Path,$newPython,[StringComparison]::OrdinalIgnoreCase)){
                & taskkill.exe /PID $record.id /T /F | Out-Null
                if($LASTEXITCODE -ne 0){throw 'Cannot stop verified release process; rollback needs operator attention.'}
            }
        }
        if(Test-Path -LiteralPath $pinPath){
            $rejected=Get-Content -LiteralPath $pinPath -Raw | ConvertFrom-Json
            if($rejected.relative_path -ne ('.runtime/python-releases/'+$releaseId+'/Scripts/python.exe')){throw 'Runtime pin changed by another actor; preserve it for operator review.'}
            Move-Item -LiteralPath $pinPath -Destination (Join-Path $folder 'rejected-pin.json')
        }
        if($sourceChanged){foreach($relative in $changed){Copy-Item -LiteralPath (Join-Path $folder ('source-before\'+$relative)) -Destination (Join-Path $root $relative)}}
        if($metadataMoved){
            if(Test-Path -LiteralPath $metadataPath){throw 'Package metadata changed after cutover; preserve both copies for review.'}
            $preservedMetadata=Join-Path $folder 'generated-metadata-before'
            if(-not (Resolve-Path -LiteralPath $preservedMetadata).Path.StartsWith('F:\PAO-ACOS\.runtime\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe metadata rollback path.'}
            Move-Item -LiteralPath $preservedMetadata -Destination $metadataPath
        }
        & (Join-Path $root 'scripts\start_acos_local.ps1') *> (Join-Path $folder 'rollback-start.log')
        & $oldPython (Join-Path $root 'scripts\check_acos_health.py') *> (Join-Path $folder 'rollback-health.log')
        if($LASTEXITCODE -ne 0){throw 'Rollback retained old runtime, but health needs operator attention.'}
        & $oldPython (Join-Path $root 'scripts\check_s62_live.py') *> (Join-Path $folder 'rollback-live.log')
        if($LASTEXITCODE -ne 0){throw 'Rollback retained old runtime, but live/replay needs operator attention.'}
    }
    throw ('Security cutover rejected; old runtime/source preserved. '+$failure)
}
