from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

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

    reasons = []
    if path_rank:
        reasons.append(f"ranked #{path_rank} inside its {row.get('Path', 'native')} path")
    if system and system != "Native engine":
        reasons.append(f"competes as a {system} opportunity-cost action")
    if domain and analysis.get("weakest") == domain:
        reasons.append("targets the profile's weakest modeled development area")
    if latest_death and latest_death not in {"Unknown", "No report saved"}:
        reasons.append(f"was adjusted using the latest {latest_death} death signal")
    if reference_rank:
        reasons.append(f"also appears at rank {reference_rank} in the imported Effective Paths reference")
    if affordability == "Affordable":
        reasons.append("fits the currently entered resource balance")
    elif affordability == "Unaffordable":
        reasons.append("is a save-up target rather than an immediate purchase")
    learning_multiplier = row.get("Learning Multiplier")
    if isinstance(learning_multiplier, (int, float)) and abs(float(learning_multiplier) - 1.0) > 0.0001:
        direction = "raised" if float(learning_multiplier) > 1.0 else "lowered"
        reasons.append(f"battle-history evidence {direction} its priority by {abs(float(learning_multiplier) - 1.0) * 100:.1f}%")

    caveats = [
        "The Priority Index compares normalized ranks, not raw ROI across unlike resources.",
        "Estimated gains are model outputs, not guaranteed wave or coin-per-hour improvements.",
    ]
    if not reference_rank and not str(row.get("Path Key", "")).startswith("account_"):
        caveats.append("No matching Effective Paths reference rank was available for this recommendation.")
    if str(row.get("Path Key", "")).startswith("account_"):
        caveats.append("This system uses transparent strategic benchmarks where a verified exact cost curve is not bundled.")
    if current_value == "Unknown":
        caveats.append("The current value could not be resolved from the profile, which lowers practical confidence.")
    if not profile.get("runs"):
        caveats.append("No recent Battle Report is available for death-cause calibration.")

    inputs = {
        "Current value": current_value,
        "Recommended next level/value": row.get("Next Level", "Unknown"),
        "Cost or time": row.get("Cost / Time", "Unknown"),
        "System": system,
        "Resource": resource,
        "Affordability": affordability,
        "Estimated relative gain": f"{float(gain):.3f}%" if isinstance(gain, (int, float)) else "Unknown",
        "Native ROI": row.get("Native ROI", "Unknown"),
        "Reference rank": reference_rank if reference_rank is not None else "Not available",
        "Model confidence": confidence,
        "Battle-learning multiplier": f"{float(learning_multiplier):.4f}×" if isinstance(learning_multiplier, (int, float)) else "Not applied",
    }

    summary = (
        f"{row.get('Upgrade', 'This upgrade')} is prioritized because it "
        + (", ".join(reasons) if reasons else "is one of the strongest eligible native-engine candidates")
        + "."
    )
    return {
        "Summary": summary,
        "Inputs": inputs,
        "Reasons": reasons,
        "Caveats": caveats,
        "Source explanation": row.get("Why", ""),
    }
