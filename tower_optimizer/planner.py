"""Progression planning, resource forecasting, and queue management.

The planner converts whole-account recommendations into an actionable schedule.
It remains deliberately explainable: it does not predict exact waves or hidden
future game changes, and it marks recommendations with unmodeled costs clearly.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
import re
import statistics
import uuid
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

from .engines.combined import build_combined_recommendations


GOAL_OPTIONS = [
    "Balanced progression",
    "Improve farming coins/hour",
    "Increase cells/hour",
    "Push tier/wave",
    "Improve tournament placement",
    "Complete GT/BH sync",
    "Build toward permanent Black Hole",
    "Module transition",
]

GOAL_FOCUS = {
    "Balanced progression": "Balanced",
    "Improve farming coins/hour": "Economy",
    "Increase cells/hour": "Damage",
    "Push tier/wave": "Survival",
    "Improve tournament placement": "Damage",
    "Complete GT/BH sync": "Economy",
    "Build toward permanent Black Hole": "Economy",
    "Module transition": "Modules",
}

RESOURCE_PROFILE_KEYS = {
    "Coins": "coins",
    "Stones": "stones",
    "Gems": "gems",
    "Medals": "medals",
    "Keys": "keys",
    "Bits": "bits",
    "Reroll Shards": "reroll_shards",
    "Module Shards": "module_shards",
}

RATE_FIELDS = {
    "Coins": "coins_per_hour",
    "Cells": "cells_per_hour",
    "Stones": "stones_per_week",
    "Gems": "gems_per_day",
    "Medals": "medals_per_week",
    "Keys": "keys_per_week",
    "Bits": "bits_per_day",
    "Reroll Shards": "reroll_shards_per_day",
    "Module Shards": "module_shards_per_day",
}

WEEKLY_RESOURCES = {"Stones", "Medals", "Keys"}
HOURLY_RESOURCES = {"Coins"}

CORE_LAB_LABELS = {
    "lab speed": "Core / long-running",
    "attack speed": "Core combat",
    "coins / kill bonus": "Core economy",
    "coins/kill bonus": "Core economy",
    "health regen": "Core sustain",
}


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
    for fmt in ("%b %d, %Y %H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def planner_defaults() -> Dict[str, Any]:
    return {
        "settings": {
            "goal": "Balanced progression",
            "focus": "Balanced",
            "target_tier": 10,
            "target_wave": 4500,
            "lab_slots": 5,
            "planning_horizon_days": 7,
            "hours_played_per_day": 4.0,
            "use_death_weighting": True,
            "income_rates": {
                "coins_per_hour": 0.0,
                "cells_per_hour": 0.0,
                "stones_per_week": 0.0,
                "gems_per_day": 0.0,
                "medals_per_week": 0.0,
                "keys_per_week": 0.0,
                "bits_per_day": 0.0,
                "reroll_shards_per_day": 0.0,
                "module_shards_per_day": 0.0,
            },
        },
        "queue": [],
        "queue_history": [],
        "completed": [],
        "weekly_snapshots": [],
        "last_generated": None,
    }


def ensure_planner_state(profile: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    defaults = planner_defaults()
    planner = profile.setdefault("planner", {})
    if not isinstance(planner, MutableMapping):
        profile["planner"] = {}
        planner = profile["planner"]
    for key, value in defaults.items():
        planner.setdefault(key, deepcopy(value))
    if not isinstance(planner.get("settings"), MutableMapping):
        planner["settings"] = deepcopy(defaults["settings"])
    settings = planner["settings"]
    for key, value in defaults["settings"].items():
        settings.setdefault(key, deepcopy(value))
    if not isinstance(settings.get("income_rates"), MutableMapping):
        settings["income_rates"] = deepcopy(defaults["settings"]["income_rates"])
    for key, value in defaults["settings"]["income_rates"].items():
        settings["income_rates"].setdefault(key, value)
    for key in ("queue", "queue_history", "completed", "weekly_snapshots"):
        if not isinstance(planner.get(key), list):
            planner[key] = []
    if settings.get("goal") not in GOAL_OPTIONS:
        settings["goal"] = "Balanced progression"
    settings["focus"] = GOAL_FOCUS.get(str(settings.get("goal")), str(settings.get("focus") or "Balanced"))
    return planner


def derive_run_rates(profile: Mapping[str, Any], recent_limit: int = 5) -> Dict[str, float]:
    """Derive conservative median rates from recent battle reports."""
    runs = profile.get("runs", []) if isinstance(profile, Mapping) else []
    if not isinstance(runs, list):
        return {"coins_per_hour": 0.0, "cells_per_hour": 0.0}
    recent = runs[-recent_limit:]
    coins = [_number(run.get("coins_per_hour")) for run in recent if isinstance(run, Mapping)]
    cells = [_number(run.get("cells_per_hour")) for run in recent if isinstance(run, Mapping)]
    coins = [value for value in coins if value > 0]
    cells = [value for value in cells if value > 0]
    return {
        "coins_per_hour": statistics.median(coins) if coins else 0.0,
        "cells_per_hour": statistics.median(cells) if cells else 0.0,
    }


def effective_income_rates(profile: MutableMapping[str, Any]) -> Dict[str, float]:
    planner = ensure_planner_state(profile)
    manual = planner["settings"]["income_rates"]
    derived = derive_run_rates(profile)
    result = {key: max(0.0, _number(value)) for key, value in manual.items()}
    for key in ("coins_per_hour", "cells_per_hour"):
        if result.get(key, 0.0) <= 0:
            result[key] = derived.get(key, 0.0)
    return result


def _resource_balance(profile: Mapping[str, Any], resource: str) -> float:
    key = RESOURCE_PROFILE_KEYS.get(resource)
    if not key:
        return 0.0
    resources = profile.get("resources", {}) if isinstance(profile, Mapping) else {}
    return max(0.0, _number(resources.get(key))) if isinstance(resources, Mapping) else 0.0


def resource_rate_per_day(profile: MutableMapping[str, Any], resource: str) -> float:
    rates = effective_income_rates(profile)
    settings = ensure_planner_state(profile)["settings"]
    if resource == "Coins":
        return max(0.0, rates.get("coins_per_hour", 0.0) * _number(settings.get("hours_played_per_day"), 4.0))
    field = RATE_FIELDS.get(resource)
    if not field:
        return 0.0
    value = max(0.0, rates.get(field, 0.0))
    if resource in WEEKLY_RESOURCES:
        return value / 7.0
    return value


def days_to_afford(profile: MutableMapping[str, Any], resource: str, cost: Any) -> Optional[float]:
    amount = _number(cost)
    if amount <= 0:
        return None
    remaining = max(0.0, amount - _resource_balance(profile, resource))
    if remaining <= 0:
        return 0.0
    daily = resource_rate_per_day(profile, resource)
    if daily <= 0:
        return None
    return remaining / daily


def _parse_duration_days(row: Mapping[str, Any]) -> Optional[float]:
    """Extract an approximate lab duration from recommendation text."""
    why = str(row.get("Why", ""))
    patterns = [
        (r"over\s+([0-9]+(?:\.[0-9]+)?)\s+adjusted lab days", 1.0),
        (r"in\s+([0-9]+(?:\.[0-9]+)?)\s+adjusted lab days", 1.0),
    ]
    for pattern, scale in patterns:
        match = re.search(pattern, why, flags=re.IGNORECASE)
        if match:
            return max(0.0, float(match.group(1)) * scale)

    text = str(row.get("Cost / Time", ""))
    # Avoid treating compact currency values such as 305.51M as minutes.
    if any(token in text.lower() for token in ("cost", "$")) or re.fullmatch(r"\s*[0-9.]+[kmbtqQsS]\s*", text):
        text = why
    days = hours = minutes = seconds = 0.0
    matched = False
    for value, unit in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*(d|h|m|s)\b", text, flags=re.IGNORECASE):
        matched = True
        number = float(value)
        unit = unit.lower()
        if unit == "d":
            days += number
        elif unit == "h":
            hours += number
        elif unit == "m":
            minutes += number
        else:
            seconds += number
    if not matched:
        return None
    return days + hours / 24.0 + minutes / 1440.0 + seconds / 86400.0


def format_duration(days: Optional[float]) -> str:
    if days is None:
        return "Duration not modeled"
    if days < 1 / 24:
        return f"{max(1, round(days * 1440))}m"
    if days < 1:
        hours = int(days * 24)
        minutes = int(round((days * 24 - hours) * 60))
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    whole_days = int(days)
    hours = int(round((days - whole_days) * 24))
    if hours >= 24:
        whole_days += 1
        hours = 0
    return f"{whole_days}d {hours}h" if hours else f"{whole_days}d"


def _goal_bonus(row: Mapping[str, Any], goal: str) -> tuple[float, list[str]]:
    upgrade = str(row.get("Upgrade", "")).casefold()
    domain = str(row.get("Domain", ""))
    resource = str(row.get("Resource", ""))
    system = str(row.get("System", ""))
    bonus = 0.0
    reasons: list[str] = []

    if goal == "Improve farming coins/hour":
        if domain == "Economy":
            bonus += 18
            reasons.append("directly supports farming income")
    elif goal == "Increase cells/hour":
        if domain in {"Damage", "Survivability", "Regen / Recovery"}:
            bonus += 10
            reasons.append("helps sustain higher-wave cell farming")
        if any(word in upgrade for word in ("enemy health skip", "enemy attack skip", "damage", "health")):
            bonus += 5
    elif goal == "Push tier/wave":
        if domain in {"Survivability", "Regen / Recovery", "Damage"}:
            bonus += 14
            reasons.append("supports deeper runs")
    elif goal == "Improve tournament placement":
        if domain == "Damage":
            bonus += 16
            reasons.append("matches tournament damage pressure")
        if system == "Modules":
            bonus += 5
    elif goal == "Complete GT/BH sync":
        if resource == "Stones" and any(word in upgrade for word in ("golden tower", "gt |", "black hole", "bh |")):
            bonus += 28
            reasons.append("directly advances GT/BH synchronization")
        if "cooldown" in upgrade and any(word in upgrade for word in ("gt", "bh", "golden tower", "black hole")):
            bonus += 12
    elif goal == "Build toward permanent Black Hole":
        if "black hole" in upgrade or "bh |" in upgrade:
            bonus += 30
            reasons.append("directly advances Black Hole uptime")
        if any(word in upgrade for word in ("duration", "cooldown")) and resource in {"Lab", "Stones"}:
            bonus += 8
    elif goal == "Module transition":
        if system == "Modules" or resource in {"Reroll Shards", "Module Shards"}:
            bonus += 28
            reasons.append("supports the selected module transition")
    return bonus, reasons


def _ranked_rows(rows: Iterable[Mapping[str, Any]], goal: str) -> list[Dict[str, Any]]:
    ranked: list[Dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        bonus, goal_reasons = _goal_bonus(row, goal)
        row["Planner Score"] = round(_number(row.get("Priority Index")) + bonus, 3)
        row["Goal Bonus"] = bonus
        row["Goal Reason"] = "; ".join(goal_reasons)
        ranked.append(row)
    return sorted(ranked, key=lambda item: _number(item.get("Planner Score")), reverse=True)


def _unique_rows(rows: Iterable[Mapping[str, Any]], limit: int) -> list[Dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[Dict[str, Any]] = []
    for source in rows:
        key = (str(source.get("Resource", "")), str(source.get("Upgrade", "")).casefold().strip())
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(source))
        if len(result) >= limit:
            break
    return result


def build_lab_plan(rows: Iterable[Mapping[str, Any]], slots: int = 5, goal: str = "Balanced progression") -> list[Dict[str, Any]]:
    candidates = _ranked_rows((row for row in rows if row.get("Resource") == "Lab"), goal)
    selected: list[Dict[str, Any]] = []
    domain_counts: Dict[str, int] = {}
    remaining = list(candidates)
    while remaining and len(selected) < max(1, int(slots)):
        best_index = 0
        best_adjusted = -1e99
        for index, row in enumerate(remaining):
            domain = str(row.get("Domain", "Other"))
            diversity_penalty = domain_counts.get(domain, 0) * 4.0
            score = _number(row.get("Planner Score")) - diversity_penalty
            if score > best_adjusted:
                best_adjusted = score
                best_index = index
        chosen = remaining.pop(best_index)
        selected.append(chosen)
        domain = str(chosen.get("Domain", "Other"))
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    replacement_pool = [row for row in candidates if row.get("Upgrade") not in {item.get("Upgrade") for item in selected}]
    result: list[Dict[str, Any]] = []
    elapsed = 0.0
    for index, row in enumerate(selected, start=1):
        duration_days = _parse_duration_days(row)
        replacement = replacement_pool[index - 1].get("Upgrade") if index - 1 < len(replacement_pool) else "Regenerate after completion"
        normalized = str(row.get("Upgrade", "")).casefold().strip()
        designation = next((label for name, label in CORE_LAB_LABELS.items() if name in normalized), "Priority research")
        result.append({
            "Slot": index,
            "Research": row.get("Upgrade"),
            "Next Level": row.get("Next Level"),
            "Domain": row.get("Domain"),
            "Estimated Duration": format_duration(duration_days),
            "Duration Days": duration_days,
            "Designation": designation,
            "Replacement": replacement,
            "Planner Score": row.get("Planner Score"),
            "Confidence": row.get("Confidence"),
            "Why": row.get("Why"),
            "Source Row": row,
            "Queue Start Day": round(elapsed, 2),
        })
        if duration_days is not None:
            elapsed += duration_days
    return result


def _action_text(row: Mapping[str, Any], profile: MutableMapping[str, Any]) -> tuple[str, str]:
    resource = str(row.get("Resource", ""))
    affordable = row.get("Affordable Bool")
    cost = row.get("Cost Numeric")
    if resource == "Lab":
        return ("Start", "Queue in an open lab slot")
    if affordable is True:
        return ("Spend", "Affordable with the entered balance")
    if affordable is False:
        wait = days_to_afford(profile, resource, cost)
        when = f"Save about {format_duration(wait)}" if wait is not None else "Save until affordable"
        return ("Save", when)
    if resource in {"Milestone / Event", "Action"}:
        return ("Target", str(row.get("Cost / Time") or "Complete the listed requirement"))
    return ("Review", "Cost is not modeled; check the in-game price")


def build_daily_actions(profile: MutableMapping[str, Any], ranked_rows: list[Dict[str, Any]], limit: int = 6) -> list[Dict[str, Any]]:
    chosen: list[Dict[str, Any]] = []
    used_resources: set[str] = set()

    # First select the highest lab and the highest bottleneck action.
    for preferred in ("Lab", "Coins", "Stones"):
        candidate = next((row for row in ranked_rows if row.get("Resource") == preferred), None)
        if candidate:
            chosen.append(candidate)
            used_resources.add(preferred)

    for row in ranked_rows:
        if len(chosen) >= limit:
            break
        resource = str(row.get("Resource", ""))
        if row in chosen:
            continue
        # Prefer resource diversity before adding a second action from the same pool.
        if resource in used_resources and len(used_resources) < 5:
            continue
        chosen.append(row)
        used_resources.add(resource)

    if len(chosen) < limit:
        for row in ranked_rows:
            if row not in chosen:
                chosen.append(row)
                if len(chosen) >= limit:
                    break

    actions: list[Dict[str, Any]] = []
    for rank, row in enumerate(chosen, start=1):
        verb, when = _action_text(row, profile)
        actions.append({
            "Order": rank,
            "Action": f"{verb}: {row.get('Upgrade')}",
            "System": row.get("System"),
            "Resource": row.get("Resource"),
            "Next Level": row.get("Next Level"),
            "When": when,
            "Planner Score": row.get("Planner Score"),
            "Confidence": row.get("Confidence"),
            "Why": row.get("Why"),
            "Source Row": row,
        })
    return actions


def build_resource_forecast(profile: MutableMapping[str, Any], ranked_rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for resource in RESOURCE_PROFILE_KEYS:
        candidates = [row for row in ranked_rows if row.get("Resource") == resource]
        if not candidates:
            continue
        row = candidates[0]
        balance = _resource_balance(profile, resource)
        cost = _number(row.get("Cost Numeric"))
        daily = resource_rate_per_day(profile, resource)
        wait = days_to_afford(profile, resource, cost)
        if cost <= 0:
            status = "Cost not modeled"
            target_date = "—"
        elif wait == 0:
            status = "Affordable now"
            target_date = _now().date().isoformat()
        elif wait is None:
            status = "Enter an income rate"
            target_date = "—"
        else:
            status = f"About {format_duration(wait)}"
            target_date = (_now() + timedelta(days=wait)).date().isoformat()
        result.append({
            "Resource": resource,
            "Current Balance": balance,
            "Estimated Gain / Day": daily,
            "Top Target": row.get("Upgrade"),
            "Target Cost": cost if cost > 0 else None,
            "Forecast": status,
            "Estimated Date": target_date,
            "Confidence": row.get("Confidence"),
        })
    return result


def build_staged_plan(
    profile: MutableMapping[str, Any], ranked_rows: list[Dict[str, Any]],
    goal: str, target_tier: int, target_wave: int,
) -> Dict[str, list[Dict[str, Any]]]:
    stages: Dict[str, list[Dict[str, Any]]] = {"Immediate": [], "Next 7 days": [], "Next 30 days": [], "Long term": []}
    for row in ranked_rows:
        resource = str(row.get("Resource", ""))
        wait = days_to_afford(profile, resource, row.get("Cost Numeric"))
        if resource == "Lab" or row.get("Affordable Bool") is True:
            stage = "Immediate"
        elif wait is not None and wait <= 7:
            stage = "Next 7 days"
        elif wait is not None and wait <= 30:
            stage = "Next 30 days"
        elif row.get("Affordable Bool") is None and _number(row.get("Planner Score")) >= 90:
            stage = "Next 7 days"
        elif row.get("Affordable Bool") is None and _number(row.get("Planner Score")) >= 75:
            stage = "Next 30 days"
        else:
            stage = "Long term"
        if len(stages[stage]) >= (6 if stage == "Immediate" else 8):
            continue
        stages[stage].append({
            "System": row.get("System"),
            "Resource": resource,
            "Upgrade": row.get("Upgrade"),
            "Next Level": row.get("Next Level"),
            "Planner Score": row.get("Planner Score"),
            "Timing": "Now" if stage == "Immediate" else (format_duration(wait) if wait is not None else "Strategic / unpriced"),
            "Why": row.get("Goal Reason") or row.get("Why"),
        })

    stages["Long term"].insert(0, {
        "System": "Milestone",
        "Resource": "Account progression",
        "Upgrade": f"{goal}: target Tier {target_tier}, wave {target_wave:,}",
        "Next Level": "Re-evaluate after each major upgrade",
        "Planner Score": None,
        "Timing": "No exact wave prediction",
        "Why": "The planner builds an upgrade route but does not claim a precise wave forecast.",
    })
    return stages


def build_progression_plan(profile: MutableMapping[str, Any]) -> Dict[str, Any]:
    planner = ensure_planner_state(profile)
    settings = planner["settings"]
    goal = str(settings.get("goal", "Balanced progression"))
    focus = GOAL_FOCUS.get(goal, str(settings.get("focus", "Balanced")))
    settings["focus"] = focus
    combined = build_combined_recommendations(
        profile,
        steps=20,
        candidates_per_path=4,
        focus=focus,
        apply_death_weighting=bool(settings.get("use_death_weighting", True)),
    )
    ranked_rows = _ranked_rows(combined.get("rows", []), goal)
    lab_plan = build_lab_plan(ranked_rows, int(settings.get("lab_slots", 5) or 5), goal)
    daily = build_daily_actions(profile, ranked_rows)
    stages = build_staged_plan(
        profile, ranked_rows, goal,
        int(settings.get("target_tier", 10) or 10),
        int(settings.get("target_wave", 4500) or 4500),
    )
    forecast = build_resource_forecast(profile, ranked_rows)
    planner["last_generated"] = _iso()
    return {
        "goal": goal,
        "focus": focus,
        "combined": combined,
        "ranked_rows": ranked_rows,
        "daily_actions": daily,
        "lab_plan": lab_plan,
        "stages": stages,
        "forecast": forecast,
        "analysis": combined.get("analysis", {}),
        "latest_death": combined.get("latest_death", "No report saved"),
        "generated_at": planner["last_generated"],
        "method": (
            "Planner scores start with the whole-account Priority Index, then apply transparent goal weighting. "
            "Affordability dates use entered balances and income rates; exact wave outcomes are not predicted."
        ),
    }


def _queue_snapshot(planner: MutableMapping[str, Any], description: str) -> None:
    history = planner.setdefault("queue_history", [])
    history.append({"at": _iso(), "description": description, "queue": deepcopy(planner.get("queue", [])), "completed": deepcopy(planner.get("completed", []))})
    del history[:-20]


def queue_add(profile: MutableMapping[str, Any], row: Mapping[str, Any], source: str = "Progression Planner") -> str:
    planner = ensure_planner_state(profile)
    queue = planner["queue"]
    upgrade = str(row.get("Upgrade") or row.get("Research") or "Unnamed action")
    resource = str(row.get("Resource") or ("Lab" if row.get("Research") else "Action"))
    existing = next((item for item in queue if item.get("upgrade") == upgrade and item.get("resource") == resource and item.get("status") not in {"Completed", "Skipped"}), None)
    if existing:
        return str(existing.get("id"))
    _queue_snapshot(planner, f"Add {upgrade}")
    order = max([int(item.get("order", 0)) for item in queue] or [0]) + 1
    item_id = uuid.uuid4().hex[:12]
    queue.append({
        "id": item_id,
        "order": order,
        "created_at": _iso(),
        "updated_at": _iso(),
        "status": "Planned",
        "locked": False,
        "source": source,
        "system": row.get("System") or "Laboratory",
        "resource": resource,
        "domain": row.get("Domain") or "Auto",
        "upgrade": upgrade,
        "next_level": row.get("Next Level"),
        "cost_text": row.get("Cost / Time") or row.get("Estimated Duration") or "Not modeled",
        "cost_numeric": _number(row.get("Cost Numeric")),
        "priority": _number(row.get("Planner Score"), _number(row.get("Priority Index"))),
        "confidence": row.get("Confidence", "Unknown"),
        "why": row.get("Why", ""),
        "completed_at": None,
        "skipped_at": None,
    })
    return item_id


def queue_set_status(profile: MutableMapping[str, Any], item_id: str, status: str) -> bool:
    if status not in {"Planned", "In Progress", "Completed", "Skipped"}:
        return False
    planner = ensure_planner_state(profile)
    item = next((entry for entry in planner["queue"] if str(entry.get("id")) == str(item_id)), None)
    if not item:
        return False
    _queue_snapshot(planner, f"Set {item.get('upgrade')} to {status}")
    item["status"] = status
    item["updated_at"] = _iso()
    if status == "Completed":
        item["completed_at"] = _iso()
        item["skipped_at"] = None
        completed = planner.setdefault("completed", [])
        completed[:] = [entry for entry in completed if str(entry.get("id")) != str(item_id)]
        completed.append(deepcopy(item))
    elif status == "Skipped":
        item["skipped_at"] = _iso()
        item["completed_at"] = None
    else:
        item["completed_at"] = None
        item["skipped_at"] = None
    return True


def queue_toggle_lock(profile: MutableMapping[str, Any], item_id: str) -> bool:
    planner = ensure_planner_state(profile)
    item = next((entry for entry in planner["queue"] if str(entry.get("id")) == str(item_id)), None)
    if not item:
        return False
    _queue_snapshot(planner, f"Toggle lock for {item.get('upgrade')}")
    item["locked"] = not bool(item.get("locked"))
    item["updated_at"] = _iso()
    return True


def queue_move(profile: MutableMapping[str, Any], item_id: str, direction: int) -> bool:
    planner = ensure_planner_state(profile)
    queue = sorted(planner["queue"], key=lambda item: int(item.get("order", 0)))
    index = next((i for i, item in enumerate(queue) if str(item.get("id")) == str(item_id)), None)
    if index is None:
        return False
    target = index + (-1 if direction < 0 else 1)
    if target < 0 or target >= len(queue):
        return False
    _queue_snapshot(planner, f"Move {queue[index].get('upgrade')}")
    queue[index]["order"], queue[target]["order"] = queue[target].get("order", target + 1), queue[index].get("order", index + 1)
    planner["queue"] = sorted(queue, key=lambda item: int(item.get("order", 0)))
    return True


def queue_remove(profile: MutableMapping[str, Any], item_id: str) -> bool:
    planner = ensure_planner_state(profile)
    queue = planner["queue"]
    index = next((i for i, item in enumerate(queue) if str(item.get("id")) == str(item_id)), None)
    if index is None:
        return False
    if bool(queue[index].get("locked")):
        return False
    _queue_snapshot(planner, f"Remove {queue[index].get('upgrade')}")
    queue.pop(index)
    for order, item in enumerate(sorted(queue, key=lambda entry: int(entry.get("order", 0))), start=1):
        item["order"] = order
    return True


def queue_undo(profile: MutableMapping[str, Any]) -> Optional[str]:
    planner = ensure_planner_state(profile)
    history = planner["queue_history"]
    if not history:
        return None
    snapshot = history.pop()
    planner["queue"] = deepcopy(snapshot.get("queue", []))
    planner["completed"] = deepcopy(snapshot.get("completed", planner.get("completed", [])))
    return str(snapshot.get("description", "Last queue action"))


def queue_rows(profile: MutableMapping[str, Any], include_finished: bool = True) -> list[Dict[str, Any]]:
    planner = ensure_planner_state(profile)
    rows = sorted(planner["queue"], key=lambda item: int(item.get("order", 0)))
    if not include_finished:
        rows = [item for item in rows if item.get("status") not in {"Completed", "Skipped"}]
    return deepcopy(rows)


def _run_timestamp(run: Mapping[str, Any]) -> Optional[datetime]:
    return _parse_datetime(run.get("battle_date")) or _parse_datetime(run.get("imported_at"))


def _period_runs(profile: Mapping[str, Any], start: datetime, end: datetime) -> list[Mapping[str, Any]]:
    runs = profile.get("runs", []) if isinstance(profile, Mapping) else []
    result = []
    if isinstance(runs, list):
        for run in runs:
            if not isinstance(run, Mapping):
                continue
            stamp = _run_timestamp(run)
            if stamp is not None and start <= stamp < end:
                result.append(run)
    return result


def _run_summary(runs: list[Mapping[str, Any]]) -> Dict[str, Any]:
    coins = [_number(run.get("coins_per_hour")) for run in runs if _number(run.get("coins_per_hour")) > 0]
    cells = [_number(run.get("cells_per_hour")) for run in runs if _number(run.get("cells_per_hour")) > 0]
    waves = [int(_number(run.get("wave"))) for run in runs]
    tiers = [int(_number(run.get("tier"))) for run in runs]
    return {
        "runs": len(runs),
        "avg_coins_per_hour": statistics.mean(coins) if coins else 0.0,
        "avg_cells_per_hour": statistics.mean(cells) if cells else 0.0,
        "best_wave": max(waves) if waves else 0,
        "highest_tier": max(tiers) if tiers else 0,
    }


def _trend(current: float, previous: float) -> Optional[float]:
    if previous <= 0:
        return None
    return 100.0 * (current - previous) / previous


def build_weekly_report(profile: MutableMapping[str, Any], plan: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    now = _now()
    current_runs = _period_runs(profile, now - timedelta(days=7), now + timedelta(seconds=1))
    previous_runs = _period_runs(profile, now - timedelta(days=14), now - timedelta(days=7))
    # If imported timestamps are old/missing, still show the most recent records as context.
    if not current_runs:
        all_runs = profile.get("runs", []) if isinstance(profile.get("runs", []), list) else []
        current_runs = [run for run in all_runs[-5:] if isinstance(run, Mapping)]
    current = _run_summary(current_runs)
    previous = _run_summary(previous_runs)
    planner = ensure_planner_state(profile)
    completed = []
    for item in planner.get("completed", []):
        stamp = _parse_datetime(item.get("completed_at")) if isinstance(item, Mapping) else None
        if stamp and stamp >= now - timedelta(days=7):
            completed.append(item)
    if plan is None:
        plan = build_progression_plan(profile)
    priorities = [
        {key: action.get(key) for key in ("Action", "Resource", "When", "Why")}
        for action in plan.get("daily_actions", [])[:5]
    ]
    return {
        "period_start": (now - timedelta(days=7)).date().isoformat(),
        "period_end": now.date().isoformat(),
        "current": current,
        "previous": previous,
        "trends": {
            "coins_per_hour_percent": _trend(current["avg_coins_per_hour"], previous["avg_coins_per_hour"]),
            "cells_per_hour_percent": _trend(current["avg_cells_per_hour"], previous["avg_cells_per_hour"]),
            "best_wave_percent": _trend(float(current["best_wave"]), float(previous["best_wave"])),
        },
        "completed_upgrades": deepcopy(completed),
        "current_bottleneck": plan.get("analysis", {}).get("weakest", "Unknown"),
        "latest_death": plan.get("latest_death", "No report saved"),
        "next_week_priorities": priorities,
        "generated_at": _iso(now),
        "note": "Battle trends use dated reports when available; otherwise the most recently imported reports are shown as context.",
    }


__all__ = [
    "GOAL_OPTIONS", "GOAL_FOCUS", "planner_defaults", "ensure_planner_state",
    "derive_run_rates", "effective_income_rates", "resource_rate_per_day",
    "days_to_afford", "format_duration", "build_lab_plan", "build_progression_plan",
    "build_weekly_report", "queue_add", "queue_set_status", "queue_toggle_lock",
    "queue_move", "queue_remove", "queue_undo", "queue_rows",
]
