$ErrorActionPreference = "Stop"
$source = $PSScriptRoot
$target = Read-Host "Enter your existing tower_optimizer folder path"

if (-not (Test-Path $target)) {
    throw "Target folder not found: $target"
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$codeBackup = Join-Path $target "code_backups\v2_preview5_$stamp"
New-Item -ItemType Directory -Force -Path $codeBackup | Out-Null

foreach ($item in @(
    "app.py", "requirements.txt", "README.md", "CUSTOM_ICONS.txt", "run_optimizer.ps1", "run_engine_health.ps1",
    "run_smoke_test.ps1", "run_v1_10_validation.ps1", "run_v2_preview_validation.ps1"
)) {
    $existing = Join-Path $target $item
    if (Test-Path $existing) {
        Copy-Item $existing $codeBackup -Force
    }
}
foreach ($folder in @("tower_optimizer", "tools", "assets")) {
    $existing = Join-Path $target $folder
    if (Test-Path $existing) {
        Copy-Item $existing $codeBackup -Recurse -Force
    }
}

Copy-Item (Join-Path $source "app.py") $target -Force
Copy-Item (Join-Path $source "tower_optimizer") $target -Recurse -Force
Copy-Item (Join-Path $source "tools") $target -Recurse -Force
Copy-Item (Join-Path $source "assets") $target -Recurse -Force
Copy-Item (Join-Path $source "requirements.txt") $target -Force
Copy-Item (Join-Path $source "README.md") $target -Force
Copy-Item (Join-Path $source "CUSTOM_ICONS.txt") $target -Force
Copy-Item (Join-Path $source "run_optimizer.ps1") $target -Force
Copy-Item (Join-Path $source "run_engine_health.ps1") $target -Force
Copy-Item (Join-Path $source "run_smoke_test.ps1") $target -Force
Copy-Item (Join-Path $source "run_v2_preview_validation.ps1") $target -Force

$oldValidation = Join-Path $target "run_v1_10_validation.ps1"
if (Test-Path $oldValidation) {
    Remove-Item $oldValidation -Force
}

Write-Host "Installed Tower Optimizer v2.0.0 Preview 6. Existing profiles, battle history, planner queues, backups, update overlays, and data\custom_icons were not changed."
Write-Host "Code backup: $codeBackup"
Write-Host "Run .\run_smoke_test.ps1 and .\run_v2_preview_validation.ps1 before starting Streamlit."
