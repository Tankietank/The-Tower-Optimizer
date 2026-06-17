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
from .game_catalog import (
    load_relics_catalog,
    load_save_mappings,
    load_uw_save_tracks,
    merge_relic_item,
    module_info_entry,
    module_rarity_label,
    relic_entry,
    uw_track_value,
)
from .save_extract import build_extended_patch, section_counts as extended_section_counts

_PACKAGE_DIR = Path(__file__).resolve().parent
_GAME_DATA_DIR = _PACKAGE_DIR / "game_data"
_LABS_PATH = _GAME_DATA_DIR / "labs.json"

ENHANCEMENT_ATTACK = list(ENHANCEMENT_MAX_LEVELS.keys())[:6]
ENHANCEMENT_DEFENSE = list(ENHANCEMENT_MAX_LEVELS.keys())[6:12]
ENHANCEMENT_UTILITY = list(ENHANCEMENT_MAX_LEVELS.keys())[12:18]

RELIC_UNLOCKED = 1


def _load_mappings() -> Dict[str, Any]:
    return load_save_mappings()


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


def _normalize_uw_attribute(uw_name: str, attr_name: str, raw: Any, tracks: Mapping[str, Any]) -> Any:
    meta = UW_ATTRIBUTE_META.get(uw_name, {}).get(attr_name, {})
    converted = uw_track_value(uw_name, attr_name, raw, tracks)
    if converted is not None:
        if isinstance(meta.get("max"), int) and not isinstance(meta.get("max"), bool):
            return int(round(converted))
        return float(converted)
    try:
        numeric = float(raw)
    except (TypeError, ValueError):
        return raw
    if meta.get("display") == "percent" and numeric > 1.0 and numeric <= 100.0:
        return numeric / 100.0
    if isinstance(meta.get("max"), int) and not isinstance(meta.get("max"), bool):
        return int(round(numeric))
    return numeric


def _map_uws(save: Mapping[str, Any]) -> Dict[str, Any]:
    unlocked = list(save.get("ultimateWeaponUnlocked") or [])
    levels = list(save.get("ultimateWeaponLevel") or [])
    tracks = load_uw_save_tracks()
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
            attributes[attr_name] = _normalize_uw_attribute(uw_name, attr_name, raw, tracks)
        if owned or attributes:
            output[uw_name] = {"owned": owned, "attributes": attributes}
    return output


def _resolve_module(info_index: int, slot_hint: Optional[str], mappings: Mapping[str, Any]) -> Tuple[str, str]:
    entry = module_info_entry(info_index, mappings)
    if entry:
        return str(entry.get("slot") or slot_hint or "Unknown"), str(entry.get("name") or f"Module {info_index}")
    return slot_hint or "Unknown", f"Module {info_index}" if info_index else ""


def _map_modules(save: Mapping[str, Any], mappings: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    slots = list(mappings.get("module_slots") or [])
    equipped_rows = list(save.get("moduleEquipped") or [])
    modules: Dict[str, Any] = {}
    inventory: Dict[str, Any] = {}

    for slot_index, row in enumerate(equipped_rows):
        if not isinstance(row, dict):
            continue
        slot_hint = slots[slot_index] if slot_index < len(slots) else f"Slot {slot_index + 1}"
        info_index = int(row.get("infoIndex") or 0)
        slot, name = _resolve_module(info_index, slot_hint, mappings)
        rarity = module_rarity_label(int(row.get("currentRarity") or 0), mappings)
        level = int(round(float(row.get("level") or 0)))
        modules[slot] = {"name": name, "rarity": rarity, "level": level}

    counts: Dict[str, int] = {}
    for row in list(save.get("moduleRecords") or []):
        if not isinstance(row, dict):
            continue
        info_index = int(row.get("infoIndex") or 0)
        slot, name = _resolve_module(info_index, None, mappings)
        rarity = module_rarity_label(int(row.get("rarity") or 0), mappings)
        key = f"{slot}::{name}::{rarity}" if name else f"Index {info_index}::{rarity}"
        counts[key] = counts.get(key, 0) + 1
    for key, copies in sorted(counts.items()):
        parts = key.split("::")
        if len(parts) == 3:
            slot, name, rarity = parts
        else:
            slot, name, rarity = "Unknown", key.split("::", 1)[0], key.split("::")[-1]
        inventory[key] = {
            "slot": slot,
            "name": name,
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
    catalog = load_relics_catalog()
    owned_ids = [int(value) for value in list(save.get("profileRelics") or []) if value is not None]
    relics_unlocked = list(save.get("relicsUnlocked") or [])
    items: Dict[str, Any] = {}
    for relic_id, owned_flag in enumerate(relics_unlocked):
        try:
            owned = int(round(float(owned_flag))) >= RELIC_UNLOCKED
        except (TypeError, ValueError):
            owned = False
        if not owned and relic_id not in owned_ids:
            continue
        entry = relic_entry(relic_id, catalog)
        if entry:
            name = str(entry["name"])
            items[name] = {
                "owned": owned or relic_id in owned_ids,
                "equipped": relic_id in owned_ids,
                "rarity": entry.get("rarity", ""),
                "bonus_type": entry.get("bonus_type", ""),
                "value": entry.get("value", 0),
                "relic_id": entry.get("id"),
                "game_index": relic_id,
            }
        else:
            items[f"Relic {relic_id}"] = {
                "owned": owned or relic_id in owned_ids,
                "equipped": relic_id in owned_ids,
                "rarity": "",
                "bonus_type": "",
                "value": 0,
                "game_index": relic_id,
            }
    return {"items": items}


def build_profile_patch(save: Mapping[str, Any]) -> Dict[str, Any]:
    mappings = _load_mappings()
    lab_names = _load_lab_names()
    modules, module_inventory = _map_modules(save, mappings)
    cards = _map_cards(save)
    base = {
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
    return build_extended_patch(base, save)


def _quality_notes(patch: Mapping[str, Any]) -> List[str]:
    modules = patch.get("modules") or {}
    relic_items = (patch.get("relics") or {}).get("items") or {}
    named_modules = sum(1 for row in modules.values() if row.get("name") and not str(row.get("name", "")).startswith("Module "))
    meta = (patch.get("save_import") or {}).get("metadata") or {}
    return [
        "Ultimate weapon attributes are converted from save upgrade levels to profile values.",
        f"Modules resolved: {named_modules}/{len(modules)} equipped slots named.",
        f"Relics resolved: {len(relic_items)} entries with catalog names and bonuses.",
        f"Themes imported: {len((patch.get('themes') or {}).get('items') or {})} owned entries.",
        f"Guardians imported: {sum(1 for n in (patch.get('guardians') or {}) if not str(n).startswith('__'))} chip tracks.",
        f"Vault nodes imported: {len((patch.get('vault') or {}).get('unlocks') or {})} unlocks.",
        f"Battle history runs imported: {len(patch.get('runs') or [])} of {meta.get('battle_history_count', '?')} saved rounds.",
        f"Module registry rows captured: {len((patch.get('save_import') or {}).get('module_registry') or [])}.",
        f"Raw save field inventory: {len((patch.get('save_import') or {}).get('raw_fields') or [])} top-level fields summarized.",
        f"Save metadata: {meta.get('field_count', '?')} top-level fields decoded.",
    ]


def preview_player_save(payload: bytes, filename: str = "playerInfo.dat") -> Dict[str, Any]:
    save = decode_player_save_bytes(payload)
    patch = build_profile_patch(save)
    modules = patch.get("modules") or {}
    relic_items = (patch.get("relics") or {}).get("items") or {}
    sections = extended_section_counts(patch)
    return {
        "filename": filename,
        "sections": sections,
        "patch": patch,
        "notes": _quality_notes(patch),
        "highlights": {
            "modules": [
                {"slot": slot, **row}
                for slot, row in sorted(modules.items())
            ],
            "relics": sorted(
                [
                    {
                        "name": name,
                        "owned": bool(item.get("owned")),
                        "equipped": bool(item.get("equipped")),
                        "rarity": item.get("rarity"),
                        "bonus_type": item.get("bonus_type"),
                    }
                    for name, item in relic_items.items()
                    if item.get("owned")
                ],
                key=lambda row: row["name"],
            )[:12],
        },
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
            if "active" in payload:
                entry["active"] = bool(payload.get("active"))
            if payload.get("plus"):
                entry["plus"] = deepcopy(payload["plus"])
        counts["uw"] = len(uw)

    cards = patch.get("cards") or {}
    if cards:
        if replace:
            profile["cards"] = {"slots": 0, "slot_target": 1, "items": {}, "presets": {}}
        card_target = profile.setdefault("cards", {"items": {}, "presets": {}})
        if cards.get("slots"):
            card_target["slots"] = int(cards["slots"])
        card_target.setdefault("items", {}).update(deepcopy(cards.get("items") or {}))
        if cards.get("presets"):
            card_target.setdefault("presets", {}).update(deepcopy(cards.get("presets") or {}))
        if cards.get("active_preset") is not None:
            card_target["active_preset"] = int(cards["active_preset"])
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
        target_items = profile.setdefault("relics", {}).setdefault("items", {})
        for name, payload in relics["items"].items():
            existing = target_items.get(name) or {}
            target_items[name] = merge_relic_item(existing, payload)
        counts["relics"] = len(relics["items"])

    themes = patch.get("themes") or {}
    if themes.get("items") or themes.get("summary"):
        if replace:
            profile["themes"] = {"summary": {}, "items": {}}
        target = profile.setdefault("themes", {"summary": {}, "items": {}})
        target.setdefault("summary", {}).update(deepcopy(themes.get("summary") or {}))
        target.setdefault("items", {}).update(deepcopy(themes.get("items") or {}))
        if themes.get("selection"):
            target["selection"] = deepcopy(themes["selection"])
        counts["themes"] = len(themes.get("items") or {})

    guardians = patch.get("guardians") or {}
    if guardians:
        if replace:
            profile["guardians"] = {}
        for name, payload in guardians.items():
            if str(name).startswith("__"):
                profile.setdefault("save_import", {})["guardian_meta"] = deepcopy(payload)
                continue
            profile.setdefault("guardians", {})[name] = deepcopy(payload)
        counts["guardians"] = sum(1 for name in guardians if not str(name).startswith("__"))

    vault = patch.get("vault") or {}
    if vault:
        if replace:
            profile["vault"] = {"keys_spent": 0, "bonuses": {}, "unlocks": {}}
        target = profile.setdefault("vault", {"keys_spent": 0, "bonuses": {}, "unlocks": {}})
        if vault.get("keys_spent") is not None:
            target["keys_spent"] = int(vault.get("keys_spent") or 0)
        target.setdefault("bonuses", {}).update(deepcopy(vault.get("bonuses") or {}))
        target.setdefault("unlocks", {}).update(deepcopy(vault.get("unlocks") or {}))
        counts["vault"] = len(vault.get("unlocks") or {})

    module_presets = patch.get("module_presets") or {}
    if module_presets:
        if replace:
            profile["module_presets"] = {}
        profile.setdefault("module_presets", {}).update(deepcopy(module_presets))
        counts["module_presets"] = len(module_presets)

    runs = patch.get("runs") or []
    if runs:
        from .battle_learning import import_runs

        if replace:
            profile["runs"] = []
        result = import_runs(profile, runs, allow_duplicates=False, batch_label=source_name)
        counts["runs"] = len(result.get("added") or [])

    save_import = patch.get("save_import") or {}
    if save_import:
        profile.setdefault("save_import", {}).update(deepcopy(save_import))
        counts["save_import"] = len(save_import)

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
