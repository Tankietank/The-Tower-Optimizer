from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .engines.economy import build_native_econ_paths
from .engines.damage import build_native_damage_paths
from .engines.health import build_native_health_paths

PATH_LABELS: Dict[str, str] = {
    "econ_lab": "Economy Labs",
    "econ_stone": "Economy Stones",
    "econ_coin": "Economy Coins",
    "econ_discount": "Economy Discounts",
    "damage_lab": "Damage Labs",
    "damage_stone": "Damage Stones",
    "damage_coin": "Damage Coins",
    "damage_key": "Damage Keys",
    "health_lab": "Health Labs",
    "health_stone": "Health Stones",
    "health_coin": "Health Coins",
    "regen_lab": "Regen Labs",
    "regen_coin": "Regen Coins",
}

# These substitutions intentionally normalize labels only. They never change
# profile values or game data.
NAME_ALIASES: Dict[str, str] = {
    "golden tower": "gt",
    "black hole": "bh",
    "death wave": "dw",
    "spotlight": "sl",
    "chain lightning": "cl",
    "smart missiles": "sm",
    "chrono field": "cf",
    "inner land mines": "ilm",
    "poison swamp": "ps",
    "coin kill bonus": "coins kill bonus",
    "coin per kill bonus": "coins kill bonus",
    "coins per kill bonus": "coins kill bonus",
    "lab speed": "labs speed",
    "orb speed": "orbs speed",
    "super critical": "super crit",
    "multiplier": "mult",
    "quantity": "qty",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_upgrade_name(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = text.replace("&", " and ")
    for old, new in NAME_ALIASES.items():
        text = text.replace(old, new)
    text = re.sub(r"\b(level|lvl|rank|upgrade|lab|labs|stone|stones|coin|coins|key|keys)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    token_score = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    sequence_score = SequenceMatcher(None, left, right).ratio()
    return max(token_score, sequence_score)


def _reference_rows(profile: Mapping[str, Any], path_key: str) -> List[Dict[str, Any]]:
    path = profile.get("roi_reference", {}).get("paths", {}).get(path_key, {})
    if not isinstance(path, Mapping):
        return []
    rows = path.get("rows", [])
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def build_native_paths(profile: Dict[str, Any], steps: int = 15) -> Dict[str, List[Dict[str, Any]]]:
    paths: Dict[str, List[Dict[str, Any]]] = {}
    for builder in (build_native_econ_paths, build_native_damage_paths, build_native_health_paths):
        result = builder(profile, steps=steps)
        for key, rows in result.items():
            if isinstance(rows, list):
                paths[key] = rows
    return paths


def compare_path(
    path_key: str,
    native_rows: Iterable[Mapping[str, Any]],
    reference_rows: Iterable[Mapping[str, Any]],
    limit: int = 15,
) -> Dict[str, Any]:
    native = [dict(row) for row in native_rows][:limit]
    reference = [dict(row) for row in reference_rows][:limit]
    reference_names = [canonical_upgrade_name(row.get("Upgrade")) for row in reference]

    details: List[Dict[str, Any]] = []
    weighted_points = 0.0
    weighted_possible = 0.0
    exact_matches = 0
    close_matches = 0
    matched_reference_indexes: set[int] = set()

    for index, row in enumerate(native):
        native_name = canonical_upgrade_name(row.get("Upgrade"))
        weight = 1.0 / (index + 1)
        weighted_possible += weight
        best_index: Optional[int] = None
        best_similarity = 0.0
        for ref_index, reference_name in enumerate(reference_names):
            similarity = _similarity(native_name, reference_name)
            if similarity > best_similarity:
                best_similarity = similarity
                best_index = ref_index

        match_type = "No match"
        points = 0.0
        if best_index is not None and best_similarity >= 0.999:
            match_type = "Exact"
            points = 1.0
            exact_matches += 1
            matched_reference_indexes.add(best_index)
        elif best_index is not None and best_similarity >= 0.72:
            match_type = "Close"
            points = 0.65
            close_matches += 1
            matched_reference_indexes.add(best_index)

        weighted_points += weight * points
        ref_row = reference[best_index] if best_index is not None and reference else {}
        native_roi = row.get("ROI Numeric", row.get("ROI"))
        reference_roi = ref_row.get("ROI Numeric", ref_row.get("ROI")) if ref_row else None
        try:
            roi_difference = ((float(native_roi) / float(reference_roi)) - 1.0) * 100.0 if float(reference_roi) else None
        except (TypeError, ValueError, ZeroDivisionError):
            roi_difference = None

        details.append({
            "Native Rank": index + 1,
            "Native Upgrade": row.get("Upgrade", "—"),
            "Native Level": row.get("Level", row.get("Next Level", "—")),
            "Reference Rank": (best_index + 1) if best_index is not None else None,
            "Reference Upgrade": ref_row.get("Upgrade", "—") if ref_row else "—",
            "Reference Level": ref_row.get("Level", "—") if ref_row else "—",
            "Match": match_type,
            "Name Similarity %": round(best_similarity * 100.0, 1),
            "Rank Difference": abs(index - best_index) if best_index is not None else None,
            "Native ROI": native_roi,
            "Reference ROI": reference_roi,
            "ROI Difference %": roi_difference,
        })

    weighted_score = 100.0 * weighted_points / weighted_possible if weighted_possible else 0.0
    top_native = canonical_upgrade_name(native[0].get("Upgrade")) if native else ""
    top_reference = canonical_upgrade_name(reference[0].get("Upgrade")) if reference else ""
    top_exact = bool(top_native and top_native == top_reference)
    native_top3 = {canonical_upgrade_name(row.get("Upgrade")) for row in native[:3]}
    reference_top3 = {canonical_upgrade_name(row.get("Upgrade")) for row in reference[:3]}
    top3_overlap = len((native_top3 & reference_top3) - {""})

    if not reference:
        status = "No reference"
        note = "Import an Effective Paths ROI reference to calibrate this path."
    elif not native:
        status = "Different"
        note = "The native engine produced no eligible rows for this profile."
    elif top_exact and weighted_score >= 80:
        status = "Exact"
        note = "Top choice and most high-ranked recommendations align."
    elif top_exact or top3_overlap >= 2 or weighted_score >= 50:
        status = "Close"
        note = "The paths broadly agree, with rank or naming differences."
    else:
        status = "Different"
        note = "The native path materially differs from the imported reference."

    return {
        "Path Key": path_key,
        "Path": PATH_LABELS.get(path_key, path_key),
        "Status": status,
        "Native Rows": len(native),
        "Reference Rows": len(reference),
        "Native Top": native[0].get("Upgrade", "—") if native else "—",
        "Reference Top": reference[0].get("Upgrade", "—") if reference else "—",
        "Top Exact": top_exact,
        "Top 3 Overlap": top3_overlap,
        "Exact Matches": exact_matches,
        "Close Matches": close_matches,
        "Weighted Agreement %": round(weighted_score, 1),
        "Note": note,
        "details": details,
    }


def build_calibration_report(profile: Dict[str, Any], steps: int = 15) -> Dict[str, Any]:
    native_paths = build_native_paths(profile, steps=steps)
    summaries: List[Dict[str, Any]] = []
    details: Dict[str, List[Dict[str, Any]]] = {}

    for path_key in PATH_LABELS:
        comparison = compare_path(
            path_key,
            native_paths.get(path_key, []),
            _reference_rows(profile, path_key),
            limit=steps,
        )
        details[path_key] = comparison.pop("details")
        summaries.append(comparison)

    counts = {status: sum(row["Status"] == status for row in summaries) for status in ["Exact", "Close", "Different", "No reference"]}
    comparable = [row for row in summaries if row["Status"] != "No reference"]
    overall_agreement = (
        sum(float(row["Weighted Agreement %"]) for row in comparable) / len(comparable)
        if comparable else None
    )
    if any(row["Status"] == "Different" for row in comparable):
        overall = "WARN"
    elif comparable:
        overall = "PASS"
    else:
        overall = "INFO"

    return {
        "generated_at": utc_now(),
        "overall": overall,
        "steps": steps,
        "reference_loaded": bool(profile.get("roi_reference", {}).get("imported_at")),
        "counts": counts,
        "overall_agreement_percent": round(overall_agreement, 1) if overall_agreement is not None else None,
        "summary": summaries,
        "details": details,
    }


def calibration_snapshot(report: Mapping[str, Any], app_version: str) -> Dict[str, Any]:
    return {
        "saved_at": utc_now(),
        "app_version": app_version,
        "overall": report.get("overall"),
        "overall_agreement_percent": report.get("overall_agreement_percent"),
        "counts": dict(report.get("counts", {})),
        "paths": [
            {
                "Path Key": row.get("Path Key"),
                "Status": row.get("Status"),
                "Native Top": row.get("Native Top"),
                "Reference Top": row.get("Reference Top"),
                "Weighted Agreement %": row.get("Weighted Agreement %"),
            }
            for row in report.get("summary", [])
        ],
    }


def compare_snapshots(current: Mapping[str, Any], previous: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    if not previous:
        return []
    prior_paths = {row.get("Path Key"): row for row in previous.get("paths", [])}
    rows: List[Dict[str, Any]] = []
    for row in current.get("summary", []):
        key = row.get("Path Key")
        old = prior_paths.get(key, {})
        old_agreement = old.get("Weighted Agreement %")
        new_agreement = row.get("Weighted Agreement %")
        try:
            delta = float(new_agreement) - float(old_agreement)
        except (TypeError, ValueError):
            delta = None
        rows.append({
            "Path": row.get("Path"),
            "Previous Status": old.get("Status", "—"),
            "Current Status": row.get("Status"),
            "Previous Top": old.get("Native Top", "—"),
            "Current Top": row.get("Native Top", "—"),
            "Agreement Change": delta,
        })
    return rows
