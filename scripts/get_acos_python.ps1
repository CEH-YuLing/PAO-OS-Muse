# A local release pin selects an isolated venv; it never changes an execution binding.
function Get-AcosPython([string]$RepoRoot) {
    $root = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
    $pinPath = Join-Path $root '.runtime\acos-python-runtime.json'
    if (-not (Test-Path -LiteralPath $pinPath)) { return (Join-Path $root '.venv\Scripts\python.exe') }
    $pinItem = Get-Item -LiteralPath $pinPath -ErrorAction Stop
    if ($pinItem.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) { throw 'Runtime pin must not be a link.' }
    $pin = Get-Content -LiteralPath $pinPath -Raw | ConvertFrom-Json
    if ($pin.version -ne 1 -or $pin.relative_path -notmatch '^\.runtime/python-releases/[0-9a-f]{32}/Scripts/python\.exe$' -or $pin.python_sha256 -notmatch '^[0-9a-f]{64}$') { throw 'Invalid local Python release pin.' }
    $python = [IO.Path]::GetFullPath((Join-Path $root $pin.relative_path))
    if (-not $python.StartsWith(($root+'\'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Python release outside project.' }
    $item = Get-Item -LiteralPath $python -ErrorAction Stop
    while ($item.FullName -ne $root) {
        if ($item.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) { throw 'Python release must not follow a link.' }
        $item = if ($item -is [IO.DirectoryInfo]) { $item.Parent } else { $item.Directory }
        if (-not $item) { throw 'Python release root could not be verified.' }
    }
    if ((Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pin.python_sha256) { throw 'Python release binary hash mismatch.' }
    return $python
}
