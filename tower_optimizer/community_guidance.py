from __future__ import annotations

import fnmatch
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

GUIDANCE_PATH = Path(__file__).resolve().parent / "game_data" / "community_guidance.json"
COMMUNITY_LABEL = "Community guide (Fandom)"

UW_ABBREVIATIONS = {
    "GT": "Golden Tower",
    "BH": "Black Hole",
    "DW": "Death Wave",
    "SL": "Spotlight",
    "CL": "Chain Lightning",
    "SM": "Smart Missiles",
    "CF": "Chrono Field",
    "ILM": "Inner Land Mines",
    "PS": "Poison Swamp",
}

SEVERITY_ORDER = {"warning": 0, "caution": 1, "info": 2}
NATURAL_GT_BH_SYNC_SECONDS = 200


@lru_cache(maxsize=1)
def load_community_guidance() -> dict[str, Any]:
    payload = json.loads(GUIDANCE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("community_guidance.json must contain a JSON object")
    return payload


def clear_guidance_cache() -> None:
    load_community_guidance.cache_clear()


def _int_level(profile: Mapping[str, Any], section: str, name: str) -> int:
    bucket = profile.get(section, {})
    if not isinstance(bucket, Mapping):
        return 0
    try:
        return int(bucket.get(name, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _uw_owned(profile: Mapping[str, Any], uw_name: str) -> bool:
    uw = profile.get("uw", {})
    if not isinstance(uw, Mapping):
        return False
    entry = uw.get(uw_name, {})
    if not isinstance(entry, Mapping):
        return False
    return bool(entry.get("owned"))


def _bot_owned(profile: Mapping[str, Any], bot_name: str) -> bool:
    bots = profile.get("bots", {})
    if not isinstance(bots, Mapping):
        return False
    entry = bots.get(bot_name, {})
    if not isinstance(entry, Mapping):
        return False
    return bool(entry.get("owned"))


def _uw_attribute(profile: Mapping[str, Any], uw_name: str, attribute: str) -> int | None:
    uw = profile.get("uw", {})
    if not isinstance(uw, Mapping):
        return None
    entry = uw.get(uw_name, {})
    if not isinstance(entry, Mapping) or not entry.get("owned"):
        return None
    attrs = entry.get("attributes", {})
    if not isinstance(attrs, Mapping):
        return None
    if attribute not in attrs:
        return None
    try:
        return int(attrs.get(attribute, 0) or 0)
    except (TypeError, ValueError):
        return None


def _bot_attribute(profile: Mapping[str, Any], bot_name: str, attribute: str) -> int | None:
    bots = profile.get("bots", {})
    if not isinstance(bots, Mapping):
        return None
    entry = bots.get(bot_name, {})
    if not isinstance(entry, Mapping) or not entry.get("owned"):
        return None
    attrs = entry.get("attributes", {})
    if not isinstance(attrs, Mapping):
        return None
    if attribute not in attrs:
        return None
    try:
        return int(attrs.get(attribute, 0) or 0)
    except (TypeError, ValueError):
        return None


def _cooldowns_synced(a: int, b: int) -> bool:
    if a <= 0 or b <= 0:
        return False
    if a == b:
        return True
    lo, hi = (a, b) if a <= b else (b, a)
    return hi % lo == 0


def gt_bh_synced(profile: Mapping[str, Any]) -> bool:
    gt_cd = _uw_attribute(profile, "Golden Tower", "Cooldown")
    bh_cd = _uw_attribute(profile, "Black Hole", "Cooldown")
    if gt_cd is None or bh_cd is None:
        return True
    return _cooldowns_synced(gt_cd, bh_cd)


def gt_bh_at_natural_sync(profile: Mapping[str, Any]) -> bool:
    gt_cd = _uw_attribute(profile, "Golden Tower", "Cooldown")
    bh_cd = _uw_attribute(profile, "Black Hole", "Cooldown")
    if gt_cd is None or bh_cd is None:
        return False
    return gt_cd == NATURAL_GT_BH_SYNC_SECONDS and bh_cd == NATURAL_GT_BH_SYNC_SECONDS


def bot_gt_synced(profile: Mapping[str, Any]) -> bool:
    gt_cd = _uw_attribute(profile, "Golden Tower", "Cooldown")
    bot_cd = _bot_attribute(profile, "Golden Bot", "Cooldown")
    if gt_cd is None or bot_cd is None:
        return True
    if gt_cd == bot_cd:
        return True
    if gt_cd == bot_cd * 2:
        return True
    return _cooldowns_synced(gt_cd, bot_cd)


def defense_absolute_is_early(profile: Mapping[str, Any]) -> bool:
    ws = _int_level(profile, "workshop", "Defense Absolute")
    lab = _int_level(profile, "labs", "Defense Absolute")
    enh = _int_level(profile, "enhancements", "Defense Absolute +")
    return ws < 50 and lab < 10 and enh < 15


def defense_absolute_is_late(profile: Mapping[str, Any]) -> bool:
    return not defense_absolute_is_early(profile)


def _tier_max_wave(profile: Mapping[str, Any], tier: int) -> int:
    player = profile.get("player", {})
    if not isinstance(player, Mapping):
        return 0
    tiers = player.get("tiers", {})
    if not isinstance(tiers, Mapping):
        return 0
    entry = tiers.get(str(tier), tiers.get(tier, {}))
    if not isinstance(entry, Mapping):
        return 0
    try:
        return int(entry.get("highest_wave", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_upgrade_name(upgrade: str) -> str:
    text = str(upgrade or "").strip()
    if "|" in text:
        prefix, attribute = [part.strip() for part in text.split("|", 1)]
        uw_name = UW_ABBREVIATIONS.get(prefix, prefix)
        return f"{uw_name} {attribute}".strip()
    return text


def _is_cooldown_upgrade(upgrade: str, row: Mapping[str, Any]) -> bool:
    upgrade_text = str(upgrade or "").casefold()
    path_key = str(row.get("Path Key", "")).casefold()
    if "cooldown" in upgrade_text:
        return True
    if path_key.endswith("_stone") and "cooldown" in upgrade_text:
        return True
    normalized = _normalize_upgrade_name(upgrade).casefold()
    return "cooldown" in normalized


def _applies_to_match(upgrade: str, row: Mapping[str, Any], patterns: Sequence[str]) -> bool:
    candidates = {
        str(upgrade or "").strip(),
        _normalize_upgrade_name(upgrade),
        str(row.get("Upgrade", "")).strip(),
        str(row.get("Path Key", "")).strip(),
    }
    normalized_candidates = {value.casefold() for value in candidates if value}
    for pattern in patterns:
        pat = str(pattern).strip()
        if not pat:
            continue
        pat_cf = pat.casefold()
        for candidate in normalized_candidates:
            if candidate == pat_cf:
                return True
        for candidate in candidates:
            if fnmatch.fnmatchcase(candidate, pattern) or fnmatch.fnmatchcase(candidate.casefold(), pat_cf):
                return True
    return False


def _evaluate_when(profile: Mapping[str, Any], upgrade: str, row: Mapping[str, Any], when: Mapping[str, Any]) -> bool:
    if not when:
        return True

    if "owns_uw" in when:
        required = when.get("owns_uw") or []
        if isinstance(required, str):
            required = [required]
        if not all(_uw_owned(profile, str(name)) for name in required):
            return False

    if "missing_uw" in when:
        missing = when.get("missing_uw") or []
        if isinstance(missing, str):
            missing = [missing]
        if any(_uw_owned(profile, str(name)) for name in missing):
            return False

    if "owns_bot" in when:
        required = when.get("owns_bot") or []
        if isinstance(required, str):
            required = [required]
        if not all(_bot_owned(profile, str(name)) for name in required):
            return False

    if when.get("missing_sync") == "gt_bh" and gt_bh_synced(profile):
        return False

    if when.get("missing_sync") == "bot_gt" and bot_gt_synced(profile):
        return False

    if when.get("gt_bh_not_at_natural_sync") and gt_bh_at_natural_sync(profile):
        return False

    if when.get("recommending_cooldown") and not _is_cooldown_upgrade(upgrade, row):
        return False

    if when.get("defense_absolute_late") and not defense_absolute_is_late(profile):
        return False

    if "workshop_min" in when:
        stat = str(when.get("workshop_stat", ""))
        try:
            minimum = int(when.get("workshop_min", 0))
        except (TypeError, ValueError):
            minimum = 0
        if stat and _int_level(profile, "workshop", stat) < minimum:
            return False

    if "lab_min" in when:
        stat = str(when.get("lab_stat", ""))
        try:
            minimum = int(when.get("lab_min", 0))
        except (TypeError, ValueError):
            minimum = 0
        if stat and _int_level(profile, "labs", stat) < minimum:
            return False

    return True


def _sort_guidance(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(item: Mapping[str, Any]) -> tuple[int, str]:
        severity = str(item.get("severity", "info")).casefold()
        return (SEVERITY_ORDER.get(severity, 99), str(item.get("id", "")))

    return [dict(item) for item in sorted(items, key=sort_key)]


def match_footguns(
    profile: Mapping[str, Any],
    upgrade: str,
    row: Mapping[str, Any],
) -> list[dict[str, Any]]:
    payload = load_community_guidance()
    footguns = payload.get("footguns") or []
    if not isinstance(footguns, list):
        return []

    matched: list[dict[str, Any]] = []
    for entry in footguns:
        if not isinstance(entry, Mapping):
            continue
        applies_to = entry.get("applies_to") or []
        if isinstance(applies_to, str):
            applies_to = [applies_to]
        if not _applies_to_match(upgrade, row, applies_to):
            continue
        when = entry.get("when") or {}
        if not isinstance(when, Mapping):
            when = {}
        if not _evaluate_when(profile, upgrade, row, when):
            continue
        matched.append(dict(entry))
    return _sort_guidance(matched)


def _requirement_met(profile: Mapping[str, Any], requirement: Mapping[str, Any]) -> bool:
    req_type = str(requirement.get("type", "")).casefold()

    if req_type == "uw_owned":
        names = requirement.get("uw") or []
        if isinstance(names, str):
            names = [names]
        return all(_uw_owned(profile, str(name)) for name in names)

    if req_type == "gt_bh_synced":
        return gt_bh_synced(profile)

    if req_type == "uw_attribute_min":
        uw_name = str(requirement.get("uw", ""))
        attribute = str(requirement.get("attribute", ""))
        try:
            minimum = int(requirement.get("min", 0))
        except (TypeError, ValueError):
            minimum = 0
        value = _uw_attribute(profile, uw_name, attribute)
        return value is not None and value >= minimum

    if req_type == "workshop_max":
        stat = str(requirement.get("stat", ""))
        try:
            maximum = int(requirement.get("max", 0))
        except (TypeError, ValueError):
            maximum = 0
        return _int_level(profile, "workshop", stat) <= maximum

    if req_type == "tier_max_wave_below":
        try:
            tier = int(requirement.get("tier", 0))
            wave = int(requirement.get("wave", 0))
        except (TypeError, ValueError):
            return False
        return _tier_max_wave(profile, tier) < wave

    return False


def _archetype_fit_score(profile: Mapping[str, Any], archetype: Mapping[str, Any]) -> tuple[int, int]:
    requirements = archetype.get("requirements") or []
    if not isinstance(requirements, list) or not requirements:
        return 0, 0
    met = sum(1 for req in requirements if isinstance(req, Mapping) and _requirement_met(profile, req))
    return met, len(requirements)


def match_build_archetypes(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    payload = load_community_guidance()
    archetypes = payload.get("build_archetypes") or []
    if not isinstance(archetypes, list):
        return []

    scored: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for entry in archetypes:
        if not isinstance(entry, Mapping):
            continue
        met, total = _archetype_fit_score(profile, entry)
        if met <= 0:
            continue
        item = dict(entry)
        item["requirements_met"] = met
        item["requirements_total"] = total
        item["fit_ratio"] = met / total if total else 0.0
        scored.append(((met, total, str(entry.get("id", ""))), item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


def format_community_guidance_line(entry: Mapping[str, Any]) -> str:
    summary = str(entry.get("summary", "")).strip()
    source_url = str(entry.get("source_url", "")).strip()
    if source_url:
        return f"{COMMUNITY_LABEL}: {summary} [{source_url}]"
    return f"{COMMUNITY_LABEL}: {summary}"


def community_guidance_for_explanation(
    profile: Mapping[str, Any],
    upgrade: str,
    row: Mapping[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    footguns = match_footguns(profile, upgrade, row)
    lines = [format_community_guidance_line(item) for item in footguns]
    return lines, footguns


def build_hint_lines(profile: Mapping[str, Any]) -> list[str]:
    hints = match_build_archetypes(profile)
    if not hints:
        return []
    best = hints[0]
    if best.get("requirements_met") != best.get("requirements_total"):
        return []
    return [format_community_guidance_line(best)]
