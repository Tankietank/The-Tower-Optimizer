# Validation fixtures

Contributor-only fixtures for Effective Paths calibration and regression checks.

## Included in Git

- `dabes_validation/dabes_profile.json` — synthetic/redacted profile JSON for automated tests.

## Local only (gitignored)

Companion `.xlsx` workbooks are excluded by the root `.gitignore` (`*.xlsx`). Place them locally under:

- `source_workbooks/The Tower/` — IDS companion workbooks from the community sheet pack.
- `dabes_validation/` — filled Effective Paths workbook after running `tools/fill_effective_paths_from_save.py`.

See [Native math vs Effective Paths validation](../README.md#native-math-vs-effective-paths-validation) in the README for the full workflow.
