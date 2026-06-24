# Getting started with Tower Optimizer

Pick the path that matches how you received the app.

---

## Windows — one download, no Python (recommended)

You get **one zip file**. No Python. No terminal. No install wizard.

### What you download

**`TowerOptimizer-2.0.0-preview.7-Windows.zip`** (name may vary by version)

### Step 1 — Extract (one time only)

1. Right-click the zip → **Extract All…**
2. Click **Extract**
3. Open the **`TowerOptimizer`** folder that appears

> Windows may show many files including an `_internal` folder — **that is normal**. You never open those; just use **`TowerOptimizer.exe`**.

### Step 2 — Run (every time)

1. Double-click **`TowerOptimizer.exe`**
2. Wait for **“Starting Tower Optimizer…”** — **first launch often takes 1–2 minutes** (later launches are faster)
3. Your browser opens — **that tab is the app**

**Done.** Pin the exe to your taskbar or desktop if you like. You do not repeat Step 1 unless you download a new version.

### Optional: truly one file (no folder)

If you received **`TowerOptimizer.exe`** alone (single-file build):

1. Put it anywhere (Desktop is fine)
2. Double-click it
3. First launch may take **1–2 minutes** while it unpacks internally

Profiles still save under `%LOCALAPPDATA%\TowerOptimizer` — not next to the exe.

### If Windows shows a security warning

Unsigned apps often trigger **SmartScreen** (“Windows protected your PC”):

1. Click **More info**
2. Click **Run anyway**

This is normal for community-built tools until a signed release is available. Only download from a source you trust.

### Where your profiles are saved

| Situation | Where data goes |
| --- | --- |
| Normal use | `C:\Users\<You>\AppData\Local\TowerOptimizer` |
| USB / one folder you can copy | Create an empty file named **`portable.txt`** next to `TowerOptimizer.exe` → data goes in **`data\`** inside that folder |

To open the default folder quickly: press **Win + R**, paste `%LOCALAPPDATA%\TowerOptimizer`, press Enter.

### First-time setup in the app

1. **Import / Export** → upload your in-game backup **`playerInfo.dat`**, **or** enter stats manually.
2. Open **Recommendation Dashboard** for upgrade suggestions.
3. Optional: import Effective Paths only if you use calibration (not required for normal play).

### Something went wrong?

| Problem | Fix |
| --- | --- |
| Nothing happens after double-click | Wait **2 minutes** on first launch. Check **`launcher.log`** in `%LOCALAPPDATA%\TowerOptimizer` (or `data\launcher.log` in portable mode). |
| Browser never opened | Open **`launcher.log`**, find a line like `http://127.0.0.1:xxxxx`, paste that address into your browser. |
| “Missing module” or instant crash | Re-download a fresh zip; do not run a lone `.exe` without its folder. |
| Antivirus removed the app | Restore from quarantine and allow **`TowerOptimizer.exe`**. PyInstaller builds are sometimes flagged by mistake. |
| App still running after closing the tab | Open Task Manager → end **TowerOptimizer.exe**. |

When asking for help, attach **`launcher.log`** from your data folder.

### Updating to a new version

1. Close the app (browser tab + **TowerOptimizer.exe** in Task Manager if needed).
2. Replace the **whole** `TowerOptimizer` folder with the new zip (or unzip the new version to a new folder).
3. Your profiles stay in `%LOCALAPPDATA%\TowerOptimizer` (or `data\` in portable mode) — you do not lose them by replacing the program folder.

---

## Windows — run from source (developers & contributors)

Only use this if you are **developing** or **building** the app yourself.

1. Install **Python 3.11 or 3.12** from [python.org](https://www.python.org/downloads/) — check **“Add python.exe to PATH”** during install.
2. Open **PowerShell** in the project folder.
3. Run once:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

4. Start the app anytime with:

```powershell
.\run_optimizer.ps1
```

Profiles are stored in the project’s **`data\`** folder.

### Build the Windows zip for other players

```powershell
.\scripts\build_windows_exe.ps1
```

Zip the entire **`dist\TowerOptimizer\`** folder and share it. See [Portable Windows executable](WINDOWS_EXE.md) for maintainer details.

---

## Docker / Unraid / Linux

See [Docker and Unraid](DOCKER.md) or the **Quick start — other platforms** section in the main [README](../README.md).

---

## Privacy reminder

Everything stays on your computer. Tower Optimizer does not upload your save or profile unless **you** export and share it.
