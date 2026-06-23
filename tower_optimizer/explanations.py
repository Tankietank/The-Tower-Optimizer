from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

UpgradeGuidanceFn = Callable[[Mapping[str, Any], Mapping[str, Any]], Tuple[List[str], List[str]]]

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


def _parse_why_text(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"\s*;\s*", str(text).strip())
    return [part.strip() for part in parts if part.strip()]


def _current_value(row: Mapping[str, Any], profile: Mapping[str, Any]) -> Any:
    upgrade = str(row.get("Upgrade", ""))
    path_key = str(row.get("Path Key", ""))
    if path_key.endswith("_lab") or path_key == "econ_discount":
        return profile.get("labs", {}).get(upgrade, "Unknown")
    if path_key.endswith("_coin"):
        return profile.get("enhancements", {}).get(upgrade, profile.get("workshop", {}).get(upgrade, "Unknown"))
    if path_key.endswith("_stone") and "|" in upgrade:
        prefix, attribute = [part.strip() for part in upgrade.split("|", 1)]
        uw_name = UW_ABBREVIATIONS.get(prefix, prefix)
        return profile.get("uw", {}).get(uw_name, {}).get("attributes", {}).get(attribute, "Unknown")
    system = str(row.get("System", ""))
    if system == "Cards" and "Card Slot" in upgrade:
        return profile.get("cards", {}).get("slots", "Unknown")
    if system == "Modules":
        return "Imported module inventory/preset"
    if system == "Bots":
        return "Imported bot state"
    if system == "Guardians":
        return "Imported guardian state"
    if system == "Vault":
        return "Imported Vault state"
    if system in {"Relics", "Themes & Songs"}:
        return "Not owned"
    return "Unknown"


def _format_gain(gain: Any) -> str:
    if not isinstance(gain, (int, float)):
        return "not modeled as a verified percent gain"
    value = float(gain)
    if value <= 0:
        return "strategic priority rather than a modeled percent gain"
    return f"about {value:.2f}% relative gain in its native path"


def _affordability_phrase(affordability: str) -> str:
    if affordability == "Affordable":
        return "You can afford this with the balances entered in your profile."
    if affordability == "Unaffordable":
        return "This is a save-up target — it ranks highly, but costs more than your entered balance."
    if affordability == "Balance not entered":
        return "Enter resource balances in your profile to check affordability."
    return "Affordability was not modeled for this action."


def _int_level(profile: Mapping[str, Any], section: str, name: str) -> int:
    bucket = profile.get(section, {})
    if not isinstance(bucket, Mapping):
        return 0
    try:
        return int(bucket.get(name, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _defense_absolute_totals(profile: Mapping[str, Any]) -> Tuple[int, int, int]:
    return (
        _int_level(profile, "workshop", "Defense Absolute"),
        _int_level(profile, "labs", "Defense Absolute"),
        _int_level(profile, "enhancements", "Defense Absolute +"),
    )


def _defense_absolute_is_early(profile: Mapping[str, Any]) -> bool:
    ws, lab, enh = _defense_absolute_totals(profile)
    return ws < 50 and lab < 10 and enh < 15


def _guidance_defense_absolute(profile: Mapping[str, Any], row: Mapping[str, Any]) -> Tuple[List[str], List[str]]:
    ws, lab, enh = _defense_absolute_totals(profile)
    why: List[str] = []
    tradeoffs: List[str] = []
    if _defense_absolute_is_early(profile):
        why.append(
            "At very low Defense Absolute totals, flat damage reduction still trims meaningful chip "
            "damage before percentage mitigation and Health pools dominate survivability."
        )
    else:
        tradeoffs.extend([
            "Defense Absolute is flat reduction — as enemy attack scales with tiers, each level buys "
            "less effective eHP than Defense %, Health, or Wall Health in the same coin/lab budget.",
            "The native eHP model weights Defense Absolute lightly because its impact shrinks relative "
            "to percentage mitigation once workshop and lab totals leave the early game.",
        ])
        if ws >= 100 or lab >= 20 or enh >= 50:
            tradeoffs.append(
                "With Defense Absolute already at mid levels, most accounts get stronger survivability "
                "returns from Defense % labs, Health enhancements, or Recovery Package paths."
            )
    return why, tradeoffs


def _guidance_defense_percent(profile: Mapping[str, Any], row: Mapping[str, Any]) -> Tuple[List[str], List[str]]:
    del profile, row
    return (
        [
            "Defense % multiplies with Health in the eHP formula — percentage mitigation stays "
            "efficient deep into late game, unlike flat Defense Absolute."
        ],
        [],
    )


def _guidance_health(profile: Mapping[str, Any], row: Mapping[str, Any]) -> Tuple[List[str], List[str]]:
    del row
    ws_health = _int_level(profile, "workshop", "Health")
    lab_health = _int_level(profile, "labs", "Health")
    if ws_health >= 4000 and lab_health >= 80:
        return (
            [],
            [
                "Health is already high — marginal eHP per coin may trail Recovery Package, "
                "Defense %, or Wall Health until those paths catch up."
            ],
        )
    return (
        [
            "Raw Health scales the entire eHP pool and pairs with Defense % mitigation — "
            "it remains a core survivability lever at most progression stages."
        ],
        [],
    )


UPGRADE_GUIDANCE: Dict[str, UpgradeGuidanceFn] = {
    "Defense Absolute": _guidance_defense_absolute,
    "Defense Absolute +": _guidance_defense_absolute,
    "Defense %": _guidance_defense_percent,
    "Health": _guidance_health,
    "Health +": _guidance_health,
}


def _upgrade_specific_guidance(
    upgrade: str,
    profile: Mapping[str, Any],
    row: Mapping[str, Any],
) -> Tuple[List[str], List[str]]:
    handler = UPGRADE_GUIDANCE.get(upgrade.strip())
    if handler is None:
        return [], []
    return handler(profile, row)


def recommendation_explanation(
    row: Mapping[str, Any],
    profile: Mapping[str, Any],
    analysis: Optional[Mapping[str, Any]] = None,
    latest_death: str = "",
) -> Dict[str, Any]:
    analysis = analysis or {}
    current_value = _current_value(row, profile)
    reference_rank = row.get("Reference Rank")
    confidence = str(row.get("Confidence", "Model estimate"))
    affordability = str(row.get("Affordability", "Unknown"))
    domain = str(row.get("Domain", "Unknown"))
    resource = str(row.get("Resource", "Unknown"))
    system = str(row.get("System", "Native engine"))
    path_rank = row.get("Path Rank")
    gain = row.get("Estimated Gain %")
    upgrade = str(row.get("Upgrade", "This upgrade"))
    next_level = row.get("Next Level", "Unknown")
    cost = row.get("Cost / Time", "Unknown")
    learning_multiplier = row.get("Learning Multiplier")

    why_now: List[str] = []
    if path_rank:
        why_now.append(f"Ranks #{path_rank} inside its {row.get('Path', 'native')} path before cross-category comparison.")
    if system and system not in {"Native engine", "Native Engines"}:
        why_now.append(f"Competes as a {system} action using your {resource} budget.")
    if domain and analysis.get("weakest") == domain:
        why_now.append(f"Your profile's weakest modeled area is {domain}, so improvements here reduce the biggest gap.")
    if latest_death and latest_death not in {"Unknown", "No report saved"}:
        why_now.append(f"Recent runs ended to {latest_death}, so {domain} upgrades were weighted accordingly.")
    if reference_rank:
        why_now.append(f"Also appears around rank {reference_rank} in your imported Effective Paths reference.")
    why_now.extend(_parse_why_text(str(row.get("Why", ""))))
    if isinstance(learning_multiplier, (int, float)) and abs(float(learning_multiplier) - 1.0) > 0.0001:
        direction = "raised" if float(learning_multiplier) > 1.0 else "lowered"
        why_now.append(
            f"Battle history {direction} this priority by {abs(float(learning_multiplier) - 1.0) * 100:.1f}% "
            f"(capped modifier, not proof of causation)."
        )
    why_now.append(_affordability_phrase(affordability))
    why_now.append(f"Expected impact: {_format_gain(gain)}.")

    guidance_why, guidance_tradeoffs = _upgrade_specific_guidance(upgrade, profile, row)
    why_now.extend(guidance_why)

    # De-dupe while preserving order.
    seen: set[str] = set()
    deduped_why: List[str] = []
    for item in why_now:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped_why.append(item)

    what_changes = [
        f"Current value: {current_value}",
        f"Suggested next step: {next_level}",
        f"Cost or time: {cost}",
        f"Resource: {resource}",
        f"System: {system}",
    ]
    native_roi = row.get("Native ROI")
    if native_roi not in (None, "", "Strategic score"):
        what_changes.append(f"Native ROI in-path: {native_roi}")

    tradeoffs = [
        "Priority scores compare normalized ranks across unlike resources — they are a shortlist, not exact game math.",
        "Modeled gains describe relative engine output, not guaranteed wave or coins-per-hour jumps.",
    ]
    if not reference_rank and not str(row.get("Path Key", "")).startswith("account_"):
        tradeoffs.append("No matching Effective Paths reference row was found for this pick.")
    if str(row.get("Path Key", "")).startswith("account_"):
        tradeoffs.append("This uses transparent strategic benchmarks where a verified in-game cost curve is not bundled.")
    if current_value == "Unknown":
        tradeoffs.append("The current level could not be read from your profile, which lowers practical confidence.")
    if not profile.get("runs"):
        tradeoffs.append("Import battle history or save runs for stronger death-cause calibration.")
    tradeoffs.extend(guidance_tradeoffs)

    # De-dupe trade-offs while preserving order.
    seen_tradeoffs: set[str] = set()
    deduped_tradeoffs: List[str] = []
    for item in tradeoffs:
        key = item.casefold()
        if key in seen_tradeoffs:
            continue
        seen_tradeoffs.add(key)
        deduped_tradeoffs.append(item)
    tradeoffs = deduped_tradeoffs

    headline = (
        f"Do **{upgrade}** next — it targets **{domain}** via **{resource}** "
        f"({affordability.lower()})."
    )
    summary = (
        f"{upgrade} is prioritized because "
        + (deduped_why[0].lower() if deduped_why else "it is one of the strongest eligible candidates")
        + "."
    )

    inputs = {
        "Current value": current_value,
        "Recommended next level/value": next_level,
        "Cost or time": cost,
        "System": system,
        "Resource": resource,
        "Affordability": affordability,
        "Estimated relative gain": f"{float(gain):.3f}%" if isinstance(gain, (int, float)) else "Unknown",
        "Native ROI": row.get("Native ROI", "Unknown"),
        "Reference rank": reference_rank if reference_rank is not None else "Not available",
        "Model confidence": confidence,
        "Battle-learning multiplier": (
            f"{float(learning_multiplier):.4f}×" if isinstance(learning_multiplier, (int, float)) else "Not applied"
        ),
    }

    return {
        "Headline": headline,
        "Why now": deduped_why,
        "What changes": what_changes,
        "Trade-offs": tradeoffs,
        "Summary": summary,
        "Inputs": inputs,
        "Reasons": deduped_why,
        "Caveats": tradeoffs,
        "Upgrade guidance": guidance_why + guidance_tradeoffs,
        "Source explanation": row.get("Why", ""),
    }


def attach_explanations(
    profile: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    analysis: Optional[Mapping[str, Any]] = None,
    latest_death: str = "",
) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        row["Explanation"] = recommendation_explanation(row, profile, analysis, latest_death)
        enriched.append(row)
    return enriched


def enrich_recommendation_payload(
    profile: MutableMapping[str, Any],
    payload: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), Mapping) else {}
    latest_death = str(payload.get("latest_death") or "No report saved")
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    payload["rows"] = attach_explanations(profile, rows, analysis=analysis, latest_death=latest_death)
    for key in ("affordable", "long_term", "unpriced", "bottleneck"):
        section = payload.get(key)
        if isinstance(section, list):
            payload[key] = attach_explanations(profile, section, analysis=analysis, latest_death=latest_death)
    by_resource = payload.get("by_resource")
    if isinstance(by_resource, dict):
        payload["by_resource"] = {
            resource: attach_explanations(profile, items, analysis=analysis, latest_death=latest_death)
            for resource, items in by_resource.items()
            if isinstance(items, list)
        }
    by_system = payload.get("by_system")
    if isinstance(by_system, dict):
        payload["by_system"] = {
            system: attach_explanations(profile, items, analysis=analysis, latest_death=latest_death)
            for system, items in by_system.items()
            if isinstance(items, list)
        }
    return payload
