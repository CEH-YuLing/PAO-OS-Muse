# Recover only the verified ACOS Web and its generated cache; preserve data/API.
$ErrorActionPreference='Stop'
$repoRoot=(Resolve-Path -LiteralPath (Split-Path $PSScriptRoot -Parent)).Path
if ($repoRoot -ne 'F:\PAO-ACOS') { throw 'ACOS checkout required.' }
$runtime=Join-Path $repoRoot '.runtime'
$recordsPath=Join-Path $runtime 'acos-processes.json'
$records=Get-Content -LiteralPath $recordsPath -Raw | ConvertFrom-Json
$record=$records.web
if (-not $record) { throw 'Missing verified Web record.' }
$process=Get-Process -Id $record.id -ErrorAction Stop
$nodeExe=(Get-Command node).Source
if ($process.StartTime.ToUniversalTime().Ticks -ne $record.started -or
    -not [string]::Equals($process.Path,$nodeExe,[StringComparison]::OrdinalIgnoreCase)) { throw 'Web process identity mismatch.' }
$native=Get-CimInstance Win32_Process -Filter ('ProcessId='+$record.id)
if ($native.CommandLine -notmatch 'node_modules/next/dist/bin/next.+apps/web.+--port.+3200') { throw 'Web command is not the owned ACOS service.' }
& taskkill.exe /PID $record.id /T /F
if ($LASTEXITCODE -ne 0) { throw 'Unable to stop owned Web tree.' }
$cache=Join-Path $repoRoot 'apps\web\.pao-next'
if (Test-Path -LiteralPath $cache) {
    $resolved=(Resolve-Path -LiteralPath $cache).Path
    if ($resolved -ne 'F:\PAO-ACOS\apps\web\.pao-next' -or
        ((Get-Item -LiteralPath $resolved).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected cache path.' }
    $destination=Join-Path $runtime ('web-cache-quarantine-'+[guid]::NewGuid().ToString('N'))
    if (-not $destination.StartsWith('F:\PAO-ACOS\.runtime\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected quarantine path.' }
    Move-Item -LiteralPath $resolved -Destination $destination
    Write-Host 'Generated Web cache preserved in private runtime quarantine.'
}
$env:PAO_API_URL='http://127.0.0.1:8100'
$env:PAO_BUILD_CHECK='0'
$replacement=Start-Process -FilePath $nodeExe -ArgumentList @('node_modules/next/dist/bin/next','dev','apps/web','--hostname','127.0.0.1','--port','3200') -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'acos-web.stdout.log') -RedirectStandardError (Join-Path $runtime 'acos-web.stderr.log')
$value=@{id=$replacement.Id;started=$replacement.StartTime.ToUniversalTime().Ticks}
$records.web=$value
$records | ConvertTo-Json | Set-Content -LiteralPath $recordsPath
$value | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'acos-web-process.json')
Write-Host ('Replaced only owned ACOS Web PID '+$replacement.Id)
$ready=$false
for ($attempt=0;$attempt -lt 15;$attempt++) {
    if ($replacement.HasExited) { throw 'Replacement Web exited during startup.' }
    try {
        $response=Invoke-WebRequest -Uri 'http://127.0.0.1:3200/' -UseBasicParsing -TimeoutSec 3
        if ($response.StatusCode -eq 200) { $ready=$true;break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) { throw 'Replacement Web did not become ready; inspect preserved runtime logs.' }
