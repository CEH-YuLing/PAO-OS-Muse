$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'get_acos_python.ps1')
$candidateRoot = Split-Path $PSScriptRoot -Parent
$testRoot = Join-Path $candidateRoot ('.runtime\pin-tests\'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
if ((Get-AcosPython $testRoot) -ne (Join-Path $testRoot '.venv\Scripts\python.exe')) { throw 'Default runtime changed.' }
$releaseId = [guid]::NewGuid().ToString('N')
$relative = '.runtime/python-releases/'+$releaseId+'/Scripts/python.exe'
$python = Join-Path $testRoot $relative
New-Item -ItemType Directory -Path (Split-Path $python -Parent) -Force | Out-Null
[IO.File]::WriteAllText($python, 'synthetic file; never executed')
$pin = @{version=1; relative_path=$relative; python_sha256=(Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant()}
$pinPath = Join-Path $testRoot '.runtime\acos-python-runtime.json'
function Write-TestPin { $pin | ConvertTo-Json | Set-Content -LiteralPath $pinPath }
function Assert-Rejected([scriptblock]$Action) {
    $rejected=$false
    try { & $Action | Out-Null } catch { $rejected=$true }
    if (-not $rejected) { throw 'Invalid runtime pin was accepted.' }
}
Write-TestPin
if ((Get-AcosPython $testRoot) -ne [IO.Path]::GetFullPath($python)) { throw 'Valid runtime pin rejected.' }
$pin.version=2; Write-TestPin; Assert-Rejected { Get-AcosPython $testRoot }; $pin.version=1
$pin.relative_path='../python.exe'; Write-TestPin; Assert-Rejected { Get-AcosPython $testRoot }; $pin.relative_path=$relative
$pin.python_sha256='0'*64; Write-TestPin; Assert-Rejected { Get-AcosPython $testRoot }
$pin.python_sha256=(Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant(); Write-TestPin
[IO.File]::WriteAllText($python, 'synthetic changed file')
Assert-Rejected { Get-AcosPython $testRoot }
$hashes=@{}
foreach($name in @('get_acos_python.ps1','start_acos_local.ps1','stop_acos_local.ps1','restart_acos_backend.ps1','supervise_acos_local.ps1','start_local.ps1')) {
    $parseErrors=$null
    [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$null,[ref]$parseErrors) | Out-Null
    if($parseErrors){throw ('Runtime helper syntax invalid: '+$name)}
    $hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $name) -Algorithm SHA256).Hash.ToLowerInvariant()
}
@{pass=$true; tests=6; source_hashes=$hashes; synthetic_only=$true; fixtures_preserved=$testRoot} | ConvertTo-Json -Depth 4
