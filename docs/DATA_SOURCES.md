# Game data and sources

Tower Optimizer separates bundled metadata, formulas, optional reference imports, and user profile data.

## Bundled data

Versioned JSON files under `tower_optimizer/game_data/` supply names, limits, and strategic metadata required by standalone operation.

## Optional references

Effective Paths and IDS companion workbooks may be imported for calibration, profile entry, and change detection. Original workbooks are not redistributed by this repository.

## Source confidence

Each change should record its source and confidence. Conflicting sources require review rather than silent replacement.

## Formula changes

A cost, effect, or formula change requires regression tests and may require an application release. A simple name or maximum-level change may be eligible for a verified game-data pack.
