"""Pure data models for the v2 visual preview.

The functions in this module intentionally avoid Streamlit so they can be tested
from the command line and reused by a future desktop or web front end.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from functools import reduce
from math import gcd
from typing import Any, Dict, Iterable, Mapping, Optional

UW_DISPLAY = {
    "Golden Tower": {"short": "GT", "kind": "economy"},
    "Black Hole": {"short": "BH", "kind": "control"},
    "Death Wave": {"short": "DW", "kind": "damage"},
}

RARITY_ORDER = [
    "Common", "Rare", "Rare+", "Epic", "Epic+", "Legendary", "Legendary+",
    "Mythic", "Mythic+", "Ancestral", "Ancestral 1*", "Ancestral 2*",
    "Ancestral 3*", "Ancestral 4*", "Ancestral 5*",
]
RARITY_RANK = {name.casefold(): index for index, name in enumerate(RARITY_ORDER)}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _integer(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return int(default)
        return int(round(float(value)))
    except (TypeError, ValueError):
        return int(default)


def format_duration(seconds: Any) -> str:
    total = max(0, _integer(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes:d}m {secs:02d}s"
    return f"{secs:d}s"


def _lcm(a: int, b: int) -> int:
    if a <= 0 or b <= 0:
        return 0
    return abs(a * b) // gcd(a, b)


def lcm_many(values: Iterable[int]) -> int:
    cleaned = [int(value) for value in values if int(value) > 0]
    return reduce(_lcm, cleaned, 1) if cleaned else 0


def _uw_record(profile: Mapping[str, Any], name: str) -> Dict[str, Any]:
    record = profile.get("uw", {}).get(name, {}) if isinstance(profile.get("uw", {}), Mapping) else {}
    attrs = record.get("attributes", {}) if isinstance(record.get("attributes", {}), Mapping) else {}
    cooldown = _number(attrs.get("Cooldown", record.get("cooldown", 0)))
    duration = _number(attrs.get("Duration", record.get("duration", 0)))
    quantity = _number(attrs.get("Quantity", record.get("quantity", 0)))
    return {
        "name": name,
        "short": UW_DISPLAY.get(name, {}).get("short", name[:2].upper()),
        "kind": UW_DISPLAY.get(name, {}).get("kind", "utility"),
        "owned": bool(record.get("owned", False)),
        "cooldown": cooldown,
        "cooldown_seconds": max(0, _integer(cooldown)),
        "duration": duration,
        "quantity": quantity,
    }


def _pair_sync(left: Mapping[str, Any], right: Mapping[str, Any]) -> Dict[str, Any]:
    left_cd = _integer(left.get("cooldown_seconds"))
    right_cd = _integer(right.get("cooldown_seconds"))
    available = bool(left.get("owned")) and bool(right.get("owned")) and left_cd > 0 and right_cd > 0
    common = _lcm(left_cd, right_cd) if available else 0
    if available and common:
        activations_left = common // left_cd
        activations_right = common // right_cd
        ratio_gcd = gcd(activations_left, activations_right) or 1
        ratio = f"{activations_left // ratio_gcd}:{activations_right // ratio_gcd}"
    else:
        activations_left = activations_right = 0
        ratio = "—"
    return {
        "left": left.get("name", ""),
        "right": right.get("name", ""),
        "left_short": left.get("short", ""),
        "right_short": right.get("short", ""),
        "available": available,
        "exact": bool(available and left_cd == right_cd),
        "ratio": ratio,
        "overlap_seconds": common,
        "overlap_text": format_duration(common) if common else "Unavailable",
        "activations": {str(left.get("short", "L")): activations_left, str(right.get("short", "R")): activations_right},
    }


def build_sync_timeline(report: Mapping[str, Any], *, horizon_seconds: Optional[int] = None, max_markers: int = 60) -> Dict[str, Any]:
    weapons = report.get("weapons", {}) if isinstance(report.get("weapons", {}), Mapping) else {}
    owned = [row for row in weapons.values() if row.get("owned") and _integer(row.get("cooldown_seconds")) > 0]
    if not owned:
        return {"horizon_seconds": 0, "lanes": [], "collisions": []}
    triple = _integer(report.get("triple_overlap_seconds"))
    if horizon_seconds is None:
        horizon_seconds = triple if triple > 0 else max(_integer(row.get("cooldown_seconds")) for row in owned) * 3
    horizon_seconds = max(1, min(int(horizon_seconds), 3600))
    lanes = []
    time_map: Dict[int, list[str]] = defaultdict(list)
    for row in owned:
        cooldown = max(1, _integer(row.get("cooldown_seconds")))
        markers = list(range(0, horizon_seconds + 1, cooldown))[:max_markers]
        lanes.append({"name": row.get("name"), "short": row.get("short"), "markers": markers, "cooldown": cooldown})
        for marker in markers:
            time_map[marker].append(str(row.get("short")))
    collisions = [
        {"time": second, "weapons": labels, "count": len(labels)}
        for second, labels in sorted(time_map.items()) if len(labels) >= 2
    ]
    return {"horizon_seconds": horizon_seconds, "lanes": lanes, "collisions": collisions}


def build_sync_report(profile: Mapping[str, Any]) -> Dict[str, Any]:
    weapon_rows = [_uw_record(profile, name) for name in UW_DISPLAY]
    weapons = {row["name"]: row for row in weapon_rows}
    gt, bh, dw = (weapons[name] for name in UW_DISPLAY)
    pairs = [_pair_sync(gt, bh), _pair_sync(gt, dw), _pair_sync(bh, dw)]
    owned = [row for row in weapon_rows if row.get("owned") and _integer(row.get("cooldown_seconds")) > 0]
    triple_available = len(owned) == 3
    triple_overlap = lcm_many(_integer(row.get("cooldown_seconds")) for row in owned) if triple_available else 0
    exact_triple = bool(triple_available and len({_integer(row.get("cooldown_seconds")) for row in owned}) == 1)
    gt_bh = pairs[0]
    if not gt.get("owned") or not bh.get("owned"):
        status = "GT/BH incomplete"
        recommendation = "The core economy pair is not fully owned in this profile."
        severity = "warning"
    elif gt_bh.get("exact") and dw.get("owned") and exact_triple:
        status = "Exact GT/BH/DW sync"
        recommendation = "Protect the 1:1:1 cooldown alignment before changing any one cooldown."
        severity = "excellent"
    elif gt_bh.get("exact") and dw.get("owned"):
        status = "GT/BH exact; DW partial"
        recommendation = (
            f"GT and BH are protected at 1:1. Death Wave joins every {format_duration(triple_overlap)}. "
            "Model a direct DW target before changing the synced pair."
        )
        severity = "good"
    elif gt_bh.get("available"):
        status = f"GT/BH {gt_bh.get('ratio')} partial sync"
        recommendation = (
            f"GT and BH currently overlap every {gt_bh.get('overlap_text')}. "
            "Compare stone costs before moving either cooldown."
        )
        severity = "review"
    else:
        status = "Sync data incomplete"
        recommendation = "Enter owned status and cooldowns for GT, BH, and DW."
        severity = "warning"
    if not dw.get("owned"):
        recommendation += " Death Wave is not marked owned, so a three-way sync is not evaluated."
    report = {
        "weapons": weapons,
        "pairs": pairs,
        "status": status,
        "severity": severity,
        "recommendation": recommendation,
        "triple_available": triple_available,
        "exact_triple": exact_triple,
        "triple_overlap_seconds": triple_overlap,
        "triple_overlap_text": format_duration(triple_overlap) if triple_overlap else "Unavailable",
        "cooldown_spread": (max((_integer(row.get("cooldown_seconds")) for row in owned), default=0) - min((_integer(row.get("cooldown_seconds")) for row in owned), default=0)),
        "mvn_detected": detect_multiverse_nexus(profile),
    }
    report["timeline"] = build_sync_timeline(report)
    return report


def detect_multiverse_nexus(profile: Mapping[str, Any]) -> bool:
    modules = profile.get("modules", {}) if isinstance(profile.get("modules", {}), Mapping) else {}
    core = modules.get("Core", {}) if isinstance(modules.get("Core", {}), Mapping) else {}
    if "multiverse nexus" in str(core.get("name", "")).casefold():
        return True
    presets = profile.get("module_presets", {}) if isinstance(profile.get("module_presets", {}), Mapping) else {}
    for preset in presets.values():
        if not isinstance(preset, Mapping):
            continue
        slot = preset.get("Core", {}) if isinstance(preset.get("Core", {}), Mapping) else {}
        if "multiverse nexus" in " ".join(str(slot.get(key, "")) for key in ("primary", "assist")).casefold():
            return True
    return False


def build_card_report(profile: Mapping[str, Any]) -> Dict[str, Any]:
    cards = profile.get("cards", {}) if isinstance(profile.get("cards", {}), Mapping) else {}
    items = cards.get("items", {}) if isinstance(cards.get("items", {}), Mapping) else {}
    slots = max(0, _integer(cards.get("slots")))
    target = max(slots, _integer(cards.get("slot_target"), slots or 1))
    vault = profile.get("vault", {}) if isinstance(profile.get("vault", {}), Mapping) else {}
    bonuses = vault.get("bonuses", {}) if isinstance(vault.get("bonuses", {}), Mapping) else {}
    additional_slot = bonuses.get("Additional Card Slot", {}) if isinstance(bonuses.get("Additional Card Slot", {}), Mapping) else {}
    vault_slots = max(0, _integer(additional_slot.get("active")))
    levels = [_integer(row.get("level")) for row in items.values() if isinstance(row, Mapping)]
    masteries = [_integer(row.get("mastery")) for row in items.values() if isinstance(row, Mapping)]
    owned = sum(1 for value in levels if value > 0)
    max_level = max(levels, default=0)
    maxed = sum(1 for value in levels if max_level > 0 and value >= max_level)
    mastered = sum(1 for value in masteries if value > 0)
    level_distribution = Counter(levels)
    progress = min(1.0, slots / target) if target > 0 else 0.0
    return {
        "slots": slots,
        "target": target,
        "remaining_to_target": max(0, target - slots),
        "progress": progress,
        "vault_slots_reported": vault_slots,
        "card_count": len(items),
        "owned_cards": owned,
        "max_card_level_seen": max_level,
        "cards_at_max_seen": maxed,
        "mastered_cards": mastered,
        "average_level": (sum(levels) / len(levels)) if levels else 0.0,
        "level_distribution": dict(sorted(level_distribution.items())),
    }


def _inventory_records(profile: Mapping[str, Any]) -> list[Dict[str, Any]]:
    inventory = profile.get("module_inventory", {}) if isinstance(profile.get("module_inventory", {}), Mapping) else {}
    rows: list[Dict[str, Any]] = []
    for key, source in inventory.items():
        if not isinstance(source, Mapping):
            continue
        row = deepcopy(dict(source))
        if not row.get("slot") and "::" in str(key):
            row["slot"] = str(key).split("::", 1)[0]
        if not row.get("name") and "::" in str(key):
            row["name"] = str(key).split("::", 1)[1]
        row["key"] = str(key)
        row["copies"] = max(0, _integer(row.get("copies"), 1 if row.get("name") else 0))
        row["locked"] = bool(row.get("locked", False))
        row["rarity"] = str(row.get("rarity") or "Unknown")
        row["level"] = max(0, _integer(row.get("level")))
        rows.append(row)
    return rows


def build_module_forge_report(profile: Mapping[str, Any]) -> Dict[str, Any]:
    rows = _inventory_records(profile)
    by_slot: Dict[str, list[Dict[str, Any]]] = defaultdict(list)
    by_rarity: Counter[str] = Counter()
    total_copies = 0
    for row in rows:
        slot = str(row.get("slot") or "Unknown")
        by_slot[slot].append(row)
        copies = max(0, _integer(row.get("copies")))
        total_copies += copies
        by_rarity[str(row.get("rarity") or "Unknown")] += copies
    exact_candidates = [
        row for row in rows
        if _integer(row.get("copies")) >= 2 and row.get("name") and str(row.get("name")).casefold() != "any other"
    ]
    exact_candidates.sort(
        key=lambda row: (RARITY_RANK.get(str(row.get("rarity", "")).casefold(), -1), _integer(row.get("copies")), _integer(row.get("level"))),
        reverse=True,
    )
    locked = [row for row in rows if row.get("locked")]
    forge = profile.get("module_forge", {}) if isinstance(profile.get("module_forge", {}), Mapping) else {}
    fodder = forge.get("fodder", {}) if isinstance(forge.get("fodder", {}), Mapping) else {}
    fodder_total = 0
    fodder_rows = []
    for slot, rarities in fodder.items():
        if not isinstance(rarities, Mapping):
            continue
        for rarity, count in rarities.items():
            number = max(0, _integer(count))
            fodder_total += number
            fodder_rows.append({"slot": str(slot), "rarity": str(rarity), "count": number})
    warnings = []
    if any(not row.get("locked") and "ancestral" in str(row.get("rarity", "")).casefold() for row in rows):
        warnings.append("At least one Ancestral module is not protected by the local lock flag.")
    if not rows:
        warnings.append("No module inventory is loaded.")
    return {
        "rows": rows,
        "by_slot": dict(by_slot),
        "by_rarity": dict(by_rarity),
        "module_names": len(rows),
        "total_copies": total_copies,
        "exact_copy_candidates": exact_candidates,
        "locked": locked,
        "fodder_rows": fodder_rows,
        "fodder_total": fodder_total,
        "warnings": warnings,
        "method": (
            "Preview mode uses only user-entered copy counts and generic fodder pools. "
            "It never labels a named unique module as safe fodder and does not yet execute a full merge recipe."
        ),
    }


def build_relic_report(profile: Mapping[str, Any]) -> Dict[str, Any]:
    relics = profile.get("relics", {}) if isinstance(profile.get("relics", {}), Mapping) else {}
    items = relics.get("items", {}) if isinstance(relics.get("items", {}), Mapping) else {}
    rows = []
    rarity_counts: Counter[str] = Counter()
    bonus_counts: Counter[str] = Counter()
    for name, source in items.items():
        if not isinstance(source, Mapping):
            continue
        row = dict(source)
        row["name"] = str(name)
        row["owned"] = bool(row.get("owned", False))
        row["rarity"] = str(row.get("rarity") or "Unknown")
        row["bonus_type"] = str(row.get("bonus_type") or "Unknown")
        rows.append(row)
        if row["owned"]:
            rarity_counts[row["rarity"]] += 1
            bonus_counts[row["bonus_type"]] += 1
    owned = sum(1 for row in rows if row.get("owned"))
    return {
        "rows": rows,
        "owned": owned,
        "total": len(rows),
        "missing": max(0, len(rows) - owned),
        "progress": owned / len(rows) if rows else 0.0,
        "rarity_counts": dict(rarity_counts),
        "bonus_counts": dict(bonus_counts),
    }


def build_overview_model(profile: Mapping[str, Any], recommendations: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    resources = profile.get("resources", {}) if isinstance(profile.get("resources", {}), Mapping) else {}
    runs = profile.get("runs", []) if isinstance(profile.get("runs", []), list) else []
    valid_runs = [row for row in runs if isinstance(row, Mapping)]
    latest = valid_runs[-1] if valid_runs else {}
    rows = recommendations.get("rows", []) if isinstance(recommendations, Mapping) else []
    analysis = recommendations.get("analysis", {}) if isinstance(recommendations, Mapping) else {}
    return {
        "profile_name": str(profile.get("name") or "default"),
        "resources": {
            "coins": _number(resources.get("coins")),
            "stones": _number(resources.get("stones")),
            "gems": _number(resources.get("gems")),
            "medals": _number(resources.get("medals")),
            "keys": _number(resources.get("keys")),
            "bits": _number(resources.get("bits")),
        },
        "sync": build_sync_report(profile),
        "cards": build_card_report(profile),
        "modules": build_module_forge_report(profile),
        "relics": build_relic_report(profile),
        "top_recommendations": list(rows[:5]),
        "weakest": str(analysis.get("weakest") or "Not modeled"),
        "latest_death": str((recommendations or {}).get("latest_death") or latest.get("killed_by") or "No report saved"),
        "run_count": len(valid_runs),
        "latest_run": dict(latest),
    }


__all__ = [
    "RARITY_ORDER", "build_card_report", "build_module_forge_report",
    "build_overview_model", "build_relic_report", "build_sync_report",
    "build_sync_timeline", "detect_multiverse_nexus", "format_duration",
    "lcm_many",
]
