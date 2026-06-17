from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Tuple

from .engines.core import (
    ENHANCEMENT_MAX_LEVELS,
    LAB_ALIASES,
    LAB_MAX_LEVELS,
    UW_ATTRIBUTE_META,
    UW_NAMES,
    WORKSHOP_MAX_LEVELS,
)
from .reliability import SUPPORTED_WORKBOOK_VERSIONS, compare_versions, parse_version


WORKSHOP_ALIASES: Dict[str, str] = {
    "Super Crit Chance": "Super Critical Chance",
    "Super Crit Mult": "Super Critical Mult",
    "Thorns": "Thorn Damage",
    "Coins / Kill": "Coin / Kill Bonus",
    "Coins / Wave": "Coin / Wave",
    "Max Recovery": "Max Amount",
    "Recovery Package Chance": "Package Chance",
}

MODULE_RARITY_MAX_LEVELS: Dict[str, int] = {
    "Common": 20,
    "Rare": 40,
    "Epic": 60,
    "Epic+": 60,
    "Legendary": 80,
    "Legendary+": 80,
    "Mythic": 100,
    "Mythic+": 100,
    "Ancestral": 200,
}

SECTION_WORKBOOK_KIND = {
    "workshop": "Workshop",
    "enhancements": "Workshop",
    "labs": "Laboratory",
    "uw": "Ultimate Weapon",
    "module_inventory": "Modules",
    "module_presets": "Modules",
    "cards": "Cards",
    "relics": "Relics",
    "themes": "Themes & Songs",
    "bots": "Bots",
    "guardians": "Guardians",
    "vault": "Vault",
    "player": "Player & Stuff",
}

UW_LAB_PREFIXES: Dict[str, Tuple[str, ...]] = {
    "Golden Tower": ("Golden Tower",),
    "Black Hole": ("Black Hole", "Extra Black Hole"),
    "Death Wave": ("Death Wave",),
    "Spotlight": ("Spotlight",),
    "Chain Lightning": ("Chain Lightning", "Shock ", "Chain Thunder", "Lightning Amplifier"),
    "Smart Missiles": ("Missile", "Smart Missile"),
    "Chrono Field": ("Chrono Field",),
    "Inner Land Mines": ("Inner Mine", "Inner Land Mine"),
    "Poison Swamp": ("Swamp", "Poison Swamp"),
}


def _issue(
    severity: str,
    category: str,
    item: str,
    details: str,
    action: str = "",
    safe_fix: str = "",
) -> Dict[str, str]:
    return {
        "Severity": severity,
        "Category": category,
        "Item": item,
        "Details": details,
        "Suggested Action": action,
        "Safe Fix": safe_fix,
    }


def _numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _duplicate_names(values: Mapping[str, Any]) -> List[List[str]]:
    groups: Dict[str, List[str]] = {}
    for name in values:
        groups.setdefault(str(name).strip().casefold(), []).append(str(name))
    return [names for names in groups.values() if len(names) > 1]


def _source_version_status(section: str, source: Mapping[str, Any]) -> Tuple[str, str, str]:
    workbook_kind = SECTION_WORKBOOK_KIND.get(section, "")
    supported = SUPPORTED_WORKBOOK_VERSIONS.get(workbook_kind, "")
    found = str(source.get("version", ""))
    if not found:
        filename = str(source.get("filename", ""))
        found_tuple = parse_version(filename)
        found = ".".join(str(part) for part in found_tuple) if found_tuple else ""
    status = compare_versions(found, supported) if found and supported else "Unknown"
    return workbook_kind, found, status


def engine_readiness(profile: Mapping[str, Any]) -> List[Dict[str, Any]]:
    workshop_count = len(profile.get("workshop", {}))
    lab_count = len(profile.get("labs", {}))
    owned_uw = sum(bool(data.get("owned")) for data in profile.get("uw", {}).values() if isinstance(data, Mapping))
    run_count = len(profile.get("runs", []))
    reference_loaded = bool(profile.get("roi_reference", {}).get("imported_at"))
    return [
        {
            "Engine": "Economy",
            "Status": "Ready" if lab_count and owned_uw else "Limited",
            "Detail": f"{lab_count} lab values; {owned_uw} owned UWs",
            "Suggested Action": "Import Laboratory and Ultimate Weapon data." if not (lab_count and owned_uw) else "—",
        },
        {
            "Engine": "Damage",
            "Status": "Ready" if workshop_count and lab_count else "Limited",
            "Detail": f"{workshop_count} workshop values; {lab_count} lab values",
            "Suggested Action": "Import Workshop and Laboratory data." if not (workshop_count and lab_count) else "—",
        },
        {
            "Engine": "Health / Regen",
            "Status": "Ready" if workshop_count and lab_count else "Limited",
            "Detail": f"{workshop_count} workshop values; {lab_count} lab values",
            "Suggested Action": "Import Workshop and Laboratory data." if not (workshop_count and lab_count) else "—",
        },
        {
            "Engine": "Bottleneck weighting",
            "Status": "Ready" if run_count else "Optional input missing",
            "Detail": f"{run_count} saved battle reports",
            "Suggested Action": "Paste a recent Battle Report for death-cause weighting." if not run_count else "—",
        },
        {
            "Engine": "Effective Paths calibration",
            "Status": "Ready" if reference_loaded else "Optional input missing",
            "Detail": "ROI reference loaded" if reference_loaded else "Standalone engines remain usable",
            "Suggested Action": "Import a filled Effective Paths workbook only when calibration is desired." if not reference_loaded else "—",
        },
    ]


def profile_quality_report(profile: Mapping[str, Any]) -> Dict[str, Any]:
    issues: List[Dict[str, str]] = []

    section_specs = [
        ("workshop", WORKSHOP_MAX_LEVELS, WORKSHOP_ALIASES),
        ("labs", LAB_MAX_LEVELS, LAB_ALIASES),
        ("enhancements", ENHANCEMENT_MAX_LEVELS, {}),
    ]
    for section, caps, aliases in section_specs:
        values = profile.get(section, {})
        gold = profile.get("maxed", {}).get(section, {})
        if not isinstance(values, Mapping):
            issues.append(_issue("Error", section.title(), "Section", "Section is not a key/value mapping.", "Restore a valid profile backup."))
            continue

        for names in _duplicate_names(values):
            issues.append(_issue(
                "Warning", section.title(), ", ".join(names),
                "Duplicate names differ only by capitalization or spacing.",
                "Keep the canonical entry and remove the duplicate.",
            ))

        for name, raw in values.items():
            canonical = aliases.get(name, name)
            if name in aliases:
                issues.append(_issue(
                    "Warning", section.title(), name,
                    f"Outdated name; current canonical name is {canonical!r}.",
                    "Run safe fixes to migrate the name.",
                    "Rename alias",
                ))
            if canonical not in caps:
                issues.append(_issue(
                    "Info", section.title(), name,
                    "Entry is not in the bundled game-data catalog.",
                    "Check whether the game or source workbook is newer than this app.",
                ))
                continue
            value = _numeric(raw)
            cap = caps[canonical]
            if value is None:
                issues.append(_issue("Error", section.title(), name, f"Non-numeric level: {raw!r}.", "Enter a numeric level."))
                continue
            if value < 0:
                issues.append(_issue("Error", section.title(), name, f"Negative level: {value:g}.", "Set the level to 0 or higher."))
            if value > cap:
                issues.append(_issue(
                    "Error", section.title(), name,
                    f"Level {value:g} exceeds bundled maximum {cap:g}.",
                    "Verify against a newer workbook before changing the value.",
                ))
            is_gold = bool(gold.get(name, gold.get(canonical, False)))
            if value >= cap and not is_gold:
                issues.append(_issue("Info", section.title(), name, "At maximum but not marked Gold.", "Run safe fixes.", "Set Gold"))
            if value < cap and is_gold:
                issues.append(_issue("Warning", section.title(), name, f"Marked Gold below maximum {cap:g}.", "Run safe fixes.", "Clear Gold"))

    for uw_name, data in profile.get("uw", {}).items():
        if uw_name not in UW_NAMES:
            issues.append(_issue("Info", "Ultimate Weapons", uw_name, "Unknown UW name in profile.", "Check for a game-data update or spelling difference."))
            continue
        if not isinstance(data, Mapping):
            issues.append(_issue("Error", "Ultimate Weapons", uw_name, "UW data is not a mapping.", "Re-import Ultimate Weapon data."))
            continue
        if not data.get("owned"):
            continue
        attrs = data.get("attributes", {})
        if not isinstance(attrs, Mapping):
            issues.append(_issue("Error", "Ultimate Weapons", uw_name, "Attributes are not a mapping.", "Re-import Ultimate Weapon data."))
            continue
        for attr, meta in UW_ATTRIBUTE_META[uw_name].items():
            if attr not in attrs:
                issues.append(_issue("Warning", "Ultimate Weapons", f"{uw_name} — {attr}", "Owned UW is missing this attribute.", "Re-import or enter it manually."))
                continue
            value = _numeric(attrs.get(attr))
            if value is None:
                issues.append(_issue("Error", "Ultimate Weapons", f"{uw_name} — {attr}", "Attribute is non-numeric.", "Enter a numeric value."))
                continue
            maximum = float(meta.get("max", 0))
            if meta.get("lower_is_better"):
                start = float(meta.get("start", maximum))
                if value < maximum or value > start:
                    issues.append(_issue("Error", "Ultimate Weapons", f"{uw_name} — {attr}", f"Value {value:g} is outside {maximum:g}–{start:g}.", "Verify the imported value."))
            elif value < 0 or value > maximum:
                issues.append(_issue("Error", "Ultimate Weapons", f"{uw_name} — {attr}", f"Value {value:g} exceeds maximum {maximum:g}.", "Verify the imported value."))

    labs = profile.get("labs", {})
    for uw_name, prefixes in UW_LAB_PREFIXES.items():
        owned = bool(profile.get("uw", {}).get(uw_name, {}).get("owned"))
        if owned:
            continue
        active_labs = [
            name for name, value in labs.items()
            if _numeric(value) and _numeric(value) > 0 and any(str(name).startswith(prefix) for prefix in prefixes)
        ]
        if active_labs:
            issues.append(_issue(
                "Warning", "Unlocks", uw_name,
                f"UW-specific labs have levels but the UW is marked locked: {', '.join(active_labs[:5])}.",
                "Correct the UW owned flag or verify the lab import.",
            ))

    for slot, module in profile.get("modules", {}).items():
        if not isinstance(module, Mapping):
            issues.append(_issue("Error", "Modules", str(slot), "Module entry is not a mapping.", "Re-import Modules."))
            continue
        rarity = str(module.get("rarity", ""))
        level = _numeric(module.get("level", 0))
        if level is not None and rarity in MODULE_RARITY_MAX_LEVELS and level > MODULE_RARITY_MAX_LEVELS[rarity]:
            issues.append(_issue("Error", "Modules", str(slot), f"Level {level:g} exceeds the {rarity} cap of {MODULE_RARITY_MAX_LEVELS[rarity]}.", "Verify rarity and level."))

    for card, data in profile.get("cards", {}).get("items", {}).items():
        if not isinstance(data, Mapping):
            continue
        level = _numeric(data.get("level", 0))
        mastery = _numeric(data.get("mastery", 0))
        if level is not None and not 0 <= level <= 7:
            issues.append(_issue("Error", "Cards", card, f"Card level {level:g} is outside 0–7.", "Correct the card level."))
        if mastery is not None and not 0 <= mastery <= 9:
            issues.append(_issue("Error", "Cards", card, f"Mastery {mastery:g} is outside 0–9.", "Correct the mastery level."))

    for section, source in profile.get("sources", {}).items():
        if not isinstance(source, Mapping) or section == "roi_reference":
            continue
        workbook_kind, found, status = _source_version_status(section, source)
        if status == "Newer than supported":
            issues.append(_issue(
                "Warning", "Source Versions", workbook_kind or section,
                f"Imported source {found or 'unknown'} is newer than the bundled supported version {SUPPORTED_WORKBOOK_VERSIONS.get(workbook_kind, 'unknown')}.",
                "Use System & Updates to compare workbook changes before trusting maximums.",
            ))
        elif status == "Older than supported":
            issues.append(_issue(
                "Info", "Source Versions", workbook_kind or section,
                f"Imported source {found or 'unknown'} is older than supported version {SUPPORTED_WORKBOOK_VERSIONS.get(workbook_kind, 'unknown')}.",
                "Re-import a current companion workbook when convenient.",
            ))

    readiness = engine_readiness(profile)
    for row in readiness:
        if row["Status"] == "Limited":
            issues.append(_issue("Warning", "Engine Readiness", row["Engine"], row["Detail"], row["Suggested Action"]))

    counts = Counter(issue["Severity"] for issue in issues)
    penalty = 18 * counts.get("Error", 0) + 6 * counts.get("Warning", 0) + 1 * counts.get("Info", 0)
    score = max(0, min(100, 100 - penalty))
    overall = "FAIL" if counts.get("Error", 0) else ("WARN" if counts.get("Warning", 0) else "PASS")
    return {
        "overall": overall,
        "score": score,
        "counts": {"Error": counts.get("Error", 0), "Warning": counts.get("Warning", 0), "Info": counts.get("Info", 0)},
        "issues": issues,
        "readiness": readiness,
    }


def apply_safe_fixes(profile: MutableMapping[str, Any]) -> Dict[str, Any]:
    changes: List[str] = []
    for section, caps, aliases in [
        ("workshop", WORKSHOP_MAX_LEVELS, WORKSHOP_ALIASES),
        ("labs", LAB_MAX_LEVELS, LAB_ALIASES),
        ("enhancements", ENHANCEMENT_MAX_LEVELS, {}),
    ]:
        values = profile.setdefault(section, {})
        maxed = profile.setdefault("maxed", {}).setdefault(section, {})
        for old, new in aliases.items():
            if old not in values:
                continue
            old_value = values.pop(old)
            if new not in values or not values.get(new):
                values[new] = old_value
            if old in maxed:
                maxed[new] = bool(maxed.get(new, False) or maxed.pop(old))
            changes.append(f"Renamed {section}: {old} → {new}")
        for name, cap in caps.items():
            if name not in values:
                continue
            value = _numeric(values.get(name))
            if value is None:
                continue
            should_gold = value >= cap
            if bool(maxed.get(name, False)) != should_gold:
                maxed[name] = should_gold
                changes.append(f"Updated Gold flag: {section} / {name}")
    return {"changed": len(changes), "changes": changes}
