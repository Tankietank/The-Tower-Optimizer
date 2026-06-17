# Assets and icon overrides

The repository ships original SVG fallback graphics. Runtime icon overrides live under `data/custom_icons/` and are ignored by Git.

Recommended override format:

- Transparent PNG or WEBP
- Square, preferably 256×256 or 512×512
- Centered artwork with transparent margin
- Maximum 8 MB per file

Do not submit extracted game artwork unless you have redistribution permission. The code may support loading a user's local assets without bundling those assets in the repository.

### Optional local artwork folder

Tower Optimizer ships original module SVGs under `assets/modules/` and generic system graphics for relics and cards. You can also point at a **local** artwork folder on your machine (not committed to Git):

```powershell
# Generic layout (your own permitted files)
$env:TOWER_GAME_ASSETS_DIR = "C:\path\to\your\icons"

# Or a local TowerSmith clone public/ folder (author granted use — see NOTICE.md)
$env:TOWER_SMITH_PUBLIC_DIR = "C:\path\to\tower-smith\public"

python app.py
```

Expected layout (all optional):

- `modules/<slot>/<item-name>.{png,webp,svg}` — slot folders such as `cannon`, `armor`, `generator`, `core`
- `relics/<rarity>/<item-slug>.{png,webp,svg}` — rarity folders such as `rare`, `epic`, `legendary`
- `relics/<item-slug>.{png,webp,svg}` — flat fallback

Resolution order for collection icons:

1. `data/custom_icons/<category>/<slug>.png` (Icon Studio uploads)
2. `TOWER_GAME_ASSETS_DIR` or `TOWER_SMITH_PUBLIC_DIR` when set by you
3. Bundled `assets/modules/<slug>.svg` or system fallbacks

Do not commit third-party or game artwork into this repository unless redistribution is explicitly allowed.
