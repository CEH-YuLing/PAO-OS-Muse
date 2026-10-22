# Interactive handoff to the original Claude CLI, not a PAO web OAuth client.
param([switch]$Preflight)
$ErrorActionPreference = 'Stop'
$paoRepo = 'F:\PAO-ACOS'
$paoSetupStage = 'launcher'
try {
    if (-not $Preflight) { $Host.UI.RawUI.WindowTitle = 'PAO - Claude native sign-in (ready)' }
    $env:PYTHONUTF8 = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $paoSetupStage = 'runtime-pin'
    # A parent PowerShell7 can export a PSModulePath its Windows PowerShell5
    # child cannot load. Import the matching signed system module in this
    # process only; retain the existing Get-AcosPython binary-hash guard.
    if ($PSVersionTable.PSVersion.Major -eq 5) {
        Import-Module 'C:\Windows\System32\WindowsPowerShell\v1.0\Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1' -Force -ErrorAction Stop
    }
    . (Join-Path $paoRepo 'scripts\get_acos_python.ps1')
    $paoPython = Get-AcosPython $paoRepo
    $paoSetupStage = 'native-profile'
    $paoAction = if ($Preflight) { 'status' } else { 'login' }
    & $paoPython -B (Join-Path $paoRepo 'scripts\ea3_claude_personal.py') $paoAction
    if ($LASTEXITCODE -ne 0) { throw 'Claude setup did not complete. Keep the window open and report only the error, never a code or token.' }
} catch {
    $paoFailedCommand = $_.Exception.CommandName
    if ($paoFailedCommand -notin @('Get-AcosPython','Get-FileHash','Join-Path','Get-Item','Test-Path','Get-Content')) { $paoFailedCommand = 'not_in_diagnostic_allowlist' }
    $paoErrorInfo = @{ stage = $paoSetupStage; error_type = $_.Exception.GetType().Name; command = $paoFailedCommand; line = $_.InvocationInfo.ScriptLineNumber; login_complete = $false } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText((Join-Path $paoRepo ('.runtime\ea3-claude-native-20261020\launcher-error-'+[guid]::NewGuid().ToString('N')+'.json')), $paoErrorInfo)
    Write-Host ('Claude setup stopped at '+$paoSetupStage+'. No password or token is needed in chat.') -ForegroundColor Yellow
    if ($Preflight) { exit 1 }
}
if ($Preflight) { exit 0 }
Write-Host 'This step only signs in. PAO chat/model acceptance is still pending.'
[void](Read-Host 'Press Enter to close this window')
