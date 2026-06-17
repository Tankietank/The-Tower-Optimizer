"""Installation and public-engine import check that does not start Streamlit."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tower_optimizer import __version__
from tower_optimizer.reliability import SUPPORTED_WORKBOOK_VERSIONS, parse_version
from tower_optimizer.engines.economy import build_native_econ_paths
from tower_optimizer.engines.damage import build_native_damage_paths
from tower_optimizer.engines.health import build_native_health_paths
from tower_optimizer.engines.combined import build_combined_recommendations
from tower_optimizer.calibration import build_calibration_report
from tower_optimizer.quality import profile_quality_report
from tower_optimizer.explanations import recommendation_explanation
from tower_optimizer.planner import build_progression_plan, ensure_planner_state, queue_add, queue_undo
from tower_optimizer.battle_learning import build_battle_learning_report, ensure_battle_learning_state
from tower_optimizer.game_data_updater import active_update_health
from tower_optimizer.visual_models import build_sync_report, build_card_report, build_module_forge_report, build_relic_report
from tower_optimizer.icon_manager import fixed_icon_status, resolve_icon_path
from tower_optimizer.navigation import NAVIGATION_SECTIONS, navigation_pages


def minimal_profile() -> dict:
    return {
        "name": "smoke_test",
        "resources": {"coins": 0, "stones": 0, "gems": 0, "medals": 0, "keys": 0, "bits": 0, "reroll_shards": 0, "module_shards": 0},
        "player": {"farming_tier": "", "tourney_league": ""},
        "workshop": {}, "labs": {}, "enhancements": {}, "uw": {}, "modules": {},
        "maxed": {"workshop": {}, "labs": {}, "enhancements": {}, "uw": {}, "modules": {}},
        "cards": {"slots": 10, "items": {"Coins": {"level": 1, "mastery": 0}}},
        "module_inventory": {}, "module_presets": {},
        "relics": {"items": {}}, "themes": {"items": {}},
        "bots": {}, "guardians": {}, "vault": {"bonuses": {}, "unlocks": {}},
        "sources": {}, "runs": [],
        "roi_reference": {"paths": {}, "imported_at": None},
        "native_econ": {"settings": {}},
        "analysis": {}, "planner": {}, "battle_learning": {},
    }


def main() -> int:
    required = [
        ROOT / "app.py",
        ROOT / "tower_optimizer" / "application.py",
        ROOT / "tower_optimizer" / "reliability.py",
        ROOT / "tower_optimizer" / "calibration.py",
        ROOT / "tower_optimizer" / "quality.py",
        ROOT / "tower_optimizer" / "explanations.py",
        ROOT / "tower_optimizer" / "engines" / "whole_account.py",
        ROOT / "tower_optimizer" / "planner.py",
        ROOT / "tower_optimizer" / "battle_learning.py",
        ROOT / "tower_optimizer" / "battle_parser.py",
        ROOT / "tower_optimizer" / "battle_ui.py",
        ROOT / "tower_optimizer" / "game_data_updater.py",
        ROOT / "tower_optimizer" / "visual_models.py",
        ROOT / "tower_optimizer" / "visual_ui.py",
        ROOT / "tower_optimizer" / "icon_manager.py",
        ROOT / "tower_optimizer" / "navigation.py",
        ROOT / "assets" / "brand" / "tower_optimizer.svg",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("Missing required files:")
        print("\n".join(missing))
        return 1

    assert __version__ == "2.0.0-preview.6"
    pages = navigation_pages()
    assert len(NAVIGATION_SECTIONS) == 7
    assert len(pages) == 41
    assert len(pages) == len(set(pages))
    assert {"Overview 2.0", "Icon Studio", "Progression Planner", "System & Updates"}.issubset(pages)
    assert parse_version("v5.06.04.00") == (5, 6, 4, 0)
    assert "Effective Paths" in SUPPORTED_WORKBOOK_VERSIONS

    profile = minimal_profile()
    econ = build_native_econ_paths(profile, steps=2)
    damage = build_native_damage_paths(profile, steps=2)
    health = build_native_health_paths(profile, steps=2)
    combined = build_combined_recommendations(profile, steps=2)
    systems = combined.get("by_system", {})
    assert "Cards" in systems
    assert any(row.get("Resource") == "Gems" for row in combined.get("rows", []))
    ensure_planner_state(profile)
    ensure_battle_learning_state(profile)
    profile["runs"] = [
        {"id": "smoke1", "battle_date": "2026-06-01 12:00", "tier": 10, "wave": 3000, "killed_by": "Fast", "real_seconds": 7200, "coins_earned": 2e11, "cells_earned": 4000},
        {"id": "smoke2", "battle_date": "2026-06-02 12:00", "tier": 10, "wave": 3200, "killed_by": "Fast", "real_seconds": 7200, "coins_earned": 2.2e11, "cells_earned": 4300},
    ]
    battle = build_battle_learning_report(profile)
    assert len(battle.get("runs", [])) == 2
    assert battle.get("tier_performance")
    plan = build_progression_plan(profile)
    assert plan.get("daily_actions")
    item_id = queue_add(profile, plan["ranked_rows"][0], source="Smoke test")
    assert item_id
    assert queue_undo(profile)
    calibration = build_calibration_report(profile, steps=2)
    quality = profile_quality_report(profile)
    update_health = active_update_health(ROOT / "data" / "game_updates")
    profile["uw"] = {
        "Golden Tower": {"owned": True, "attributes": {"Cooldown": 200, "Duration": 33}},
        "Black Hole": {"owned": True, "attributes": {"Cooldown": 200, "Duration": 21}},
        "Death Wave": {"owned": True, "attributes": {"Cooldown": 300}},
    }
    sync = build_sync_report(profile)
    assert sync["pairs"][0]["exact"] is True
    assert sync["triple_overlap_seconds"] == 600
    card_visual = build_card_report(profile)
    assert card_visual["slots"] == 10
    profile["module_inventory"] = {
        "Cannon::Example": {"slot": "Cannon", "name": "Example", "rarity": "Epic", "level": 1, "copies": 2, "locked": True}
    }
    module_visual = build_module_forge_report(profile)
    assert len(module_visual["exact_copy_candidates"]) == 1
    relic_visual = build_relic_report(profile)
    assert relic_visual["total"] == 0
    icon_rows = fixed_icon_status()
    assert len(icon_rows) >= 11
    assert all(row.get("exists") for row in icon_rows)
    assert resolve_icon_path("resources/coins.svg") is not None
    if combined.get("rows"):
        recommendation_explanation(combined["rows"][0], profile, combined.get("analysis"), combined.get("latest_death", ""))

    print(json.dumps({
        "status": "OK",
        "app_version": __version__,
        "supported_workbooks": len(SUPPORTED_WORKBOOK_VERSIONS),
        "navigation_sections": len(NAVIGATION_SECTIONS),
        "navigation_pages": len(pages),
        "engine_paths": len(econ) + len(damage) + len(health),
        "combined_rows": len(combined.get("rows", [])),
        "whole_account_systems": len(systems),
        "planner_daily_actions": len(plan.get("daily_actions", [])),
        "planner_lab_slots": len(plan.get("lab_plan", [])),
        "battle_runs": len(battle.get("runs", [])),
        "battle_tiers": len(battle.get("tier_performance", [])),
        "calibration_paths": len(calibration.get("summary", [])),
        "quality_status": quality.get("overall"),
        "game_data_update_status": update_health.get("Status"),
        "sync_overlap_seconds": sync.get("triple_overlap_seconds"),
        "visual_assets": len(icon_rows),
        "custom_icon_support": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
