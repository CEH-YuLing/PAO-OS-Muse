param([ValidateSet('cpu','vulkan','auto')][string]$Engine = 'cpu')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$executable = Join-Path $repoRoot '.runtime\ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw 'Install Ollama standalone under .runtime/ollama first; see docs/LOCAL-DEVELOPMENT.md' }
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = Join-Path $repoRoot '.runtime\models'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
if ($Engine -eq 'cpu') {
    $env:CUDA_VISIBLE_DEVICES = '-1'
    $env:GGML_VK_VISIBLE_DEVICES = '-1'
    $env:OLLAMA_VULKAN = '0'
} elseif ($Engine -eq 'vulkan') {
    $env:CUDA_VISIBLE_DEVICES = '-1'
    $env:GGML_VK_VISIBLE_DEVICES = '0'
    $env:OLLAMA_VULKAN = '1'
} else {
    Remove-Item Env:CUDA_VISIBLE_DEVICES -ErrorAction SilentlyContinue
    Remove-Item Env:GGML_VK_VISIBLE_DEVICES -ErrorAction SilentlyContinue
    Remove-Item Env:OLLAMA_VULKAN -ErrorAction SilentlyContinue
}
& $executable serve
exit $LASTEXITCODE
