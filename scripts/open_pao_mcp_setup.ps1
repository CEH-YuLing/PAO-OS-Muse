param([switch]$Preflight)
$ErrorActionPreference = 'Stop'
try {
    if ($PSVersionTable.PSVersion.Major -eq 5) {
        Import-Module 'C:\Windows\System32\WindowsPowerShell\v1.0\Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1' -Force
    }
    $paoMcpRoot = Split-Path $PSScriptRoot -Parent
    if ($paoMcpRoot -ne 'F:\PAO-ACOS') { throw 'Sai thu muc PAO' }
    $env:PYTHONUTF8 = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    . (Join-Path $PSScriptRoot 'get_acos_python.ps1')
    $paoMcpPython = Get-AcosPython $paoMcpRoot
    if ($Preflight) {
        & $paoMcpPython -I -B (Join-Path $PSScriptRoot 'pao_mcp.py') --help
        exit $LASTEXITCODE
    }
    $Host.UI.RawUI.WindowTitle = 'PAO - MCP read-only setup'
    & $paoMcpPython -I -B (Join-Path $PSScriptRoot 'pao_mcp.py') setup
    if ($LASTEXITCODE -ne 0) { Write-Host 'Chua hoan tat. Khong gui mat khau/token trong chat.' }
} catch {
    Write-Host 'Khong mo duoc thiet lap PAO MCP. Xem huong dan, khong dan thong tin bi mat vao chat.'
    if ($Preflight) { exit 1 }
}
Read-Host 'Nhan Enter de dong'
