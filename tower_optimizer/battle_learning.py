"""Battle-history analytics and conservative recommendation feedback.

The learning layer observes saved Battle Reports and completed upgrade events. It
never claims causation from a single run. Comparisons are same-tier when possible,
use medians, expose sample sizes, and cap any recommendation adjustment to a small
range so noisy reports cannot dominate the verified optimization engines.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import math
import re
import statistics
import uuid
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional


SCHEMA_VERSION = 1
RUN_TYPES = ["Auto", "Farming", "Push", "Tournament", "Milestone / Test"]
PLAY_STYLES = ["Auto", "Active", "Overnight"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Optional[datetime] = None) -> str:
    return (value or _now()).isoformat()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _parse_duration_seconds(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0, int(value))
    text = str(value).strip().lower()
    if not text:
        return None
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    total = 0.0
    found = False
    for amount, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([dhms])", text):
        total += float(amount) * units[unit]
        found = True
    return max(0, int(total)) if found else None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    for fmt in (
        "%b %d, %Y %H:%M", "%b %d, %Y %I:%M %p", "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M", "%Y-%m-%d", "%m/%d/%Y %H:%M", "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _run_timestamp(run: Mapping[str, Any]) -> Optional[datetime]:
    return _parse_datetime(run.get("battle_date")) or _parse_datetime(run.get("imported_at"))


def _recover_text_field(run: Mapping[str, Any], key: str, label: str) -> str:
    value = str(run.get(key) or "").strip()
    if value and value.casefold() not in {"unknown", "none", "n/a"}:
        return value
    raw_values = run.get("raw_values", {})
    if isinstance(raw_values, Mapping):
        recovered = str(raw_values.get(key) or "").strip()
        if recovered:
            return recovered
    raw_text = str(run.get("raw_text") or "")
    match = re.search(rf"(?im)^\s*{re.escape(label)}\s+(.+?)\s*$", raw_text)
    return match.group(1).strip() if match else value


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def battle_learning_defaults() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "settings": {
            "minimum_runs_per_tier": 2,
            "comparison_window_runs": 5,
            "active_max_hours": 2.0,
            "overnight_min_hours": 4.0,
            "apply_observed_feedback": True,
            "feedback_cap_percent": 8.0,
        },
        "upgrade_events": [],
        "import_batches": [],
        "last_report": None,
    }


def ensure_battle_learning_state(profile: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    defaults = battle_learning_defaults()
    state = profile.setdefault("battle_learning", {})
    if not isinstance(state, MutableMapping):
        state = {}
        profile["battle_learning"] = state
    state.setdefault("schema_version", SCHEMA_VERSION)
    settings = state.setdefault("settings", {})
    if not isinstance(settings, MutableMapping):
        settings = {}
        state["settings"] = settings
    for key, value in defaults["settings"].items():
        settings.setdefault(key, value)
    for key in ("upgrade_events", "import_batches"):
        if not isinstance(state.get(key), list):
            state[key] = []
    state.setdefault("last_report", None)
    return state


def normalize_run(run: Mapping[str, Any]) -> Dict[str, Any]:
    result = deepcopy(dict(run))
    if not result.get("id"):
        result["id"] = uuid.uuid4().hex[:20]
    if not result.get("imported_at"):
        result["imported_at"] = _iso()
    result["battle_date"] = _recover_text_field(result, "battle_date", "Battle Date")
    result["killed_by"] = _recover_text_field(result, "killed_by", "Killed By") or "Unknown"
    result["tier"] = max(0, _integer(result.get("tier")))
    result["wave"] = max(0, _integer(result.get("wave")))

    real_seconds = _integer(result.get("real_seconds"), -1)
    if real_seconds < 0:
        parsed = _parse_duration_seconds(result.get("real_time"))
        real_seconds = parsed if parsed is not None else 0
    game_seconds = _integer(result.get("game_seconds"), -1)
    if game_seconds < 0:
        parsed = _parse_duration_seconds(result.get("game_time"))
        game_seconds = parsed if parsed is not None else 0
    result["real_seconds"] = max(0, real_seconds)
    result["game_seconds"] = max(0, game_seconds)
    if not result.get("real_time") and real_seconds:
        result["real_time"] = _format_duration(real_seconds)
    if not result.get("game_time") and game_seconds:
        result["game_time"] = _format_duration(game_seconds)

    for key in ("coins_earned", "coins_per_hour", "cells_earned", "cells_per_hour"):
        result[key] = max(0.0, _number(result.get(key)))
    hours = result["real_seconds"] / 3600.0 if result["real_seconds"] else 0.0
    if result["coins_per_hour"] <= 0 and result["coins_earned"] > 0 and hours > 0:
        result["coins_per_hour"] = result["coins_earned"] / hours
    if result["cells_per_hour"] <= 0 and result["cells_earned"] > 0 and hours > 0:
        result["cells_per_hour"] = result["cells_earned"] / hours

    result.setdefault("run_type", "Auto")
    if result["run_type"] not in RUN_TYPES:
        result["run_type"] = "Auto"
    result.setdefault("play_style", "Auto")
    if result["play_style"] not in PLAY_STYLES:
        result["play_style"] = "Auto"
    result.setdefault("notes", "")
    if not isinstance(result.get("metrics"), Mapping):
        result["metrics"] = {}
    result["fingerprint"] = run_fingerprint(result)
    return result


def run_fingerprint(run: Mapping[str, Any]) -> str:
    battle_date = str(run.get("battle_date") or "").strip().casefold()
    payload = [
        str(_integer(run.get("tier"))), str(_integer(run.get("wave"))), battle_date,
        str(_integer(run.get("real_seconds"))), f"{_number(run.get('coins_earned')):.3f}",
        f"{_number(run.get('cells_earned')):.3f}",
    ]
    return hashlib.sha1("|".join(payload).encode("utf-8")).hexdigest()[:20]


def normalize_profile_runs(profile: MutableMapping[str, Any]) -> int:
    ensure_battle_learning_state(profile)
    runs = profile.setdefault("runs", [])
    if not isinstance(runs, list):
        profile["runs"] = []
        return 0
    changed = 0
    normalized = []
    for original in runs:
        if not isinstance(original, Mapping):
            changed += 1
            continue
        updated = normalize_run(original)
        if updated != original:
            changed += 1
        normalized.append(updated)
    normalized.sort(key=lambda item: (_run_timestamp(item) or datetime.min.replace(tzinfo=timezone.utc), str(item.get("id"))))
    profile["runs"] = normalized
    return changed


def prepare_import_batch(existing_runs: Iterable[Mapping[str, Any]], candidates: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    existing_fingerprints = {run_fingerprint(normalize_run(run)) for run in existing_runs if isinstance(run, Mapping)}
    seen = set(existing_fingerprints)
    unique: list[Dict[str, Any]] = []
    duplicates: list[Dict[str, Any]] = []
    invalid: list[Dict[str, Any]] = []
    for source in candidates:
        if not isinstance(source, Mapping):
            invalid.append({"reason": "Not an object", "value": repr(source)[:200]})
            continue
        run = normalize_run(source)
        if run.get("tier", 0) <= 0 or run.get("wave", 0) <= 0:
            invalid.append({"reason": "Missing valid Tier or Wave", "run": run})
            continue
        fingerprint = run["fingerprint"]
        if fingerprint in seen:
            duplicates.append(run)
            continue
        seen.add(fingerprint)
        unique.append(run)
    return {"unique": unique, "duplicates": duplicates, "invalid": invalid}


def import_runs(
    profile: MutableMapping[str, Any], candidates: Iterable[Mapping[str, Any]],
    *, allow_duplicates: bool = False, batch_label: str = "Battle import",
) -> Dict[str, Any]:
    normalize_profile_runs(profile)
    prepared = prepare_import_batch(profile.get("runs", []), candidates)
    added = list(prepared["unique"])
    if allow_duplicates:
        for run in prepared["duplicates"]:
            duplicate = deepcopy(run)
            duplicate["id"] = uuid.uuid4().hex[:20]
            duplicate["fingerprint"] = run_fingerprint({**duplicate, "id": duplicate["id"]})
            added.append(duplicate)
    profile.setdefault("runs", []).extend(added)
    normalize_profile_runs(profile)
    state = ensure_battle_learning_state(profile)
    state["import_batches"].append({
        "id": uuid.uuid4().hex[:12], "at": _iso(), "label": batch_label,
        "added": len(added), "duplicates": len(prepared["duplicates"]),
        "invalid": len(prepared["invalid"]),
    })
    del state["import_batches"][:-25]
    return {**prepared, "added": added}


def apply_run_correction(
    profile: MutableMapping[str, Any], run_id: str, updates: Mapping[str, Any], *, recalculate_rates: bool = True,
) -> bool:
    normalize_profile_runs(profile)
    run = next((item for item in profile.get("runs", []) if str(item.get("id")) == str(run_id)), None)
    if run is None:
        return False
    allowed = {
        "battle_date", "tier", "wave", "killed_by", "real_seconds", "game_seconds",
        "coins_earned", "cells_earned", "coins_per_hour", "cells_per_hour",
        "run_type", "play_style", "notes",
    }
    for key, value in updates.items():
        if key in allowed:
            run[key] = value
    corrected = normalize_run(run)
    if recalculate_rates and corrected.get("real_seconds", 0) > 0:
        hours = corrected["real_seconds"] / 3600.0
        corrected["coins_per_hour"] = corrected.get("coins_earned", 0.0) / hours
        corrected["cells_per_hour"] = corrected.get("cells_earned", 0.0) / hours
    corrected["corrected_at"] = _iso()
    run.clear()
    run.update(corrected)
    normalize_profile_runs(profile)
    return True


def delete_run(profile: MutableMapping[str, Any], run_id: str) -> bool:
    runs = profile.get("runs", [])
    if not isinstance(runs, list):
        return False
    original = len(runs)
    profile["runs"] = [run for run in runs if str(run.get("id")) != str(run_id)]
    return len(profile["runs"]) < original


def battle_rows(profile: MutableMapping[str, Any]) -> list[Dict[str, Any]]:
    normalize_profile_runs(profile)
    rows = []
    settings = ensure_battle_learning_state(profile)["settings"]
    active_max = max(0.1, _number(settings.get("active_max_hours"), 2.0))
    overnight_min = max(active_max, _number(settings.get("overnight_min_hours"), 4.0))
    for index, run in enumerate(profile.get("runs", []), start=1):
        stamp = _run_timestamp(run)
        duration_hours = _number(run.get("real_seconds")) / 3600.0
        play_style = str(run.get("play_style") or "Auto")
        if play_style == "Auto":
            if duration_hours >= overnight_min:
                play_style = "Overnight"
            elif duration_hours <= active_max:
                play_style = "Active"
            else:
                play_style = "Mixed"
        wave = max(0, _integer(run.get("wave")))
        rows.append({
            "Run": index,
            "ID": run.get("id"),
            "Timestamp": stamp.isoformat() if stamp else "",
            "Date": stamp.date().isoformat() if stamp else "Undated",
            "Tier": _integer(run.get("tier")),
            "Wave": wave,
            "Killed By": run.get("killed_by", "Unknown"),
            "Run Type": run.get("run_type", "Auto"),
            "Play Style": play_style,
            "Duration Hours": duration_hours,
            "Coins": _number(run.get("coins_earned")),
            "Coins / Hour": _number(run.get("coins_per_hour")),
            "Cells": _number(run.get("cells_earned")),
            "Cells / Hour": _number(run.get("cells_per_hour")),
            "Coins / Wave": _number(run.get("coins_earned")) / wave if wave else 0.0,
            "Cells / Wave": _number(run.get("cells_earned")) / wave if wave else 0.0,
            "Notes": run.get("notes", ""),
        })
    return rows


def _median(values: Iterable[float]) -> float:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    return statistics.median(clean) if clean else 0.0


def _mean(values: Iterable[float]) -> float:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    return statistics.mean(clean) if clean else 0.0


def _cv(values: Iterable[float]) -> Optional[float]:
    clean = [float(value) for value in values if float(value) > 0 and math.isfinite(float(value))]
    if len(clean) < 2:
        return None
    mean = statistics.mean(clean)
    return statistics.pstdev(clean) / mean if mean else None


def tier_performance(profile: MutableMapping[str, Any]) -> list[Dict[str, Any]]:
    rows = battle_rows(profile)
    grouped: Dict[int, list[Dict[str, Any]]] = {}
    for row in rows:
        if row["Tier"] > 0:
            grouped.setdefault(row["Tier"], []).append(row)
    result = []
    for tier, values in sorted(grouped.items()):
        cph = [row["Coins / Hour"] for row in values if row["Coins / Hour"] > 0]
        cells = [row["Cells / Hour"] for row in values if row["Cells / Hour"] > 0]
        waves = [row["Wave"] for row in values if row["Wave"] > 0]
        durations = [row["Duration Hours"] for row in values if row["Duration Hours"] > 0]
        cph_cv = _cv(cph)
        result.append({
            "Tier": tier,
            "Runs": len(values),
            "Best Wave": max(waves) if waves else 0,
            "Median Wave": _median(waves),
            "Median Coins / Hour": _median(cph),
            "Average Coins / Hour": _mean(cph),
            "Best Coins / Hour": max(cph) if cph else 0.0,
            "Median Cells / Hour": _median(cells),
            "Average Cells / Hour": _mean(cells),
            "Best Cells / Hour": max(cells) if cells else 0.0,
            "Median Duration Hours": _median(durations),
            "Coins/H Consistency": None if cph_cv is None else max(0.0, 100.0 * (1.0 - min(cph_cv, 1.0))),
            "Most Common Death": statistics.mode([str(row["Killed By"]) for row in values]) if values else "Unknown",
            "Active Runs": sum(row["Play Style"] == "Active" for row in values),
            "Overnight Runs": sum(row["Play Style"] == "Overnight" for row in values),
        })
    return result


def _normalized(value: float, maximum: float) -> float:
    return value / maximum if maximum > 0 else 0.0


def farming_recommendations(profile: MutableMapping[str, Any]) -> Dict[str, Optional[Dict[str, Any]]]:
    summaries = tier_performance(profile)
    settings = ensure_battle_learning_state(profile)["settings"]
    minimum = max(1, _integer(settings.get("minimum_runs_per_tier"), 2))
    eligible = [row for row in summaries if row["Runs"] >= minimum] or summaries
    if not eligible:
        return {"coins": None, "cells": None, "balanced": None, "active": None, "overnight": None}

    max_cph = max(row["Median Coins / Hour"] for row in eligible)
    max_cells = max(row["Median Cells / Hour"] for row in eligible)
    max_wave = max(row["Median Wave"] for row in eligible)
    scored = []
    for row in eligible:
        sample_factor = min(1.0, row["Runs"] / max(minimum, 3))
        consistency = (row["Coins/H Consistency"] or 50.0) / 100.0
        balanced = (
            0.48 * _normalized(row["Median Coins / Hour"], max_cph)
            + 0.32 * _normalized(row["Median Cells / Hour"], max_cells)
            + 0.20 * _normalized(row["Median Wave"], max_wave)
        ) * (0.75 + 0.15 * sample_factor + 0.10 * consistency)
        enriched = dict(row)
        enriched["Balanced Score"] = round(100.0 * balanced, 2)
        enriched["Confidence"] = "High" if row["Runs"] >= 5 else "Moderate" if row["Runs"] >= 3 else "Low"
        scored.append(enriched)

    active = [row for row in scored if row["Active Runs"] > 0]
    overnight = [row for row in scored if row["Overnight Runs"] > 0]
    return {
        "coins": max(scored, key=lambda row: row["Median Coins / Hour"], default=None),
        "cells": max(scored, key=lambda row: row["Median Cells / Hour"], default=None),
        "balanced": max(scored, key=lambda row: row["Balanced Score"], default=None),
        "active": max(active, key=lambda row: row["Median Coins / Hour"], default=None),
        "overnight": max(overnight, key=lambda row: (row["Median Cells / Hour"], row["Median Coins / Hour"]), default=None),
    }


def death_summary(profile: MutableMapping[str, Any]) -> list[Dict[str, Any]]:
    rows = battle_rows(profile)
    counts: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        cause = str(row.get("Killed By") or "Unknown").strip() or "Unknown"
        bucket = counts.setdefault(cause, {"Cause": cause, "Runs": 0, "Tiers": set(), "Waves": []})
        bucket["Runs"] += 1
        bucket["Tiers"].add(row["Tier"])
        bucket["Waves"].append(row["Wave"])
    total = len(rows)
    result = []
    for bucket in counts.values():
        result.append({
            "Cause": bucket["Cause"], "Runs": bucket["Runs"],
            "Share %": 100.0 * bucket["Runs"] / total if total else 0.0,
            "Median Wave": _median(bucket["Waves"]),
            "Tiers": ", ".join(str(value) for value in sorted(bucket["Tiers"])),
        })
    return sorted(result, key=lambda row: (row["Runs"], row["Median Wave"]), reverse=True)


def _trend_percent(current: float, previous: float) -> Optional[float]:
    return 100.0 * (current - previous) / previous if previous > 0 else None


def bottleneck_findings(profile: MutableMapping[str, Any]) -> list[Dict[str, Any]]:
    findings: list[Dict[str, Any]] = []
    deaths = death_summary(profile)
    if deaths:
        top = deaths[0]
        cause = str(top["Cause"])
        share = float(top["Share %"])
        if top["Runs"] >= 2 and share >= 40:
            lower = cause.casefold()
            if "vampire" in lower:
                action = "Prioritize Garlic Thorns, recovery, regen, and Vampire-specific control."
                domain = "Regen / Recovery"
            elif "fast" in lower:
                action = "Review attack speed, crowd clear, knockback, and burst eHP."
                domain = "Damage / Survivability"
            elif "boss" in lower:
                action = "Review boss damage, thorns interaction, plasma cannon, and eHP."
                domain = "Damage / Survivability"
            elif "ray" in lower:
                action = "Prioritize burst eHP, defense, and recovery timing."
                domain = "Survivability"
            elif "scatter" in lower:
                action = "Prioritize area clear, damage, and recovery from repeated hits."
                domain = "Damage / Recovery"
            else:
                action = "Inspect the repeated death cause before changing build priorities."
                domain = "Review"
            findings.append({
                "Severity": "High" if share >= 60 else "Medium",
                "Finding": f"{cause} caused {top['Runs']} of {sum(item['Runs'] for item in deaths)} recorded deaths ({share:.0f}%).",
                "Domain": domain, "Suggested Action": action,
            })

    rows = battle_rows(profile)
    by_tier: Dict[int, list[Dict[str, Any]]] = {}
    for row in rows:
        by_tier.setdefault(row["Tier"], []).append(row)
    for tier, tier_rows in by_tier.items():
        if len(tier_rows) < 6:
            continue
        recent = tier_rows[-3:]
        previous = tier_rows[-6:-3]
        recent_wave = _median(row["Wave"] for row in recent)
        previous_wave = _median(row["Wave"] for row in previous)
        recent_cph = _median(row["Coins / Hour"] for row in recent)
        previous_cph = _median(row["Coins / Hour"] for row in previous)
        wave_change = _trend_percent(recent_wave, previous_wave)
        cph_change = _trend_percent(recent_cph, previous_cph)
        if wave_change is not None and cph_change is not None and wave_change < 2 and cph_change > 8:
            findings.append({
                "Severity": "Medium", "Finding": f"Tier {tier} economy improved {cph_change:.1f}% while median wave changed only {wave_change:.1f}%.",
                "Domain": "Damage / Survivability", "Suggested Action": "Shift some priority from economy into the repeated run-ending bottleneck.",
            })

        durations = [row["Duration Hours"] for row in tier_rows if row["Duration Hours"] > 0 and row["Coins / Hour"] > 0]
        cph = [row["Coins / Hour"] for row in tier_rows if row["Duration Hours"] > 0 and row["Coins / Hour"] > 0]
        if len(durations) >= 4:
            mean_x, mean_y = _mean(durations), _mean(cph)
            numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(durations, cph))
            denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in durations))
            denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in cph))
            corr = numerator / (denom_x * denom_y) if denom_x and denom_y else 0.0
            if corr < -0.55:
                findings.append({
                    "Severity": "Info", "Finding": f"Tier {tier} longer runs correlate with lower coins/hour (r={corr:.2f}).",
                    "Domain": "Farming efficiency", "Suggested Action": "Consider ending or lowering the tier before late-run efficiency collapses.",
                })

    if not findings:
        findings.append({
            "Severity": "Info", "Finding": "No repeated bottleneck has enough evidence yet.",
            "Domain": "Data", "Suggested Action": "Import several comparable runs per farming tier.",
        })
    return findings


def data_quality_findings(profile: MutableMapping[str, Any]) -> list[Dict[str, Any]]:
    normalize_profile_runs(profile)
    findings: list[Dict[str, Any]] = []
    fingerprints: Dict[str, list[str]] = {}
    for run in profile.get("runs", []):
        run_id = str(run.get("id"))
        fingerprint = run_fingerprint(run)
        fingerprints.setdefault(fingerprint, []).append(run_id)
        if _integer(run.get("tier")) <= 0 or _integer(run.get("wave")) <= 0:
            findings.append({"Severity": "Error", "Run ID": run_id, "Finding": "Invalid Tier or Wave", "Suggested Action": "Correct or delete this report."})
        if not _parse_datetime(run.get("battle_date")):
            findings.append({"Severity": "Info", "Run ID": run_id, "Finding": "Battle date is missing or unrecognized", "Suggested Action": "Add a date for before/after analysis."})
        if str(run.get("killed_by") or "Unknown").casefold() == "unknown":
            findings.append({"Severity": "Info", "Run ID": run_id, "Finding": "Cause of death is Unknown", "Suggested Action": "Correct it for bottleneck weighting."})
        if _number(run.get("real_seconds")) <= 0:
            findings.append({"Severity": "Warning", "Run ID": run_id, "Finding": "Real Time is missing", "Suggested Action": "Enter duration to calculate hourly rates."})
        elif _number(run.get("coins_earned")) > 0:
            expected = _number(run.get("coins_earned")) / (_number(run.get("real_seconds")) / 3600.0)
            actual = _number(run.get("coins_per_hour"))
            if actual > 0 and abs(actual - expected) / expected > 0.08:
                findings.append({"Severity": "Info", "Run ID": run_id, "Finding": "Coins/hour differs from Coins ÷ Real Time by more than 8%", "Suggested Action": "Keep the in-game rate or recalculate during correction."})
    for ids in fingerprints.values():
        if len(ids) > 1:
            findings.append({"Severity": "Warning", "Run ID": ", ".join(ids), "Finding": "Possible duplicate reports", "Suggested Action": "Review and delete unintended duplicates."})
    return findings


def add_upgrade_event(
    profile: MutableMapping[str, Any], *, upgrade: str, completed_at: str,
    system: str = "Manual", resource: str = "Unknown", domain: str = "Auto", notes: str = "",
) -> str:
    state = ensure_battle_learning_state(profile)
    event_id = uuid.uuid4().hex[:12]
    state["upgrade_events"].append({
        "id": event_id, "upgrade": upgrade.strip() or "Unnamed upgrade",
        "completed_at": completed_at, "system": system, "resource": resource,
        "domain": domain, "notes": notes, "source": "Manual",
    })
    return event_id


def delete_upgrade_event(profile: MutableMapping[str, Any], event_id: str) -> bool:
    state = ensure_battle_learning_state(profile)
    events = state["upgrade_events"]
    before = len(events)
    state["upgrade_events"] = [event for event in events if str(event.get("id")) != str(event_id)]
    return len(state["upgrade_events"]) < before


def upgrade_events(profile: MutableMapping[str, Any]) -> list[Dict[str, Any]]:
    state = ensure_battle_learning_state(profile)
    events: list[Dict[str, Any]] = [deepcopy(event) for event in state.get("upgrade_events", []) if isinstance(event, Mapping)]
    planner = profile.get("planner", {}) if isinstance(profile.get("planner", {}), Mapping) else {}
    completed = planner.get("completed", []) if isinstance(planner.get("completed", []), list) else []
    seen = {str(event.get("id")) for event in events}
    for item in completed:
        if not isinstance(item, Mapping) or not item.get("completed_at"):
            continue
        event_id = f"queue:{item.get('id')}"
        if event_id in seen:
            continue
        events.append({
            "id": event_id, "upgrade": item.get("upgrade", "Completed upgrade"),
            "completed_at": item.get("completed_at"), "system": item.get("system", "Unknown"),
            "resource": item.get("resource", "Unknown"), "domain": item.get("domain", "Auto"),
            "notes": item.get("why", ""), "source": "Progression queue",
        })
        seen.add(event_id)
    events.sort(key=lambda event: _parse_datetime(event.get("completed_at")) or datetime.min.replace(tzinfo=timezone.utc))
    return events


def _infer_domain(event: Mapping[str, Any]) -> str:
    explicit = str(event.get("domain") or "Auto")
    if explicit not in {"", "Auto", "Unknown"}:
        return explicit
    text = f"{event.get('upgrade', '')} {event.get('system', '')} {event.get('resource', '')}".casefold()
    if any(word in text for word in ("coin", "golden tower", "black hole bonus", "economy", "cash")):
        return "Economy"
    if any(word in text for word in ("regen", "recovery", "garlic", "lifesteal", "wall")):
        return "Regen / Recovery"
    if any(word in text for word in ("health", "defense", "shield", "fortification", "thorn")):
        return "Survivability"
    if any(word in text for word in ("damage", "attack", "crit", "missile", "lightning", "rend")):
        return "Damage"
    if "module" in text or "reroll" in text:
        return "Modules"
    return "Utility"


def _event_primary_metric(domain: str, event: Mapping[str, Any]) -> str:
    text = str(event.get("upgrade") or "").casefold()
    if "cell" in text:
        return "Cells / Hour"
    if domain == "Economy":
        return "Coins / Hour"
    return "Wave"


def upgrade_impact_rows(profile: MutableMapping[str, Any]) -> list[Dict[str, Any]]:
    rows = battle_rows(profile)
    events = upgrade_events(profile)
    settings = ensure_battle_learning_state(profile)["settings"]
    window = max(1, _integer(settings.get("comparison_window_runs"), 5))
    result: list[Dict[str, Any]] = []
    for event in events:
        stamp = _parse_datetime(event.get("completed_at"))
        if stamp is None:
            result.append({
                "Event ID": event.get("id"), "Upgrade": event.get("upgrade"), "Completed": event.get("completed_at"),
                "Domain": _infer_domain(event), "Tier": "—", "Metric": "—", "Before": None, "After": None,
                "Change %": None, "Before Runs": 0, "After Runs": 0, "Result": "No dated event",
                "Confidence": "None", "Caveat": "Enter a recognizable completion date/time.",
            })
            continue
        before_all = [row for row in rows if _parse_datetime(row.get("Timestamp")) and _parse_datetime(row.get("Timestamp")) < stamp]
        after_all = [row for row in rows if _parse_datetime(row.get("Timestamp")) and _parse_datetime(row.get("Timestamp")) >= stamp]
        common_tiers = sorted(set(row["Tier"] for row in before_all) & set(row["Tier"] for row in after_all))
        if not common_tiers:
            result.append({
                "Event ID": event.get("id"), "Upgrade": event.get("upgrade"), "Completed": event.get("completed_at"),
                "Domain": _infer_domain(event), "Tier": "—", "Metric": "—", "Before": None, "After": None,
                "Change %": None, "Before Runs": len(before_all), "After Runs": len(after_all), "Result": "Insufficient comparable runs",
                "Confidence": "None", "Caveat": "Need at least one same-tier run before and after completion.",
            })
            continue
        tier = max(common_tiers, key=lambda value: min(sum(row["Tier"] == value for row in before_all), sum(row["Tier"] == value for row in after_all)))
        before = [row for row in before_all if row["Tier"] == tier][-window:]
        after = [row for row in after_all if row["Tier"] == tier][:window]
        domain = _infer_domain(event)
        metric = _event_primary_metric(domain, event)
        before_value = _median(row[metric] for row in before)
        after_value = _median(row[metric] for row in after)
        change = _trend_percent(after_value, before_value)
        sample = min(len(before), len(after))
        confidence = "High" if sample >= 5 else "Moderate" if sample >= 3 else "Low" if sample >= 1 else "None"
        if change is None:
            observed = "No baseline"
        elif change > 3:
            observed = "Improved"
        elif change < -3:
            observed = "Declined"
        else:
            observed = "No clear change"
        concurrent = sum(
            1 for other in events
            if other is not event and (other_stamp := _parse_datetime(other.get("completed_at")))
            and abs((other_stamp - stamp).total_seconds()) <= 86400
        )
        caveat = "Observational comparison; other upgrades, perks, cards, and run conditions may contribute."
        if concurrent:
            caveat += f" {concurrent} other completion(s) occurred within 24 hours."
        result.append({
            "Event ID": event.get("id"), "Upgrade": event.get("upgrade"), "Completed": event.get("completed_at"),
            "System": event.get("system"), "Resource": event.get("resource"), "Domain": domain,
            "Tier": tier, "Metric": metric, "Before": before_value, "After": after_value,
            "Change %": change, "Before Runs": len(before), "After Runs": len(after),
            "Result": observed, "Confidence": confidence, "Caveat": caveat,
        })
    return result


def feedback_modifiers(profile: MutableMapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    state = ensure_battle_learning_state(profile)
    if not bool(state["settings"].get("apply_observed_feedback", True)):
        return {}
    cap = max(0.0, min(15.0, _number(state["settings"].get("feedback_cap_percent"), 8.0))) / 100.0
    grouped: Dict[str, list[float]] = {}
    for row in upgrade_impact_rows(profile):
        change = row.get("Change %")
        if not isinstance(change, (int, float)) or row.get("Confidence") not in {"Moderate", "High"}:
            continue
        grouped.setdefault(str(row.get("Domain") or "Utility"), []).append(float(change))
    result: Dict[str, Dict[str, Any]] = {}
    for domain, changes in grouped.items():
        median_change = statistics.median(changes)
        adjustment = max(-cap, min(cap, median_change / 100.0 * 0.25))
        result[domain] = {
            "multiplier": 1.0 + adjustment,
            "observed_change_percent": median_change,
            "samples": len(changes),
            "reason": f"observed {median_change:+.1f}% median same-tier result after {len(changes)} comparable upgrade event(s)",
        }
    return result


def recommendation_feedback_multiplier(
    profile: Mapping[str, Any], domain: str, system: str = "", upgrade: str = "",
) -> tuple[float, Optional[str]]:
    if not isinstance(profile, MutableMapping):
        return 1.0, None
    modifiers = feedback_modifiers(profile)
    record = modifiers.get(domain)
    if not record:
        if system == "Modules":
            record = modifiers.get("Modules")
    if not record:
        return 1.0, None
    return float(record["multiplier"]), str(record["reason"])


def trend_rows(profile: MutableMapping[str, Any], tier: Optional[int] = None) -> list[Dict[str, Any]]:
    rows = battle_rows(profile)
    if tier is not None:
        rows = [row for row in rows if row["Tier"] == tier]
    return rows


def build_battle_learning_report(profile: MutableMapping[str, Any]) -> Dict[str, Any]:
    normalize_profile_runs(profile)
    report = {
        "generated_at": _iso(),
        "runs": battle_rows(profile),
        "tier_performance": tier_performance(profile),
        "farming_recommendations": farming_recommendations(profile),
        "death_summary": death_summary(profile),
        "bottlenecks": bottleneck_findings(profile),
        "quality": data_quality_findings(profile),
        "upgrade_impacts": upgrade_impact_rows(profile),
        "feedback_modifiers": feedback_modifiers(profile),
        "method": (
            "Uses same-tier medians, visible sample counts, and capped feedback adjustments. "
            "Observed changes are correlations, not proof that a single upgrade caused the result."
        ),
    }
    state = ensure_battle_learning_state(profile)
    state["last_report"] = report["generated_at"]
    return report


def runs_to_csv(profile: MutableMapping[str, Any]) -> str:
    rows = battle_rows(profile)
    fields = [
        "ID", "Timestamp", "Date", "Tier", "Wave", "Killed By", "Run Type", "Play Style",
        "Duration Hours", "Coins", "Coins / Hour", "Cells", "Cells / Hour", "Coins / Wave", "Cells / Wave", "Notes",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fields})
    return buffer.getvalue()


def export_battle_learning_json(profile: MutableMapping[str, Any]) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "profile": profile.get("name"),
        "report": build_battle_learning_report(profile),
        "upgrade_events": upgrade_events(profile),
    }
    return json.dumps(payload, indent=2, default=str)


__all__ = [
    "SCHEMA_VERSION", "RUN_TYPES", "PLAY_STYLES", "battle_learning_defaults",
    "ensure_battle_learning_state", "normalize_run", "normalize_profile_runs",
    "run_fingerprint", "prepare_import_batch", "import_runs", "apply_run_correction",
    "delete_run", "battle_rows", "tier_performance", "farming_recommendations",
    "death_summary", "bottleneck_findings", "data_quality_findings", "add_upgrade_event",
    "delete_upgrade_event", "upgrade_events", "upgrade_impact_rows", "feedback_modifiers",
    "recommendation_feedback_multiplier", "trend_rows", "build_battle_learning_report",
    "runs_to_csv", "export_battle_learning_json",
]
