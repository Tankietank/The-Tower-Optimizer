"""Personalized optimal-build reports for common playstyle archetypes."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from .engines.combined import build_combined_recommendations
from .engines.core import LAB_MAX_LEVELS, WORKSHOP_MAX_LEVELS, build_analysis, ratio


ARCHETYPE_IDS = (
    "economy_farmer",
    "glass_cannon",
    "ehp_tank",
    "recovery_sustain",
    "balanced",
)

ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "economy_farmer": {
        "label": "Economy Farmer",
        "tagline": "Push coins/hour, GT/BH income, and farming presets.",
        "focus": "Economy",
        "domain_weights": {
            "Economy": 0.52,
            "Damage": 0.22,
            "Survivability": 0.16,
            "Regen / Recovery": 0.10,
        },
        "priority_cards": ["Enemy Balance", "Coins", "Critical Coin", "Wave Skip", "Wave Accelerator", "Cash"],
        "priority_workshop": ["Coin / Kill Bonus", "Cash Bonus", "Cash / Wave", "Damage", "Attack Speed"],
        "priority_labs": [
            "Coins / Kill Bonus", "Golden Tower Bonus", "Black Hole Coin Bonus",
            "Golden Tower Duration", "Death Wave Coin Bonus", "Labs Speed",
        ],
        "priority_systems": ["Cards", "Laboratory", "Workshop / Enhancements", "Ultimate Weapons", "Modules"],
        "module_focus": {"Generator": "coin or economy modules", "Cannon": "wave clear damage"},
    },
    "glass_cannon": {
        "label": "Glass Cannon",
        "tagline": "Trade survivability for kill speed, crits, and burst damage.",
        "focus": "Damage",
        "domain_weights": {
            "Damage": 0.58,
            "Economy": 0.18,
            "Survivability": 0.12,
            "Regen / Recovery": 0.12,
        },
        "priority_cards": ["Damage", "Attack Speed", "Berserker", "Plasma Cannon", "Critical Chance", "Ultimate Crit"],
        "priority_workshop": ["Damage", "Attack Speed", "Critical Factor", "Critical Chance", "Damage / Meter"],
        "priority_labs": ["Damage", "Attack Speed", "Critical Factor", "Shock Multiplier", "Black Hole Damage"],
        "priority_systems": ["Laboratory", "Workshop / Enhancements", "Cards", "Ultimate Weapons", "Modules"],
        "module_focus": {"Cannon": "primary damage", "Core": "crit or multishot effects", "Armor": "minimal — don't over-invest"},
    },
    "ehp_tank": {
        "label": "eHP Tank",
        "tagline": "Survive burst hits with health, defense, packages, and wall scaling.",
        "focus": "Survival",
        "domain_weights": {
            "Survivability": 0.50,
            "Regen / Recovery": 0.25,
            "Damage": 0.15,
            "Economy": 0.10,
        },
        "priority_cards": ["Health", "Extra Defense", "Fortress", "Energy Shield", "Second Wind"],
        "priority_workshop": ["Health", "Defense %", "Recovery Amount", "Max Amount", "Package Chance", "Thorn Damage"],
        "priority_labs": ["Health", "Defense %", "Recovery Package Chance", "Recovery Package Amount", "Recovery Package Max"],
        "priority_systems": ["Laboratory", "Workshop / Enhancements", "Cards", "Modules"],
        "module_focus": {"Armor": "health or defense substats", "Core": "sustain if needed"},
    },
    "recovery_sustain": {
        "label": "Recovery / Sustain",
        "tagline": "Outlast vampires and chip damage with regen and packages.",
        "focus": "Recovery",
        "domain_weights": {
            "Regen / Recovery": 0.48,
            "Survivability": 0.28,
            "Damage": 0.14,
            "Economy": 0.10,
        },
        "priority_cards": ["Health Regen", "Recovery Package Chance", "Second Wind", "Health", "Extra Defense"],
        "priority_workshop": ["Health Regen", "Recovery Amount", "Package Chance", "Max Amount", "Lifesteal"],
        "priority_labs": [
            "Health Regen", "Recovery Package Chance", "Recovery Package Amount",
            "Recovery Package Max", "Wall Regen", "Garlic Thorns",
        ],
        "priority_systems": ["Laboratory", "Workshop / Enhancements", "Cards", "Guardians"],
        "module_focus": {"Armor": "regen or package effects", "Generator": "secondary"},
    },
    "balanced": {
        "label": "Balanced Progression",
        "tagline": "Keep all four development areas moving without over-specializing.",
        "focus": "Balanced",
        "domain_weights": {
            "Economy": 0.25,
            "Damage": 0.25,
            "Survivability": 0.25,
            "Regen / Recovery": 0.25,
        },
        "priority_cards": ["Enemy Balance", "Damage", "Health", "Coins", "Attack Speed"],
        "priority_workshop": ["Damage", "Health", "Coin / Kill Bonus", "Attack Speed", "Defense %"],
        "priority_labs": ["Damage", "Health", "Coins / Kill Bonus", "Attack Speed", "Health Regen"],
        "priority_systems": ["Laboratory", "Cards", "Workshop / Enhancements", "Ultimate Weapons", "Modules"],
        "module_focus": {"Cannon": "damage", "Armor": "survivability", "Generator": "economy", "Core": "utility"},
    },
}


def _clean_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _section_progress(profile: Mapping[str, Any], section: str, names: Sequence[str]) -> float:
    bucket = profile.get(section, {}) if isinstance(profile.get(section), Mapping) else {}
    caps = WORKSHOP_MAX_LEVELS if section == "workshop" else LAB_MAX_LEVELS
    ratios: List[float] = []
    for name in names:
        maximum = caps.get(name)
        if not maximum:
            continue
        ratios.append(ratio(bucket.get(name), maximum))
    return sum(ratios) / len(ratios) if ratios else 0.0


def _card_progress(profile: Mapping[str, Any], names: Sequence[str]) -> float:
    items = profile.get("cards", {}).get("items", {}) if isinstance(profile.get("cards"), Mapping) else {}
    if not isinstance(items, Mapping):
        return 0.0
    levels: List[float] = []
    for name in names:
        record = items.get(name)
        if not isinstance(record, Mapping):
            continue
        levels.append(min(1.0, _clean_number(record.get("level")) / 7.0))
    return sum(levels) / len(levels) if levels else 0.0


def _domain_fit(scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total = 0.0
    weight_sum = 0.0
    for domain, weight in weights.items():
        total += float(scores.get(domain, 0.0)) * float(weight)
        weight_sum += float(weight)
    return total / weight_sum if weight_sum else 0.0


def _profile_gaps(profile: Mapping[str, Any], archetype: Mapping[str, Any]) -> List[str]:
    gaps: List[str] = []
    items = profile.get("cards", {}).get("items", {}) if isinstance(profile.get("cards"), Mapping) else {}
    if isinstance(items, Mapping):
        for card in archetype.get("priority_cards", []):
            record = items.get(card)
            if not isinstance(record, Mapping):
                gaps.append(f"Track {card} cards — not entered yet.")
                continue
            level = int(_clean_number(record.get("level")))
            if level < 5:
                gaps.append(f"{card} is only level {level}/7 for this build.")
            elif level < 7:
                gaps.append(f"Finish {card} ({level}/7) when gems allow.")

    ws_progress = _section_progress(profile, "workshop", archetype.get("priority_workshop", []))
    if ws_progress < 0.35:
        gaps.append("Core workshop stats for this build are still early.")
    lab_progress = _section_progress(profile, "labs", archetype.get("priority_labs", []))
    if lab_progress < 0.30:
        gaps.append("Priority labs for this build are underdeveloped.")

    uw = profile.get("uw", {}) if isinstance(profile.get("uw"), Mapping) else {}
    if archetype.get("focus") == "Economy":
        if not (isinstance(uw.get("Golden Tower"), Mapping) and uw.get("Golden Tower", {}).get("owned")):
            gaps.append("Golden Tower is not marked owned — economy builds lean on GT.")
        if not (isinstance(uw.get("Black Hole"), Mapping) and uw.get("Black Hole", {}).get("owned")):
            gaps.append("Black Hole is not marked owned — coin uptime suffers.")

    slots = int(_clean_number(profile.get("cards", {}).get("slots")))
    if slots and slots < 12:
        gaps.append(f"Only {slots} card slots entered — most builds want 12+ for flexible presets.")

    if not gaps:
        gaps.append("No major gaps detected in tracked priorities — focus on the ranked next steps below.")
    return gaps[:6]


def _upgrade_matches_archetype(upgrade: str, archetype: Mapping[str, Any]) -> bool:
    text = str(upgrade or "").casefold()
    tokens: List[str] = []
    for bucket in ("priority_cards", "priority_workshop", "priority_labs"):
        tokens.extend(str(item).casefold() for item in archetype.get(bucket, []))
    return any(token and token in text for token in tokens)


def _rerank_rows(rows: Sequence[Mapping[str, Any]], archetype: Mapping[str, Any]) -> List[Dict[str, Any]]:
    preferred_systems = {str(item).casefold() for item in archetype.get("priority_systems", [])}
    adjusted: List[Dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        boost = 0.0
        reasons: List[str] = []
        domain = str(row.get("Domain", ""))
        weights = archetype.get("domain_weights", {})
        if domain in weights:
            boost += 4.0 * float(weights[domain])
            reasons.append(f"matches {archetype.get('label')} domain mix")
        if _upgrade_matches_archetype(str(row.get("Upgrade", "")), archetype):
            boost += 8.0
            reasons.append("targets a priority stat/card for this build")
        system = str(row.get("System", "")).casefold()
        if system in preferred_systems:
            boost += 3.0
        row["Archetype Boost"] = round(boost, 2)
        row["Archetype Score"] = round(float(row.get("Priority Index", 0.0)) + boost, 2)
        if reasons:
            existing = str(row.get("Why", "")).strip()
            extra = f"build fit: {'; '.join(reasons)}"
            row["Why"] = "; ".join(part for part in [existing, extra] if part)
        adjusted.append(row)
    return sorted(adjusted, key=lambda item: float(item.get("Archetype Score", 0.0)), reverse=True)


def build_archetype_report(
    profile: Mapping[str, Any],
    archetype_id: str,
    *,
    steps: int = 12,
    candidates_per_path: int = 3,
    apply_death_weighting: bool = True,
    top_n: int = 8,
) -> Dict[str, Any]:
    archetype = ARCHETYPES.get(archetype_id)
    if not archetype:
        raise KeyError(f"Unknown archetype: {archetype_id}")
    analysis = build_analysis(dict(profile))
    scores = analysis.get("scores", {})
    fit_score = round(
        0.55 * _domain_fit(scores, archetype["domain_weights"])
        + 0.25 * _card_progress(profile, archetype.get("priority_cards", [])) * 100.0
        + 0.20 * (_section_progress(profile, "workshop", archetype.get("priority_workshop", [])) * 50.0
                  + _section_progress(profile, "labs", archetype.get("priority_labs", [])) * 50.0),
        1,
    )
    combined = build_combined_recommendations(
        dict(profile),
        steps=steps,
        candidates_per_path=candidates_per_path,
        apply_death_weighting=apply_death_weighting,
        focus=str(archetype.get("focus", "Balanced")),
    )
    ranked = _rerank_rows(combined.get("rows", []), archetype)
    return {
        "id": archetype_id,
        "label": archetype["label"],
        "tagline": archetype["tagline"],
        "focus": archetype.get("focus", "Balanced"),
        "fit_score": fit_score,
        "fit_label": "Strong match" if fit_score >= 70 else "Work in progress" if fit_score >= 45 else "Needs investment",
        "domain_scores": scores,
        "gaps": _profile_gaps(profile, archetype),
        "priority_cards": list(archetype.get("priority_cards", [])),
        "priority_labs": list(archetype.get("priority_labs", [])),
        "priority_workshop": list(archetype.get("priority_workshop", [])),
        "module_focus": dict(archetype.get("module_focus", {})),
        "next_steps": ranked[:top_n],
        "latest_death": combined.get("latest_death", "No report saved"),
        "weakest_domain": analysis.get("weakest"),
    }


def build_all_archetype_reports(
    profile: Mapping[str, Any],
    *,
    steps: int = 10,
    candidates_per_path: int = 3,
    apply_death_weighting: bool = True,
    top_n: int = 6,
) -> Dict[str, Any]:
    reports = [
        build_archetype_report(
            profile,
            archetype_id,
            steps=steps,
            candidates_per_path=candidates_per_path,
            apply_death_weighting=apply_death_weighting,
            top_n=top_n,
        )
        for archetype_id in ARCHETYPE_IDS
    ]
    best = max(reports, key=lambda item: float(item.get("fit_score", 0.0)))
    return {
        "archetypes": reports,
        "best_match_id": best["id"],
        "best_match_label": best["label"],
        "best_match_score": best["fit_score"],
    }


def archetype_display_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    display: List[Dict[str, Any]] = []
    for row in rows:
        explanation = row.get("Explanation") if isinstance(row.get("Explanation"), Mapping) else {}
        why_now = explanation.get("Why now") or []
        why_text = " · ".join(why_now[:2]) if why_now else str(row.get("Why", ""))
        display.append({
            "Build score": row.get("Archetype Score", row.get("Priority Index")),
            "Upgrade": row.get("Upgrade"),
            "Resource": row.get("Resource"),
            "System": row.get("System"),
            "Affordability": row.get("Affordability"),
            "Why": why_text,
        })
    return display
