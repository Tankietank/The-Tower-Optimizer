"""Load bundled game catalogs used by save import and icon resolution."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

_GAME_DATA_DIR = Path(__file__).resolve().parent / "game_data"

UW_ATTRIBUTE_TRACK_KEYS: Dict[str, List[str]] = {
    "Chain Lightning": ["chainLightningDamageLevel", "chainLightningQuantityLevel", "chainLightningChanceLevel"],
    "Smart Missiles": ["smartMissilesDamageLevel", "smartMissilesQuantityLevel", "smartMissilesCooldownLevel"],
    "Death Wave": ["deathWaveDamageLevel", "deathWaveQuantityLevel", "deathWaveCooldownLevel"],
    "Chrono Field": ["chronoFieldDurationLevel", "chronoFieldSpeedReductionLevel", "chronoFieldCooldownLevel"],
    "Inner Land Mines": ["innerLandMinesDamageLevel", "innerLandMinesQuantityLevel", "innerLandMinesCooldownLevel"],
    "Golden Tower": ["goldenTowerMultiplierLevel", "goldenTowerDurationLevel", "goldenTowerCooldownLevel"],
    "Poison Swamp": ["poisonSwampDamageLevel", "poisonSwampDurationLevel", "poisonSwampCooldownLevel"],
    "Black Hole": ["blackHoleSizeLevel", "blackHoleDurationLevel", "blackHoleCooldownLevel"],
    "Spotlight": ["spotlightMultiplierLevel", "spotlightAngleLevel", "spotlightQuantityLevel"],
}

MODULE_SLOT_FOLDERS = {
    "Cannon": "cannon",
    "Armor": "armor",
    "Generator": "generator",
    "Core": "core",
}

RELIC_RARITY_FOLDERS = {
    "1-Rare": "rare",
    "2-Epic": "epic",
    "3-Legendary": "legendary",
}


@lru_cache(maxsize=1)
def load_save_mappings() -> Dict[str, Any]:
    return json.loads((_GAME_DATA_DIR / "save_mappings.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_relics_catalog() -> Dict[str, Any]:
    return json.loads((_GAME_DATA_DIR / "relics.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_uw_save_tracks() -> Dict[str, Any]:
    return json.loads((_GAME_DATA_DIR / "uw_save_tracks.json").read_text(encoding="utf-8"))


def module_info_entry(info_index: int, mappings: Optional[Mapping[str, Any]] = None) -> Optional[Dict[str, Any]]:
    rows = list((mappings or load_save_mappings()).get("module_info_index") or [])
    if info_index < 0 or info_index >= len(rows):
        return None
    row = rows[info_index]
    return dict(row) if isinstance(row, dict) else None


def module_rarity_label(rarity_index: int, mappings: Optional[Mapping[str, Any]] = None) -> str:
    names = list((mappings or load_save_mappings()).get("module_rarity") or [])
    if 0 <= rarity_index < len(names) and names[rarity_index]:
        return str(names[rarity_index])
    return f"Rarity {rarity_index}"


def relic_entry(game_index: int, catalog: Optional[Mapping[str, Any]] = None) -> Optional[Dict[str, Any]]:
    rows = list((catalog or load_relics_catalog()).get("by_index") or [])
    if game_index < 0 or game_index >= len(rows):
        return None
    row = rows[game_index]
    return dict(row) if isinstance(row, dict) else None


def uw_track_value(
    weapon_name: str,
    attribute_name: str,
    upgrade_level: Any,
    tracks: Optional[Mapping[str, Any]] = None,
) -> Optional[float]:
    payload = tracks or load_uw_save_tracks()
    weapon = (payload.get("weapons") or {}).get(weapon_name) or {}
    track_keys = list(weapon.get("tracks") or UW_ATTRIBUTE_TRACK_KEYS.get(weapon_name, []))
    attributes = list(UW_ATTRIBUTE_META_ATTRS(weapon_name))
    if attribute_name not in attributes:
        return None
    track_key = track_keys[attributes.index(attribute_name)]
    track = (weapon.get("attributes") or {}).get(track_key)
    if not track:
        return None
    try:
        level = int(round(float(upgrade_level)))
    except (TypeError, ValueError):
        return None
    milestones = list(track.get("milestones") or [])
    if not milestones:
        return None
    level = max(0, min(level, len(milestones) - 1))
    value = float(milestones[level])
    kind = str(track.get("value_kind") or "")
    if kind == "percent":
        return value / 100.0
    if kind == "mult":
        return float(value)
    return float(value)


def UW_ATTRIBUTE_META_ATTRS(weapon_name: str) -> List[str]:
    from .engines.core import UW_ATTRIBUTE_META

    return list(UW_ATTRIBUTE_META.get(weapon_name, {}).keys())


def merge_relic_item(existing: Mapping[str, Any], incoming: Mapping[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key in {"rarity", "bonus_type", "value", "type", "event"} and not value:
            continue
        if key == "name" and str(value).startswith("Relic "):
            continue
        merged[key] = value
    return merged
