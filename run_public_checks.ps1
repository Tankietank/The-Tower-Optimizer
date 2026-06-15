\
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

python -m compileall -q app.py tower_optimizer tools tests scripts
python .\tools\smoke_test.py
python .\tools\v2_preview_validation.py
python .\tools\public_release_audit.py
python -m pytest -q

Write-Host "All public-release checks passed."
