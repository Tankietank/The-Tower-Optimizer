# Portable Windows executable

Tower Optimizer can be packaged as a folder-style Windows build so players do not need Python or PowerShell. This document covers the **maintainer MVP** workflow; a GitHub Actions release job is planned separately.

## What users get

After building, distribute the entire `dist/TowerOptimizer/` folder (zip it for download). Users double-click `TowerOptimizer.exe`:

1. Streamlit starts on `127.0.0.1` with a free local port.
2. The default browser opens automatically.
3. Profiles, backups, and custom icons live in a writable folder:
   - Default: `%LOCALAPPDATA%\TowerOptimizer`
   - Override: set `TOWER_OPTIMIZER_DATA_DIR` before launching.

The install directory (including `Program Files`) stays read-only; no profile data is written beside the executable unless `%LOCALAPPDATA%` is unavailable.

## Prerequisites

- Windows 10/11
- Python 3.11 or 3.12
- Project virtual environment with runtime dependencies installed

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Build

From the repository root:

```powershell
.\scripts\build_windows_exe.ps1
```

Output: `dist/TowerOptimizer/TowerOptimizer.exe` plus bundled dependencies (~hundreds of MB).

### Smoke-test the launcher without PyInstaller

```powershell
$env:TOWER_OPTIMIZER_DATA_DIR = "$env:LOCALAPPDATA\TowerOptimizer-dev"
python scripts\windows_launcher.py
```

## Architecture

| Piece | Role |
| --- | --- |
| `scripts/windows_launcher.py` | PyInstaller entry point; sets data dir, picks port, opens browser, runs Streamlit |
| `scripts/build_windows_exe.ps1` | Installs PyInstaller, bundles app + assets + game JSON |
| `tower_optimizer/runtime_paths.py` | Honors `TOWER_OPTIMIZER_DATA_DIR` for profiles and custom icons |

PyInstaller uses **onedir** mode (not one-file) because Streamlit pulls many runtime files. The build script uses `--collect-all streamlit` to reduce missing-module failures.

## Known limitations (MVP)

- Console window remains visible (`--console`) so startup errors are visible; a windowless build can switch to `--noconsole` after QA.
- First cold start can take 10–30 seconds while Streamlit initializes.
- Antivirus heuristics may flag fresh PyInstaller builds; code-signing and CI builds will help.
- No auto-update channel yet; users replace the folder or download a new zip.
- Effective Paths `.xlsx` imports still require the user to browse to their own workbook files.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Browser never opens | Firewall blocking localhost; try the URL printed in the console |
| Missing module at runtime | Re-run build after `pip install -e ".[dev]"`; add `--hidden-import` in the PS1 script |
| Profiles not saved | Confirm `%LOCALAPPDATA%\TowerOptimizer\profiles` exists and is writable |
| Wrong data folder | Echo `$env:TOWER_OPTIMIZER_DATA_DIR` — launcher respects a pre-set value |

## Roadmap

- GitHub Actions workflow producing versioned release zips
- `--noconsole` build + log file under the data directory
- Optional portable mode: `data/` beside the executable when `TOWER_OPTIMIZER_PORTABLE=1`
