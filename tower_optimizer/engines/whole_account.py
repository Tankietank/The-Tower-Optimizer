"""Whole-account progression and opportunity-cost recommendations.

This layer extends the verified native Economy, Damage, eHP, and Regen engines
with practical recommendations for cards, modules, relics, themes, bots,
guardians, and the Vault.  It deliberately uses transparent strategic scoring
where exact in-game costs or formulas are not available in the bundled data.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, Mapping, Optional

from .core import (
    build_analysis,
    build_combined_recommendations as build_native_combined_recommendations,
    native_latest_death,
    native_number,
    resolve_module_record,
)
from ..battle_learning import feedback_modifiers
from ..explanations import enrich_recommendation_payload


MODULE_RARITY_MAX_LEVELS = {
    "Common": 20, "Rare": 30, "Rare+": 40, "Epic": 60, "Epic+": 80,
    "Legendary": 100, "Legendary+": 120, "Mythic": 140, "Mythic+": 160,
    "Ancestral": 200, "Ancestral 1*": 220, "Ancestral 2*": 240,
    "Ancestral 3*": 260, "Ancestral 4*": 280, "Ancestral 5*": 300,
}

RESOURCE_KEYS = {
    "Coins": "coins",
    "Stones": "stones",
    "Gems": "gems",
    "Medals": "medals",
    "Keys": "keys",
    "Bits": "bits",
    "Reroll Shards": "reroll_shards",
    "Module Shards": "module_shards",
}

RESOURCE_ORDER = [
    "Lab", "Coins", "Stones", "Gems", "Medals", "Keys", "Bits",
    "Reroll Shards", "Module Shards", "Milestone / Event", "Action",
]

RARITY_RANK = {
    "None": 0, "Common": 1, "Rare": 2, "Rare+": 3, "Epic": 4,
    "Epic+": 5, "Legendary": 6, "Legendary+": 7, "Mythic": 8,
    "Mythic+": 9, "Ancestral": 10, "Ancestral 1*": 11,
    "Ancestral 2*": 12, "Ancestral 3*": 13, "Ancestral 4*": 14,
    "Ancestral 5*": 15,
}

CARD_DOMAIN = {
    "Damage": "Damage", "Attack Speed": "Damage", "Critical Chance": "Damage",
    "Super Tower": "Damage", "Berserker": "Damage", "Ultimate Crit": "Damage",
    "Plasma Cannon": "Damage", "Death Ray": "Damage", "Nuke": "Damage",
    "Area of Effect": "Damage", "Health": "Survivability",
    "Extra Defense": "Survivability", "Fortress": "Survivability",
    "Energy Shield": "Survivability", "Second Wind": "Survivability",
    "Health Regen": "Regen / Recovery", "Recovery Package Chance": "Regen / Recovery",
    "Coins": "Economy", "Cash": "Economy", "Critical Coin": "Economy",
    "Wave Skip": "Economy", "Enemy Balance": "Economy",
    "Wave Accelerator": "Economy", "Free Upgrades": "Economy",
}

CARD_PRIORITY = {
    "Enemy Balance": 1.00, "Coins": 0.99, "Critical Coin": 0.96,
    "Wave Skip": 0.94, "Wave Accelerator": 0.91, "Attack Speed": 0.90,
    "Damage": 0.88, "Health": 0.87, "Extra Defense": 0.85,
    "Recovery Package Chance": 0.84, "Health Regen": 0.82,
    "Berserker": 0.82, "Plasma Cannon": 0.80, "Super Tower": 0.78,
    "Free Upgrades": 0.76, "Critical Chance": 0.74,
}

BOT_TARGETS: Dict[str, Dict[str, tuple[float, bool]]] = {
    "Golden Bot": {
        "Bonus": (6.0, False), "Range": (55.0, False),
        "Duration": (25.0, False), "Cooldown": (90.0, True),
    },
    "Flame Bot": {
        "Damage": (100.0, False), "Range": (45.0, False),
        "Damage R.": (0.5, False), "Cooldown": (60.0, True),
    },
    "Thunder Bot": {
        "Duration": (8.0, False), "Range": (45.0, False),
        "Linger": (1.0, False), "Cooldown": (90.0, True),
    },
    "Amplify Bot": {
        "Bonus": (5.0, False), "Range": (45.0, False),
        "Duration": (25.0, False), "Cooldown": (90.0, True),
    },
    "Bot Bot": {
        "Bonus": (2.0, False), "Range": (45.0, False),
        "Duration": (25.0, False), "Cooldown": (90.0, True),
    },
}

BOT_DOMAIN = {
    "Golden Bot": "Economy", "Flame Bot": "Damage",
    "Thunder Bot": "Survivability", "Amplify Bot": "Damage",
    "Bot Bot": "Utility",
}

GUARDIAN_TARGETS: Dict[str, Dict[str, tuple[float, bool]]] = {
    "Attack": {"Percentage": (0.10, False), "Targets": (3.0, False), "Cooldown": (90.0, True)},
    "Ally": {"Recovery Amount": (0.10, False), "Max Recovery": (1.5, False), "Cooldown": (90.0, True)},
    "Bounty": {"Multiplier": (0.10, False), "Targets": (3.0, False), "Cooldown": (90.0, True)},
    "Fetch": {"Find Chance": (0.50, False), "Double Find Chance": (0.15, False), "Cooldown": (80.0, True)},
    "Summon": {"Cash Bonus": (3.0, False), "Duration": (30.0, False), "Cooldown": (80.0, True)},
    "Scout": {"Range Bonus": (6.0, False), "Duration": (25.0, False), "Cooldown": (80.0, True)},
}

GUARDIAN_DOMAIN = {
    "Attack": "Damage", "Ally": "Regen / Recovery", "Bounty": "Economy",
    "Fetch": "Economy", "Summon": "Economy", "Scout": "Utility",
}

VAULT_PRIORITY = {
    "Additional Card Slot": (1.00, "Utility"),
    "Discount Enhancements": (0.96, "Economy"),
    "Discount Rerolls": (0.94, "Utility"),
    "Coins / Kill": (0.93, "Economy"),
    "Enemy Health Skip": (0.91, "Damage"),
    "Enemy Attack Skip": (0.91, "Survivability"),
    "Attack Speed": (0.89, "Damage"),
    "Health": (0.88, "Survivability"),
    "Health Regen": (0.87, "Regen / Recovery"),
    "Damage": (0.86, "Damage"),
    "Ultimate Weapon Damage": (0.85, "Damage"),
    "Defense %": (0.84, "Survivability"),
    "Recovery Amount": (0.83, "Regen / Recovery"),
    "Max Recovery": (0.82, "Regen / Recovery"),
    "Free Utility Upgrade": (0.80, "Economy"),
    "Free Attack Upgrade": (0.78, "Damage"),
    "Free Defense Upgrade": (0.78, "Survivability"),
    "Bot Range": (0.70, "Utility"),
}

VAULT_UNLOCK_PRIORITY = {
    "Workshop Presets": (0.90, "Utility"),
    "Bot Presets": (0.88, "Utility"),
    "Bot Cooldown Sliders": (0.87, "Utility"),
    "Auto Restart Run": (0.82, "Economy"),
    "Free Mission Reroll": (0.80, "Utility"),
    "Daily Mission - Set Shard Type": (0.79, "Utility"),
    "Auto Shatter Rare Modules": (0.76, "Utility"),
}

RELIC_BONUS_PRIORITY = {
    "Lab Speed": (1.00, "Economy"), "Coins": (0.98, "Economy"),
    "Coin": (0.98, "Economy"), "Damage": (0.90, "Damage"),
    "Ultimate Damage": (0.88, "Damage"), "Attack Speed": (0.87, "Damage"),
    "Health": (0.87, "Survivability"), "Health Regen": (0.86, "Regen / Recovery"),
    "Defense %": (0.84, "Survivability"), "Recovery Amount": (0.82, "Regen / Recovery"),
    "Max Recovery": (0.82, "Regen / Recovery"), "Bot Range": (0.72, "Utility"),
}

FOCUS_DOMAIN = {
    "Economy": "Economy", "Damage": "Damage", "Survival": "Survivability",
    "Recovery": "Regen / Recovery", "Modules": "Utility",
}


def _clean_number(value: Any) -> float:
    return native_number(value, 0.0)


def _resource_balance(profile: Mapping[str, Any], resource: str) -> Optional[float]:
    key = RESOURCE_KEYS.get(resource)
    if not key:
        return None
    resources = profile.get("resources", {}) if isinstance(profile, Mapping) else {}
    if key not in resources:
        return None
    return _clean_number(resources.get(key))


def _affordability(profile: Mapping[str, Any], resource: str, cost: Optional[float]) -> tuple[str, Optional[bool]]:
    if resource in {"Lab", "Milestone / Event", "Action"}:
        return ("Queueable" if resource == "Lab" else "No direct purchase", True if resource == "Lab" else None)
    if cost is None or cost <= 0:
        balance = _resource_balance(profile, resource)
        return ("Balance entered; cost not modeled" if balance is not None else "Cost not modeled", None)
    balance = _resource_balance(profile, resource)
    if balance is None:
        return ("Balance not entered", None)
    affordable = cost <= balance + 1e-9
    return ("Affordable" if affordable else "Unaffordable", affordable)


def _domain_multiplier(domain: str, focus: str, analysis: Mapping[str, Any], death: str) -> tuple[float, list[str]]:
    multiplier = 1.0
    reasons: list[str] = []
    if domain == str(analysis.get("weakest", "")):
        multiplier *= 1.16
        reasons.append("supports the weakest modeled area")
    if FOCUS_DOMAIN.get(focus) == domain:
        multiplier *= 1.22
        reasons.append(f"matches the {focus.lower()} focus")
    lower = death.casefold()
    if "vampire" in lower and domain in {"Regen / Recovery", "Survivability"}:
        multiplier *= 1.15
        reasons.append("recent Vampire death favors sustain")
    elif "boss" in lower and domain in {"Damage", "Survivability"}:
        multiplier *= 1.12
        reasons.append("recent Boss death favors damage or eHP")
    elif "ray" in lower and domain == "Survivability":
        multiplier *= 1.14
        reasons.append("recent Ray death favors burst eHP")
    elif "scatter" in lower and domain in {"Damage", "Regen / Recovery"}:
        multiplier *= 1.10
        reasons.append("recent Scatter death favors clear and recovery")
    elif "fast" in lower and domain in {"Damage", "Survivability"}:
        multiplier *= 1.08
        reasons.append("recent Fast death favors kill speed or eHP")
    return multiplier, reasons


def _row(
    profile: Mapping[str, Any], *, priority: float, domain: str, resource: str,
    system: str, upgrade: str, next_level: Any = "Review", cost_text: str = "Not modeled",
    cost_numeric: Optional[float] = None, confidence: str = "Strategic",
    why: Iterable[str] = (), gain: float = 0.0, path_rank: int = 1,
    focus: str = "Balanced", analysis: Optional[Mapping[str, Any]] = None,
    death: str = "",
) -> Dict[str, Any]:
    analysis = analysis or {}
    multiplier, dynamic_reasons = _domain_multiplier(domain, focus, analysis, death)
    if focus == "Modules" and system == "Modules":
        multiplier *= 1.35
        dynamic_reasons.append("matches the modules focus")
    affordability, affordable = _affordability(profile, resource, cost_numeric)
    all_reasons = [*dynamic_reasons, *[str(item) for item in why if str(item).strip()]]
    return {
        "Priority Index": round(float(priority) * multiplier, 4),
        "Domain": domain,
        "Resource": resource,
        "System": system,
        "Path": f"{system} opportunity cost",
        "Path Key": f"account_{system.casefold().replace(' ', '_').replace('/', '_')}",
        "Path Rank": path_rank,
        "Upgrade": upgrade,
        "Next Level": next_level,
        "Cost / Time": cost_text,
        "Cost Numeric": float(cost_numeric or 0.0),
        "Estimated Gain %": float(gain),
        "Native ROI": "Strategic score",
        "Affordability": affordability,
        "Affordable Bool": affordable,
        "Reference Rank": None,
        "Confidence": confidence,
        "Why": "; ".join(all_reasons),
    }


def _card_rows(profile: Mapping[str, Any], focus: str, analysis: Mapping[str, Any], death: str) -> list[Dict[str, Any]]:
    cards = profile.get("cards", {}) if isinstance(profile.get("cards", {}), Mapping) else {}
    slots = int(_clean_number(cards.get("slots")))
    items = cards.get("items", {}) if isinstance(cards.get("items", {}), Mapping) else {}
    rows: list[Dict[str, Any]] = []
    if slots < 18:
        urgency = 98.0 if slots < 12 else 91.0 if slots < 15 else 80.0
        rows.append(_row(
            profile, priority=urgency, domain="Utility", resource="Gems", system="Cards",
            upgrade="Buy the next Card Slot", next_level=slots + 1,
            cost_text="Use the next in-game Card Slot price", confidence="High strategic",
            why=[f"{slots} slots currently entered", "additional slots improve every farming and tournament preset"],
            focus=focus, analysis=analysis, death=death,
        ))
    incomplete = []
    for name, record in items.items():
        if not isinstance(record, Mapping):
            continue
        level = int(_clean_number(record.get("level")))
        if level < 7:
            incomplete.append((CARD_PRIORITY.get(str(name), 0.55), str(name), level))
    incomplete.sort(reverse=True)
    for rank, (base_weight, name, level) in enumerate(incomplete[:6], start=1):
        domain = CARD_DOMAIN.get(name, "Utility")
        rows.append(_row(
            profile, priority=58.0 + 34.0 * base_weight - rank,
            domain=domain, resource="Gems", system="Cards",
            upgrade=f"Draw cards toward {name} level {level + 1}", next_level=level + 1,
            cost_text="Card draw RNG; exact gem cost is not deterministic", confidence="Medium strategic",
            why=[f"{name} is level {level}/7", "card draws also progress other incomplete cards"],
            focus=focus, analysis=analysis, death=death, path_rank=rank,
        ))
    return rows


def _equipped_module(profile: Mapping[str, Any], slot: str, preset: str = "Farming") -> tuple[str, Mapping[str, Any]]:
    presets = profile.get("module_presets", {}) if isinstance(profile.get("module_presets", {}), Mapping) else {}
    configured = presets.get(preset, {}) if isinstance(presets.get(preset, {}), Mapping) else {}
    slot_record = configured.get(slot, {}) if isinstance(configured.get(slot, {}), Mapping) else {}
    name = str(slot_record.get("primary") or "").strip()
    if not name or name == "Any Other":
        fallback = profile.get("modules", {}).get(slot, {}) if isinstance(profile.get("modules", {}), Mapping) else {}
        name = str(fallback.get("name") or "").strip()
    record = resolve_module_record(dict(profile), slot, name) if name else {}
    return name, record if isinstance(record, Mapping) else {}


def _module_rows(profile: Mapping[str, Any], focus: str, analysis: Mapping[str, Any], death: str) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    inventory = profile.get("module_inventory", {}) if isinstance(profile.get("module_inventory", {}), Mapping) else {}
    slot_domain = {"Cannon": "Damage", "Armor": "Survivability", "Generator": "Economy", "Core": "Damage"}
    for slot in ["Cannon", "Armor", "Generator", "Core"]:
        name, record = _equipped_module(profile, slot)
        if not name or name == "Any Other" or not record:
            rows.append(_row(
                profile, priority=97.0, domain=slot_domain[slot], resource="Action", system="Modules",
                upgrade=f"Set a named Farming {slot} module", next_level="Equip primary",
                cost_text="No resource cost", confidence="High",
                why=["the Farming preset has no resolvable named primary module"],
                focus=focus, analysis=analysis, death=death,
            ))
            continue
        rarity = str(record.get("rarity") or "None")
        level = int(_clean_number(record.get("level")))
        cap = int(MODULE_RARITY_MAX_LEVELS.get(rarity, max(level, 0)))
        if level < cap:
            gap_ratio = (cap - level) / max(cap, 1)
            rows.append(_row(
                profile, priority=67.0 + 24.0 * gap_ratio, domain=slot_domain[slot],
                resource="Module Shards", system="Modules", upgrade=f"Level {name}",
                next_level=min(cap, level + max(1, min(10, (cap - level) // 4 or 1))),
                cost_text="Use the in-game module level cost", confidence="High strategic",
                why=[f"equipped Farming {slot} is level {level}/{cap}", "module base-stat gains affect every run"],
                focus=focus, analysis=analysis, death=death,
            ))
        substats = record.get("substats", []) if isinstance(record.get("substats", []), list) else []
        weak_substats = []
        module_rank = RARITY_RANK.get(rarity, 0)
        for sub in substats:
            if not isinstance(sub, Mapping):
                continue
            sub_rarity = str(sub.get("rarity") or "None")
            weak_substats.append((RARITY_RANK.get(sub_rarity, 0), str(sub.get("name") or "Unnamed"), sub_rarity))
        weak_substats.sort()
        if len(substats) < 3:
            rows.append(_row(
                profile, priority=86.0, domain=slot_domain[slot], resource="Reroll Shards", system="Modules",
                upgrade=f"Fill missing sub-effects on {name}", next_level=f"At least 3 useful {slot} effects",
                cost_text="Reroll cost varies", confidence="High strategic",
                why=[f"only {len(substats)} sub-effects were imported"], focus=focus, analysis=analysis, death=death,
            ))
        elif weak_substats and weak_substats[0][0] + 3 < module_rank:
            _, sub_name, sub_rarity = weak_substats[0]
            rows.append(_row(
                profile, priority=76.0 + min(12.0, module_rank - weak_substats[0][0]),
                domain=slot_domain[slot], resource="Reroll Shards", system="Modules",
                upgrade=f"Reroll {name}'s weakest sub-effect", next_level=f"Improve {sub_name} ({sub_rarity})",
                cost_text="Set a reroll budget before locking effects", confidence="Medium strategic",
                why=[f"the weakest effect trails the module rarity ({rarity}) by several tiers"],
                focus=focus, analysis=analysis, death=death,
            ))

        alternatives = []
        current_stat = _clean_number(record.get("stat"))
        for key, candidate in inventory.items():
            if not isinstance(candidate, Mapping) or str(candidate.get("slot")) != slot:
                continue
            candidate_name = str(candidate.get("name") or key.split("::")[-1])
            if candidate_name == name:
                continue
            candidate_stat = _clean_number(candidate.get("stat"))
            candidate_rarity = RARITY_RANK.get(str(candidate.get("rarity") or "None"), 0)
            if candidate_stat > current_stat * 1.15 and candidate_rarity >= max(1, module_rank - 1):
                alternatives.append((candidate_stat, candidate_name, str(candidate.get("rarity") or "None")))
        if alternatives:
            alternatives.sort(reverse=True)
            best_stat, best_name, best_rarity = alternatives[0]
            rows.append(_row(
                profile, priority=74.0, domain=slot_domain[slot], resource="Action", system="Modules",
                upgrade=f"Compare {best_name} with equipped {name}", next_level="Run a preset comparison",
                cost_text="No direct resource cost", confidence="Low–Medium",
                why=[f"{best_name} has a materially higher imported base stat ({best_stat:g})", "unique effects are build-dependent, so this is a review prompt rather than an automatic swap"],
                focus=focus, analysis=analysis, death=death,
            ))
    return rows


def _bot_rows(profile: Mapping[str, Any], focus: str, analysis: Mapping[str, Any], death: str) -> list[Dict[str, Any]]:
    bots = profile.get("bots", {}) if isinstance(profile.get("bots", {}), Mapping) else {}
    rows: list[Dict[str, Any]] = []
    unlock_priority = ["Golden Bot", "Flame Bot", "Amplify Bot", "Thunder Bot", "Bot Bot"]
    for index, name in enumerate(unlock_priority):
        record = bots.get(name, {}) if isinstance(bots.get(name, {}), Mapping) else {}
        unlocked = record.get("unlocked")
        domain = BOT_DOMAIN.get(name, "Utility")
        if unlocked is False:
            rows.append(_row(
                profile, priority=90.0 - index * 5.0, domain=domain, resource="Medals", system="Bots",
                upgrade=f"Unlock {name}", next_level="Unlocked", cost_text="Use the in-game medal price",
                confidence="Medium strategic", why=[f"{name} is marked locked"],
                focus=focus, analysis=analysis, death=death, path_rank=index + 1,
            ))
            continue
        if unlocked is not True:
            continue
        attrs = record.get("attributes", {}) if isinstance(record.get("attributes", {}), Mapping) else {}
        deficits = []
        for attr, (target, lower_better) in BOT_TARGETS.get(name, {}).items():
            current = _clean_number(attrs.get(attr))
            if lower_better:
                deficit = max(0.0, current / max(target, 1e-9) - 1.0)
            else:
                deficit = max(0.0, 1.0 - current / max(target, 1e-9))
            if deficit > 0.01:
                deficits.append((deficit, attr, current, target, lower_better))
        deficits.sort(reverse=True)
        if deficits:
            deficit, attr, current, target, lower_better = deficits[0]
            direction = "lower" if lower_better else "higher"
            rows.append(_row(
                profile, priority=68.0 + min(22.0, deficit * 25.0), domain=domain,
                resource="Medals", system="Bots", upgrade=f"{name} | {attr}",
                next_level=f"Move {direction} toward {target:g}", cost_text="Use the in-game medal price",
                confidence="Medium strategic",
                why=[f"current imported value is {current:g}", "target is a strategic benchmark, not a verified cap"],
                focus=focus, analysis=analysis, death=death,
            ))
    return rows


def _guardian_rows(profile: Mapping[str, Any], focus: str, analysis: Mapping[str, Any], death: str) -> list[Dict[str, Any]]:
    guardians = profile.get("guardians", {}) if isinstance(profile.get("guardians", {}), Mapping) else {}
    rows: list[Dict[str, Any]] = []
    unlock_priority = ["Bounty", "Fetch", "Ally", "Attack", "Summon", "Scout"]
    for index, name in enumerate(unlock_priority):
        record = guardians.get(name, {}) if isinstance(guardians.get(name, {}), Mapping) else {}
        unlocked = record.get("unlocked")
        domain = GUARDIAN_DOMAIN.get(name, "Utility")
        if unlocked is False:
            rows.append(_row(
                profile, priority=86.0 - index * 4.0, domain=domain, resource="Bits", system="Guardians",
                upgrade=f"Unlock {name} Guardian", next_level="Unlocked", cost_text="Use the in-game bit price",
                confidence="Medium strategic", why=[f"{name} is marked locked"],
                focus=focus, analysis=analysis, death=death, path_rank=index + 1,
            ))
            continue
        if unlocked is not True:
            continue
        attrs = record.get("attributes", {}) if isinstance(record.get("attributes", {}), Mapping) else {}
        deficits = []
        for attr, (target, lower_better) in GUARDIAN_TARGETS.get(name, {}).items():
            current = _clean_number(attrs.get(attr))
            if lower_better:
                deficit = max(0.0, current / max(target, 1e-9) - 1.0)
            else:
                deficit = max(0.0, 1.0 - current / max(target, 1e-9))
            if deficit > 0.01:
                deficits.append((deficit, attr, current, target, lower_better))
        deficits.sort(reverse=True)
        if deficits:
            deficit, attr, current, target, lower_better = deficits[0]
            direction = "lower" if lower_better else "higher"
            rows.append(_row(
                profile, priority=62.0 + min(20.0, deficit * 24.0), domain=domain,
                resource="Bits", system="Guardians", upgrade=f"{name} Guardian | {attr}",
                next_level=f"Move {direction} toward {target:g}", cost_text="Use the in-game bit price",
                confidence="Medium strategic",
                why=[f"current imported value is {current:g}", "target is a strategic benchmark, not a verified cap"],
                focus=focus, analysis=analysis, death=death,
            ))
    return rows


def _vault_rows(profile: Mapping[str, Any], focus: str, analysis: Mapping[str, Any], death: str) -> list[Dict[str, Any]]:
    vault = profile.get("vault", {}) if isinstance(profile.get("vault", {}), Mapping) else {}
    bonuses = vault.get("bonuses", {}) if isinstance(vault.get("bonuses", {}), Mapping) else {}
    unlocks = vault.get("unlocks", {}) if isinstance(vault.get("unlocks", {}), Mapping) else {}
    rows: list[Dict[str, Any]] = []
    ranked = []
    for name, record in bonuses.items():
        if not isinstance(record, Mapping):
            continue
        active = _clean_number(record.get("active"))
        total = _clean_number(record.get("total"))
        if active >= total and total >= 0:
            continue
        base, domain = VAULT_PRIORITY.get(str(name), (0.55, "Utility"))
        if total > 0:
            remaining = max(0.0, 1.0 - active / total)
        elif total < 0:
            remaining = 1.0 if active == 0 else 0.5
        else:
            continue
        ranked.append((base * (0.75 + 0.25 * remaining), str(name), active, total, domain))
    ranked.sort(reverse=True)
    for rank, (weight, name, active, total, domain) in enumerate(ranked[:8], start=1):
        rows.append(_row(
            profile, priority=62.0 + 35.0 * weight - rank, domain=domain, resource="Keys",
            system="Vault", upgrade=f"Vault | {name}", next_level="Next available node",
            cost_text="Use the Vault's displayed key cost", confidence="Medium strategic",
            why=[f"active {active:g} of listed total {total:g}", "prioritized by account-wide utility and opportunity cost"],
            focus=focus, analysis=analysis, death=death, path_rank=rank,
        ))
    unlock_ranked = []
    for name, owned in unlocks.items():
        if bool(owned):
            continue
        weight, domain = VAULT_UNLOCK_PRIORITY.get(str(name), (0.52, "Utility"))
        unlock_ranked.append((weight, str(name), domain))
    unlock_ranked.sort(reverse=True)
    for rank, (weight, name, domain) in enumerate(unlock_ranked[:4], start=1):
        rows.append(_row(
            profile, priority=58.0 + 34.0 * weight - rank, domain=domain, resource="Keys",
            system="Vault", upgrade=f"Unlock {name}", next_level="Unlocked",
            cost_text="Use the Vault's displayed key cost", confidence="Medium strategic",
            why=["the utility is currently marked locked"], focus=focus, analysis=analysis, death=death,
            path_rank=rank,
        ))
    return rows


def _relic_rows(profile: Mapping[str, Any], focus: str, analysis: Mapping[str, Any], death: str) -> list[Dict[str, Any]]:
    relics = profile.get("relics", {}) if isinstance(profile.get("relics", {}), Mapping) else {}
    items = relics.get("items", {}) if isinstance(relics.get("items", {}), Mapping) else {}
    ranked = []
    for name, record in items.items():
        if not isinstance(record, Mapping) or bool(record.get("owned")):
            continue
        bonus_type = str(record.get("bonus_type") or "").strip()
        weight, domain = RELIC_BONUS_PRIORITY.get(bonus_type, (0.45, "Utility"))
        value = abs(_clean_number(record.get("value")))
        source = str(record.get("unlocked_by") or record.get("event") or record.get("type") or "Unknown source")
        source_lower = source.casefold()
        obtainable_boost = 0.10 if any(term in source_lower for term in ["tier", "wave", "play", "mission", "event"]) else 0.0
        ranked.append((weight + min(0.12, value) + obtainable_boost, str(name), bonus_type, value, source, domain))
    ranked.sort(reverse=True)
    rows = []
    for rank, (weight, name, bonus_type, value, source, domain) in enumerate(ranked[:6], start=1):
        rows.append(_row(
            profile, priority=48.0 + 42.0 * min(1.15, weight) - rank, domain=domain,
            resource="Milestone / Event", system="Relics", upgrade=f"Target relic: {name}",
            next_level=f"Acquire {bonus_type or 'account bonus'}", cost_text=source,
            confidence="Medium strategic", why=[f"missing relic with {bonus_type or 'utility'} bonus {value:g}", f"listed source: {source}"],
            focus=focus, analysis=analysis, death=death, path_rank=rank,
        ))
    return rows


def _theme_rows(profile: Mapping[str, Any], focus: str, analysis: Mapping[str, Any], death: str) -> list[Dict[str, Any]]:
    themes = profile.get("themes", {}) if isinstance(profile.get("themes", {}), Mapping) else {}
    items = themes.get("items", {}) if isinstance(themes.get("items", {}), Mapping) else {}
    missing = []
    type_weight = {"Event Tower": 1.00, "Event Background": 0.98, "Songs": 0.80, "Tier Skin": 0.55}
    for key, record in items.items():
        if not isinstance(record, Mapping) or bool(record.get("owned")):
            continue
        item_type = str(record.get("type") or key.split("::", 1)[0])
        name = str(record.get("name") or key.split("::")[-1])
        weight = type_weight.get(item_type, 0.45)
        event = str(record.get("event") or record.get("source") or "")
        missing.append((weight, item_type, name, event))
    missing.sort(reverse=True)
    rows = []
    for rank, (weight, item_type, name, event) in enumerate(missing[:5], start=1):
        resource = "Medals" if item_type in {"Event Tower", "Event Background", "Songs"} else "Milestone / Event"
        rows.append(_row(
            profile, priority=50.0 + 35.0 * weight - rank, domain="Economy", resource=resource,
            system="Themes & Songs", upgrade=f"Acquire {item_type}: {name}", next_level="Owned",
            cost_text="Event shop / listed source" if not event else event, confidence="Medium strategic",
            why=["unowned cosmetic progression contributes to the account-wide bonus tracked by the companion sheet"],
            focus=focus, analysis=analysis, death=death, path_rank=rank,
        ))
    return rows


def build_progression_recommendations(
    profile_data: Dict[str, Any], *, focus: str = "Balanced",
    apply_death_weighting: bool = True,
) -> Dict[str, Any]:
    analysis = build_analysis(profile_data)
    death = native_latest_death(profile_data) if apply_death_weighting else ""
    generators = [
        _card_rows, _module_rows, _bot_rows, _guardian_rows,
        _vault_rows, _relic_rows, _theme_rows,
    ]
    rows: list[Dict[str, Any]] = []
    for generator in generators:
        rows.extend(generator(profile_data, focus, analysis, death))
    rows.sort(key=lambda item: float(item.get("Priority Index", 0.0)), reverse=True)
    by_system: Dict[str, list[Dict[str, Any]]] = {}
    for row in rows:
        by_system.setdefault(str(row.get("System", "Other")), []).append(row)
    return {
        "rows": rows,
        "by_system": by_system,
        "by_resource": {resource: [row for row in rows if row.get("Resource") == resource] for resource in RESOURCE_ORDER},
        "analysis": analysis,
        "latest_death": death or "No report saved",
        "method": (
            "Whole-account rows use transparent strategic benchmarks and imported ownership/level data. "
            "They do not claim exact ROI when a companion workbook does not expose a verified cost curve."
        ),
    }


def _apply_learning_feedback(profile: Dict[str, Any], rows: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Apply small, evidence-gated battle-history modifiers once per row."""
    modifiers = feedback_modifiers(profile)
    adjusted: list[Dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        if row.get("Learning Applied"):
            adjusted.append(row)
            continue
        record = modifiers.get(str(row.get("Domain", "")))
        if record:
            multiplier = float(record.get("multiplier", 1.0))
            row["Base Priority Index"] = row.get("Priority Index")
            row["Priority Index"] = round(float(row.get("Priority Index", 0.0)) * multiplier, 4)
            row["Learning Multiplier"] = round(multiplier, 4)
            reason = str(record.get("reason", "")).strip()
            if reason:
                existing = str(row.get("Why", "")).strip()
                row["Why"] = "; ".join(part for part in [existing, f"battle learning: {reason}"] if part)
        else:
            row["Learning Multiplier"] = 1.0
        row["Learning Applied"] = True
        adjusted.append(row)
    return sorted(adjusted, key=lambda item: float(item.get("Priority Index", 0.0)), reverse=True)


def _dedupe_rows(rows: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    chosen: Dict[tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("Resource", "")), str(row.get("Upgrade", "")).casefold().strip())
        if key not in chosen or float(row.get("Priority Index", 0.0)) > float(chosen[key].get("Priority Index", 0.0)):
            chosen[key] = row
    return sorted(chosen.values(), key=lambda item: float(item.get("Priority Index", 0.0)), reverse=True)


def build_combined_recommendations(
    profile_data: Dict[str, Any], steps: int = 12, candidates_per_path: int = 3,
    apply_death_weighting: bool = True, focus: str = "Balanced",
) -> Dict[str, Any]:
    """Return native-engine and whole-account recommendations in one schema."""
    native = deepcopy(build_native_combined_recommendations(
        profile_data, steps=steps, candidates_per_path=candidates_per_path,
        apply_death_weighting=apply_death_weighting, focus=focus,
    ))
    for row in native.get("rows", []):
        path_key = str(row.get("Path Key", ""))
        if path_key.endswith("_stone"):
            row.setdefault("System", "Ultimate Weapons")
        elif path_key.endswith("_lab") or path_key == "econ_discount":
            row.setdefault("System", "Laboratory")
        elif path_key.endswith("_coin"):
            row.setdefault("System", "Workshop / Enhancements")
        elif path_key.endswith("_key"):
            row.setdefault("System", "Vault")
        else:
            row.setdefault("System", "Native Engines")
    progression = build_progression_recommendations(
        profile_data, focus=focus, apply_death_weighting=apply_death_weighting,
    )
    rows = _apply_learning_feedback(profile_data, _dedupe_rows([*native.get("rows", []), *progression.get("rows", [])]))
    by_resource = {resource: [row for row in rows if row.get("Resource") == resource] for resource in RESOURCE_ORDER}
    by_system: Dict[str, list[Dict[str, Any]]] = {}
    for row in rows:
        system = str(row.get("System") or ("Native Engines" if not str(row.get("Path Key", "")).startswith("account_") else "Other"))
        by_system.setdefault(system, []).append(row)
    weakest = str(native.get("analysis", {}).get("weakest", ""))
    bottleneck = [row for row in rows if row.get("Domain") == weakest]
    latest_death = str(native.get("latest_death") or progression.get("latest_death") or "No report saved")
    if "vampire" in latest_death.casefold():
        favored = [row for row in rows if row.get("Domain") in {"Regen / Recovery", "Survivability"}]
        bottleneck = _dedupe_rows([*bottleneck, *favored])
    payload = {
        **native,
        "rows": rows,
        "by_resource": by_resource,
        "by_system": by_system,
        "affordable": [row for row in rows if row.get("Affordable Bool") is True],
        "long_term": [row for row in rows if row.get("Affordable Bool") is False],
        "unpriced": [row for row in rows if row.get("Affordable Bool") is None],
        "bottleneck": bottleneck,
        "latest_death": latest_death,
        "progression": progression,
        "method": (
            f"{native.get('method', '')} Whole-account systems are added with strategic, explainable scoring. "
            "Exact affordability is shown only when both a verified cost and an entered balance exist. "
            "Moderate/high-confidence battle observations may apply a small capped priority modifier when enabled."
        ).strip(),
    }
    return enrich_recommendation_payload(profile_data, payload)


__all__ = [
    "RESOURCE_ORDER", "build_progression_recommendations", "build_combined_recommendations",
]
