"""Beast-mode playbook extras: bots, guardians, relics, UWs, assist modules, vault, masteries."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from .engines.core import build_analysis
from .engines.whole_account import (
    BOT_DOMAIN,
    BOT_TARGETS,
    GUARDIAN_DOMAIN,
    GUARDIAN_TARGETS,
    RELIC_BONUS_PRIORITY,
    VAULT_PRIORITY,
)


def _clean_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


BEAST_ARCHETYPE_CONFIG: Dict[str, Dict[str, Any]] = {
    "economy_farmer": {
        "bots": ["Golden Bot", "Flame Bot", "Bot Bot"],
        "guardians": ["Bounty", "Fetch", "Summon"],
        "relic_bonus_types": ["Coins", "Cash", "Golden Tower", "Black Hole"],
        "mastery_cards": ["Enemy Balance", "Coins", "Critical Coin", "Wave Skip"],
        "vault_nodes": ["Additional Card Slot", "Discount Enhancements", "Coins / Kill"],
        "uw_focus": ["Golden Tower", "Black Hole", "Death Wave"],
        "uw_notes": [
            "Sync Golden Tower and Black Hole cooldowns for maximum coin uptime.",
            "Death Wave coin bonus labs scale farming hard — keep DW coin labs moving.",
        ],
        "assist_notes": "Assist slots should mirror economy: coin/cash/GT/BH substats on Generator and Core.",
    },
    "glass_cannon": {
        "bots": ["Flame Bot", "Amplify Bot", "Golden Bot"],
        "guardians": ["Attack", "Bounty"],
        "relic_bonus_types": ["Damage", "Attack Speed", "Critical Factor", "Critical Chance"],
        "mastery_cards": ["Damage", "Attack Speed", "Berserker", "Plasma Cannon", "Ultimate Crit"],
        "vault_nodes": ["Ultimate Weapon Damage", "Additional Card Slot", "Attack Speed"],
        "uw_focus": ["Spotlight", "Chain Lightning", "Black Hole", "Smart Missiles"],
        "uw_notes": [
            "Spotlight and Chain Lightning are core damage amplifiers for glass builds.",
            "Only invest BH duration/size if you still need economy uptime for gem income.",
        ],
        "assist_notes": "Assist Cannons/Cores should add crit or attack speed; avoid defensive assists on glass.",
    },
    "ehp_tank": {
        "bots": ["Thunder Bot", "Golden Bot", "Bot Bot"],
        "guardians": ["Ally", "Attack"],
        "relic_bonus_types": ["Health", "Defense", "Recovery Package"],
        "mastery_cards": ["Health", "Extra Defense", "Fortress", "Energy Shield"],
        "vault_nodes": ["Additional Card Slot", "Health", "Defense %"],
        "uw_focus": ["Death Wave", "Black Hole", "Golden Tower"],
        "uw_notes": [
            "Death Wave health saturation is a major eHP lever — check native eHP stones path.",
            "Keep enough damage online so tanks can still clear — don't ignore Cannon/Core labs.",
        ],
        "assist_notes": "Assist Armor modules should stack health, defense, or package effects.",
    },
    "recovery_sustain": {
        "bots": ["Thunder Bot", "Golden Bot", "Flame Bot"],
        "guardians": ["Ally", "Fetch", "Bounty"],
        "relic_bonus_types": ["Health Regen", "Recovery Package", "Health"],
        "mastery_cards": ["Health Regen", "Recovery Package Chance", "Second Wind", "Health"],
        "vault_nodes": ["Additional Card Slot", "Discount Enhancements"],
        "uw_focus": ["Golden Tower", "Death Wave", "Black Hole"],
        "uw_notes": [
            "Garlic Thorns and recovery package labs matter heavily after Vampire deaths.",
            "Regen labs should stay ahead of damage labs if sustain is the bottleneck.",
        ],
        "assist_notes": "Assist slots on Armor/Generator should favor regen, package chance, or lifesteal substats.",
    },
    "balanced": {
        "bots": ["Golden Bot", "Flame Bot", "Thunder Bot"],
        "guardians": ["Bounty", "Ally", "Attack"],
        "relic_bonus_types": ["Coins", "Damage", "Health", "Attack Speed"],
        "mastery_cards": ["Enemy Balance", "Damage", "Health", "Coins", "Attack Speed"],
        "vault_nodes": ["Additional Card Slot", "Discount Enhancements", "Health Regen"],
        "uw_focus": ["Golden Tower", "Black Hole", "Spotlight", "Death Wave"],
        "uw_notes": [
            "Maintain GT/BH sync while slowly adding Spotlight or Chain Lightning.",
            "Rotate lab priority toward whichever domain score is lowest this week.",
        ],
        "assist_notes": "Assist modules should complement primaries — economy on Generator, damage on Cannon.",
    },
}

DEATH_TWEAKS: Dict[str, Dict[str, Any]] = {
    "vampire": {
        "summary": "Vampire deaths — prioritize sustain, thorns, and package coverage.",
        "add_cards": ["Health Regen", "Recovery Package Chance", "Plasma Cannon"],
        "add_labs": ["Garlic Thorns", "Recovery Package Chance", "Recovery Package Amount"],
        "add_modules_note": "Look for thorn, regen, or package substats on Armor.",
    },
    "boss": {
        "summary": "Boss deaths — spike single-target damage and burst eHP.",
        "add_cards": ["Plasma Cannon", "Ultimate Crit", "Berserker"],
        "add_labs": ["Damage", "Critical Factor", "Health"],
        "add_modules_note": "Prioritize crit factor and boss damage substats on Cannon/Core.",
    },
    "ray": {
        "summary": "Ray deaths — burst survivability and defense spikes matter.",
        "add_cards": ["Energy Shield", "Second Wind", "Fortress"],
        "add_labs": ["Health", "Defense %", "Recovery Package Max"],
        "add_modules_note": "Armor substats should lean health/defense over greed.",
    },
    "fast": {
        "summary": "Fast deaths — kill speed or eHP; enemies are outpacing your clear.",
        "add_cards": ["Attack Speed", "Area of Effect", "Health"],
        "add_labs": ["Attack Speed", "Damage", "Health"],
        "add_modules_note": "Cannon attack speed and multishot substats rise in value.",
    },
    "scatter": {
        "summary": "Scatter deaths — multi-target control and consistent packages.",
        "add_cards": ["Area of Effect", "Plasma Cannon", "Recovery Package Chance"],
        "add_labs": ["Shock Multiplier", "Damage", "Recovery Package Chance"],
        "add_modules_note": "Core multishot/AoE substats and knockback/control help.",
    },
}


def _bot_blueprint(profile: Mapping[str, Any], archetype_id: str) -> Dict[str, Any]:
    config = BEAST_ARCHETYPE_CONFIG.get(archetype_id, {})
    bots = profile.get("bots", {}) if isinstance(profile.get("bots"), Mapping) else {}
    rows: List[Dict[str, Any]] = []
    for name in config.get("bots", []):
        record = bots.get(name, {}) if isinstance(bots.get(name), Mapping) else {}
        unlocked = record.get("unlocked")
        attrs = record.get("attributes", {}) if isinstance(record.get("attributes"), Mapping) else {}
        if unlocked is False:
            rows.append({
                "Bot": name,
                "Priority": "Unlock",
                "Target": "Unlocked",
                "Current": "Locked",
                "Status": "Action needed",
                "Why": f"{name} supports {BOT_DOMAIN.get(name, 'this build')}.",
            })
            continue
        if unlocked is not True and not attrs:
            rows.append({
                "Bot": name,
                "Priority": "Track",
                "Target": "Import bot stats",
                "Current": "Unknown",
                "Status": "Missing data",
                "Why": "Enter or import bot attributes to compare against targets.",
            })
            continue
        worst = None
        for attr, (target, lower_better) in BOT_TARGETS.get(name, {}).items():
            current = _clean_number(attrs.get(attr))
            if lower_better:
                gap = max(0.0, current / max(target, 1e-9) - 1.0)
            else:
                gap = max(0.0, 1.0 - current / max(target, 1e-9))
            if gap > 0.01 and (worst is None or gap > worst[0]):
                worst = (gap, attr, current, target, lower_better)
        if worst:
            _, attr, current, target, lower_better = worst
            direction = "Lower" if lower_better else "Raise"
            rows.append({
                "Bot": name,
                "Priority": attr,
                "Target": f"{direction} toward {target:g}",
                "Current": current,
                "Status": "Tune",
                "Why": f"Biggest remaining bot gap for {name}.",
            })
        else:
            rows.append({
                "Bot": name,
                "Priority": "Maintain",
                "Target": "At benchmark",
                "Current": "OK",
                "Status": "Ready",
                "Why": f"{name} meets strategic targets for this build.",
            })
    return {"rows": rows, "summary": "Unlock and tune these bots for the build's secondary systems."}


def _guardian_blueprint(profile: Mapping[str, Any], archetype_id: str) -> Dict[str, Any]:
    config = BEAST_ARCHETYPE_CONFIG.get(archetype_id, {})
    guardians = profile.get("guardians", {}) if isinstance(profile.get("guardians"), Mapping) else {}
    rows: List[Dict[str, Any]] = []
    for name in config.get("guardians", []):
        record = guardians.get(name, {}) if isinstance(guardians.get(name), Mapping) else {}
        unlocked = record.get("unlocked")
        attrs = record.get("attributes", {}) if isinstance(record.get("attributes"), Mapping) else {}
        label = f"{name} Guardian"
        if unlocked is False:
            rows.append({
                "Guardian": label,
                "Priority": "Unlock",
                "Target": "Unlocked",
                "Current": "Locked",
                "Status": "Action needed",
                "Why": f"{name} supports {GUARDIAN_DOMAIN.get(name, 'this build')}.",
            })
            continue
        if unlocked is not True and not attrs:
            rows.append({
                "Guardian": label,
                "Priority": "Track",
                "Target": "Import guardian stats",
                "Current": "Unknown",
                "Status": "Missing data",
                "Why": "Enter or import guardian attributes.",
            })
            continue
        worst = None
        for attr, (target, lower_better) in GUARDIAN_TARGETS.get(name, {}).items():
            current = _clean_number(attrs.get(attr))
            if lower_better:
                gap = max(0.0, current / max(target, 1e-9) - 1.0)
            else:
                gap = max(0.0, 1.0 - current / max(target, 1e-9))
            if gap > 0.01 and (worst is None or gap > worst[0]):
                worst = (gap, attr, current, target, lower_better)
        if worst:
            _, attr, current, target, lower_better = worst
            direction = "Lower" if lower_better else "Raise"
            rows.append({
                "Guardian": label,
                "Priority": attr,
                "Target": f"{direction} toward {target:g}",
                "Current": current,
                "Status": "Tune",
                "Why": f"Primary guardian tuning target for {name}.",
            })
        else:
            rows.append({
                "Guardian": label,
                "Priority": "Maintain",
                "Target": "At benchmark",
                "Current": "OK",
                "Status": "Ready",
                "Why": f"{name} meets strategic targets.",
            })
    return {"rows": rows, "summary": "Guardian unlocks and attribute targets for this build."}


def _relic_theme_blueprint(profile: Mapping[str, Any], archetype_id: str) -> Dict[str, Any]:
    config = BEAST_ARCHETYPE_CONFIG.get(archetype_id, {})
    target_types = {str(item).casefold() for item in config.get("relic_bonus_types", [])}
    relics = profile.get("relics", {}) if isinstance(profile.get("relics"), Mapping) else {}
    items = relics.get("items", {}) if isinstance(relics.get("items"), Mapping) else {}
    owned_rows: List[Dict[str, Any]] = []
    missing_rows: List[Dict[str, Any]] = []
    for name, record in items.items():
        if not isinstance(record, Mapping):
            continue
        bonus_type = str(record.get("bonus_type") or "")
        row = {
            "Name": name,
            "Bonus type": bonus_type or "Unknown",
            "Value": record.get("value"),
            "Owned": "Yes" if record.get("owned") else "No",
        }
        if record.get("owned"):
            if bonus_type.casefold() in target_types or any(token in bonus_type.casefold() for token in target_types):
                owned_rows.append(row)
        else:
            weight = RELIC_BONUS_PRIORITY.get(bonus_type, (0.0, ""))[0]
            if bonus_type.casefold() in target_types or weight >= 0.5:
                missing_rows.append({**row, "Priority": "High" if bonus_type.casefold() in target_types else "Medium"})
    themes = profile.get("themes", {}) if isinstance(profile.get("themes"), Mapping) else {}
    theme_items = themes.get("items", {}) if isinstance(themes.get("items"), Mapping) else {}
    missing_themes = [
        {
            "Name": str(record.get("name") or key),
            "Type": str(record.get("type") or "Theme"),
            "Owned": "No",
            "Event": str(record.get("event") or record.get("source") or "Event shop"),
        }
        for key, record in theme_items.items()
        if isinstance(record, Mapping) and not record.get("owned")
    ][:5]
    return {
        "owned_relics": owned_rows[:8],
        "missing_relics": missing_rows[:8],
        "missing_themes": missing_themes,
        "summary": "Owned relics that match this build plus high-value missing relic/theme targets.",
    }


def _uw_blueprint(profile: Mapping[str, Any], archetype_id: str) -> Dict[str, Any]:
    config = BEAST_ARCHETYPE_CONFIG.get(archetype_id, {})
    uw = profile.get("uw", {}) if isinstance(profile.get("uw"), Mapping) else {}
    rows: List[Dict[str, Any]] = []
    for name in config.get("uw_focus", []):
        record = uw.get(name, {}) if isinstance(uw.get(name), Mapping) else {}
        owned = bool(record.get("owned"))
        attrs = record.get("attributes", {}) if isinstance(record.get("attributes"), Mapping) else {}
        rows.append({
            "Ultimate Weapon": name,
            "Owned": "Yes" if owned else "No",
            "Status": "Upgrade attributes" if owned else "Unlock / track",
            "Notes": ", ".join(f"{key} {value}" for key, value in list(attrs.items())[:3]) or "No attributes entered",
        })
    analysis = build_analysis(dict(profile))
    return {
        "rows": rows,
        "gt_bh_synced": bool(analysis.get("gt_bh_synced")),
        "bh_quantity": analysis.get("bh_quantity"),
        "notes": list(config.get("uw_notes", [])),
        "summary": "Ultimate Weapon ownership and upgrade focus for this build.",
    }


def _assist_module_blueprint(
    profile: Mapping[str, Any],
    *,
    module_preset_keys: Sequence[str],
    assist_notes: str,
) -> Dict[str, Any]:
    presets = profile.get("module_presets", {}) if isinstance(profile.get("module_presets"), Mapping) else {}
    inventory = profile.get("module_inventory", {}) if isinstance(profile.get("module_inventory"), Mapping) else {}
    rows: List[Dict[str, Any]] = []
    for preset_key in module_preset_keys:
        preset = presets.get(preset_key, {}) if isinstance(presets.get(preset_key), Mapping) else {}
        if not preset:
            continue
        for slot in ["Cannon", "Armor", "Generator", "Core"]:
            slot_data = preset.get(slot, {}) if isinstance(preset.get(slot), Mapping) else {}
            primary = str(slot_data.get("primary") or "").strip()
            assist = str(slot_data.get("assist") or "").strip()
            if not assist or assist == "Any Other":
                rows.append({
                    "Preset": preset_key,
                    "Slot": slot,
                    "Primary": primary or "—",
                    "Assist": "Not set",
                    "Status": "Set assist module",
                    "Why": assist_notes,
                })
                continue
            record = inventory.get(f"{slot}::{assist}", {}) if isinstance(inventory, Mapping) else {}
            rows.append({
                "Preset": preset_key,
                "Slot": slot,
                "Primary": primary or "—",
                "Assist": assist,
                "Rarity": record.get("rarity", "Unknown") if isinstance(record, Mapping) else "Unknown",
                "Level": record.get("level", "—") if isinstance(record, Mapping) else "—",
                "Status": "Review substats" if isinstance(record, Mapping) else "Import inventory",
                "Why": assist_notes,
            })
        if rows:
            break
    if not rows:
        rows = [{
            "Preset": module_preset_keys[0] if module_preset_keys else "Farming",
            "Slot": "All",
            "Primary": "—",
            "Assist": "Not imported",
            "Status": "Import module presets",
            "Why": assist_notes,
        }]
    return {"rows": rows, "summary": assist_notes}


def _mastery_blueprint(profile: Mapping[str, Any], archetype_id: str) -> Dict[str, Any]:
    config = BEAST_ARCHETYPE_CONFIG.get(archetype_id, {})
    items = profile.get("cards", {}).get("items", {}) if isinstance(profile.get("cards"), Mapping) else {}
    rows: List[Dict[str, Any]] = []
    for name in config.get("mastery_cards", []):
        record = items.get(name) if isinstance(items, Mapping) else None
        level = int(_clean_number(record.get("level"))) if isinstance(record, Mapping) else 0
        mastery = int(_clean_number(record.get("mastery"))) if isinstance(record, Mapping) else 0
        if level < 7:
            status = "Level first"
            target = "Reach level 7"
        elif mastery < 3:
            status = "Master next"
            target = "Mastery 3+"
        elif mastery < 9:
            status = "Push mastery"
            target = "Mastery 9"
        else:
            status = "Complete"
            target = "Max mastery"
        rows.append({
            "Card": name,
            "Level": f"{level}/7",
            "Mastery": f"{mastery}/9",
            "Target": target,
            "Status": status,
        })
    return {"rows": rows, "summary": "Long-term card mastery order for this build."}


def _vault_blueprint(profile: Mapping[str, Any], archetype_id: str) -> Dict[str, Any]:
    config = BEAST_ARCHETYPE_CONFIG.get(archetype_id, {})
    vault = profile.get("vault", {}) if isinstance(profile.get("vault"), Mapping) else {}
    bonuses = vault.get("bonuses", {}) if isinstance(vault.get("bonuses"), Mapping) else {}
    rows: List[Dict[str, Any]] = []
    for name in config.get("vault_nodes", []):
        record = bonuses.get(name, {}) if isinstance(bonuses.get(name), Mapping) else {}
        active = _clean_number(record.get("active"))
        total = _clean_number(record.get("total"))
        domain = VAULT_PRIORITY.get(name, (0.0, "Utility"))[1]
        if total > 0 and active >= total:
            status = "Complete"
        elif active > 0:
            status = "In progress"
        else:
            status = "Start"
        rows.append({
            "Vault node": name,
            "Progress": f"{int(active)}/{int(total)}" if total > 0 else str(int(active)),
            "Domain": domain,
            "Status": status,
        })
    return {"rows": rows, "summary": "Vault key spending order for this build."}


def _death_blueprint(latest_death: str) -> Dict[str, Any]:
    text = str(latest_death or "").casefold()
    for key, payload in DEATH_TWEAKS.items():
        if key in text:
            return {
                "matched": key.title(),
                **payload,
                "add_cards": list(payload.get("add_cards", [])),
                "add_labs": list(payload.get("add_labs", [])),
            }
    return {
        "matched": None,
        "summary": "No recent death-specific tweak applied — use the base build loadouts.",
        "add_cards": [],
        "add_labs": [],
        "add_modules_note": "",
    }


def _readiness_score(profile: Mapping[str, Any], blueprint: Mapping[str, Any], beast: Mapping[str, Any]) -> float:
    scores: List[float] = []
    pushing = (blueprint.get("presets") or {}).get("pushing", {})
    cards = pushing.get("cards", {})
    if cards.get("recommended"):
        scores.append(float(cards.get("preset_overlap", 0)) / max(len(cards["recommended"]), 1))
    substats = blueprint.get("substats", {}).get("rows", [])
    if substats:
        met = sum(1 for row in substats if row.get("Status") == "Met")
        scores.append(met / len(substats))
    for key in ("bots", "guardians"):
        rows = beast.get(key, {}).get("rows", [])
        if rows:
            ready = sum(1 for row in rows if row.get("Status") in {"Ready", "Complete"})
            scores.append(ready / len(rows))
    masteries = beast.get("masteries", {}).get("rows", [])
    if masteries:
        done = sum(1 for row in masteries if row.get("Status") == "Complete")
        scores.append(done / len(masteries))
    if not scores:
        return 0.0
    return round(100.0 * sum(scores) / len(scores), 1)


def build_master_checklist(
    profile: Mapping[str, Any],
    archetype_id: str,
    blueprint: Mapping[str, Any],
    beast: Mapping[str, Any],
    *,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    items: List[tuple[float, Dict[str, Any]]] = []
    pushing = (blueprint.get("presets") or {}).get("pushing", {})
    for card in pushing.get("cards", {}).get("missing", []):
        items.append((95.0, {"Priority": 95, "Action": f"Pull {card} cards", "System": "Cards", "Why": "Core build card missing."}))
    for row in pushing.get("modules", {}).get("rows", []):
        if row.get("status") == "Swap recommended":
            items.append((88.0, {
                "Priority": 88,
                "Action": f"Swap {row.get('slot')} to {row.get('recommended')}",
                "System": "Modules",
                "Why": row.get("reason", ""),
            }))
    for row in blueprint.get("substats", {}).get("rows", []):
        if row.get("Status") != "Met":
            items.append((84.0, {
                "Priority": 84,
                "Action": row.get("Advice", "Reroll sub-effect"),
                "System": "Module sub-effects",
                "Why": f"{row.get('Slot')} · {row.get('Target')}",
            }))
    for row in beast.get("bots", {}).get("rows", []):
        if row.get("Status") != "Ready":
            items.append((72.0, {
                "Priority": 72,
                "Action": f"{row.get('Bot')}: {row.get('Priority')}",
                "System": "Bots",
                "Why": row.get("Why", ""),
            }))
    for row in beast.get("guardians", {}).get("rows", []):
        if row.get("Status") != "Ready":
            items.append((70.0, {
                "Priority": 70,
                "Action": f"{row.get('Guardian')}: {row.get('Priority')}",
                "System": "Guardians",
                "Why": row.get("Why", ""),
            }))
    for row in blueprint.get("research", {}).get("labs", [])[:5]:
        if row.get("Status") in {"Not started", "Started"}:
            items.append((66.0, {
                "Priority": 66,
                "Action": f"Research lab: {row.get('Research')}",
                "System": "Labs",
                "Why": f"Priority #{row.get('Priority')} for this build.",
            }))
    for row in beast.get("relics", {}).get("missing_relics", [])[:4]:
        items.append((58.0, {
            "Priority": 58,
            "Action": f"Acquire relic: {row.get('Name')}",
            "System": "Relics",
            "Why": f"Missing {row.get('Bonus type')} bonus.",
        }))
    for row in beast.get("vault", {}).get("rows", []):
        if row.get("Status") != "Complete":
            items.append((55.0, {
                "Priority": 55,
                "Action": f"Vault: {row.get('Vault node')}",
                "System": "Vault",
                "Why": f"Progress {row.get('Progress')}.",
            }))
    for card in beast.get("death", {}).get("add_cards", []):
        items.append((80.0, {
            "Priority": 80,
            "Action": f"Add {card} vs recent death",
            "System": "Death tweak",
            "Why": beast.get("death", {}).get("summary", ""),
        }))
    items.sort(key=lambda pair: pair[0], reverse=True)
    seen: set[str] = set()
    checklist: List[Dict[str, Any]] = []
    for _, row in items:
        key = f"{row['System']}::{row['Action']}"
        if key in seen:
            continue
        seen.add(key)
        checklist.append(row)
        if len(checklist) >= limit:
            break
    return checklist


def enrich_blueprint_beast_mode(
    profile: Mapping[str, Any],
    archetype_id: str,
    blueprint: Dict[str, Any],
    *,
    latest_death: str = "",
) -> Dict[str, Any]:
    config = BEAST_ARCHETYPE_CONFIG.get(archetype_id, {})
    beast = {
        "bots": _bot_blueprint(profile, archetype_id),
        "guardians": _guardian_blueprint(profile, archetype_id),
        "relics": _relic_theme_blueprint(profile, archetype_id),
        "ultimate_weapons": _uw_blueprint(profile, archetype_id),
        "masteries": _mastery_blueprint(profile, archetype_id),
        "vault": _vault_blueprint(profile, archetype_id),
        "death": _death_blueprint(latest_death),
        "assist": _assist_module_blueprint(
            profile,
            module_preset_keys=["Farming", "Tourney", "Preset 1", "Preset 2"],
            assist_notes=str(config.get("assist_notes", "Set assist modules that complement primaries.")),
        ),
    }
    blueprint["beast"] = beast
    blueprint["readiness_score"] = _readiness_score(profile, blueprint, beast)
    blueprint["master_checklist"] = build_master_checklist(profile, archetype_id, blueprint, beast)
    return blueprint
