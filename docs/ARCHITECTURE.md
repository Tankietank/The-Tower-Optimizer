# Architecture

## Entry points

- `app.py` is the Streamlit launcher.
- `tower_optimizer/application.py` coordinates the current interface and legacy pages.
- `tower_optimizer/navigation.py` defines grouped navigation.
- `tower_optimizer/visual_ui.py` and `visual_models.py` power the v2 visual pages.

## Engines

- `engines/economy.py`
- `engines/damage.py`
- `engines/health.py`
- `engines/regen.py`
- `engines/combined.py`
- `engines/whole_account.py`

Engine functions accept profile dictionaries and return transparent recommendation rows. UI code should not contain calculation formulas.

## Supporting systems

- `planner.py` creates staged plans and persistent queues.
- `battle_learning.py` evaluates battle history conservatively.
- `calibration.py` compares native results with optional references.
- `quality.py` finds inconsistent or incomplete profile data.
- `reliability.py` handles atomic saves and backups.
- `game_data_updater.py` stages reversible metadata updates.
- `icon_manager.py` resolves bundled and local override artwork.

## Data boundaries

Bundled versioned metadata belongs in `tower_optimizer/game_data/`. User profiles and imports belong under `data/` and must not be committed. Synthetic fixtures belong in `sample_data/`.

## Refactoring direction

`application.py` remains large because legacy pages were preserved during the engine split. New features should be placed in focused modules and invoked from the application layer. Large unrelated additions to `application.py` should be avoided.
