# Changelog

All notable changes to Tower Optimizer will be documented here.

The project follows semantic versioning where practical. Preview releases may still include profile-schema or interface changes.

## [2.0.0-preview.11] - 2026-06-25

### Fixed

- Windows launcher log tee accepts bytes from Streamlit stdout (fixes `write() argument must be str, not bytes` on startup)
- Dev-mode splash subprocess passes the launcher script path correctly on Windows

### Added

- `tools/test_windows_launcher.py` — local smoke test for dev and packaged Windows builds

## [2.0.0-preview.10] - 2026-06-24

### Fixed

- Windows launcher runs Streamlit on the main thread again (fixes `signal only works in main thread`) while the splash timer runs in a separate subprocess

## [2.0.0-preview.9] - 2026-06-24

### Fixed

- Windows splash no longer freezes as "Not Responding": Streamlit runs on a background thread while tkinter updates the elapsed timer on the main thread, and the splash closes when the app is ready

## [2.0.0-preview.8] - 2026-06-24

### Changed

- Windows launcher waits up to 10 minutes, polls Streamlit health before opening the browser, and shows a live elapsed timer during slow first launches

## [2.0.0-preview.7] - 2026-06-24

### Changed

- Windows portable launcher and docs now set honest first-launch expectations (often 1–2 minutes) and extend the browser startup timeout

## [2.0.0-preview.6] - 2026-06-15

### Added

- One-click **Import report(s)** workflow that parses and saves reports directly to the active profile
- Multiple Battle Reports can be pasted together and imported in one batch
- Batch preview showing new reports, duplicates, parse errors, and invalid rows before saving
- Shared parser-level batch splitting for the Streamlit UI, tests, and future desktop builds

### Changed

- Duplicate reports are skipped automatically during direct and reviewed imports
- The Battle Reports page now explains clearly when data is only previewed versus saved

## [2.0.0-preview.5] - 2026-06-14

### Fixed

- Battle Reports copied with single spaces, non-breaking spaces, punctuation variants, or flattened clipboard formatting now parse Tier and Wave reliably
- Current report headings such as Damage Taken, Health Regenerated, Total Enemies, Coins, Currencies, and Enemies Destroyed By are recognized
- Section-specific values no longer overwrite unrelated values with the same label
- Direct Cells Per Hour values are retained instead of always being recalculated

### Added

- Standalone battle-report parser with regression coverage using a real June 2026 report format

## [2.0.0-preview.4] - 2026-06-14

### Added

- GitHub-ready repository documentation and privacy safeguards
- MIT license and third-party notice
- Reproducible Python package metadata through `pyproject.toml`
- Synthetic example profile
- Public-release audit tool
- Pytest validation suite
- GitHub Actions continuous-integration workflow
- Issue, pull-request, security, and contribution templates
- Source-release builder with SHA-256 output

### Changed

- Public documentation now uses Markdown
- Installer and validation scripts identify Preview 4

## [2.0.0-preview.3]

### Added

- Expandable grouped navigation
- Automatic opening of the active navigation section
- Validation that every application page appears exactly once

## Earlier previews

See the Git history and packaged release notes for the v1.x engine, planner, battle-learning, update, and visual-preview milestones.
