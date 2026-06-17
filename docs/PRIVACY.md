# Privacy

Tower Optimizer is currently local-first and does not require a game login, player ID, cloud account, or telemetry service.

## Local data

Profiles, battle reports, planner state, imports, backups, diagnostics, and custom icons may contain private information. They are stored under `data/` and ignored by Git.

## Before sharing

Review exported profiles and diagnostic ZIPs. Remove player IDs, names, local paths, imported source files, and any other details you do not want public.

## Contributions

Use `sample_data/example_profile.json` for tests and screenshots. Never submit a real profile or save file.

## Future online services

Any future update checker, cloud profile, API connector, or telemetry feature must be opt-in, documented, and reviewed separately. Game credentials must never be requested without an official, authorized interface.
