"""Robust parser for copied The Tower battle reports.

This module intentionally has no Streamlit dependency so it can be tested in
isolation and reused by command-line tools, the desktop build, and the web UI.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

NUMBER_SUFFIXES = {
    "": 1.0,
    "K": 1e3,
    "M": 1e6,
    "B": 1e9,
    "T": 1e12,
    "q": 1e15,
    "Q": 1e18,
    "s": 1e21,
    "S": 1e24,
    "O": 1e27,
    "N": 1e30,
    "D": 1e33,
}

SECTION_HEADINGS = {
    "records": "records",
    "damage": "damage",
    "damage taken": "damage_taken",
    "bonus health gained": "bonus_health_gained",
    "health regenerated": "health_regenerated",
    "damage blocked": "damage_blocked",
    "utility": "utility",
    "counts": "counts",
    "enemies hit by": "enemies_hit_by",
    "killed with effect active": "killed_with_effect_active",
    "total enemies": "total_enemies",
    "coins": "coins",
    "cash": "cash",
    "currencies": "currencies",
    "enemies destroyed by": "enemies_destroyed_by",
}

SECTION_METRIC_ALIASES = {
    ("damage", "projectiles"): "projectiles_damage",
    ("damage", "thorns"): "thorn_damage",
    ("damage", "orbs"): "orb_damage",
    ("damage", "black_hole"): "black_hole_damage",
    ("damage", "death_ray"): "death_ray_damage",
    ("damage_taken", "tower"): "damage_taken",
    ("damage_taken", "wall"): "damage_taken_wall",
    ("health_regenerated", "lifesteal"): "lifesteal",
    ("coins", "golden_tower"): "coins_from_golden_tower",
    ("coins", "black_hole"): "coins_from_black_hole",
    ("coins", "spotlight"): "coins_from_spotlight",
    ("coins", "death_wave"): "coins_from_death_wave",
    ("total_enemies", "protector"): "protectors",
    ("total_enemies", "protectors"): "protectors",
    ("enemies_destroyed_by", "orbs"): "destroyed_by_orbs",
    ("enemies_destroyed_by", "thorns"): "destroyed_by_thorns",
    ("enemies_destroyed_by", "death_ray"): "destroyed_by_death_ray",
}

CORE_TEXT_LABELS = (
    "Battle Date",
    "Game Time",
    "Real Time",
    "Tier",
    "Wave",
    "Killed By",
)


def normalize_report_text(value: Any) -> str:
    """Normalize clipboard whitespace while preserving report line structure."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for char in ("\u00a0", "\u2007", "\u202f"):
        text = text.replace(char, " ")
    for char in ("\u200b", "\u200c", "\u200d", "\ufeff"):
        text = text.replace(char, "")
    return text


def split_battle_reports(report_text: str) -> list[str]:
    """Split one clipboard payload into individual Battle Reports.

    The game places a ``Battle Report`` heading at the start of every copied
    report. Keeping this logic in the parser module lets both Streamlit pages,
    tests, and future desktop builds share identical batch behavior.
    """
    text = normalize_report_text(report_text).strip()
    if not text:
        return []

    # Split at every standalone Battle Report heading while retaining it in
    # each chunk. A payload without the heading is treated as one report so
    # older/manual clipboard formats remain supported.
    chunks = re.split(r"(?im)(?=^\s*Battle Report\s*$)", text)
    chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
    return chunks or [text]


def parse_battle_report_batch(report_text: str) -> Dict[str, Any]:
    """Parse one or more pasted reports and collect per-report errors."""
    chunks = split_battle_reports(report_text)
    parsed: list[Dict[str, Any]] = []
    errors: list[Dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        try:
            parsed.append(parse_battle_report_text(chunk))
        except Exception as exc:
            errors.append({
                "report": index,
                "error": str(exc),
                "preview": " ".join(chunk.split())[:180],
            })
    return {
        "total": len(chunks),
        "parsed": parsed,
        "errors": errors,
    }


def parse_tower_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "N/A"}:
        return None
    text = text.replace("$", "").replace("%", "").replace("×", "x")
    if text.lower().startswith("x"):
        text = text[1:]
    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*([KMBTqQsSOND]?)", text)
    if not match:
        try:
            return float(text)
        except ValueError:
            return None
    return float(match.group(1)) * NUMBER_SUFFIXES.get(match.group(2), 1.0)


def parse_duration_seconds(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    text = str(value).strip().lower()
    if not text:
        return None
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    total = 0
    found = False
    for amount, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([dhms])", text):
        total += int(float(amount) * units[unit])
        found = True
    return total if found else None


def canonical_report_key(key: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
    aliases = {
        "battle_date": "battle_date",
        "game_time": "game_time",
        "real_time": "real_time",
        "tier": "tier",
        "wave": "wave",
        "killed_by": "killed_by",
        "coins_earned": "coins_earned",
        "coins_per_hour": "coins_per_hour",
        "cells_earned": "cells_earned",
        "cells_per_hour": "cells_per_hour",
        "cash_earned": "cash_earned",
        "reroll_shards_earned": "reroll_shards_earned",
        "damage_dealt": "damage_dealt",
        "waves_skipped": "waves_skipped",
        "recovery_packages": "recovery_packages",
        "free_attack_upgrade": "free_attack_upgrade",
        "free_defense_upgrade": "free_defense_upgrade",
        "free_utility_upgrade": "free_utility_upgrade",
        "total_enemies": "total_enemies",
        "vampires": "vampires",
        "rays": "rays",
        "scatters": "scatters",
        "protector": "protectors",
        "protectors": "protectors",
    }
    return aliases.get(cleaned, cleaned)


def _split_label_value(line: str) -> Optional[Tuple[str, str]]:
    # Text fields are parsed before numeric lines because their values contain spaces.
    for label in CORE_TEXT_LABELS:
        match = re.match(rf"^{re.escape(label)}\s*(?::|=|-)?\s+(.+?)\s*$", line, re.IGNORECASE)
        if match:
            return label, match.group(1).strip()

    # Most report rows end in one Tower-formatted number. Splitting from the end
    # avoids hard-coding every current and future label.
    match = re.match(
        r"^(.+?\S)\s+(\$?x?[+-]?\d[\d,.]*(?:\.\d+)?\s*[KMBTqQsSOND%]?)\s*$",
        line,
    )
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None


def _extract_core_field(text: str, label: str) -> Optional[str]:
    # Preferred line-oriented form.
    match = re.search(rf"(?im)^\s*{re.escape(label)}\s*(?::|=|-)?\s+(.+?)\s*$", text)
    if match:
        return match.group(1).strip()

    # Clipboard fall-back for reports flattened to one long line. Limit numeric
    # fields tightly so a later label cannot be swallowed.
    if label in {"Tier", "Wave"}:
        match = re.search(rf"(?i)\b{re.escape(label)}\s*(?::|=|-)?\s*(\d+)\b", text)
        return match.group(1) if match else None
    return None


def parse_battle_report_text(report_text: str) -> Dict[str, Any]:
    original_text = str(report_text or "")
    text = normalize_report_text(original_text)
    if not text.strip():
        raise ValueError("Paste a Battle Report before parsing.")

    raw_values: Dict[str, str] = {}
    section = "general"

    for raw_line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line or line.casefold() == "battle report":
            continue

        section_name = SECTION_HEADINGS.get(line.casefold())
        if section_name:
            section = section_name
            continue

        parsed = _split_label_value(line)
        if not parsed:
            continue

        label, value = parsed
        key = canonical_report_key(label)
        section_key = f"{section}__{key}"
        raw_values[section_key] = value

        # General fields and first-seen labels remain available under their
        # historical unqualified key for backward compatibility.
        if section == "general" or key not in raw_values:
            raw_values[key] = value

        mapped_key = SECTION_METRIC_ALIASES.get((section, key))
        if mapped_key:
            raw_values[mapped_key] = value

    # Direct extraction makes Tier/Wave resilient to non-breaking spaces,
    # punctuation variants, and flattened clipboard text.
    for label in CORE_TEXT_LABELS:
        key = canonical_report_key(label)
        if not raw_values.get(key):
            value = _extract_core_field(text, label)
            if value:
                raw_values[key] = value
                raw_values[f"general__{key}"] = value

    tier = int(parse_tower_number(raw_values.get("tier")) or 0)
    wave = int(parse_tower_number(raw_values.get("wave")) or 0)
    if tier <= 0 or wave <= 0:
        found = ", ".join(sorted(k for k in ("tier", "wave") if raw_values.get(k))) or "neither field"
        raise ValueError(
            "Could not find a valid Tier and Wave in the pasted report "
            f"(found {found}). Copy the report from its 'Battle Report' heading through the final row."
        )

    numeric_keys = [
        "coins_earned", "coins_per_hour", "cash_earned", "cells_earned", "cells_per_hour",
        "reroll_shards_earned", "damage_dealt", "damage_taken", "damage_taken_wall",
        "lifesteal", "projectiles_damage", "thorn_damage", "orb_damage",
        "black_hole_damage", "death_ray_damage", "waves_skipped", "recovery_packages",
        "free_attack_upgrade", "free_defense_upgrade", "free_utility_upgrade",
        "coins_from_golden_tower", "coins_from_black_hole", "coins_from_spotlight",
        "coins_from_death_wave", "total_enemies", "vampires", "rays", "scatters",
        "protectors", "destroyed_by_orbs", "destroyed_by_thorns", "destroyed_by_death_ray",
    ]
    parsed_numbers = {key: parse_tower_number(raw_values.get(key)) for key in numeric_keys}
    game_seconds = parse_duration_seconds(raw_values.get("game_time"))
    real_seconds = parse_duration_seconds(raw_values.get("real_time"))

    coins = parsed_numbers.get("coins_earned") or 0.0
    cph = parsed_numbers.get("coins_per_hour")
    if (cph is None or cph <= 0) and real_seconds:
        cph = coins / (real_seconds / 3600)

    cells = parsed_numbers.get("cells_earned") or 0.0
    cells_per_hour = parsed_numbers.get("cells_per_hour")
    if (cells_per_hour is None or cells_per_hour <= 0) and real_seconds:
        cells_per_hour = cells / (real_seconds / 3600)

    return {
        "id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "battle_date": raw_values.get("battle_date", ""),
        "tier": tier,
        "wave": wave,
        "killed_by": raw_values.get("killed_by", "Unknown"),
        "game_time": raw_values.get("game_time", ""),
        "real_time": raw_values.get("real_time", ""),
        "game_seconds": game_seconds,
        "real_seconds": real_seconds,
        "coins_earned": coins,
        "coins_per_hour": cph or 0.0,
        "cells_earned": cells,
        "cells_per_hour": cells_per_hour or 0.0,
        "metrics": parsed_numbers,
        "raw_values": raw_values,
        "raw_text": original_text,
    }
