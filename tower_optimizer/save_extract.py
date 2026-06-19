"""Extended playerInfo.dat field extraction for Tower Optimizer profiles."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Tuple

from .engines.core import BOT_NAMES, CARD_NAMES, UW_NAMES
from .game_catalog import (
    load_relics_catalog,
    module_info_entry,
    module_rarity_label,
    relic_entry,
)

_GAME_DATA = Path(__file__).resolve().parent / "game_data"
DOTNET_EPOCH_TICKS = 621355968000000000
BOT_ATTRIBUTES = {
    "Flame Bot": ["Damage R.", "Cooldown", "Damage", "Range"],
    "Thunder Bot": ["Duration", "Cooldown", "Linger", "Range"],
    "Golden Bot": ["Duration", "Cooldown", "Bonus", "Range"],
    "Amplify Bot": ["Duration", "Cooldown", "Bonus", "Range"],
    "Bot Bot": ["Duration", "Cooldown", "Bonus", "Range"],
}
BOT_PRESET_KEYS = {
    "Flame Bot": "flameBotPresets",
    "Thunder Bot": "thunderBotPresets",
    "Golden Bot": "goldenBotPresets",
    "Amplify Bot": "amplifyBotPresets",
    "Bot Bot": "botBotPresets",
}
UW_PLUS_NAMES = {
    "Chain Lightning": "Chain Lightning+",
    "Smart Missiles": "Smart Missiles+",
    "Death Wave": "Death Wave+",
    "Chrono Field": "Chrono Field+",
    "Inner Land Mines": "Inner Land Mines+",
    "Golden Tower": "Golden Tower+",
    "Poison Swamp": "Poison Swamp+",
    "Black Hole": "Black Hole+",
    "Spotlight": "Spotlight+",
}
THEME_UNLOCK_FIELDS = {
    "tower": "towerUnlocked",
    "background": "backgroundUnlocked",
    "menus": "menuUnlocked",
    "banners": "profileBannerUnlocked",
    "music": "trackAvailable",
    "guardian_skins": "guardianSkinUnlocked",
}
PROFILE_SECTION_KEYS = (
    "resources",
    "player",
    "workshop",
    "labs",
    "enhancements",
    "uw",
    "cards",
    "modules",
    "module_inventory",
    "module_presets",
    "bots",
    "relics",
    "themes",
    "guardians",
    "vault",
    "runs",
)

SAVE_BATTLE_HISTORY_SOURCE = "playerInfo.dat"
KILLED_BY_NAMES = {
    0: "Unknown",
    1: "Basic",
    2: "Fast",
    3: "Tank",
    4: "Ranged",
    5: "Boss",
    6: "Ray",
    7: "Vampire",
    8: "Scatter",
    9: "Protector",
    10: "Saboteur",
    11: "Commander",
    12: "Overcharge",
    99: "Unknown",
}


@lru_cache(maxsize=1)
def _load_json(name: str) -> Dict[str, Any]:
    return json.loads((_GAME_DATA / name).read_text(encoding="utf-8"))


def save_datetime(value: Any) -> Optional[str]:
    try:
        raw = int(value)
    except (TypeError, ValueError):
        return None
    if raw <= 0:
        return None
    kind_mask = raw & 0xC000000000000000
    if kind_mask in (0x4000000000000000, 0x8000000000000000):
        ticks = raw & 0x3FFFFFFFFFFFFFFF
        seconds = (ticks - DOTNET_EPOCH_TICKS) / 10_000_000.0
    elif raw > DOTNET_EPOCH_TICKS:
        seconds = (raw - DOTNET_EPOCH_TICKS) / 10_000_000.0
    elif raw > 10_000_000_000:
        seconds = raw / 1000.0
    else:
        seconds = float(raw)
    try:
        stamp = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return stamp.strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return None


def resolve_killed_by(row: Mapping[str, Any]) -> str:
    raw = row.get("killedBy")
    if isinstance(raw, str) and raw.strip() and not raw.strip().isdigit():
        return raw.strip()
    try:
        index = int(raw)
    except (TypeError, ValueError):
        return "Unknown"
    return KILLED_BY_NAMES.get(index, f"Enemy {index}")


def _bool(value: Any) -> bool:
    return bool(value)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _theme_display_name(category: str, index: int) -> Tuple[str, str]:
    catalog = _load_json("save_themes.json")
    entry = (catalog.get("index_maps") or {}).get(category, {}).get(str(index))
    if entry:
        return str(entry.get("name") or entry.get("id")), str(entry.get("id") or "")
    fallback = f"{category.replace('_', ' ').title()} {index}"
    return fallback, ""


def _module_effect_entry(effect_id: int) -> Optional[Dict[str, Any]]:
    if effect_id <= 0:
        return None
    catalog = _load_json("save_module_effects.json")
    return (catalog.get("by_index") or {}).get(str(effect_id))


def summarize_raw_fields(save: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in sorted(save.keys()):
        if key == "__class__":
            continue
        value = save[key]
        row: Dict[str, Any] = {"field": key}
        if isinstance(value, bool):
            row.update(type="bool", value=value)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            row.update(type="number", value=value)
        elif isinstance(value, str):
            row.update(type="string", length=len(value), preview=value[:120])
        elif isinstance(value, list):
            row.update(type="list", length=len(value))
            if value:
                sample = value[0]
                row["item_type"] = type(sample).__name__
                if isinstance(sample, dict):
                    row["item_keys"] = sorted(sample.keys())[:8]
        elif isinstance(value, dict):
            row.update(type="object", keys=len(value))
        else:
            row["type"] = type(value).__name__
        rows.append(row)
    return rows


def map_module_registry(save: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = list(save.get("moduleRecords") or [])
    output: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        info_index = _int(row.get("infoIndex"))
        entry = module_info_entry(info_index)
        output.append(
            {
                "info_index": info_index,
                "name": entry.get("name") if entry else f"Module {info_index}",
                "slot": entry.get("slot") if entry else None,
                "rarity": module_rarity_label(_int(row.get("rarity"))),
                "obtained_at": save_datetime(row.get("dateObtained")),
            }
        )
    return output


def map_player_extended(save: Mapping[str, Any]) -> Dict[str, Any]:
    player: Dict[str, Any] = {}
    for key, target in (
        ("playerID", "player_id"),
        ("lastGuildID", "guild_id"),
        ("currentTier", "farming_tier"),
        ("currentWave", "current_wave"),
        ("tourneyLeague", "tourney_league"),
        ("totalCoinsEarned", "lifetime_coins"),
    ):
        if key in save and save[key] not in (None, ""):
            value = save[key]
            if target in {"farming_tier", "current_wave"}:
                player[target] = _int(value)
            elif target == "lifetime_coins":
                player[target] = _float(value)
            else:
                player[target] = str(value)
    packs: Dict[str, Any] = {}
    for key, label in (
        ("starterPackUnlockedBool", "Starter Pack"),
        ("epicPackUnlockedBool", "Epic Pack"),
        ("disableAdsUnlockedBool", "Disable Ads"),
    ):
        if key in save:
            packs[label] = _bool(save.get(key))
    if packs:
        player["packs"] = packs
    if "lastAttempt" in save and isinstance(save["lastAttempt"], dict):
        player["last_tournament_attempt"] = dict(save["lastAttempt"])
    player["selected_themes"] = {
        "tower_index": _int(save.get("themeTower")),
        "background_index": _int(save.get("themeBackground")),
        "guardian_skin_index": _int(save.get("guardianSkinIndex")),
    }
    return player


def map_resources_extended(save: Mapping[str, Any]) -> Dict[str, Any]:
    resources: Dict[str, Any] = {}
    for key in (
        "coins", "stones", "gems", "medals", "keys", "bits", "cells", "cash",
        "moduleRerollCurrency", "moduleCannonShards", "moduleArmorShards",
        "moduleGeneratorShards", "moduleCoreShards", "tickets", "tokens",
    ):
        if key not in save:
            continue
        value = save[key]
        if key == "coins":
            resources[key] = _float(value)
        elif key in {"cash"}:
            resources[key] = _float(value)
        elif key == "moduleRerollCurrency":
            resources["reroll_shards"] = _int(value)
        elif key.startswith("module") and key.endswith("Shards"):
            resources.setdefault("module_shards_by_slot", {})[
                key.replace("module", "").replace("Shards", "").lower()
            ] = _int(value)
        else:
            resources[key] = _int(value)
    shard_total = sum(
        _int(save.get(field))
        for field in ("moduleCannonShards", "moduleArmorShards", "moduleGeneratorShards", "moduleCoreShards")
    )
    if shard_total:
        resources["module_shards"] = shard_total
    if "totalKeysSpent" in save:
        resources["total_keys_spent"] = _int(save.get("totalKeysSpent"))
    if "totalKeysEarned" in save:
        resources["total_keys_earned"] = _int(save.get("totalKeysEarned"))
    return resources


def map_cards_extended(save: Mapping[str, Any], cards: Mapping[str, Any]) -> Dict[str, Any]:
    payload = dict(cards)
    slots = _int(save.get("slotsUnlocked"))
    if slots > 0:
        payload["slots"] = slots
    card_index = _load_json("save_card_index.json")
    index_to_name = {int(k): v for k, v in card_index.get("save_index_to_name", {}).items()}
    mastery = list(save.get("cardMasteryUnlocked") or [])
    items = dict(payload.get("items") or {})
    for index, name in index_to_name.items():
        if index >= len(mastery):
            continue
        if name in items and _bool(mastery[index]):
            items[name]["mastery"] = 1
    payload["items"] = items
    presets = _map_card_presets(save, card_index)
    if presets:
        payload["presets"] = presets
        payload["active_preset"] = _int(save.get("currentPreset"))
    return payload


def _map_card_presets(save: Mapping[str, Any], card_index: Mapping[str, Any]) -> Dict[str, Any]:
    assigned = list(save.get("slotPresetCardAssignedBool") or [])
    values = list(save.get("slotPresetCardInt") or [])
    slot_count = int(card_index.get("preset_slot_count") or 35)
    preset_count = int(card_index.get("preset_count") or 4)
    index_to_name = {int(k): v for k, v in card_index.get("save_index_to_name", {}).items()}
    presets: Dict[str, Any] = {}
    for preset in range(preset_count):
        cards: List[str] = []
        for slot in range(slot_count):
            idx = preset * slot_count + slot
            if idx >= len(assigned) or idx >= len(values):
                break
            if not _bool(assigned[idx]):
                continue
            name = index_to_name.get(_int(values[idx]))
            if name and name not in cards:
                cards.append(name)
        if cards:
            presets[f"Preset {preset + 1}"] = cards
    return presets


def map_uw_extended(save: Mapping[str, Any], uw: Mapping[str, Any]) -> Dict[str, Any]:
    payload = {name: dict(entry) for name, entry in uw.items()}
    active = list(save.get("ultimateWeaponOn") or [])
    plus_levels = list(save.get("ultimateWeaponPlusLevel") or [])
    plus_unlocked = list(save.get("ultimateWeaponPlusUnlocked") or [])
    plus_active = list(save.get("ultimateWeaponPlusOn") or [])
    for index, name in enumerate(UW_NAMES):
        entry = payload.setdefault(name, {"owned": False, "attributes": {}})
        if index < len(active):
            entry["active"] = _bool(active[index])
        plus_name = UW_PLUS_NAMES.get(name)
        if not plus_name:
            continue
        plus: Dict[str, Any] = {}
        if index < len(plus_unlocked):
            plus["owned"] = _bool(plus_unlocked[index])
        if index < len(plus_active):
            plus["active"] = _bool(plus_active[index])
        if index < len(plus_levels):
            plus["level"] = _int(plus_levels[index])
        if plus:
            entry["plus"] = plus
    return payload


def map_bots_extended(save: Mapping[str, Any]) -> Dict[str, Any]:
    bots: Dict[str, Any] = {}
    for bot_name in BOT_NAMES:
        presets = list(save.get(BOT_PRESET_KEYS.get(bot_name, "")) or [])
        active = next((row for row in presets if isinstance(row, dict) and row.get("active")), None)
        if not active:
            unlocked_any = any(isinstance(row, dict) and row.get("unlocked") for row in presets)
            if not unlocked_any:
                continue
        row = active or next((item for item in presets if isinstance(item, dict)), {})
        levels = list(row.get("selectedLevels") or row.get("levels") or [])
        attrs = BOT_ATTRIBUTES.get(bot_name, [])
        attributes = {
            attr: levels[index]
            for index, attr in enumerate(attrs)
            if index < len(levels)
        }
        bots[bot_name] = {
            "owned": _bool(row.get("unlocked")),
            "levels": levels,
            "attributes": attributes,
            "plus_unlocked": _bool(row.get("plusUnlocked")),
            "plus_level": _int(row.get("plusLevel")),
        }
    return bots


def map_guardians(save: Mapping[str, Any]) -> Dict[str, Any]:
    catalog = _load_json("save_guardians.json")
    chip_index = {str(k): int(v) for k, v in catalog.get("chip_index", {}).items()}
    tracks = catalog.get("tracks") or {}
    upgrades_per = int(catalog.get("upgrades_per_chip") or 3)
    levels = list(save.get("guardianChipLevel") or [])
    unlocked = list(save.get("guardianChipUnlocked") or [])
    equipped = list(save.get("guardianChipSlot") or [])
    guardians: Dict[str, Any] = {}
    for name, game_index in chip_index.items():
        entry: Dict[str, Any] = {
            "unlocked": _bool(unlocked[game_index]) if game_index < len(unlocked) else False,
            "attributes": {},
            "bits_spent": 0,
        }
        track_names = list(tracks.get(name) or [])
        base = game_index * upgrades_per
        for offset, attr in enumerate(track_names):
            raw = levels[base + offset] if base + offset < len(levels) else 0
            entry["attributes"][attr] = max(1, _int(raw) + 1)
        if entry["unlocked"] or entry["attributes"]:
            guardians[name] = entry
    guardians["__meta__"] = {
        "slots_unlocked": _int(save.get("guardianSlotsUnlocked")),
        "equipped_chip_indices": [ _int(value) for value in equipped ],
        "guardian_unlocked": _bool(save.get("guardianUnlocked")),
    }
    return guardians


def map_themes(save: Mapping[str, Any]) -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    summary: Dict[str, Any] = {}
    for category, field in THEME_UNLOCK_FIELDS.items():
        flags = list(save.get(field) or [])
        owned = sum(1 for flag in flags if _bool(flag))
        summary[category] = {"owned": owned, "total": len(flags)}
        for index, flag in enumerate(flags):
            if not _bool(flag):
                continue
            name, theme_id = _theme_display_name(category, index)
            key = theme_id or f"{category}::{index}"
            items[key] = {
                "type": category.replace("_", " ").title(),
                "name": name,
                "owned": True,
                "index": index,
                "theme_id": theme_id or None,
            }
    selection = {
        "tower_index": _int(save.get("themeTower")),
        "background_index": _int(save.get("themeBackground")),
        "guardian_skin_index": _int(save.get("guardianSkinIndex")),
    }
    return {"summary": summary, "items": items, "selection": selection}


def map_vault(save: Mapping[str, Any]) -> Dict[str, Any]:
    vault: Dict[str, Any] = {
        "keys_spent": _int(save.get("totalKeysSpent")),
        "bonuses": {},
        "unlocks": {},
    }
    power_unlocked = list(save.get("powerNodesUnlocked") or [])
    power_levels = list(save.get("powerNodesLevel") or [])
    for index, unlocked in enumerate(power_unlocked):
        name = f"Power Node {index + 1}"
        if _bool(unlocked):
            vault["unlocks"][name] = True
        level = power_levels[index] if index < len(power_levels) else 0
        if level > 0:
            vault["bonuses"][name] = {"active": level, "total": level}
    harmony_unlocked = list(save.get("harmonyNodesUnlocked") or [])
    for index, unlocked in enumerate(harmony_unlocked):
        if not _bool(unlocked):
            continue
        vault["unlocks"][f"Harmony Node {index + 1}"] = True
    if "keys" in save:
        vault["keys_balance"] = _int(save.get("keys"))
    return vault


def map_module_presets(save: Mapping[str, Any]) -> Dict[str, Any]:
    names = list(save.get("workshopPresetName") or [])
    current = _int(save.get("currentWorkshopPreset"))
    if not names and current <= 0:
        return {}
    return {"names": names, "active_index": current}


def map_modules_with_substats(save: Mapping[str, Any], modules: Mapping[str, Any]) -> Dict[str, Any]:
    equipped_rows = list(save.get("moduleEquipped") or [])
    slots = list(modules.keys())
    equipped = dict(modules)
    slot_names = ["Cannon", "Armor", "Generator", "Core"]
    for slot_index, row in enumerate(equipped_rows):
        if not isinstance(row, dict):
            continue
        slot = slot_names[slot_index] if slot_index < len(slot_names) else (slots[slot_index] if slot_index < len(slots) else f"Slot {slot_index + 1}")
        if slot not in equipped:
            continue
        effects = [_int(value) for value in list(row.get("effects") or []) if _int(value) > 0]
        locked = list(row.get("effectLocked") or [])
        substats = []
        for effect_index, effect_id in enumerate(effects[:8]):
            decoded = _module_effect_entry(effect_id)
            substats.append(
                {
                    "effect_id": effect_id,
                    "name": (decoded or {}).get("name"),
                    "slot": (decoded or {}).get("slot"),
                    "rarity": (decoded or {}).get("rarity"),
                    "locked": _bool(locked[effect_index]) if effect_index < len(locked) else False,
                }
            )
        equipped[slot] = {**equipped[slot], "substats": substats, "favorite": _bool(row.get("favorite"))}
    return equipped


def map_battle_history(save: Mapping[str, Any], *, limit: int = 30) -> List[Dict[str, Any]]:
    rows = list(save.get("battleHistory") or [])
    runs: List[Dict[str, Any]] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        tier = _int(row.get("tier"))
        wave = _int(row.get("wave"))
        if tier <= 0 or wave <= 0:
            continue
        real_seconds = _float(row.get("realTime"))
        game_seconds = _float(row.get("gameTime"))
        coins = _float(row.get("coinsEarned"))
        cells = _float(row.get("cellsEarned"))
        hours = real_seconds / 3600.0 if real_seconds > 0 else 0.0
        runs.append(
            {
                "id": uuid.uuid4().hex[:20],
                "source": SAVE_BATTLE_HISTORY_SOURCE,
                "imported_from_save": True,
                "battle_date": save_datetime(row.get("battleDate")),
                "tier": tier,
                "wave": wave,
                "killed_by": resolve_killed_by(row),
                "real_seconds": int(round(real_seconds)),
                "game_seconds": int(round(game_seconds)),
                "coins_earned": coins,
                "cells_earned": cells,
                "coins_per_hour": coins / hours if hours > 0 else 0.0,
                "cells_per_hour": cells / hours if hours > 0 else 0.0,
                "run_type": "Tournament" if _bool(row.get("isTournament")) else "Auto",
                "play_style": "Auto",
                "metrics": {
                    "damage_dealt": _float(row.get("damageDealt")),
                    "damage_taken": _float(row.get("damageTaken")),
                    "waves_skipped": _int(row.get("wavesSkipped")),
                    "coins_from_golden_tower": _float(row.get("coinsFromGoldenTower")),
                    "coins_from_black_hole": _float(row.get("coinsFromBlackHole")),
                    "coins_from_spotlight": _float(row.get("coinsFromSpotlight")),
                    "coins_from_death_wave": _float(row.get("coinsFromDeathWave")),
                },
            }
        )
    return runs


def map_save_metadata(save: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "data_version": save.get("dataVersion"),
        "save_revision": save.get("saveRevision"),
        "field_count": len(save),
        "battle_history_count": len(list(save.get("battleHistory") or [])),
        "module_records_count": len(list(save.get("moduleRecords") or [])),
        "relic_slots_equipped": len(list(save.get("profileRelics") or [])),
        "labs_unlocked": _int(save.get("labsUnlocked")),
        "ultimate_weapons_unlocked": sum(1 for flag in list(save.get("ultimateWeaponUnlocked") or []) if _bool(flag)),
        "cards_bought_total": _int(save.get("cardsBoughtTotal")),
        "common_modules_obtained": _int(save.get("commonModulesObtained")),
    }


def build_extended_patch(base_patch: Mapping[str, Any], save: Mapping[str, Any]) -> Dict[str, Any]:
    patch = dict(base_patch)
    patch["modules"] = map_modules_with_substats(save, patch.get("modules") or {})
    patch["player"] = {**(patch.get("player") or {}), **map_player_extended(save)}
    patch["resources"] = {**(patch.get("resources") or {}), **map_resources_extended(save)}
    patch["cards"] = map_cards_extended(save, patch.get("cards") or {})
    patch["uw"] = map_uw_extended(save, patch.get("uw") or {})
    patch["bots"] = map_bots_extended(save)
    patch["themes"] = map_themes(save)
    patch["guardians"] = map_guardians(save)
    patch["vault"] = map_vault(save)
    presets = map_module_presets(save)
    if presets:
        patch["module_presets"] = presets
    patch["runs"] = map_battle_history(save)
    patch["save_import"] = {
        "metadata": map_save_metadata(save),
        "assist_modules": _serialize_assist_modules(save),
        "events": _serialize_events(save),
        "module_registry": map_module_registry(save),
        "raw_fields": summarize_raw_fields(save),
    }
    return patch


def _serialize_assist_modules(save: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = list(save.get("assistModuleSlots") or [])
    output = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        equipped = row.get("equippedModule")
        payload = {
            "slot_index": index,
            "unlocked": _bool(row.get("unlocked")),
            "type": _int(row.get("type")),
            "unique_effect_efficiency_level": _int(row.get("uniqueEffectEfficiencyLevel")),
            "main_effect_efficiency_level": _int(row.get("mainEffectEfficiencyLevel")),
            "substat_efficiency_level": _int(row.get("substatEfficiencyLevel")),
        }
        if isinstance(equipped, dict):
            info_index = _int(equipped.get("infoIndex"))
            entry = module_info_entry(info_index)
            payload["equipped"] = {
                "info_index": info_index,
                "name": entry.get("name") if entry else f"Module {info_index}",
                "slot": entry.get("slot") if entry else None,
                "rarity": module_rarity_label(_int(equipped.get("rarity"))),
                "level": _int(equipped.get("level")),
            }
        output.append(payload)
    return output


def _serialize_events(save: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = list(save.get("eventRecords") or [])
    output = []
    for row in rows[:50]:
        if not isinstance(row, dict):
            continue
        output.append(
            {
                "event_number": row.get("eventNumber"),
                "medals": row.get("medals"),
                "medals_spent": row.get("medalsSpent"),
                "date": save_datetime(row.get("date")),
            }
        )
    return output


def section_counts(patch: Mapping[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for key in PROFILE_SECTION_KEYS:
        value = patch.get(key)
        if key == "cards" and isinstance(value, dict):
            counts[key] = len(value.get("items") or {})
        elif key == "relics" and isinstance(value, dict):
            counts[key] = len((value.get("items") or {}))
        elif key == "themes" and isinstance(value, dict):
            counts[key] = len((value.get("items") or {}))
        elif key == "guardians" and isinstance(value, dict):
            counts[key] = sum(1 for name in value if not str(name).startswith("__"))
        elif key == "vault" and isinstance(value, dict):
            counts[key] = len((value.get("unlocks") or {}))
        elif key == "runs" and isinstance(value, list):
            counts[key] = len(value)
        elif isinstance(value, dict):
            counts[key] = len(value)
        elif isinstance(value, list):
            counts[key] = len(value)
    counts["save_import"] = len(patch.get("save_import") or {})
    meta = (patch.get("save_import") or {}).get("metadata") or {}
    if meta.get("field_count"):
        counts["raw_fields"] = int(meta["field_count"])
    return counts
