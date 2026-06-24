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
    "$(Join-Path $PWD 'tower_optimizer\game_data');tower_optimizer\game_data",
    "$(Join-Path $PWD 'data\README.md');data"
)

$pyArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--name", "TowerOptimizer",
    "--onedir",
    "--console",
    "--distpath", (Join-Path $PWD "dist"),
    "--workpath", (Join-Path $PWD "build"),
    "--collect-all", "streamlit",
    "--collect-all", "altair",
    "--collect-all", "pandas",
    "--hidden-import", "streamlit.web.cli",
    "--hidden-import", "streamlit.runtime.scriptrunner.magic_funcs",
    "--hidden-import", "PIL",
    "--hidden-import", "openpyxl",
    "--hidden-import", "nrbf"
)
foreach ($pair in $addData) {
    $pyArgs += @("--add-data", $pair)
}
$pyArgs += (Join-Path $PWD "scripts\windows_launcher.py")

Write-Host "Running PyInstaller..."
& $venvPython @pyArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$readme = @"
Tower Optimizer (portable Windows build)

1. Double-click TowerOptimizer.exe
2. Your browser opens automatically at http://127.0.0.1:<port>
3. Profiles and custom icons are stored under:
   %LOCALAPPDATA%\TowerOptimizer

Set TOWER_OPTIMIZER_DATA_DIR before launch to use a different folder.
See docs/WINDOWS_EXE.md in the source repository for maintainer notes.
"@
Set-Content -Path (Join-Path $distRoot "README.txt") -Value $readme -Encoding UTF8

Write-Host ""
Write-Host "Build complete: $distRoot"
Write-Host "Run: $(Join-Path $distRoot 'TowerOptimizer.exe')"
