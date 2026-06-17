# Tower Optimizer

An unofficial, open-source planning and analysis tool for **The Tower – Idle Tower Defense**.

Tower Optimizer combines account data, upgrade paths, battle reports, resource balances, and transparent heuristics to help players decide what to research, buy, save for, and test next.

> **Preview software:** `v2.0.0-preview.6` is suitable for testing and contribution, but profiles should still be backed up before upgrades. Calculations marked **strategic** or **heuristic** are not claimed to be exact game formulas.

## Current features

- Native economy, damage, health, and regeneration recommendation engines
- Whole-account opportunity-cost recommendations
- Progression planner and upgrade queue
- Battle-history learning and farming-tier comparisons
- One-click single or multi-report paste import with duplicate detection
- GT/BH/DW synchronization visualization
- Card-slot and preset tracking
- Conservative module inventory and merge-readiness review
- Relic gallery and custom icon overrides
- IDS companion-workbook and optional Effective Paths imports
- Local backups, diagnostics, update staging, and rollback
- Expandable navigation designed for desktop and smaller displays

## Screenshots

Screenshots will be added after the interface and bundled artwork are finalized. Contributors should use synthetic profiles when capturing images for the repository.

## Quick start — Windows

1. Install Python 3.11 or 3.12.
2. Clone the repository:

```powershell
git clone https://github.com/Tankietank/The-Tower-Optimizer.git
cd The-Tower-Optimizer
```

3. Create an isolated environment and install the project:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

4. Run the checks:

```powershell
.\run_public_checks.ps1
```

5. Start the application:

```powershell
.\run_optimizer.ps1
```

Streamlit opens the app in the default browser. Profile data remains on the local computer under `data/`, which is excluded from Git by default.

## Quick start — other platforms

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m streamlit run app.py
```

## Import options

Users can build a profile through:

- Manual entry
- IDS companion workbook bundle
- Optional Effective Paths workbook reference
- Tower Optimizer profile JSON
- Battle-report text, JSON, or CSV

Effective Paths is **not required** for normal standalone calculations. It remains useful for profile import, calibration, and detecting game-data changes.

## Accuracy labels

The interface distinguishes between:

- **Verified calculation** — based on a bundled and tested formula or cost curve
- **Reference-aligned** — compared with a trusted imported reference
- **Estimated calculation** — incomplete formula with stated assumptions
- **Strategic heuristic** — relative priority, not an exact ROI value

See [Verification levels](docs/VERIFICATION_LEVELS.md).

## Privacy

Tower Optimizer is local-first. The current preview does not require an account, transmit player profiles, or collect telemetry. Imported workbooks, battle history, custom icons, backups, and profiles remain under `data/` unless the user explicitly exports them.

Never include real profiles, player IDs, imported spreadsheets, diagnostics, or custom game artwork in issues or pull requests without reviewing them first. See [Privacy](docs/PRIVACY.md).

## Artwork and affiliation

This is an unofficial fan project and is not affiliated with or endorsed by Tech Tree Games. The Tower and its game assets belong to their respective rights holders.

The repository ships only original fallback artwork. Users may install local icon overrides containing images they are permitted to use. Do not submit extracted game artwork unless redistribution permission is clear. See [Assets](docs/ASSETS.md).

## Development

The application is organized as a Python package with independent engines, planning, battle-learning, update, and visual layers. Start with:

- [Architecture](docs/ARCHITECTURE.md)
- [Contributing](CONTRIBUTING.md)
- [Data sources](docs/DATA_SOURCES.md)
- [Release process](docs/RELEASES.md)
- [Roadmap](docs/ROADMAP.md)

Run the complete local validation suite with:

```powershell
.\run_public_checks.ps1
```

Or individually:

```powershell
python -m compileall -q app.py tower_optimizer tools tests scripts
python tools/smoke_test.py
python tools/v2_preview_validation.py
python tools/public_release_audit.py
pytest -q
```

## Releases

The initial public release should be published as a GitHub **pre-release**. Source users can clone the repository; a portable Windows executable will be added through a reproducible build workflow after launcher and writable-data-path testing are complete.

## License

Source code is released under the [MIT License](LICENSE). That license does not grant rights to third-party game names, artwork, spreadsheets, or other separately owned material.
