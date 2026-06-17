"""Maintain bundled save-import catalogs for Tower Optimizer.

This maintainer script rebuilds JSON under tower_optimizer/game_data/ from
public community references on playerInfo.dat layout. It is not used at runtime.

See NOTICE.md for attribution and independence from other community tools.

TowerSmith reference sources are used with the author's permission when rebuilding catalogs.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
GAME_DATA = ROOT / "tower_optimizer" / "game_data"

CATALOG_ATTRIBUTION = (
    "Tower Optimizer bundled catalog derived from authorized TowerSmith reference data "
    "(see NOTICE.md)."
)

# Public community references used only by maintainers to validate index tables.
_REF_RELIC_INDEX = "https://raw.githubusercontent.com/AngryBrit/tower-smith/main/src/playerSave/gameRelicMapping.ts"
_REF_RELIC_NAMES = "https://raw.githubusercontent.com/AngryBrit/tower-smith/main/src/data/workshopRelics.generated.json"
_REF_UW_TRACKS = "https://raw.githubusercontent.com/AngryBrit/tower-smith/main/src/data/workshopUltimateData.ts"
_REF_TOWER_THEME_SLOTS = "https://raw.githubusercontent.com/AngryBrit/tower-smith/main/src/playerSave/towerSaveSlotMap.ts"
_REF_BACKGROUND_THEME_SLOTS = "https://raw.githubusercontent.com/AngryBrit/tower-smith/main/src/playerSave/backgroundSaveSlotMap.ts"
_REF_MUSIC_THEME_SLOTS = "https://raw.githubusercontent.com/AngryBrit/tower-smith/main/src/playerSave/musicSaveSlotMap.ts"
_REF_MODULE_EFFECTS = "https://raw.githubusercontent.com/AngryBrit/tower-smith/main/src/playerSave/gameModuleEffectIndex.ts"
_REF_GAME_THEME_INDEX = "https://raw.githubusercontent.com/AngryBrit/tower-smith/main/src/playerSave/gameThemeIndex.ts"

# Game ModuleRarity enum ordinals -> app rarity labels.
GAME_MODULE_RARITY = [
    None,
    "Rare",
    "Rare",
    "Rare+",
    "Epic",
    "Epic+",
    "Legendary",
    "Legendary+",
    "Mythic",
    "Mythic+",
    "Ancestral",
    "Ancestral 1*",
    "Ancestral 2*",
    "Ancestral 3*",
    "Ancestral 4*",
    "Ancestral 5*",
]

MODULE_INFO_INDEX_TO_WORKSHOP_ID: List[Optional[str]] = [
    None, None, None, None, None, None, None,
    "havocBringer", "deathPenalty", "beingAnnihilator", "astralDeliverance", "shrinkRay",
    None, None, None, None, None, None,
    "negativeMassProjector", "spaceDisplacer", "antiCubePortal", "wormholeRedirector", "sharpFortitude", "orbitalAugment",
    None, None, None,
    "blackHoleDigestor", "pulsarHarvester", "galaxyCompressor", "singularityHarness",
    "pulsarHarvester", "galaxyCompressor", "singularityHarness",
    "projectFunding", "restorativeBonus",
    None,
    "multiverseNexus", "dimensionCore", "harmonyConductor", "omChip",
    "shrinkRay", "sharpFortitude", "projectFunding", "magneticHook", "amplifyingStrike",
    "orbitalAugment", "restorativeBonus", "primordialCollapse",
]

SLOT_ORDERS = {
    "Cannon": [
        "astralDeliverance", "beingAnnihilator", "deathPenalty", "havocBringer", "shrinkRay", "amplifyingStrike",
    ],
    "Armor": [
        "antiCubePortal", "negativeMassProjector", "wormholeRedirector", "spaceDisplacer", "sharpFortitude", "orbitalAugment",
    ],
    "Generator": [
        "singularityHarness", "galaxyCompressor", "pulsarHarvester", "blackHoleDigestor", "projectFunding", "restorativeBonus",
    ],
    "Core": [
        "omChip", "harmonyConductor", "dimensionCore", "multiverseNexus", "magneticHook", "primordialCollapse",
    ],
}

WORKSHOP_ID_TO_NAME: Dict[str, str] = {}
for slot, ids in SLOT_ORDERS.items():
    modules_payload = json.loads((GAME_DATA / "modules.json").read_text(encoding="utf-8"))
    names = [name for name in modules_payload["slots"][slot] if name]
    for workshop_id, name in zip(ids, names):
        WORKSHOP_ID_TO_NAME[workshop_id] = name

UW_TRACK_KEYS: Dict[str, List[str]] = {
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

RARITY_LABEL = {"rare": "1-Rare", "epic": "2-Epic", "legendary": "3-Legendary"}


def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


def _parse_ts_milestones(source: str) -> Dict[str, Dict[str, Any]]:
    tracks: Dict[str, Dict[str, Any]] = {}
    pattern = re.compile(
        r"(?P<key>[a-zA-Z]+Level):\s*\{\s*valueKind:\s*\"(?P<kind>[^\"]+)\",\s*milestones:\s*\[(?P<body>.*?)\]\s*\}",
        re.DOTALL,
    )
    value_pattern = re.compile(r"value:\s*(?P<value>[-\d.]+)")
    for match in pattern.finditer(source):
        values = [float(item.group("value")) for item in value_pattern.finditer(match.group("body"))]
        tracks[match.group("key")] = {"value_kind": match.group("kind"), "milestones": values}
    return tracks


def _parse_relic_bonus(description: str) -> Tuple[str, float]:
    text = description.strip()
    percent = re.search(r"Increase (.+?) by ([\d.]+)%", text, flags=re.I)
    if percent:
        stat_raw = percent.group(1).strip().lower()
        value = float(percent.group(2)) / 100.0
        stat_map = {
            "coins earned": "Coins",
            "coin": "Coins",
            "lab speed": "Lab Speed",
            "tower damage": "Damage",
            "tower health": "Health",
            "defense absolute": "Defense %",
            "critical factor": "Critical Factor",
            "damage/meter": "Damage / Meter",
            "ultimate damage": "Ultimate Damage",
            "attack speed": "Attack Speed",
            "health regen": "Health Regen",
        }
        return stat_map.get(stat_raw, percent.group(1).strip()), value
    flat = re.search(r"Increase (.+?) by ([\d.]+)", text, flags=re.I)
    if flat:
        return flat.group(1).strip(), float(flat.group(2))
    return "Unknown", 0.0


def _load_relic_index_table() -> List[Optional[str]]:
    source = _fetch(_REF_RELIC_INDEX)
    ids: List[Optional[str]] = []
    for line in source.splitlines():
        match = re.match(r'\s*"(?P<id>[a-z0-9_]+)",\s*//', line)
        if match:
            ids.append(match.group("id"))
            continue
        if re.match(r"\s*null,\s*//", line):
            ids.append(None)
    return ids


def _load_workshop_relics() -> List[Dict[str, Any]]:
    payload = _fetch(_REF_RELIC_NAMES)
    return json.loads(payload)


def build_relics_catalog() -> Dict[str, Any]:
    relic_ids = _load_relic_index_table()
    workshop_rows = _load_workshop_relics()
    by_workshop_id = {row["id"]: row for row in workshop_rows}
    by_index: List[Optional[Dict[str, Any]]] = []
    by_name: Dict[str, Dict[str, Any]] = {}
    for index, workshop_id in enumerate(relic_ids):
        if not workshop_id:
            by_index.append(None)
            continue
        row = by_workshop_id.get(workshop_id)
        if not row:
            by_index.append({"index": index, "id": workshop_id, "name": workshop_id.replace("_", " ").title()})
            continue
        bonus_type, value = _parse_relic_bonus(str(row.get("description") or ""))
        entry = {
            "index": index,
            "id": workshop_id,
            "name": row["name"],
            "rarity": RARITY_LABEL.get(str(row.get("rarity") or "").lower(), str(row.get("rarity") or "")),
            "bonus_type": bonus_type,
            "value": value,
            "description": row.get("description"),
            "unlock_group": row.get("unlockGroup"),
        }
        by_index.append(entry)
        by_name[entry["name"]] = entry
    return {"version": "1.0.0", "source": CATALOG_ATTRIBUTION, "by_index": by_index, "by_name": by_name}


def build_uw_tracks() -> Dict[str, Any]:
    source = _fetch(_REF_UW_TRACKS)
    parsed = _parse_ts_milestones(source)
    weapons: Dict[str, Any] = {}
    for weapon_name, track_keys in UW_TRACK_KEYS.items():
        attrs = {}
        for track_key in track_keys:
            track = parsed.get(track_key)
            if track:
                attrs[track_key] = track
        weapons[weapon_name] = {"tracks": track_keys, "attributes": attrs}
    return {"version": "1.0.0", "source": CATALOG_ATTRIBUTION, "weapons": weapons}


def _parse_theme_index_map(source: str) -> Dict[str, int]:
    pattern = re.compile(r"'(?P<id>[^']+)':\s*(?P<index>\d+)")
    return {match.group("id"): int(match.group("index")) for match in pattern.finditer(source)}


def _theme_id_to_name(theme_id: str) -> str:
    _, _, slug = theme_id.partition("-")
    label = slug or theme_id
    return " ".join(part.capitalize() for part in label.replace("_", "-").split("-"))


def _invert_theme_index(index_by_id: Dict[str, int]) -> Dict[str, Dict[str, str]]:
    inverted: Dict[str, Dict[str, str]] = {}
    for theme_id, index in index_by_id.items():
        inverted[str(index)] = {"id": theme_id, "name": _theme_id_to_name(theme_id)}
    return inverted


def _parse_guardian_theme_index(source: str) -> Dict[str, Dict[str, str]]:
    match = re.search(
        r"GUARDIAN_THEME_IDS_BY_GAME_INDEX:\s*readonly\s*\(string\s*\|\s*undefined\)\[\]\s*=\s*\[(?P<body>.*?)\]",
        source,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    body = match.group("body")
    guardian_ids = re.findall(r"GUARDIAN_THEME_IDS\[(\d+)\]", body)
    guardian_catalog = re.findall(r"id:\s*'(?P<id>guardian-[^']+)'", _fetch(
        "https://raw.githubusercontent.com/AngryBrit/tower-smith/main/src/data/gameThemes.ts"
    ))
    ordered_guardians = [item for item in guardian_catalog if item.startswith("guardian-")]
    mapping: Dict[str, Dict[str, str]] = {}
    index = 0
    for token in re.findall(r"undefined|GUARDIAN_THEME_IDS\[\d+\]", body):
        if token == "undefined":
            index += 1
            continue
        ref = int(re.search(r"\d+", token).group())
        theme_id = ordered_guardians[ref] if ref < len(ordered_guardians) else f"guardian-{ref}"
        mapping[str(index)] = {"id": theme_id, "name": _theme_id_to_name(theme_id)}
        index += 1
    return mapping


def build_themes_catalog() -> Dict[str, Any]:
    tower = _invert_theme_index(_parse_theme_index_map(_fetch(_REF_TOWER_THEME_SLOTS)))
    background = _invert_theme_index(_parse_theme_index_map(_fetch(_REF_BACKGROUND_THEME_SLOTS)))
    music = _invert_theme_index(_parse_theme_index_map(_fetch(_REF_MUSIC_THEME_SLOTS)))
    guardian = _parse_guardian_theme_index(_fetch(_REF_GAME_THEME_INDEX))
    return {
        "version": "1.0.0",
        "source": CATALOG_ATTRIBUTION,
        "index_maps": {
            "tower": tower,
            "background": background,
            "music": music,
            "guardian_skins": guardian,
        },
    }


def build_module_effects_catalog() -> Dict[str, Any]:
    source = _fetch(_REF_MODULE_EFFECTS)
    pattern = re.compile(
        r'\{\s*slot:\s*"(?P<slot>[^"]+)",\s*effectId:\s*"(?P<effect>[^"]+)",\s*rarity:\s*"(?P<rarity>[^"]+)"\s*\},\s*//\s*(?P<index>\d+)',
    )
    by_index: Dict[str, Dict[str, str]] = {}
    for match in pattern.finditer(source):
        effect_id = match.group("effect")
        by_index[match.group("index")] = {
            "slot": match.group("slot").title(),
            "effect_id": effect_id,
            "name": _theme_id_to_name(effect_id),
            "rarity": match.group("rarity"),
        }
    return {"version": "1.0.0", "source": CATALOG_ATTRIBUTION, "by_index": by_index}


def build_module_index_catalog() -> List[Optional[Dict[str, Any]]]:
    rows: List[Optional[Dict[str, Any]]] = []
    for info_index, workshop_id in enumerate(MODULE_INFO_INDEX_TO_WORKSHOP_ID):
        if not workshop_id:
            rows.append(None)
            continue
        slot = next((slot_name for slot_name, ids in SLOT_ORDERS.items() if workshop_id in ids), None)
        name = WORKSHOP_ID_TO_NAME.get(workshop_id, workshop_id)
        rows.append({"info_index": info_index, "workshop_id": workshop_id, "slot": slot, "name": name})
    return rows


def update_save_mappings(module_index: List[Optional[Dict[str, Any]]]) -> None:
    path = GAME_DATA / "save_mappings.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = "1.1.0"
    payload["source"] = CATALOG_ATTRIBUTION
    payload["module_rarity"] = GAME_MODULE_RARITY
    payload["module_info_index"] = module_index
    payload["module_workshop_id_to_name"] = WORKSHOP_ID_TO_NAME
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    module_index = build_module_index_catalog()
    relics = build_relics_catalog()
    uw_tracks = build_uw_tracks()
    themes = build_themes_catalog()
    module_effects = build_module_effects_catalog()
    (GAME_DATA / "relics.json").write_text(json.dumps(relics, indent=2) + "\n", encoding="utf-8")
    (GAME_DATA / "uw_save_tracks.json").write_text(json.dumps(uw_tracks, indent=2) + "\n", encoding="utf-8")
    (GAME_DATA / "save_themes.json").write_text(json.dumps(themes, indent=2) + "\n", encoding="utf-8")
    (GAME_DATA / "save_module_effects.json").write_text(json.dumps(module_effects, indent=2) + "\n", encoding="utf-8")
    update_save_mappings(module_index)
    print(f"Wrote relics.json ({len(relics['by_index'])} indices, {len(relics['by_name'])} named)")
    print(f"Wrote uw_save_tracks.json ({len(uw_tracks['weapons'])} weapons)")
    print(f"Wrote save_themes.json ({sum(len(v) for v in themes['index_maps'].values())} theme slots)")
    print(f"Wrote save_module_effects.json ({len(module_effects['by_index'])} effect indices)")
    print("Updated save_mappings.json module tables")


if __name__ == "__main__":
    main()
