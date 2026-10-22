param([switch]$RepairMissing, [int]$Cycles=1, [int]$PollSeconds=15, [int]$MaxRestarts=3)
$ErrorActionPreference='Stop'
if ($Cycles -lt 1 -or $Cycles -gt 100 -or $PollSeconds -lt 5 -or $PollSeconds -gt 60 -or $MaxRestarts -lt 1 -or $MaxRestarts -gt 3) {throw 'Invalid supervisor bounds'}
$repoRoot=Split-Path $PSScriptRoot -Parent
if ((Resolve-Path -LiteralPath $repoRoot).Path -ne 'F:\PAO-ACOS') {throw 'Supervisor is ACOS-local only'}
$env:PAO_ROOT=$repoRoot
$env:PYTHONPATH=@((Join-Path $repoRoot 'apps\api'), (Join-Path $repoRoot 'packages\cli-runtime')) -join [IO.Path]::PathSeparator
$env:PYTHONDONTWRITEBYTECODE='1'
$restarts=0
. (Join-Path $PSScriptRoot 'get_acos_python.ps1')
Push-Location $repoRoot
try {
 for ($cycle=0;$cycle -lt $Cycles;$cycle++) {
  $pythonExe=Get-AcosPython $repoRoot
  $ledger=Get-Content -LiteralPath '.runtime\acos-processes.json' -Raw|ConvertFrom-Json
  $missing=@()
  foreach($name in @('api','worker')) {
   $entry=$ledger.$name
   $proc=if($entry){Get-Process -Id $entry.id -ErrorAction SilentlyContinue}else{$null}
   if(-not $proc -or $proc.StartTime.ToUniversalTime().Ticks -ne $entry.started){$missing+=$name;continue}
   if($proc.Path -ne $pythonExe){throw 'Recorded process executable mismatch; no automatic kill'}
   $row=Get-CimInstance Win32_Process -Filter "ProcessId=$($entry.id)"
   $needle=if($name -eq 'api'){'pao.main:app'}else{'pao.runtime.WorkerSettings'}
   if(-not $row.CommandLine.Contains($needle)){throw 'Recorded process entrypoint mismatch; no automatic kill'}
  }
  if($missing.Count -and $RepairMissing) {
   if($restarts -ge $MaxRestarts){throw 'Restart budget exhausted'}
   & $pythonExe scripts\check_acos_idle.py --safe-repair
   if($LASTEXITCODE -ne 0){throw 'Active/pending jobs: manual recovery required; no automatic rebind'}
   & .\scripts\start_acos_local.ps1
   $restarts++
  }
  [pscustomobject]@{cycle=$cycle+1;missing=$missing;restarts=$restarts;mode=if($RepairMissing){'bounded-repair'}else{'observe-only'};productionAccepted=$false}|ConvertTo-Json -Compress
  if($cycle+1 -lt $Cycles){Start-Sleep -Seconds $PollSeconds}
 }
} finally {Pop-Location}
