"""Parse The Tower playerInfo.dat saves into Tower Optimizer profile patches."""
from __future__ import annotations

import gzip
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Tuple

from .engines.core import (
    BOT_NAMES,
    CARD_NAMES,
    ENHANCEMENT_MAX_LEVELS,
    LAB_ALIASES,
    LAB_MAX_LEVELS,
    UW_ATTRIBUTE_META,
    UW_NAMES,
    WORKSHOP_MAX_LEVELS,
)

_PACKAGE_DIR = Path(__file__).resolve().parent
_GAME_DATA_DIR = _PACKAGE_DIR / "game_data"
_MAPPINGS_PATH = _GAME_DATA_DIR / "save_mappings.json"
_LABS_PATH = _GAME_DATA_DIR / "labs.json"

ENHANCEMENT_ATTACK = list(ENHANCEMENT_MAX_LEVELS.keys())[:6]
ENHANCEMENT_DEFENSE = list(ENHANCEMENT_MAX_LEVELS.keys())[6:12]
ENHANCEMENT_UTILITY = list(ENHANCEMENT_MAX_LEVELS.keys())[12:18]


def _load_mappings() -> Dict[str, Any]:
    return json.loads(_MAPPINGS_PATH.read_text(encoding="utf-8"))


def _load_lab_names() -> List[str]:
    payload = json.loads(_LABS_PATH.read_text(encoding="utf-8"))
    return [str(row["name"]) for row in payload.get("stats", [])]


def decode_player_save_bytes(payload: bytes) -> Dict[str, Any]:
    """Decode gzip-wrapped or raw NRBF player save bytes."""
    import nrbf

    if payload[:2] == b"\x1f\x8b":
        payload = gzip.decompress(payload)
    data = nrbf.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Decoded player save is not the expected SaveLoad+PlayerData object.")
    return data


def decode_player_save_file(path: Path | str) -> Dict[str, Any]:
    return decode_player_save_bytes(Path(path).read_bytes())


def _levels_from_array(values: List[Any], names: List[str], known: Mapping[str, int]) -> Dict[str, int]:
    output: Dict[str, int] = {}
    for index, name in enumerate(names):
        if index >= len(values):
            break
        level = values[index]
        if level is None:
            continue
        try:
            numeric = int(round(float(level)))
        except (TypeError, ValueError):
            continue
        if numeric <= 0 or name not in known:
            continue
        output[name] = numeric
    return output


def _map_workshop(save: Mapping[str, Any], mappings: Mapping[str, Any]) -> Dict[str, int]:
    workshop: Dict[str, int] = {}
    workshop.update(_levels_from_array(list(save.get("upgradeWorkshopLevel") or []), list(mappings["workshop_attack"]), WORKSHOP_MAX_LEVELS))
    workshop.update(_levels_from_array(list(save.get("upgradeWorkshopDefenseLevel") or []), list(mappings["workshop_defense"]), WORKSHOP_MAX_LEVELS))
    workshop.update(_levels_from_array(list(save.get("upgradeWorkshopUtilityLevel") or []), list(mappings["workshop_utility"]), WORKSHOP_MAX_LEVELS))
    return workshop


def _map_enhancements(save: Mapping[str, Any]) -> Dict[str, int]:
    enhancements: Dict[str, int] = {}
    enhancements.update(_levels_from_array(list(save.get("enhancementLevel") or []), ENHANCEMENT_ATTACK, ENHANCEMENT_MAX_LEVELS))
    enhancements.update(_levels_from_array(list(save.get("enhancementDefenseLevel") or []), ENHANCEMENT_DEFENSE, ENHANCEMENT_MAX_LEVELS))
    enhancements.update(_levels_from_array(list(save.get("enhancementUtilityLevel") or []), ENHANCEMENT_UTILITY, ENHANCEMENT_MAX_LEVELS))
    return enhancements


def _map_labs(save: Mapping[str, Any], mappings: Mapping[str, Any], lab_names: List[str]) -> Dict[str, int]:
    research_levels = list(save.get("researchLevel") or [])
    id_to_flat = list(mappings.get("research_id_to_manifest_flat") or [])
    labs: Dict[str, int] = {}
    for research_id, level in enumerate(research_levels):
        try:
            numeric = int(round(float(level)))
        except (TypeError, ValueError):
            continue
        if numeric <= 0:
            continue
        if research_id >= len(id_to_flat):
            continue
        flat = int(id_to_flat[research_id])
        if flat < 0 or flat >= len(lab_names):
            continue
        canonical = LAB_ALIASES.get(lab_names[flat], lab_names[flat])
        if canonical not in LAB_MAX_LEVELS:
            continue
        labs[canonical] = numeric
    return labs


def _map_cards(save: Mapping[str, Any]) -> Dict[str, Any]:
    levels = list(save.get("cardLevel") or [])
    unlocked = list(save.get("cardUnlocked") or [])
    active = list(save.get("cardActive") or [])
    items: Dict[str, Dict[str, int]] = {}
    for index, name in enumerate(CARD_NAMES):
        if index >= len(levels):
            break
        try:
            level = int(round(float(levels[index])))
        except (TypeError, ValueError):
            level = 0
        is_unlocked = bool(unlocked[index]) if index < len(unlocked) else level > 0
        if level <= 0 and not is_unlocked:
            continue
        items[name] = {"level": max(level, 0), "mastery": 0}
    slots = sum(1 for flag in active if flag)
    if slots <= 0:
        slots = sum(1 for item in items.values() if item.get("level", 0) > 0)
    return {"slots": slots, "items": items}


def _map_uws(save: Mapping[str, Any]) -> Dict[str, Any]:
    unlocked = list(save.get("ultimateWeaponUnlocked") or [])
    levels = list(save.get("ultimateWeaponLevel") or [])
    output: Dict[str, Any] = {}
    cursor = 0
    for uw_index, uw_name in enumerate(UW_NAMES):
        attrs = UW_ATTRIBUTE_META.get(uw_name, {})
        owned = bool(unlocked[uw_index]) if uw_index < len(unlocked) else False
        attributes: Dict[str, Any] = {}
        for attr_name in attrs:
            if cursor >= len(levels):
                break
            raw = levels[cursor]
            cursor += 1
            meta = attrs[attr_name]
            if isinstance(meta.get("max"), float) and meta.get("display") == "percent":
                attributes[attr_name] = float(raw)
            else:
                try:
                    attributes[attr_name] = int(round(float(raw)))
                except (TypeError, ValueError):
                    attributes[attr_name] = raw
        if owned or attributes:
            output[uw_name] = {"owned": owned, "attributes": attributes}
    return output


def _rarity_name(index: int, mappings: Mapping[str, Any]) -> str:
    names = list(mappings.get("module_rarity") or [])
    if 0 <= index < len(names):
        return names[index]
    return f"Rarity {index}"


def _map_modules(save: Mapping[str, Any], mappings: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    slots = list(mappings.get("module_slots") or [])
    equipped_rows = list(save.get("moduleEquipped") or [])
    modules: Dict[str, Any] = {}
    inventory: Dict[str, Any] = {}

    for slot_index, row in enumerate(equipped_rows):
        if not isinstance(row, dict):
            continue
        slot = slots[slot_index] if slot_index < len(slots) else f"Slot {slot_index + 1}"
        info_index = int(row.get("infoIndex") or 0)
        rarity = _rarity_name(int(row.get("currentRarity") or 0), mappings)
        level = int(round(float(row.get("level") or 0)))
        name = f"Module {info_index}" if info_index else ""
        modules[slot] = {"name": name, "rarity": rarity, "level": level}

    counts: Dict[str, int] = {}
    for row in list(save.get("moduleRecords") or []):
        if not isinstance(row, dict):
            continue
        info_index = int(row.get("infoIndex") or 0)
        rarity = _rarity_name(int(row.get("rarity") or 0), mappings)
        key = f"Index {info_index}::{rarity}"
        counts[key] = counts.get(key, 0) + 1
    for key, copies in sorted(counts.items()):
        info_index, rarity = key.split("::", 1)
        index_value = info_index.replace("Index ", "")
        inventory[key] = {
            "slot": "Unknown",
            "name": f"Module {index_value}",
            "rarity": rarity,
            "level": 1,
            "copies": copies,
            "locked": True,
            "substats": [],
        }
    return modules, inventory


def _map_resources(save: Mapping[str, Any]) -> Dict[str, Any]:
    resources: Dict[str, Any] = {}
    for key in ("coins", "stones", "gems", "medals", "keys", "bits", "cells"):
        if key not in save:
            continue
        value = save[key]
        try:
            resources[key] = float(value) if key == "coins" else int(round(float(value)))
        except (TypeError, ValueError):
            continue
    if "moduleRerollCurrency" in save:
        resources["reroll_shards"] = int(round(float(save["moduleRerollCurrency"])))
    shard_total = sum(
        int(round(float(save.get(field) or 0)))
        for field in ("moduleCannonShards", "moduleArmorShards", "moduleGeneratorShards", "moduleCoreShards")
    )
    if shard_total:
        resources["module_shards"] = shard_total
    return resources


def _map_player(save: Mapping[str, Any]) -> Dict[str, Any]:
    player: Dict[str, Any] = {}
    current_tier = save.get("currentTier")
    if current_tier is not None:
        try:
            player["farming_tier"] = int(current_tier)
        except (TypeError, ValueError):
            pass
    if "totalCoinsEarned" in save:
        try:
            player["lifetime_coins"] = float(save["totalCoinsEarned"])
        except (TypeError, ValueError):
            pass
    tiers: Dict[str, Dict[str, int]] = {}
    highest = list(save.get("highestWaveThisTier") or [])
    for tier_index, wave in enumerate(highest):
        try:
            wave_value = int(round(float(wave)))
        except (TypeError, ValueError):
            continue
        if wave_value <= 0:
            continue
        tiers[str(tier_index)] = {"highest_wave": wave_value}
    if tiers:
        player["tiers"] = tiers
    return player


def _map_bots(save: Mapping[str, Any]) -> Dict[str, Any]:
    preset_keys = {
        "Flame Bot": "flameBotPresets",
        "Thunder Bot": "thunderBotPresets",
        "Golden Bot": "goldenBotPresets",
        "Amplify Bot": "amplifyBotPresets",
        "Bot Bot": "botBotPresets",
    }
    bots: Dict[str, Any] = {}
    for bot_name in BOT_NAMES:
        presets = list(save.get(preset_keys.get(bot_name, "")) or [])
        active = next((row for row in presets if isinstance(row, dict) and row.get("active")), None)
        if not active:
            continue
        levels = list(active.get("selectedLevels") or active.get("levels") or [])
        bots[bot_name] = {
            "owned": bool(active.get("unlocked", True)),
            "levels": levels,
            "plus_unlocked": bool(active.get("plusUnlocked")),
            "plus_level": int(active.get("plusLevel") or 0),
        }
    return bots


def _map_relics(save: Mapping[str, Any]) -> Dict[str, Any]:
    owned_ids = [int(value) for value in list(save.get("profileRelics") or []) if value is not None]
    relics_unlocked = list(save.get("relicsUnlocked") or [])
    items: Dict[str, Any] = {}
    for relic_id, owned_flag in enumerate(relics_unlocked):
        try:
            owned = int(round(float(owned_flag))) > 0
        except (TypeError, ValueError):
            owned = False
        if not owned and relic_id not in owned_ids:
            continue
        items[f"Relic {relic_id}"] = {
            "owned": owned or relic_id in owned_ids,
            "equipped": relic_id in owned_ids,
            "rarity": "",
            "bonus_type": "",
            "value": 0,
        }
    return {"items": items}


def build_profile_patch(save: Mapping[str, Any]) -> Dict[str, Any]:
    mappings = _load_mappings()
    lab_names = _load_lab_names()
    modules, module_inventory = _map_modules(save, mappings)
    cards = _map_cards(save)
    return {
        "resources": _map_resources(save),
        "player": _map_player(save),
        "workshop": _map_workshop(save, mappings),
        "labs": _map_labs(save, mappings, lab_names),
        "enhancements": _map_enhancements(save),
        "uw": _map_uws(save),
        "cards": cards,
        "modules": modules,
        "module_inventory": module_inventory,
        "bots": _map_bots(save),
        "relics": _map_relics(save),
    }


def preview_player_save(payload: bytes, filename: str = "playerInfo.dat") -> Dict[str, Any]:
    save = decode_player_save_bytes(payload)
    patch = build_profile_patch(save)
    return {
        "filename": filename,
        "sections": {
            "resources": len(patch.get("resources", {})),
            "workshop": len(patch.get("workshop", {})),
            "labs": len(patch.get("labs", {})),
            "enhancements": len(patch.get("enhancements", {})),
            "uw": len(patch.get("uw", {})),
            "cards": len(patch.get("cards", {}).get("items", {})),
            "modules": len(patch.get("modules", {})),
            "module_inventory": len(patch.get("module_inventory", {})),
            "bots": len(patch.get("bots", {})),
            "relics": len(patch.get("relics", {}).get("items", {})),
        },
        "patch": patch,
        "notes": [
            "Ultimate weapon attribute values are imported as stored in the save file.",
            "Module names use game infoIndex labels until a full module catalog is bundled.",
            "Battle report history is not stored in playerInfo.dat.",
        ],
        "data_version": save.get("dataVersion"),
        "save_revision": save.get("saveRevision"),
    }


def apply_player_save_patch(
    profile: MutableMapping[str, Any],
    patch: Mapping[str, Any],
    *,
    replace: bool = False,
    source_name: str = "playerInfo.dat",
) -> Dict[str, int]:
    """Merge a save-derived patch into a profile. Returns per-section counts."""
    counts: Dict[str, int] = {}
    profile.setdefault("maxed", {})

    resources = patch.get("resources") or {}
    if resources:
        profile.setdefault("resources", {}).update(deepcopy(resources))
        counts["resources"] = len(resources)

    player = patch.get("player") or {}
    if player:
        target = profile.setdefault("player", {})
        for key, value in player.items():
            if key == "tiers" and isinstance(value, dict):
                target.setdefault("tiers", {}).update(deepcopy(value))
            else:
                target[key] = value
        counts["player"] = len(player)

    for section in ("workshop", "labs", "enhancements"):
        values = patch.get(section) or {}
        if not values:
            continue
        if replace:
            profile[section] = {}
            profile.setdefault("maxed", {}).setdefault(section, {})
        for name, level in values.items():
            profile.setdefault(section, {})[name] = int(level)
        counts[section] = len(values)

    uw = patch.get("uw") or {}
    if uw:
        if replace:
            profile["uw"] = {}
            profile.setdefault("maxed", {}).setdefault("uw", {})
        for uw_name, payload in uw.items():
            entry = profile.setdefault("uw", {}).setdefault(uw_name, {"owned": False, "attributes": {}})
            entry["owned"] = bool(payload.get("owned"))
            entry.setdefault("attributes", {}).update(deepcopy(payload.get("attributes") or {}))
        counts["uw"] = len(uw)

    cards = patch.get("cards") or {}
    if cards:
        if replace:
            profile["cards"] = {"slots": 0, "slot_target": 1, "items": {}, "presets": {}}
        card_target = profile.setdefault("cards", {"items": {}, "presets": {}})
        if cards.get("slots"):
            card_target["slots"] = int(cards["slots"])
        card_target.setdefault("items", {}).update(deepcopy(cards.get("items") or {}))
        counts["cards"] = len(cards.get("items") or {})

    modules = patch.get("modules") or {}
    if modules:
        if replace:
            profile["modules"] = {}
        profile.setdefault("modules", {}).update(deepcopy(modules))
        counts["modules"] = len(modules)

    module_inventory = patch.get("module_inventory") or {}
    if module_inventory:
        if replace:
            profile["module_inventory"] = {}
        profile.setdefault("module_inventory", {}).update(deepcopy(module_inventory))
        counts["module_inventory"] = len(module_inventory)

    bots = patch.get("bots") or {}
    if bots:
        if replace:
            profile["bots"] = {}
        profile.setdefault("bots", {}).update(deepcopy(bots))
        counts["bots"] = len(bots)

    relics = patch.get("relics") or {}
    if relics.get("items"):
        if replace:
            profile["relics"] = {"summary": {}, "bonuses": {}, "items": {}}
        profile.setdefault("relics", {}).setdefault("items", {}).update(deepcopy(relics["items"]))
        counts["relics"] = len(relics["items"])

    profile.setdefault("sources", {})["player_save"] = {
        "filename": source_name,
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }
    profile.setdefault("import_audit", []).append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "source": source_name,
            "kind": "playerInfo.dat",
            "sections": counts,
        }
    )
    profile.setdefault("metadata", {})["last_import"] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "source": source_name,
        "kind": "playerInfo.dat",
    }
    _mark_profile_caps(profile)
    return counts


def _mark_profile_caps(profile: MutableMapping[str, Any]) -> None:
    maxed = profile.setdefault("maxed", {})
    for name, level in profile.get("workshop", {}).items():
        cap = WORKSHOP_MAX_LEVELS.get(name)
        if cap is not None:
            maxed.setdefault("workshop", {})[name] = int(level) >= int(cap)
    for name, level in profile.get("labs", {}).items():
        cap = LAB_MAX_LEVELS.get(name)
        if cap is not None:
            maxed.setdefault("labs", {})[name] = int(level) >= int(cap)
    for name, level in profile.get("enhancements", {}).items():
        cap = ENHANCEMENT_MAX_LEVELS.get(name)
        if cap is not None:
            maxed.setdefault("enhancements", {})[name] = int(level) >= int(cap)
    for uw_name, payload in profile.get("uw", {}).items():
        attrs = payload.get("attributes") or {}
        gold = maxed.setdefault("uw", {}).setdefault(uw_name, {})
        for attr, value in attrs.items():
            meta = UW_ATTRIBUTE_META.get(uw_name, {}).get(attr)
            if not meta:
                continue
            if meta.get("lower_is_better"):
                gold[attr] = float(value) <= float(meta["max"])
            else:
                gold[attr] = float(value) >= float(meta["max"])


__all__ = [
    "decode_player_save_bytes",
    "decode_player_save_file",
    "build_profile_patch",
    "preview_player_save",
    "apply_player_save_patch",
]
