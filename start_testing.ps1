# Start the trained candidate for local testing; qualification remains unchanged.
foreach ($taskCheckpoint in @('qwen_nutrition_evidence_candidate', 'smolvlm_500m')) {
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot "models\$taskCheckpoint\model.safetensors"))) {
        throw "Missing weights for $taskCheckpoint. Follow the download/training steps in README.md before starting model testing."
    }
}
$env:NUTRIGUIDE_TEXT_MODEL = Join-Path $PSScriptRoot 'models\qwen_nutrition_evidence_candidate'
$env:NUTRIGUIDE_ALLOW_UNQUALIFIED = '1'
$env:NUTRIGUIDE_CPU_INT8 = '0'
$env:NUTRIGUIDE_VISION_MODEL = Join-Path $PSScriptRoot 'models\smolvlm_500m'
$env:HF_HUB_OFFLINE = '1'
$env:NUTRIGUIDE_WARMUP = '1'
Set-Location -LiteralPath $PSScriptRoot
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -u server.py 8088
