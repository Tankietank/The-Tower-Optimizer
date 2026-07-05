# Game data and sources

Tower Optimizer separates bundled metadata, formulas, optional reference imports, and user profile data.

## Bundled data

Versioned JSON files under `tower_optimizer/game_data/` supply names, limits, and strategic metadata required by standalone operation.

## Community wiki guidance

`tower_optimizer/game_data/community_guidance.json` bundles curated strategic notes distilled from the [Fandom Guides wiki](https://the-tower-idle-tower-defense.fandom.com/wiki/Guides) (Footguns, build guides). Each entry includes a `source_url` for attribution.

- **License:** Fandom wikis are typically [CC BY-SA](https://creativecommons.org/licenses/by-sa/3.0/). Summaries in this repo are paraphrased; the UI links to the wiki page when showing guidance.
- **Confidence:** Labeled **Community guide (Fandom)** — strategic/heuristic only; does not change native ROI ranking.
- **Maintenance:** Update `bundle_version` when refreshing entries after game patches.

## Optional references

Effective Paths and IDS companion workbooks may be imported for calibration, profile entry, and change detection. Original workbooks are not redistributed by this repository.

## Source confidence

Each change should record its source and confidence. Conflicting sources require review rather than silent replacement.

## Formula changes

A cost, effect, or formula change requires regression tests and may require an application release. A simple name or maximum-level change may be eligible for a verified game-data pack.
