"""Rebuild bundled TowerSmith artwork path metadata for runtime icon resolution.

Fetches public mapping tables from the authorized TowerSmith reference repo.
See NOTICE.md — this writes path metadata only, not image binaries.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME_DATA = ROOT / "tower_optimizer" / "game_data"
OUT_PATH = GAME_DATA / "towersmith_icon_paths.json"

ATTRIBUTION = (
    "Tower Optimizer bundled catalog derived from authorized TowerSmith reference data "
    "(see NOTICE.md)."
)

_REF_MODULE_IMAGES = (
    "https://raw.githubusercontent.com/AngryBrit/tower-smith/main/src/data/workshopModuleImages.ts"
)
_REF_RELIC_IMAGES = (
    "https://raw.githubusercontent.com/AngryBrit/tower-smith/main/src/data/workshopRelicImages.generated.json"
)

ULTIMATE_WEAPON_PATHS = {
    "goldenTower": "ultimate_weapons/weapon_goldenTower.webp",
    "blackHole": "ultimate_weapons/weapon_blackHole.webp",
    "spotlight": "ultimate_weapons/weapon_spotlight.webp",
    "deathWave": "ultimate_weapons/weapon_deathWave.webp",
    "chainLightning": "ultimate_weapons/weapon_chainLightning.webp",
    "smartMissiles": "ultimate_weapons/weapon_smartMissilies.webp",
    "innerLandMines": "ultimate_weapons/weapon_landMines.webp",
    "poisonSwamp": "ultimate_weapons/weapon_swamp.webp",
    "chronoField": "ultimate_weapons/weapon_chronoField.webp",
}


def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


def _parse_module_paths(source: str) -> dict[str, dict[str, str]]:
    block = re.search(r"WORKSHOP_CHASSIS_MODULE_IMAGE[^=]+=\s*\{(.+?)\n\}", source, re.S)
    modules: dict[str, dict[str, str]] = {}
    if not block:
        return modules
    for slot, body in re.findall(r"(cannon|armor|generator|core):\s*\{([^}]+)\}", block.group(1), re.S):
        modules[slot] = {}
        for workshop_id, relative in re.findall(r"(\w+):\s*'([^']+)'", body):
            modules[slot][workshop_id] = relative
    return modules


def build_payload() -> dict:
    modules = _parse_module_paths(_fetch(_REF_MODULE_IMAGES))
    relics = json.loads(_fetch(_REF_RELIC_IMAGES))
    return {
        "version": "1.0.0",
        "source": ATTRIBUTION,
        "modules": modules,
        "relics": relics,
        "ultimate_weapons": dict(ULTIMATE_WEAPON_PATHS),
    }


def main() -> int:
    payload = build_payload()
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    module_count = sum(len(slot_map) for slot_map in payload["modules"].values())
    print(
        f"Wrote {OUT_PATH} "
        f"(modules={module_count}, relics={len(payload['relics'])}, "
        f"ultimate_weapons={len(payload['ultimate_weapons'])})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
