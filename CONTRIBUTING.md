\
# Contributing

Contributions are welcome. The project is intended to remain understandable, testable, privacy-conscious, and honest about calculation confidence.

## Before opening a pull request

1. Create a branch from the current default branch.
2. Use a virtual environment.
3. Install development dependencies:

```powershell
pip install -e ".[dev]"
```

4. Run:

```powershell
.\run_public_checks.ps1
```

5. Remove all personal profiles, exports, screenshots, workbooks, diagnostics, and custom artwork.

## Contribution rules

- Keep game formulas isolated in engine or game-data modules.
- Add a test for each formula, importer, profile migration, or bug fix.
- Mark incomplete models as estimated or strategic; do not present them as exact.
- Document assumptions and source versions.
- Avoid scraping or reverse-engineering private account endpoints.
- Do not add write-capable game integrations.
- Do not submit exact game artwork without redistribution permission.
- Preserve existing profiles through explicit, reversible migrations.
- Never log credentials, player IDs, or full profile content by default.

## Game-data changes

A game-data pull request should include:

- Source and version
- Items changed
- Why the source is trusted
- Tests or regression output
- Whether an app-version bump is required
- Any profile migration needed

Trust order:

1. Official patch notes or developer-provided data
2. Confirmed in-game observations or exports
3. Trusted calculation/reference workbooks
4. Community wiki
5. Community reports awaiting verification

## Pull-request scope

Smaller pull requests are easier to review. Separate visual changes, data updates, formula changes, and profile migrations where possible.

## Reporting security issues

Do not open a public issue for credential exposure, unsafe archive extraction, or update-signature bypasses. Follow [SECURITY.md](SECURITY.md).
