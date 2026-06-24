# Tower Optimizer

An unofficial, open-source planning and analysis tool for **The Tower – Idle Tower Defense**.

Tower Optimizer combines account data, upgrade paths, battle reports, resource balances, and transparent heuristics to help players decide what to research, buy, save for, and test next.

> **Preview software:** `v2.0.0-preview.7` is suitable for testing and contribution, but profiles should still be backed up before upgrades. Calculations marked **strategic** or **heuristic** are not claimed to be exact game formulas.

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
- In-game `playerInfo.dat` save import with module names, relic catalog, and UW normalization
- Local backups, diagnostics, update staging, and rollback
- Expandable navigation designed for desktop and smaller displays

## Screenshots

Screenshots will be added after the interface and bundled artwork are finalized. Contributors should use synthetic profiles when capturing images for the repository.

## Getting started (Windows)

**Players:** download **one zip file** — no Python, no terminal.

1. Download **`TowerOptimizer-*-Windows.zip`** from **[GitHub Releases](https://github.com/Tankietank/The-Tower-Optimizer/releases)** (the zip is built by CI — it is not stored in the source repo).
2. Right-click → **Extract All**
3. Open the **`TowerOptimizer`** folder → double-click **`TowerOptimizer.exe`**
4. Wait **1–2 minutes** on first launch (faster afterward) → browser opens = app is running

After the first extract, you only ever double-click the exe again. Full guide: **[Getting started](docs/GETTING_STARTED.md)**.

### Developers (Python from source)

```powershell
git clone https://github.com/Tankietank/The-Tower-Optimizer.git
cd The-Tower-Optimizer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
.\run_optimizer.ps1
```

Run checks with `.\run_public_checks.ps1`. Build a shareable Windows zip with `.\scripts\build_windows_exe.ps1` (see [Portable Windows executable](docs/WINDOWS_EXE.md)).

## Quick start — Docker / Unraid

Optional container deployment for home servers (Unraid, NAS, Linux host):

```bash
docker compose up -d
```

Image: `ghcr.io/tankietank/the-tower-optimizer:latest` (rebuilt on each push to `main`).

Open `http://<host>:8501` and mount a persistent folder to `/app/data` so profiles survive upgrades.

See [Docker and Unraid](docs/DOCKER.md) for Unraid UI steps, update options, and troubleshooting.

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
- In-game tower backup (`playerInfo.dat`)
- IDS companion workbook bundle
- Optional Effective Paths workbook reference
- Tower Optimizer profile JSON
- Battle-report text, JSON, or CSV

Effective Paths is **not required** for normal standalone calculations. It remains useful for profile import, calibration, and detecting game-data changes.

## Native math vs Effective Paths validation

Tower Optimizer runs **native Python engines** for economy, damage, eHP, and regen upgrade paths. **Recommendation Dashboard** rankings come from these engines plus heuristics (bottleneck weighting, affordability, death signals). Importing an Effective Paths ROI reference **does not overwrite** the dashboard shortlist — EP is an optional **comparison layer**.

| Layer | Source | Used for |
| --- | --- | --- |
| **Native engines** | Profile + bundled cost curves, computed in Python | Recommendation Dashboard, Native e* pages, Progression Planner |
| **EP ROI reference** | Cached calculated rows from a recalculated `.xlsx` | ROI Paths (read-only), Calibration Center, small Priority Index tie-break |
| **Heuristics** | Relative scores and checklists | Build Analyzer, whole-account systems without verified ROI |

Each major screen includes a **How are these numbers calculated?** expander describing which layer applies.

### Validation workflow

Use this when checking whether native formulas align with Effective Paths for a given account:

1. **Build or import a profile** — e.g. `playerInfo.dat` or Tower Optimizer JSON (`sample_data/example_profile.json` for synthetic testing).
2. **Fill Master Sheet only** — do not rely on stale EP recommendation tabs. From the repo root:

```powershell
python tools/fill_effective_paths_from_save.py path\to\playerInfo.dat
```

   Add `--quick` to skip the inline calibration printout. Output lands under `validation_fixtures/` (and a copy in Downloads when writable).

3. **Recalculate in Excel** — open the filled workbook, force full recalc (`Ctrl+Alt+F9`), then **Save**. Skipping this step leaves cached `#NAME?` or outdated ROI rows.
4. **Import in Tower Optimizer** — profile via save or JSON, then **Import / Export → ROI Reference** with the saved workbook.
5. **Review Calibration Center** — compare native rank-by-rank against imported EP paths. Export a snapshot from the Calibration tab if you want a regression record.

Automated checks also run via `pytest`, `tools/v2_preview_validation.py`, and `run_public_checks.ps1`.

### Agreement scores (Calibration Center)

- **Exact** — same upgrade at that rank in native and EP reference.
- **Close** — same upgrade within ±1 rank (name aliases handled).
- **Different** — material mismatch; review assumptions, EP recalc, or known native gaps before changing formulas.
- **No reference** — EP had no rows for that path (often maxed paths, missing unlocks, or unmodeled categories).

Overall agreement is a weighted summary across populated paths. A **WARN** result means at least one path differs materially — it flags review, not automatic failure of standalone recommendations.

### Example baseline (synthetic regression profile)

Against a filled and recalculated Effective Paths v5.06.04.00 workbook paired with the bundled example profile workflow, preview.6 typically reaches **roughly mid‑70% overall agreement** with most economy and core lab paths **Exact**, occasional **Different** rows on coin paths where native and EP prioritize adjacent workshop stats, and **No reference** on sparse categories (health stones when Death Wave is saturated, regen when recovery labs are zero, assist modules when slots are locked). Treat any single account as a datapoint — stale EP imports, `#NAME?` formula errors, or missing recalc commonly produce misleading low scores.

### Known gaps to expect

- **Health stones** — native path currently emphasizes Death Wave; empty EP/native stone tables can be normal when DW is maxed or not owned.
- **Regen / recovery** — sparse when recovery-package labs are at 0 or assist modules are locked.
- **Assist modules** — limited native ROI coverage; EP may also show no rows until unlocks are reflected on Master Sheet.
- **Stale EP / `#NAME?` rows** — import after Master Sheet fill **and** Excel recalc; old ROI tabs or broken formulas skew calibration without affecting native dashboard picks much.
- **Build Analyzer** — milestone heuristics, not native ROI or EP paths.

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

## Related community tools

**[TowerSmith](https://github.com/AngryBrit/tower-smith)** (AngryBrit) is a complementary fan tool focused on save decoding, workshop simulation, and in-browser lab/workshop UI. Its author granted permission for Tower Optimizer to use TowerSmith reference code and data for save import and local artwork paths — see [NOTICE.md](NOTICE.md).

Tower Optimizer remains a separate project: native recommendation engines, Streamlit planning UI, IDS imports, battle learning, and progression planner.

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

**Players (Windows):** download **`TowerOptimizer-*-Windows.zip`**, extract once, double-click **`TowerOptimizer.exe`**. See **[Getting started](docs/GETTING_STARTED.md)**.

**Developers:** build the release zip with:

```powershell
.\scripts\build_windows_exe.ps1
```

Output: **`dist\TowerOptimizer-2.0.0-preview.7-Windows.zip`** — ship that single file. Optional single-exe build: `.\scripts\build_windows_exe.ps1 -SingleExe`. See [Portable Windows executable](docs/WINDOWS_EXE.md).

**Publishing to GitHub:** push a version tag (e.g. `v2.0.0-preview.7`). The [Build Windows executable](.github/workflows/windows-release.yml) workflow builds the zip and attaches it to a **pre-release** on the Releases page. You can also run that workflow manually from the Actions tab.

## License

Source code is released under the [MIT License](LICENSE). That license does not grant rights to third-party game names, artwork, spreadsheets, or other separately owned material.
