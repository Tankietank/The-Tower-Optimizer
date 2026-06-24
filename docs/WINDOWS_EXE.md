# Portable Windows executable

Tower Optimizer can be packaged as a folder-style Windows build so players do not need Python or PowerShell.

**End-user instructions:** share **[Getting started](GETTING_STARTED.md)** (or the `START_HERE.txt` / `README.txt` inside the zip). This document is mainly for maintainers who build the zip.

## What users get

After building, **zip the entire `dist/TowerOptimizer/` folder** and distribute that zip. Tell users:

1. **Extract All** — do not run from inside the zip.
2. Double-click **`TowerOptimizer.exe`** or **`run_tower_optimizer.bat`**.
3. Wait up to **30 seconds** for the “Starting…” window.
4. Use the browser tab that opens — that **is** the app.

What happens on launch:

1. A small **“Starting Tower Optimizer…”** window appears (first launch may take 10–30 seconds).
2. Streamlit starts on `127.0.0.1` with a free local port.
3. The default browser opens automatically.
4. Profiles, backups, and custom icons are saved to a writable folder (see below).

No console window is shown. Errors are written to **`launcher.log`** in the data folder and, for fatal startup failures, a Windows message box appears.

**Do not** instruct users to copy only `TowerOptimizer.exe` — the `_internal` folder and bundled files must stay together.

## Where your data lives

| Mode | Location |
| --- | --- |
| **Default** | `%LOCALAPPDATA%\TowerOptimizer` |
| **Portable** | `data\` beside `TowerOptimizer.exe` |
| **Custom** | Set `TOWER_OPTIMIZER_DATA_DIR` before launching |

**Portable mode** — keep profiles next to the app (USB stick, single folder copy):

- Create an empty file named `portable.txt` next to `TowerOptimizer.exe`, **or**
- Set `TOWER_OPTIMIZER_PORTABLE=1` before launch.

Important folders inside the data directory:

- `profiles/` — saved player profiles
- `custom_icons/` — icon overrides
- `launcher.log` — startup and error log in the data folder (share this when reporting problems)
- `launcher.log` next to `TowerOptimizer.exe` — always records which data folder was selected

The install directory stays read-only; nothing is written beside the executable unless portable mode is enabled.

## End-user troubleshooting

| Symptom | What to try |
| --- | --- |
| Nothing seems to happen | Wait 30 seconds; check `launcher.log` in your data folder |
| Browser never opens | Open the URL shown in `launcher.log` manually (e.g. `http://127.0.0.1:xxxxx`) |
| Windows SmartScreen warning | Click **More info → Run anyway** (unsigned build) or use a signed release when available |
| Antivirus blocked the app | Allow `TowerOptimizer.exe`; PyInstaller builds are sometimes flagged heuristically |
| “Missing module” or crash on load | Re-download a fresh zip; report the issue with `launcher.log` attached |
| Profiles not saved | Confirm `%LOCALAPPDATA%\TowerOptimizer\profiles` exists and is writable |
| Wrong data folder | Check `TOWER_OPTIMIZER_DATA_DIR` / portable mode; the app sidebar also shows the active data path |

To stop the app, close the browser tab and end **`TowerOptimizer.exe`** in Task Manager if it is still running.

---

## Maintainer: prerequisites

- Windows 10/11
- Python 3.11 or 3.12
- Project virtual environment with runtime dependencies installed

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Maintainer: build

From the repository root:

```powershell
.\scripts\build_windows_exe.ps1
```

Output: `dist/TowerOptimizer/` containing `TowerOptimizer.exe`, `run_tower_optimizer.bat`, bundled dependencies (~hundreds of MB), and `README.txt`.

### Smoke-test the launcher without PyInstaller

```powershell
$env:TOWER_OPTIMIZER_DATA_DIR = "$env:LOCALAPPDATA\TowerOptimizer-dev"
python scripts\windows_launcher.py
```

### Smoke-test the packaged build

```powershell
$dest = "$env:TEMP\TowerOptimizer-smoke"
Copy-Item dist\TowerOptimizer $dest -Recurse -Force
Start-Process "$dest\TowerOptimizer.exe" -WorkingDirectory $dest
# Wait ~30s, then open http://127.0.0.1:<port>/_stcore/health — should return "ok"
```

Copy the build outside the repo before testing so editable-install paths do not mask missing bundles.

## Architecture

| Piece | Role |
| --- | --- |
| `scripts/windows_launcher.py` | PyInstaller entry point; data dir, logging, splash, port, browser, Streamlit |
| `scripts/build_windows_exe.ps1` | PyInstaller onedir build; bundles app, assets, and full `tower_optimizer` package |
| `tower_optimizer/runtime_paths.py` | Honors `TOWER_OPTIMIZER_DATA_DIR` for profiles and custom icons |

PyInstaller uses **onedir** mode (not one-file) because Streamlit pulls many runtime files. The build uses `--collect-all streamlit` and bundles the full `tower_optimizer/` source tree into `_internal/`; the launcher adds that folder to `sys.path` at runtime so the app loads without a separate Python install.

## Known limitations

- First cold start can take 10–30 seconds while Streamlit initializes.
- Antivirus heuristics may flag fresh PyInstaller builds; code-signing and CI builds will help.
- No auto-update channel yet; users replace the folder or download a new zip.
- Effective Paths `.xlsx` imports still require the user to browse to their own workbook files.

## Roadmap

- GitHub Actions workflow producing versioned release zips
- Code signing to reduce SmartScreen friction
