from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .engines.economy import build_native_econ_paths
from .engines.damage import build_native_damage_paths
from .engines.health import build_native_health_paths
from .engines.combined import build_combined_recommendations, build_progression_recommendations
from .calibration import build_calibration_report
from .quality import profile_quality_report
from .planner import build_progression_plan
from .battle_learning import build_battle_learning_report
from .game_data_updater import active_update_health


def bundled_data_status() -> List[Dict[str, Any]]:
    root = Path(__file__).resolve().parent / "game_data"
    rows: List[Dict[str, Any]] = []
    for name in ["metadata.json", "workshop.json", "labs.json", "ultimate_weapons.json", "modules.json", "whole_account.json"]:
        path = root / name
        status = "PASS"
        detail = ""
        action = "—"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            detail = str(payload.get("version") or payload.get("bundle_version") or payload.get("schema_version") or "loaded")
        except Exception as exc:
            status = "FAIL"
            detail = str(exc)
            action = "Reinstall the current Tower Optimizer package."
        rows.append({"Component": name, "Status": status, "Detail": detail, "Suggested Action": action})
    rows.append(active_update_health())
    return rows


def run_engine_health(profile: Dict[str, Any], steps: int = 10) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    all_paths: Dict[str, List[Dict[str, Any]]] = {}
    engine_calls = [
        ("Economy", build_native_econ_paths),
        ("Damage", build_native_damage_paths),
        ("Health / Regen", build_native_health_paths),
    ]
    for engine_name, function in engine_calls:
        try:
            paths = function(profile, steps=steps)
            all_paths.update({key: value for key, value in paths.items() if isinstance(value, list)})
            total_rows = sum(len(value) for value in paths.values() if isinstance(value, list))
            status = "PASS" if total_rows else "WARN"
            action = "—" if total_rows else "Check profile imports, unlocks, and Gold Boxes."
            results.append({
                "Check": engine_name,
                "Status": status,
                "Detail": f"{total_rows} rows across {len(paths)} paths",
                "Suggested Action": action,
            })
        except Exception as exc:
            results.append({
                "Check": engine_name,
                "Status": "FAIL",
                "Detail": str(exc),
                "Suggested Action": "Download diagnostics and restore the prior code backup if this persists.",
            })

    try:
        combined = build_combined_recommendations(profile, steps=min(steps, 12))
        count = len(combined.get("rows", []))
        systems = len([name for name, rows in combined.get("by_system", {}).items() if rows])
        results.append({
            "Check": "Combined dashboard",
            "Status": "PASS" if count else "WARN",
            "Detail": f"{count} recommendations across {systems} systems",
            "Suggested Action": "—" if count else "Enter resources and import core profile sections.",
        })
    except Exception as exc:
        results.append({
            "Check": "Combined dashboard",
            "Status": "FAIL",
            "Detail": str(exc),
            "Suggested Action": "Review individual engine failures first.",
        })

    try:
        progression = build_progression_recommendations(profile)
        system_count = len([name for name, rows in progression.get("by_system", {}).items() if rows])
        row_count = len(progression.get("rows", []))
        results.append({
            "Check": "Whole-account systems",
            "Status": "PASS" if row_count else "WARN",
            "Detail": f"{row_count} strategic rows across {system_count} imported systems",
            "Suggested Action": "—" if row_count else "Import Cards, Modules, Bots, Guardians, Vault, Relics, or Themes data.",
        })
    except Exception as exc:
        results.append({
            "Check": "Whole-account systems",
            "Status": "FAIL",
            "Detail": str(exc),
            "Suggested Action": "Review whole-account profile sections and reinstall v1.10 if the module is missing.",
        })

    try:
        planner = build_progression_plan(profile)
        daily_count = len(planner.get("daily_actions", []))
        lab_count = len(planner.get("lab_plan", []))
        results.append({
            "Check": "Progression planner",
            "Status": "PASS" if daily_count and lab_count else "WARN",
            "Detail": f"{daily_count} daily actions and {lab_count} planned lab slots",
            "Suggested Action": "—" if daily_count and lab_count else "Open Progression Planner and review missing profile data.",
        })
    except Exception as exc:
        results.append({
            "Check": "Progression planner",
            "Status": "FAIL",
            "Detail": str(exc),
            "Suggested Action": "Reinstall v1.10 or restore the v1.8 code backup.",
        })

    try:
        battle = build_battle_learning_report(profile)
        run_count = len(battle.get("runs", []))
        tier_count = len(battle.get("tier_performance", []))
        impact_count = len(battle.get("upgrade_impacts", []))
        results.append({
            "Check": "Battle learning",
            "Status": "PASS" if run_count else "INFO",
            "Detail": f"{run_count} runs across {tier_count} tiers; {impact_count} upgrade comparisons",
            "Suggested Action": "—" if run_count else "Import Battle Reports to activate performance learning.",
        })
    except Exception as exc:
        results.append({
            "Check": "Battle learning",
            "Status": "FAIL",
            "Detail": str(exc),
            "Suggested Action": "Review Battle Learning data or reinstall v1.10.",
        })

    try:
        calibration = build_calibration_report(profile, steps=steps)
        comparisons = []
        for row in calibration.get("summary", []):
            status_map = {"Exact": "PASS", "Close": "PASS", "Different": "WARN", "No reference": "INFO"}
            status = status_map.get(row.get("Status"), "INFO")
            if status == "WARN":
                action = "Open Calibration Center and inspect the first differing ranks."
            elif status == "INFO":
                action = "Optional: import an Effective Paths ROI reference for calibration."
            else:
                action = "—"
            comparisons.append({
                "Path": row.get("Path"),
                "Status": status,
                "Native rows": row.get("Native Rows"),
                "Reference rows": row.get("Reference Rows"),
                "Native top": row.get("Native Top"),
                "Reference top": row.get("Reference Top"),
                "Agreement %": row.get("Weighted Agreement %"),
                "Note": row.get("Note"),
                "Suggested Action": action,
            })
    except Exception as exc:
        calibration = {"overall": "FAIL", "summary": [], "error": str(exc)}
        comparisons = [{
            "Path": "Calibration",
            "Status": "FAIL",
            "Native rows": 0,
            "Reference rows": 0,
            "Native top": "—",
            "Reference top": "—",
            "Agreement %": None,
            "Note": str(exc),
            "Suggested Action": "Check engine execution and ROI reference structure.",
        }]

    try:
        quality = profile_quality_report(profile)
    except Exception as exc:
        quality = {
            "overall": "FAIL",
            "score": 0,
            "counts": {"Error": 1, "Warning": 0, "Info": 0},
            "issues": [{"Severity": "Error", "Category": "Quality", "Item": "Report", "Details": str(exc), "Suggested Action": "Download diagnostics."}],
            "readiness": [],
        }

    data_rows = bundled_data_status()
    overall = "PASS"
    if any(row["Status"] == "FAIL" for row in results + data_rows) or quality.get("overall") == "FAIL":
        overall = "FAIL"
    elif (
        any(row["Status"] == "WARN" for row in results + comparisons)
        or quality.get("overall") == "WARN"
    ):
        overall = "WARN"

    actions: List[str] = []
    for row in results + comparisons:
        action = row.get("Suggested Action")
        if action and action != "—" and action not in actions:
            actions.append(str(action))
    for issue in quality.get("issues", []):
        if issue.get("Severity") in {"Error", "Warning"}:
            action = issue.get("Suggested Action")
            if action and action not in actions:
                actions.append(str(action))

    return {
        "overall": overall,
        "engines": results,
        "comparisons": comparisons,
        "game_data": data_rows,
        "quality": quality,
        "calibration": calibration,
        "actions": actions[:12],
    }
