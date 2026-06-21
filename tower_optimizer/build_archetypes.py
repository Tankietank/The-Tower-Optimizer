"""Personalized optimal-build reports for common playstyle archetypes."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from .build_beast_mode import enrich_blueprint_beast_mode
from .engines.combined import build_combined_recommendations
from .engines.core import LAB_MAX_LEVELS, WORKSHOP_MAX_LEVELS, build_analysis, ratio
from .engines.whole_account import CARD_DOMAIN, RARITY_RANK


ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "economy_farmer": {
        "label": "Economy Farmer",
        "tagline": "Push coins/hour, GT/BH income, and farming presets.",
        "focus": "Economy",
        "domain_weights": {
            "Economy": 0.52,
            "Damage": 0.22,
            "Survivability": 0.16,
            "Regen / Recovery": 0.10,
        },
        "priority_cards": ["Enemy Balance", "Coins", "Critical Coin", "Wave Skip", "Wave Accelerator", "Cash"],
        "priority_workshop": ["Coin / Kill Bonus", "Cash Bonus", "Cash / Wave", "Damage", "Attack Speed"],
        "priority_labs": [
            "Coins / Kill Bonus", "Golden Tower Bonus", "Black Hole Coin Bonus",
            "Golden Tower Duration", "Death Wave Coin Bonus", "Labs Speed",
        ],
        "priority_systems": ["Cards", "Laboratory", "Workshop / Enhancements", "Ultimate Weapons", "Modules"],
        "module_focus": {"Generator": "coin or economy modules", "Cannon": "wave clear damage"},
        "module_preferences": {
            "Generator": ["Black Hole Digestor", "Pulsar Harvester", "Project Funding", "Galaxy Compressor"],
            "Cannon": ["Havoc Bringer", "Astral Deliverance", "Death Penalty"],
            "Core": ["Harmony Conductor", "Multiverse Nexus", "Dimension Core"],
            "Armor": ["Wormhole Redirector", "Anti-Cube Portal", "Sharp Fortitude"],
        },
        "substat_keywords": ["coin", "cash", "golden tower", "black hole", "wave skip", "enemy balance"],
        "card_loadout": {
            "core": ["Enemy Balance", "Coins", "Critical Coin", "Wave Skip", "Wave Accelerator", "Cash"],
            "support": ["Attack Speed", "Damage", "Free Upgrades", "Plasma Cannon"],
            "flex": ["Super Tower", "Berserker"],
        },
        "avoid_cards": ["Fortress", "Energy Shield"],
        "uw_priorities": ["Golden Tower Bonus", "Golden Tower Duration", "Black Hole Coin Bonus", "Death Wave Coin Bonus"],
        "enhancement_priorities": ["Coin Bonus +", "Damage +", "Health +"],
    },
    "glass_cannon": {
        "label": "Glass Cannon",
        "tagline": "Trade survivability for kill speed, crits, and burst damage.",
        "focus": "Damage",
        "domain_weights": {
            "Damage": 0.58,
            "Economy": 0.18,
            "Survivability": 0.12,
            "Regen / Recovery": 0.12,
        },
        "priority_cards": ["Damage", "Attack Speed", "Berserker", "Plasma Cannon", "Critical Chance", "Ultimate Crit"],
        "priority_workshop": ["Damage", "Attack Speed", "Critical Factor", "Critical Chance", "Damage / Meter"],
        "priority_labs": ["Damage", "Attack Speed", "Critical Factor", "Shock Multiplier", "Black Hole Damage"],
        "priority_systems": ["Laboratory", "Workshop / Enhancements", "Cards", "Ultimate Weapons", "Modules"],
        "module_focus": {"Cannon": "primary damage", "Core": "crit or multishot effects", "Armor": "minimal — don't over-invest"},
        "module_preferences": {
            "Cannon": ["Death Penalty", "Havoc Bringer", "Astral Deliverance", "Amplifying Strike"],
            "Core": ["Multiverse Nexus", "Primordial Collapse", "Harmony Conductor", "Dimension Core"],
            "Armor": ["Anti-Cube Portal", "Sharp Fortitude", "Wormhole Redirector"],
            "Generator": ["Pulsar Harvester", "Singularity Harness", "Black Hole Digestor"],
        },
        "substat_keywords": ["damage", "attack speed", "crit", "critical", "multishot", "super crit", "berserk"],
        "card_loadout": {
            "core": ["Damage", "Attack Speed", "Berserker", "Plasma Cannon", "Critical Chance", "Ultimate Crit"],
            "support": ["Super Tower", "Death Ray", "Area of Effect", "Nuke", "Demon Mode"],
            "flex": ["Free Upgrades", "Wave Skip", "Coins"],
        },
        "avoid_cards": ["Health", "Fortress", "Extra Defense", "Health Regen", "Recovery Package Chance", "Energy Shield", "Second Wind"],
        "uw_priorities": ["Damage", "Attack Speed", "Critical Factor", "Black Hole Damage", "Shock Multiplier"],
        "enhancement_priorities": ["Damage +", "Attack Speed +", "Critical Factor +"],
    },
    "ehp_tank": {
        "label": "eHP Tank",
        "tagline": "Survive burst hits with health, defense, packages, and wall scaling.",
        "focus": "Survival",
        "domain_weights": {
            "Survivability": 0.50,
            "Regen / Recovery": 0.25,
            "Damage": 0.15,
            "Economy": 0.10,
        },
        "priority_cards": ["Health", "Extra Defense", "Fortress", "Energy Shield", "Second Wind"],
        "priority_workshop": ["Health", "Defense %", "Recovery Amount", "Max Amount", "Package Chance", "Thorn Damage"],
        "priority_labs": ["Health", "Defense %", "Recovery Package Chance", "Recovery Package Amount", "Recovery Package Max"],
        "priority_systems": ["Laboratory", "Workshop / Enhancements", "Cards", "Modules"],
        "module_focus": {"Armor": "health or defense substats", "Core": "sustain if needed"},
        "module_preferences": {
            "Armor": ["Wormhole Redirector", "Space Displacer", "Negative Mass Projector", "Sharp Fortitude"],
            "Core": ["Harmony Conductor", "Dimension Core", "Om Chip"],
            "Cannon": ["Astral Deliverance", "Shrink Ray"],
            "Generator": ["Restorative Bonus", "Project Funding", "Singularity Harness"],
        },
        "substat_keywords": ["health", "defense", "damage reduction", "recovery", "package", "shield"],
        "card_loadout": {
            "core": ["Health", "Extra Defense", "Fortress", "Energy Shield", "Second Wind", "Damage"],
            "support": ["Attack Speed", "Recovery Package Chance", "Health Regen", "Plasma Cannon"],
            "flex": ["Enemy Balance", "Free Upgrades"],
        },
        "avoid_cards": ["Berserker", "Demon Mode", "Nuke"],
        "uw_priorities": ["Health", "Defense %", "Recovery Package Chance", "Recovery Package Amount", "Recovery Package Max"],
        "enhancement_priorities": ["Health +", "Recovery Package +", "Defense Absolute +"],
    },
    "recovery_sustain": {
        "label": "Recovery / Sustain",
        "tagline": "Outlast vampires and chip damage with regen and packages.",
        "focus": "Recovery",
        "domain_weights": {
            "Regen / Recovery": 0.48,
            "Survivability": 0.28,
            "Damage": 0.14,
            "Economy": 0.10,
        },
        "priority_cards": ["Health Regen", "Recovery Package Chance", "Second Wind", "Health", "Extra Defense"],
        "priority_workshop": ["Health Regen", "Recovery Amount", "Package Chance", "Max Amount", "Lifesteal"],
        "priority_labs": [
            "Health Regen", "Recovery Package Chance", "Recovery Package Amount",
            "Recovery Package Max", "Wall Regen", "Garlic Thorns",
        ],
        "priority_systems": ["Laboratory", "Workshop / Enhancements", "Cards", "Guardians"],
        "module_focus": {"Armor": "regen or package effects", "Generator": "secondary"},
        "module_preferences": {
            "Armor": ["Wormhole Redirector", "Sharp Fortitude", "Space Displacer", "Negative Mass Projector"],
            "Core": ["Harmony Conductor", "Om Chip", "Dimension Core"],
            "Generator": ["Restorative Bonus", "Project Funding", "Singularity Harness"],
            "Cannon": ["Shrink Ray", "Astral Deliverance"],
        },
        "substat_keywords": ["health regen", "recovery", "package", "lifesteal", "regen", "thorn"],
        "card_loadout": {
            "core": ["Health Regen", "Recovery Package Chance", "Second Wind", "Health", "Extra Defense", "Attack Speed"],
            "support": ["Fortress", "Energy Shield", "Damage", "Plasma Cannon"],
            "flex": ["Enemy Balance", "Free Upgrades"],
        },
        "avoid_cards": ["Berserker", "Demon Mode", "Nuke", "Ultimate Crit"],
        "uw_priorities": ["Health Regen", "Recovery Package Chance", "Recovery Package Amount", "Garlic Thorns", "Wall Regen"],
        "enhancement_priorities": ["Health Regen +", "Recovery Package +", "Health +"],
    },
    "balanced": {
        "label": "Balanced Progression",
        "tagline": "Keep all four development areas moving without over-specializing.",
        "focus": "Balanced",
        "domain_weights": {
            "Economy": 0.25,
            "Damage": 0.25,
            "Survivability": 0.25,
            "Regen / Recovery": 0.25,
        },
        "priority_cards": ["Enemy Balance", "Damage", "Health", "Coins", "Attack Speed"],
        "priority_workshop": ["Damage", "Health", "Coin / Kill Bonus", "Attack Speed", "Defense %"],
        "priority_labs": ["Damage", "Health", "Coins / Kill Bonus", "Attack Speed", "Health Regen"],
        "priority_systems": ["Laboratory", "Cards", "Workshop / Enhancements", "Ultimate Weapons", "Modules"],
        "module_focus": {"Cannon": "damage", "Armor": "survivability", "Generator": "economy", "Core": "utility"},
        "module_preferences": {
            "Cannon": ["Astral Deliverance", "Havoc Bringer", "Death Penalty"],
            "Armor": ["Wormhole Redirector", "Anti-Cube Portal", "Sharp Fortitude"],
            "Generator": ["Black Hole Digestor", "Pulsar Harvester", "Project Funding"],
            "Core": ["Multiverse Nexus", "Harmony Conductor", "Dimension Core"],
        },
        "substat_keywords": ["damage", "health", "coin", "attack speed", "defense"],
        "card_loadout": {
            "core": ["Enemy Balance", "Damage", "Health", "Coins", "Attack Speed", "Extra Defense"],
            "support": ["Wave Skip", "Plasma Cannon", "Recovery Package Chance", "Critical Coin"],
            "flex": ["Free Upgrades", "Super Tower", "Berserker"],
        },
        "avoid_cards": [],
        "uw_priorities": ["Damage", "Health", "Coins / Kill Bonus", "Golden Tower Bonus", "Black Hole Coin Bonus"],
        "enhancement_priorities": ["Damage +", "Health +", "Coin Bonus +"],
    },
}


ARCHETYPE_IDS = tuple(ARCHETYPES.keys())

PRESET_CONTEXT_IDS = ("farming", "pushing", "tournament")

PRESET_CONTEXTS: Dict[str, Dict[str, str]] = {
    "farming": {
        "label": "Farming preset",
        "summary": "Daily farming — enough clear speed without sacrificing your build's main goal.",
    },
    "pushing": {
        "label": "Pushing preset",
        "summary": "Tier and wave pushes — lean into the build's core power spikes.",
    },
    "tournament": {
        "label": "Tournament preset",
        "summary": "Tournament runs — burst damage and targeted survival, minimal economy cards.",
    },
}

DEFAULT_CARD_PRESET_KEYS: Dict[str, List[str]] = {
    "farming": ["Farming", "Preset 1"],
    "pushing": ["Pushing", "Preset 2"],
    "tournament": ["Tourney", "Preset 2", "Pushing"],
}

DEFAULT_MODULE_PRESET_KEYS: Dict[str, List[str]] = {
    "farming": ["Farming", "Preset 1"],
    "pushing": ["Pushing", "Preset 2"],
    "tournament": ["Tourney", "Preset 2"],
}

TOURNAMENT_DROP_CARDS = {
    "Coins", "Wave Skip", "Cash", "Wave Accelerator", "Enemy Balance", "Critical Coin",
}

SUBSTAT_TARGETS: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "economy_farmer": {
        "Generator": [
            {"label": "Golden Tower bonus", "keywords": ["golden tower", "gt"], "min_rarity": "Epic"},
            {"label": "Black Hole bonus", "keywords": ["black hole", "bh"], "min_rarity": "Epic"},
            {"label": "Cash / coin effect", "keywords": ["coin", "cash"], "min_rarity": "Rare"},
        ],
        "Cannon": [
            {"label": "Attack Speed", "keywords": ["speed", "attack-speed"], "min_rarity": "Rare"},
        ],
        "Core": [
            {"label": "Wave skip / economy utility", "keywords": ["wave", "coin", "cash"], "min_rarity": "Rare"},
        ],
    },
    "glass_cannon": {
        "Cannon": [
            {"label": "Attack Speed", "keywords": ["speed", "attack-speed"], "min_rarity": "Epic"},
            {"label": "Critical Chance", "keywords": ["chance", "crit-chance"], "min_rarity": "Rare"},
            {"label": "Critical Factor", "keywords": ["factor", "crit-factor"], "min_rarity": "Rare"},
        ],
        "Core": [
            {"label": "Super Crit / burst", "keywords": ["super crit", "super-crit", "multishot"], "min_rarity": "Epic"},
            {"label": "Damage / meter", "keywords": ["damage", "damage-meter"], "min_rarity": "Rare"},
        ],
        "Armor": [
            {"label": "Minimal defense", "keywords": ["defense", "health", "damage reduction"], "min_rarity": "Rare"},
        ],
    },
    "ehp_tank": {
        "Armor": [
            {"label": "Health", "keywords": ["health", "hp"], "min_rarity": "Epic"},
            {"label": "Defense %", "keywords": ["defense", "damage reduction"], "min_rarity": "Epic"},
            {"label": "Recovery / package", "keywords": ["recovery", "package"], "min_rarity": "Rare"},
        ],
        "Core": [
            {"label": "Health / shield", "keywords": ["health", "shield"], "min_rarity": "Rare"},
        ],
    },
    "recovery_sustain": {
        "Armor": [
            {"label": "Health Regen", "keywords": ["regen", "health regen"], "min_rarity": "Epic"},
            {"label": "Recovery Package", "keywords": ["recovery", "package"], "min_rarity": "Epic"},
        ],
        "Generator": [
            {"label": "Secondary sustain", "keywords": ["health", "regen", "recovery"], "min_rarity": "Rare"},
        ],
    },
    "balanced": {
        "Cannon": [
            {"label": "Attack Speed", "keywords": ["speed", "attack-speed"], "min_rarity": "Rare"},
            {"label": "Critical Factor", "keywords": ["factor", "crit-factor"], "min_rarity": "Rare"},
        ],
        "Armor": [
            {"label": "Health / defense", "keywords": ["health", "defense"], "min_rarity": "Rare"},
        ],
        "Generator": [
            {"label": "Economy effect", "keywords": ["coin", "cash", "golden tower"], "min_rarity": "Rare"},
        ],
    },
}

PLAYSTYLE_PRESETS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "economy_farmer": {
        "farming": {
            "note": "Full economy stack for coins/hour.",
            "card_loadout": {
                "core": ["Enemy Balance", "Coins", "Critical Coin", "Wave Skip", "Wave Accelerator", "Cash"],
                "support": ["Attack Speed", "Damage", "Plasma Cannon", "Free Upgrades"],
                "flex": ["Super Tower", "Health"],
            },
        },
        "tournament": {
            "note": "Tournament variant — keep damage online, trim pure farming cards.",
            "card_loadout": {
                "core": ["Damage", "Attack Speed", "Plasma Cannon", "Health", "Critical Chance", "Berserker"],
                "support": ["Super Tower", "Ultimate Crit", "Extra Defense"],
                "flex": ["Free Upgrades", "Second Wind"],
            },
        },
    },
    "glass_cannon": {
        "farming": {
            "note": "Farm fast enough while running a damage-first account.",
            "card_loadout": {
                "core": ["Damage", "Attack Speed", "Coins", "Wave Skip", "Critical Chance", "Plasma Cannon"],
                "support": ["Berserker", "Ultimate Crit", "Enemy Balance", "Super Tower"],
                "flex": ["Free Upgrades", "Nuke"],
            },
        },
        "tournament": {
            "note": "Pure burst — drop economy cards and stack damage.",
            "card_loadout": {
                "core": ["Damage", "Attack Speed", "Berserker", "Plasma Cannon", "Ultimate Crit", "Critical Chance"],
                "support": ["Super Tower", "Death Ray", "Area of Effect", "Demon Mode"],
                "flex": ["Nuke", "Free Upgrades"],
            },
        },
    },
    "ehp_tank": {
        "farming": {
            "note": "Safer farming with sustain online.",
            "card_loadout": {
                "core": ["Health", "Extra Defense", "Enemy Balance", "Coins", "Attack Speed", "Recovery Package Chance"],
                "support": ["Fortress", "Energy Shield", "Damage", "Wave Skip"],
                "flex": ["Free Upgrades", "Plasma Cannon"],
            },
        },
        "tournament": {
            "note": "Tournament survivability — packages and burst defense first.",
            "card_loadout": {
                "core": ["Health", "Extra Defense", "Fortress", "Energy Shield", "Second Wind", "Damage"],
                "support": ["Attack Speed", "Recovery Package Chance", "Plasma Cannon", "Ultimate Crit"],
                "flex": ["Berserker", "Free Upgrades"],
            },
        },
    },
    "recovery_sustain": {
        "farming": {
            "note": "Outlast chip damage while farming.",
            "card_loadout": {
                "core": ["Health Regen", "Recovery Package Chance", "Health", "Enemy Balance", "Attack Speed", "Coins"],
                "support": ["Second Wind", "Extra Defense", "Damage", "Wave Skip"],
                "flex": ["Free Upgrades", "Plasma Cannon"],
            },
        },
        "tournament": {
            "note": "Tournament sustain — packages and regen over economy.",
            "card_loadout": {
                "core": ["Health Regen", "Recovery Package Chance", "Second Wind", "Health", "Extra Defense", "Damage"],
                "support": ["Attack Speed", "Fortress", "Plasma Cannon", "Energy Shield"],
                "flex": ["Ultimate Crit", "Free Upgrades"],
            },
        },
    },
    "balanced": {
        "tournament": {
            "note": "Flexible tournament preset without heavy economy.",
            "card_loadout": {
                "core": ["Damage", "Attack Speed", "Health", "Extra Defense", "Plasma Cannon", "Critical Chance"],
                "support": ["Berserker", "Recovery Package Chance", "Super Tower", "Ultimate Crit"],
                "flex": ["Free Upgrades", "Second Wind"],
            },
        },
    },
}

ENHANCEMENT_CAPS: Dict[str, int] = {
    "Damage +": 400,
    "Attack Speed +": 75,
    "Critical Factor +": 400,
    "Health +": 400,
    "Health Regen +": 400,
    "Recovery Package +": 300,
    "Defense Absolute +": 400,
    "Coin Bonus +": 200,
    "Cash Bonus +": 400,
}


def _clean_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _section_progress(profile: Mapping[str, Any], section: str, names: Sequence[str]) -> float:
    bucket = profile.get(section, {}) if isinstance(profile.get(section), Mapping) else {}
    caps = WORKSHOP_MAX_LEVELS if section == "workshop" else LAB_MAX_LEVELS
    ratios: List[float] = []
    for name in names:
        maximum = caps.get(name)
        if not maximum:
            continue
        ratios.append(ratio(bucket.get(name), maximum))
    return sum(ratios) / len(ratios) if ratios else 0.0


def _card_progress(profile: Mapping[str, Any], names: Sequence[str]) -> float:
    items = profile.get("cards", {}).get("items", {}) if isinstance(profile.get("cards"), Mapping) else {}
    if not isinstance(items, Mapping):
        return 0.0
    levels: List[float] = []
    for name in names:
        record = items.get(name)
        if not isinstance(record, Mapping):
            continue
        levels.append(min(1.0, _clean_number(record.get("level")) / 7.0))
    return sum(levels) / len(levels) if levels else 0.0


def _domain_fit(scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total = 0.0
    weight_sum = 0.0
    for domain, weight in weights.items():
        total += float(scores.get(domain, 0.0)) * float(weight)
        weight_sum += float(weight)
    return total / weight_sum if weight_sum else 0.0


def _card_record(profile: Mapping[str, Any], name: str) -> Optional[Mapping[str, Any]]:
    items = profile.get("cards", {}).get("items", {}) if isinstance(profile.get("cards"), Mapping) else {}
    record = items.get(name) if isinstance(items, Mapping) else None
    return record if isinstance(record, Mapping) else None


def _card_level(profile: Mapping[str, Any], name: str) -> int:
    record = _card_record(profile, name)
    return int(_clean_number(record.get("level"))) if record else 0


def _ideal_card_order(
    archetype: Mapping[str, Any],
    *,
    context_id: str = "pushing",
    loadout_override: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    avoid = set(archetype.get("avoid_cards", []))
    loadout = loadout_override
    if loadout is None:
        playstyle = PLAYSTYLE_PRESETS.get(str(archetype.get("_id", "")), {})
        context_cfg = playstyle.get(context_id, {}) if isinstance(playstyle, Mapping) else {}
        loadout = context_cfg.get("card_loadout")
    if loadout is None:
        loadout = archetype.get("card_loadout", {})
    ordered: List[str] = []
    for bucket in ("core", "support", "flex"):
        for card in loadout.get(bucket, []) if isinstance(loadout, Mapping) and isinstance(loadout.get(bucket), list) else []:
            if card not in ordered and card not in avoid:
                ordered.append(str(card))
    if context_id == "tournament":
        ordered = [card for card in ordered if card not in TOURNAMENT_DROP_CARDS]
    for card in archetype.get("priority_cards", []):
        if card not in ordered and card not in avoid and card not in TOURNAMENT_DROP_CARDS:
            ordered.append(str(card))
    if context_id == "farming" and str(archetype.get("focus")) != "Economy":
        prefer = [card for card in ordered if card in {"Coins", "Enemy Balance", "Wave Skip", "Critical Coin", "Cash"}]
        rest = [card for card in ordered if card not in prefer]
        ordered = prefer + rest
    return ordered


def _resolve_card_preset(profile: Mapping[str, Any], preset_keys: Sequence[str]) -> tuple[List[str], str]:
    presets = profile.get("cards", {}).get("presets", {}) if isinstance(profile.get("cards"), Mapping) else {}
    if not isinstance(presets, Mapping):
        return [], "None"
    for key in preset_keys:
        value = presets.get(key)
        if isinstance(value, list) and value:
            return [str(item) for item in value], str(key)
    for value in presets.values():
        if isinstance(value, list) and value:
            return [str(item) for item in value], "Imported preset"
    return [], "None"


def _current_card_preset(profile: Mapping[str, Any], context_id: str = "farming") -> List[str]:
    cards, _ = _resolve_card_preset(profile, DEFAULT_CARD_PRESET_KEYS.get(context_id, ["Farming", "Preset 1"]))
    return cards


def _inventory_modules(profile: Mapping[str, Any], slot: str) -> List[Mapping[str, Any]]:
    inventory = profile.get("module_inventory", {}) if isinstance(profile.get("module_inventory"), Mapping) else {}
    rows: List[Mapping[str, Any]] = []
    if not isinstance(inventory, Mapping):
        return rows
    for key, record in inventory.items():
        if not isinstance(record, Mapping):
            continue
        if str(record.get("slot") or key.split("::", 1)[0]) != slot:
            continue
        rows.append({**record, "inventory_key": key})
    return rows


def _equipped_module_name(profile: Mapping[str, Any], slot: str, preset_keys: Optional[Sequence[str]] = None) -> str:
    keys = list(preset_keys or DEFAULT_MODULE_PRESET_KEYS["farming"])
    presets = profile.get("module_presets", {}) if isinstance(profile.get("module_presets"), Mapping) else {}
    for preset in keys:
        preset_data = presets.get(preset, {}) if isinstance(presets.get(preset, {}), Mapping) else {}
        slot_data = preset_data.get(slot, {}) if isinstance(preset_data.get(slot, {}), Mapping) else {}
        name = str(slot_data.get("primary") or "").strip()
        if name and name != "Any Other":
            return name
    modules = profile.get("modules", {}) if isinstance(profile.get("modules"), Mapping) else {}
    fallback = modules.get(slot, {}) if isinstance(modules.get(slot, {}), Mapping) else {}
    return str(fallback.get("name") or "").strip()


def _module_inventory_record(profile: Mapping[str, Any], slot: str, module_name: str) -> Mapping[str, Any]:
    if not module_name:
        return {}
    inventory = profile.get("module_inventory", {}) if isinstance(profile.get("module_inventory"), Mapping) else {}
    if not isinstance(inventory, Mapping):
        return {}
    record = inventory.get(f"{slot}::{module_name}")
    return record if isinstance(record, Mapping) else {}


def _normalize_rarity(value: Any) -> str:
    text = str(value or "None").strip()
    if not text:
        return "None"
    lowered = text.casefold()
    if lowered in RARITY_RANK:
        return text if text in RARITY_RANK else lowered.title()
    replacements = {
        "common": "Common", "rare": "Rare", "rare+": "Rare+", "epic": "Epic", "epic+": "Epic+",
        "legendary": "Legendary", "legendary+": "Legendary+", "mythic": "Mythic", "mythic+": "Mythic+",
        "ancestral": "Ancestral",
    }
    return replacements.get(lowered, text)


def _rarity_rank(value: Any) -> int:
    return int(RARITY_RANK.get(_normalize_rarity(value), 0))


def _substat_label(sub: Mapping[str, Any]) -> str:
    return str(sub.get("display") or sub.get("name") or sub.get("effect_id") or "Unnamed").strip()


def _substat_matches_target(sub: Mapping[str, Any], target: Mapping[str, Any]) -> bool:
    label = _substat_label(sub).casefold()
    effect_id = str(sub.get("effect_id") or "").casefold()
    for keyword in target.get("keywords", []):
        token = str(keyword).casefold()
        if token and (token in label or token in effect_id):
            return True
    return False


def _evaluate_substat_targets(
    profile: Mapping[str, Any],
    archetype_id: str,
    module_name: str,
    slot: str,
) -> List[Dict[str, Any]]:
    targets = SUBSTAT_TARGETS.get(archetype_id, {}).get(slot, [])
    record = _module_inventory_record(profile, slot, module_name)
    substats = record.get("substats", []) if isinstance(record.get("substats"), list) else []
    rows: List[Dict[str, Any]] = []
    for target in targets:
        min_rank = _rarity_rank(target.get("min_rarity", "Rare"))
        best_match: Optional[Mapping[str, Any]] = None
        for sub in substats:
            if isinstance(sub, Mapping) and _substat_matches_target(sub, target):
                if best_match is None or _rarity_rank(sub.get("rarity")) > _rarity_rank(best_match.get("rarity")):
                    best_match = sub
        if best_match is None:
            rows.append({
                "Slot": slot,
                "Module": module_name or "—",
                "Target": target.get("label"),
                "Current": "Missing",
                "Goal": f"{target.get('min_rarity')}+",
                "Status": "Reroll target",
                "Advice": f"Reroll {slot.lower()} until you hit {target.get('label')} at {target.get('min_rarity')} or better.",
            })
            continue
        current_rank = _rarity_rank(best_match.get("rarity"))
        current_label = _substat_label(best_match)
        current_rarity = _normalize_rarity(best_match.get("rarity"))
        if current_rank >= min_rank:
            status = "Met"
            advice = "Keep this sub-effect locked."
        else:
            status = "Below target"
            advice = f"Reroll until {target.get('label')} is {target.get('min_rarity')}+ (currently {current_rarity})."
        rows.append({
            "Slot": slot,
            "Module": module_name or "—",
            "Target": target.get("label"),
            "Current": f"{current_label} ({current_rarity})",
            "Goal": f"{target.get('min_rarity')}+",
            "Status": status,
            "Advice": advice,
        })
    return rows


def _score_module(record: Mapping[str, Any], archetype: Mapping[str, Any], slot: str) -> float:
    score = 0.0
    name = str(record.get("name") or "")
    prefs = archetype.get("module_preferences", {}).get(slot, []) if isinstance(archetype.get("module_preferences"), Mapping) else []
    if name in prefs:
        score += 120.0 - prefs.index(name) * 12.0
    rarity = str(record.get("rarity") or "None")
    score += float(RARITY_RANK.get(rarity, 0)) * 6.0
    score += _clean_number(record.get("stat")) * 0.35
    score += _clean_number(record.get("level")) * 0.05
    keywords = [str(item).casefold() for item in archetype.get("substat_keywords", [])]
    for sub in record.get("substats", []) if isinstance(record.get("substats"), list) else []:
        if not isinstance(sub, Mapping):
            continue
        label = str(sub.get("name") or sub.get("display") or "").casefold()
        if any(keyword in label for keyword in keywords):
            score += 12.0
        score += float(RARITY_RANK.get(str(sub.get("rarity") or "None"), 0)) * 0.8
    return score


def _pick_module(
    profile: Mapping[str, Any],
    archetype: Mapping[str, Any],
    slot: str,
    *,
    module_preset_keys: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    inventory = _inventory_modules(profile, slot)
    prefs = archetype.get("module_preferences", {}).get(slot, []) if isinstance(archetype.get("module_preferences"), Mapping) else []
    preset_keys = list(module_preset_keys or DEFAULT_MODULE_PRESET_KEYS["farming"])
    equipped = _equipped_module_name(profile, slot, preset_keys)
    if inventory:
        best = max(inventory, key=lambda item: _score_module(item, archetype, slot))
        best_name = str(best.get("name") or "")
        status = "Equipped" if best_name == equipped else "Swap recommended"
        reason = "Best match in your imported inventory for this build."
        if best_name in prefs:
            reason = f"Preferred {slot.lower()} module for this build."
        if equipped and best_name != equipped:
            reason = f"Your {preset_keys[0]} preset uses {equipped}, but {best_name} fits this build better."
        return {
            "slot": slot,
            "recommended": best_name,
            "equipped": equipped or "Not set",
            "rarity": str(best.get("rarity") or "Unknown"),
            "level": int(_clean_number(best.get("level"))),
            "status": status,
            "reason": reason,
            "preset": preset_keys[0],
        }
    target = str(prefs[0]) if prefs else "Set a named module"
    return {
        "slot": slot,
        "recommended": target,
        "equipped": equipped or "Not set",
        "rarity": "Unknown",
        "level": 0,
        "status": "Import inventory" if not equipped else "Review manually",
        "reason": "No imported inventory row for this slot — target module is a build template.",
        "preset": preset_keys[0],
    }


def _build_card_blueprint(
    profile: Mapping[str, Any],
    archetype: Mapping[str, Any],
    *,
    context_id: str,
) -> Dict[str, Any]:
    slots = int(_clean_number(profile.get("cards", {}).get("slots"))) or 10
    preset_keys = DEFAULT_CARD_PRESET_KEYS.get(context_id, ["Farming", "Preset 1"])
    ideal_cards = _ideal_card_order(archetype, context_id=context_id)[:slots]
    current_preset, preset_name = _resolve_card_preset(profile, preset_keys)
    avoid = set(archetype.get("avoid_cards", []))

    card_rows: List[Dict[str, Any]] = []
    missing_cards: List[str] = []
    for index, card in enumerate(ideal_cards, start=1):
        level = _card_level(profile, card)
        if level <= 0:
            missing_cards.append(card)
            status = "Missing — pull when able"
        elif level < 5:
            status = "Owned — level up soon"
        elif level < 7:
            status = "Owned — finish leveling"
        else:
            status = "Ready"
        card_rows.append({
            "Slot": index,
            "Equip": card,
            "Your level": f"{level}/7" if level else "—",
            "Status": status,
            "Domain": CARD_DOMAIN.get(card, "Utility"),
        })

    swap_out = [card for card in current_preset if card in avoid]
    overlap = len(set(ideal_cards) & set(current_preset))
    playstyle = PLAYSTYLE_PRESETS.get(str(archetype.get("_id", "")), {})
    note = (playstyle.get(context_id, {}) or {}).get("note") if isinstance(playstyle, Mapping) else None
    if not note:
        note = PRESET_CONTEXTS.get(context_id, {}).get("summary", "")

    return {
        "context": context_id,
        "label": PRESET_CONTEXTS.get(context_id, {}).get("label", context_id.title()),
        "note": note,
        "preset_name": preset_name,
        "slot_count": slots,
        "recommended": ideal_cards,
        "rows": card_rows,
        "missing": missing_cards,
        "avoid": sorted(avoid),
        "swap_out": swap_out,
        "current_preset": current_preset,
        "preset_overlap": overlap,
        "summary": (
            f"Equip {len(ideal_cards)} cards for {PRESET_CONTEXTS.get(context_id, {}).get('label', context_id)}. "
            f"{len(missing_cards)} priority cards are not in your profile yet."
        ),
    }


def _build_context_blueprint(
    profile: Mapping[str, Any],
    archetype: Mapping[str, Any],
    *,
    context_id: str,
) -> Dict[str, Any]:
    module_preset_keys = DEFAULT_MODULE_PRESET_KEYS.get(context_id, ["Farming", "Preset 1"])
    module_rows = [
        _pick_module(profile, archetype, slot, module_preset_keys=module_preset_keys)
        for slot in ["Cannon", "Armor", "Generator", "Core"]
    ]
    return {
        "cards": _build_card_blueprint(profile, archetype, context_id=context_id),
        "modules": {
            "preset": module_preset_keys[0],
            "rows": module_rows,
            "summary": f"Primary modules for your {module_preset_keys[0]} workshop preset.",
        },
    }


def _research_status(current: float, maximum: int) -> str:
    if maximum <= 0:
        return "Unknown cap"
    ratio_value = current / float(maximum)
    if ratio_value >= 0.85:
        return "Strong"
    if ratio_value >= 0.45:
        return "In progress"
    if current > 0:
        return "Started"
    return "Not started"


def _research_rows(profile: Mapping[str, Any], section: str, names: Sequence[str]) -> List[Dict[str, Any]]:
    bucket = profile.get(section, {}) if isinstance(profile.get(section), Mapping) else {}
    if section == "workshop":
        caps = WORKSHOP_MAX_LEVELS
    elif section == "labs":
        caps = LAB_MAX_LEVELS
    elif section == "enhancements":
        caps = ENHANCEMENT_CAPS
    else:
        caps = {}
    rows: List[Dict[str, Any]] = []
    for index, name in enumerate(names, start=1):
        lookup = str(name)
        maximum = int(caps.get(lookup, 0) or 0)
        current = _clean_number(bucket.get(lookup, bucket.get(lookup.replace(" +", ""))))
        rows.append({
            "Priority": index,
            "Research": lookup,
            "Current": int(current) if current == int(current) else round(current, 2),
            "Cap": maximum or "—",
            "Status": _research_status(current, maximum) if maximum else ("Tracked" if current else "Not entered"),
        })
    return rows


def build_archetype_blueprint(
    profile: Mapping[str, Any],
    archetype: Mapping[str, Any],
    *,
    archetype_id: str = "",
    latest_death: str = "",
) -> Dict[str, Any]:
    archetype = {**archetype, "_id": archetype_id or archetype.get("_id", "")}
    presets = {
        context_id: _build_context_blueprint(profile, archetype, context_id=context_id)
        for context_id in PRESET_CONTEXT_IDS
    }
    substat_rows: List[Dict[str, Any]] = []
    pushing_modules = {row["slot"]: row["recommended"] for row in presets["pushing"]["modules"]["rows"]}
    for slot in ["Cannon", "Armor", "Generator", "Core"]:
        substat_rows.extend(
            _evaluate_substat_targets(profile, str(archetype.get("_id")), pushing_modules.get(slot, ""), slot)
        )

    payload = {
        "presets": presets,
        "cards": presets["pushing"]["cards"],
        "modules": presets["pushing"]["modules"],
        "substats": {
            "rows": substat_rows,
            "summary": "Reroll targets for the recommended pushing modules. Lock effects that are met; reroll weak or missing ones.",
            "open_targets": sum(1 for row in substat_rows if row.get("Status") != "Met"),
        },
        "research": {
            "labs": _research_rows(profile, "labs", archetype.get("priority_labs", [])),
            "workshop": _research_rows(profile, "workshop", archetype.get("priority_workshop", [])),
            "enhancements": _research_rows(profile, "enhancements", archetype.get("enhancement_priorities", [])),
            "uw_labs": _research_rows(profile, "labs", archetype.get("uw_priorities", [])),
            "summary": "Research these labs and workshop stats in order; strong entries can be maintained while you catch up elsewhere.",
        },
    }
    return enrich_blueprint_beast_mode(
        profile,
        str(archetype.get("_id")),
        payload,
        latest_death=latest_death,
    )


def _profile_gaps(profile: Mapping[str, Any], archetype: Mapping[str, Any]) -> List[str]:
    gaps: List[str] = []
    items = profile.get("cards", {}).get("items", {}) if isinstance(profile.get("cards"), Mapping) else {}
    if isinstance(items, Mapping):
        for card in archetype.get("priority_cards", []):
            record = items.get(card)
            if not isinstance(record, Mapping):
                gaps.append(f"Track {card} cards — not entered yet.")
                continue
            level = int(_clean_number(record.get("level")))
            if level < 5:
                gaps.append(f"{card} is only level {level}/7 for this build.")
            elif level < 7:
                gaps.append(f"Finish {card} ({level}/7) when gems allow.")

    ws_progress = _section_progress(profile, "workshop", archetype.get("priority_workshop", []))
    if ws_progress < 0.35:
        gaps.append("Core workshop stats for this build are still early.")
    lab_progress = _section_progress(profile, "labs", archetype.get("priority_labs", []))
    if lab_progress < 0.30:
        gaps.append("Priority labs for this build are underdeveloped.")

    uw = profile.get("uw", {}) if isinstance(profile.get("uw"), Mapping) else {}
    if archetype.get("focus") == "Economy":
        if not (isinstance(uw.get("Golden Tower"), Mapping) and uw.get("Golden Tower", {}).get("owned")):
            gaps.append("Golden Tower is not marked owned — economy builds lean on GT.")
        if not (isinstance(uw.get("Black Hole"), Mapping) and uw.get("Black Hole", {}).get("owned")):
            gaps.append("Black Hole is not marked owned — coin uptime suffers.")

    slots = int(_clean_number(profile.get("cards", {}).get("slots")))
    if slots and slots < 12:
        gaps.append(f"Only {slots} card slots entered — most builds want 12+ for flexible presets.")

    if not gaps:
        gaps.append("No major gaps detected in tracked priorities — focus on the ranked next steps below.")
    return gaps[:6]


def _upgrade_matches_archetype(upgrade: str, archetype: Mapping[str, Any]) -> bool:
    text = str(upgrade or "").casefold()
    tokens: List[str] = []
    for bucket in ("priority_cards", "priority_workshop", "priority_labs"):
        tokens.extend(str(item).casefold() for item in archetype.get(bucket, []))
    return any(token and token in text for token in tokens)


def _rerank_rows(rows: Sequence[Mapping[str, Any]], archetype: Mapping[str, Any]) -> List[Dict[str, Any]]:
    preferred_systems = {str(item).casefold() for item in archetype.get("priority_systems", [])}
    adjusted: List[Dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        boost = 0.0
        reasons: List[str] = []
        domain = str(row.get("Domain", ""))
        weights = archetype.get("domain_weights", {})
        if domain in weights:
            boost += 4.0 * float(weights[domain])
            reasons.append(f"matches {archetype.get('label')} domain mix")
        if _upgrade_matches_archetype(str(row.get("Upgrade", "")), archetype):
            boost += 8.0
            reasons.append("targets a priority stat/card for this build")
        system = str(row.get("System", "")).casefold()
        if system in preferred_systems:
            boost += 3.0
        row["Archetype Boost"] = round(boost, 2)
        row["Archetype Score"] = round(float(row.get("Priority Index", 0.0)) + boost, 2)
        if reasons:
            existing = str(row.get("Why", "")).strip()
            extra = f"build fit: {'; '.join(reasons)}"
            row["Why"] = "; ".join(part for part in [existing, extra] if part)
        adjusted.append(row)
    return sorted(adjusted, key=lambda item: float(item.get("Archetype Score", 0.0)), reverse=True)


def build_archetype_report(
    profile: Mapping[str, Any],
    archetype_id: str,
    *,
    steps: int = 12,
    candidates_per_path: int = 3,
    apply_death_weighting: bool = True,
    top_n: int = 8,
) -> Dict[str, Any]:
    archetype = ARCHETYPES.get(archetype_id)
    if not archetype:
        raise KeyError(f"Unknown archetype: {archetype_id}")
    analysis = build_analysis(dict(profile))
    scores = analysis.get("scores", {})
    fit_score = round(
        0.55 * _domain_fit(scores, archetype["domain_weights"])
        + 0.25 * _card_progress(profile, archetype.get("priority_cards", [])) * 100.0
        + 0.20 * (_section_progress(profile, "workshop", archetype.get("priority_workshop", [])) * 50.0
                  + _section_progress(profile, "labs", archetype.get("priority_labs", [])) * 50.0),
        1,
    )
    combined = build_combined_recommendations(
        dict(profile),
        steps=steps,
        candidates_per_path=candidates_per_path,
        apply_death_weighting=apply_death_weighting,
        focus=str(archetype.get("focus", "Balanced")),
    )
    ranked = _rerank_rows(combined.get("rows", []), archetype)
    blueprint = build_archetype_blueprint(
        profile, archetype, archetype_id=archetype_id, latest_death=str(combined.get("latest_death") or ""),
    )
    return {
        "id": archetype_id,
        "label": archetype["label"],
        "tagline": archetype["tagline"],
        "focus": archetype.get("focus", "Balanced"),
        "fit_score": fit_score,
        "fit_label": "Strong match" if fit_score >= 70 else "Work in progress" if fit_score >= 45 else "Needs investment",
        "domain_scores": scores,
        "gaps": _profile_gaps(profile, archetype),
        "priority_cards": list(archetype.get("priority_cards", [])),
        "priority_labs": list(archetype.get("priority_labs", [])),
        "priority_workshop": list(archetype.get("priority_workshop", [])),
        "module_focus": dict(archetype.get("module_focus", {})),
        "blueprint": blueprint,
        "next_steps": ranked[:top_n],
        "latest_death": combined.get("latest_death", "No report saved"),
        "weakest_domain": analysis.get("weakest"),
    }


def build_all_archetype_reports(
    profile: Mapping[str, Any],
    *,
    steps: int = 10,
    candidates_per_path: int = 3,
    apply_death_weighting: bool = True,
    top_n: int = 6,
) -> Dict[str, Any]:
    reports = [
        build_archetype_report(
            profile,
            archetype_id,
            steps=steps,
            candidates_per_path=candidates_per_path,
            apply_death_weighting=apply_death_weighting,
            top_n=top_n,
        )
        for archetype_id in ARCHETYPE_IDS
    ]
    best = max(reports, key=lambda item: float(item.get("fit_score", 0.0)))
    return {
        "archetypes": reports,
        "best_match_id": best["id"],
        "best_match_label": best["label"],
        "best_match_score": best["fit_score"],
    }


def archetype_display_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    display: List[Dict[str, Any]] = []
    for row in rows:
        explanation = row.get("Explanation") if isinstance(row.get("Explanation"), Mapping) else {}
        why_now = explanation.get("Why now") or []
        why_text = " · ".join(why_now[:2]) if why_now else str(row.get("Why", ""))
        display.append({
            "Build score": row.get("Archetype Score", row.get("Priority Index")),
            "Upgrade": row.get("Upgrade"),
            "Resource": row.get("Resource"),
            "System": row.get("System"),
            "Affordability": row.get("Affordability"),
            "Why": why_text,
        })
    return display
