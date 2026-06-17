# Third-party notice

Tower Optimizer is an unofficial fan project. It is not affiliated with or endorsed by Tech Tree Games.

The MIT License applies to the original source code and original fallback artwork contained in this repository. It does not grant rights to The Tower – Idle Tower Defense, its names, trademarks, interface artwork, icons, or other assets, nor to third-party spreadsheets or community content.

Contributors must not submit copyrighted game artwork, private APIs, credentials, player save data, or spreadsheet content unless they have the right to redistribute it.

## TowerSmith (AngryBrit)

The **[TowerSmith](https://github.com/AngryBrit/tower-smith)** author granted permission for Tower Optimizer to use TowerSmith reference code and data for save import, catalog maintenance, and optional local artwork paths.

What that means in practice:

- **Save-import catalogs** under `tower_optimizer/game_data/` (`relics.json`, `uw_save_tracks.json`, module/relic index tables) are derived from that authorized reference and rebundled for this app. The maintainer script `tools/build_save_catalogs.py` may fetch public TowerSmith sources when rebuilding those files.
- **TowerSmith is still a separate project** with its own UI, simulation, and release cadence. Use and star it directly if you rely on it.
- **Artwork** from a local TowerSmith clone may be loaded at runtime via `TOWER_GAME_ASSETS_DIR` or `TOWER_SMITH_PUBLIC_DIR` on your machine only. Do not commit those image files into this repository unless redistribution is explicitly allowed.

Tower Optimizer’s Streamlit UI, recommendation engines, planner, battle learning, and bundled SVG fallbacks remain original to this repository unless a file states otherwise.
