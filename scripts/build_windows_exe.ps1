# Build a portable Windows distribution for Tower Optimizer (PyInstaller).
# Default: onedir folder (most reliable for Streamlit).
# Optional: -SingleExe for one double-clickable file (slower first launch).
param(
    [switch]$SingleExe,
    [switch]$NoZip
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$appVersion = "2.0.0-preview.8"
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
$singleExePath = Join-Path $PWD "dist\TowerOptimizer.exe"
if (Test-Path $singleExePath) { Remove-Item $singleExePath -Force }

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
    $(if ($SingleExe) { "--onefile" } else { "--onedir" }),
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

Write-Host "Running PyInstaller ($(if ($SingleExe) { 'onefile' } else { 'onedir' }))..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $venvPython @pyArgs 2>&1 | ForEach-Object { Write-Host $_ }
$pyExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($pyExit -ne 0) { throw "PyInstaller failed with exit code $pyExit" }

if (-not $SingleExe) {
$bat = @"
@echo off
title Tower Optimizer
cd /d "%~dp0"
echo.
echo  Tower Optimizer - starting...
echo  Please wait — first launch can take several minutes.
echo.
start "" "%~dp0TowerOptimizer.exe"
"@
Set-Content -Path (Join-Path $distRoot "run_tower_optimizer.bat") -Value $bat -Encoding ASCII

$startHere = @"
================================================================================
  TOWER OPTIMIZER - START HERE
  (Unofficial fan tool for The Tower - Idle Tower Defense)
================================================================================

HOW TO RUN (2 STEPS)
--------------------

  1. Double-click  TowerOptimizer.exe
     (inside this folder — do not copy only the exe elsewhere)

  2. Wait for the "Starting Tower Optimizer..." window.
     FIRST LAUNCH: can take several minutes (timer shows elapsed time).
     Your web browser will open - that page IS the app.

  You only unzip/download once. After that, always use the same exe.


IF WINDOWS BLOCKS IT
--------------------

  You may see "Windows protected your PC":
    Click  More info  ->  Run anyway

  This is normal until a signed release is available.


FIRST TIME IN THE APP
---------------------

  1. Use the sidebar: Import / Export
  2. Upload your in-game backup file: playerInfo.dat
     (or enter your stats manually)
  3. Open Recommendation Dashboard for upgrade suggestions


WHERE YOUR PROFILES ARE SAVED
------------------------------

  Normal:     C:\Users\YOU\AppData\Local\TowerOptimizer
  Quick open: Win+R, type:  %LOCALAPPDATA%\TowerOptimizer

  USB / portable: create an empty file named portable.txt next to
  TowerOptimizer.exe - then data goes in the data\ folder here.


SOMETHING WRONG?
----------------

  - Wait 5 minutes on first launch before assuming it failed.
  - Open launcher.log in the folder above (or data\launcher.log if portable).
  - If the browser did not open, copy the http://127.0.0.1:... address from
    launcher.log into Chrome or Edge.
  - To fully quit: close the browser tab AND end TowerOptimizer.exe in
    Task Manager if it is still running.

  When asking for help, attach launcher.log.


UPDATING
--------

  Replace this whole TowerOptimizer folder with a new zip.
  Your profiles stay in AppData (or data\ in portable mode).


More help: https://github.com/Tankietank/The-Tower-Optimizer/blob/main/docs/GETTING_STARTED.md
================================================================================
"@
Set-Content -Path (Join-Path $distRoot "START_HERE.txt") -Value $startHere -Encoding UTF8
Copy-Item (Join-Path $distRoot "START_HERE.txt") (Join-Path $distRoot "README.txt") -Force
} else {
    $singleStartHere = @"
================================================================================
  TOWER OPTIMIZER - SINGLE FILE BUILD
================================================================================

HOW TO RUN
----------
  Double-click TowerOptimizer.exe
  Wait several minutes on first launch (it unpacks in the background).
  Your browser opens - that page IS the app.

  You can move this ONE file to Desktop or Downloads - no folder needed.
  Profiles save to:  %LOCALAPPDATA%\TowerOptimizer

IF WINDOWS BLOCKS IT:  More info  ->  Run anyway

More help: https://github.com/Tankietank/The-Tower-Optimizer/blob/main/docs/GETTING_STARTED.md
================================================================================
"@
    Set-Content -Path (Join-Path $PWD "dist\START_HERE.txt") -Value $singleStartHere -Encoding UTF8
}

if (-not $NoZip) {
    $zipName = if ($SingleExe) {
        "TowerOptimizer-$appVersion-Windows-single.exe.zip"
    } else {
        "TowerOptimizer-$appVersion-Windows.zip"
    }
    $zipPath = Join-Path $PWD "dist\$zipName"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Write-Host "Creating release zip: $zipName"
    if ($SingleExe) {
        Compress-Archive -Path $singleExePath, (Join-Path $PWD "dist\START_HERE.txt") -DestinationPath $zipPath -Force
    } else {
        Compress-Archive -Path $distRoot -DestinationPath $zipPath -Force
    }
    Write-Host "Release package: $zipPath"
}

Write-Host ""
if ($SingleExe) {
    Write-Host "Build complete: $singleExePath"
    Write-Host "Share dist\$zipName (one exe inside) OR the exe alone."
} else {
    Write-Host "Build complete: $distRoot"
    Write-Host "Share dist\TowerOptimizer-$appVersion-Windows.zip — users extract once, then double-click TowerOptimizer.exe"
}
