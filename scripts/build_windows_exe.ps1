# Build a portable Windows folder distribution for Tower Optimizer (PyInstaller onedir).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$venvPython = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Create and activate a venv first: python -m venv .venv ; .\.venv\Scripts\Activate.ps1 ; pip install -e `".[dev]`""
}

Write-Host "Installing build dependencies..."
& $venvPython -m pip install --upgrade pip pyinstaller | Out-Null
& $venvPython -m pip install -e ".[dev]" | Out-Null

$distRoot = Join-Path $PWD "dist\TowerOptimizer"
$buildRoot = Join-Path $PWD "build\TowerOptimizer"
if (Test-Path $distRoot) { Remove-Item $distRoot -Recurse -Force }
if (Test-Path $buildRoot) { Remove-Item $buildRoot -Recurse -Force }

$addData = @(
    "$(Join-Path $PWD 'app.py');.",
    "$(Join-Path $PWD '.streamlit\config.toml');.streamlit",
    "$(Join-Path $PWD 'assets');assets",
    "$(Join-Path $PWD 'tower_optimizer');tower_optimizer",
    "$(Join-Path $PWD 'data\README.md');data"
)

$pyArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--name", "TowerOptimizer",
    "--onedir",
    "--noconsole",
    "--distpath", (Join-Path $PWD "dist"),
    "--workpath", (Join-Path $PWD "build"),
    "--paths", $PWD,
    "--collect-all", "streamlit",
    "--collect-all", "altair",
    "--collect-all", "pandas",
    "--hidden-import", "streamlit.web.cli",
    "--hidden-import", "streamlit.runtime.scriptrunner.magic_funcs",
    "--hidden-import", "PIL",
    "--hidden-import", "openpyxl",
    "--hidden-import", "nrbf",
    "--hidden-import", "tkinter"
)
foreach ($pair in $addData) {
    $pyArgs += @("--add-data", $pair)
}
$pyArgs += (Join-Path $PWD "scripts\windows_launcher.py")

Write-Host "Running PyInstaller..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $venvPython @pyArgs 2>&1 | ForEach-Object { Write-Host $_ }
$pyExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($pyExit -ne 0) { throw "PyInstaller failed with exit code $pyExit" }

$bat = @"
@echo off
rem Launch Tower Optimizer (same folder as this file).
cd /d "%~dp0"
start "" "%~dp0TowerOptimizer.exe"
"@
Set-Content -Path (Join-Path $distRoot "run_tower_optimizer.bat") -Value $bat -Encoding ASCII

$readme = @"
Tower Optimizer (portable Windows build)

Quick start
-----------
1. Double-click TowerOptimizer.exe (or run_tower_optimizer.bat)
2. Wait for the "Starting..." window — first launch can take 10–30 seconds
3. Your browser opens automatically at http://127.0.0.1:<port>

Your data (profiles, backups, custom icons)
-------------------------------------------
Default location:
  %LOCALAPPDATA%\TowerOptimizer

Portable mode (keep data beside this folder):
  Create an empty file named portable.txt next to TowerOptimizer.exe
  OR set environment variable TOWER_OPTIMIZER_PORTABLE=1 before launch
  Data will be stored in the data\ folder here.

Logs and troubleshooting
------------------------
If the app fails to start, open:
  %LOCALAPPDATA%\TowerOptimizer\launcher.log
(or data\launcher.log in portable mode)

Share launcher.log when asking for help.

See docs/WINDOWS_EXE.md in the source repository for maintainer notes.
"@
Set-Content -Path (Join-Path $distRoot "README.txt") -Value $readme -Encoding UTF8

Write-Host ""
Write-Host "Build complete: $distRoot"
Write-Host "Run: $(Join-Path $distRoot 'TowerOptimizer.exe')"
