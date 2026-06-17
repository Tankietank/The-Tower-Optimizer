# Publish Tower Optimizer v2.0.0-preview.6 to GitHub.
# Run from this folder in PowerShell:
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\publish_to_github.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$git = "C:\Program Files\Git\cmd\git.exe"
if (-not (Test-Path $git)) {
    throw "Git not found at $git. Install Git for Windows or update the path in this script."
}

Write-Host "== Validation =="
python tools/smoke_test.py
python tools/v2_preview_validation.py
python tools/public_release_audit.py
python -m pip install -e ".[dev]" | Out-Null
python -m pytest -q

Write-Host "== Source release archive =="
python scripts/build_source_release.py

Write-Host "== Git publish =="
& $git branch -M main
& $git add -A
$staged = & $git diff --cached --name-only
if ($staged -match '(?i)(^data/|tanker|\.xlsx|\.csv|diagnostic|backup)') {
    throw "Refusing to publish: staged files may include private data.`n$($staged -join "`n")"
}
& $git status --short

$commitMsg = @"
Publish full v2.0.0-preview.6 source tree.

Includes application package, tests, docs, assets, CI workflows, and validation tools.
Fixes repository URLs and version metadata for Tankietank/The-Tower-Optimizer.
"@

& $git commit -m $commitMsg
& $git fetch origin main
& $git pull origin main --allow-unrelated-histories --no-edit
& $git push -u origin main
& $git tag -a v2.0.0-preview.6 -m "Tower Optimizer v2.0.0-preview.6 pre-release"
& $git push origin v2.0.0-preview.6

Write-Host ""
Write-Host "Push complete."
Write-Host "Create the GitHub pre-release:"
Write-Host "  1. Open https://github.com/Tankietank/The-Tower-Optimizer/releases/new"
Write-Host "  2. Choose tag v2.0.0-preview.6"
Write-Host "  3. Mark as pre-release"
Write-Host "  4. Attach dist\tower-optimizer-2.0.0-preview.6-source.zip"
Write-Host "  5. Attach dist\tower-optimizer-2.0.0-preview.6-source.zip.sha256"
Write-Host ""
Write-Host "Or, if GitHub CLI is installed:"
Write-Host '  gh release create v2.0.0-preview.6 --prerelease --title "v2.0.0-preview.6" --notes-file RELEASE_NOTES_preview6.md dist\tower-optimizer-2.0.0-preview.6-source.zip dist\tower-optimizer-2.0.0-preview.6-source.zip.sha256'
