import json
from pathlib import Path

from tower_optimizer.engines.combined import build_combined_recommendations
from tower_optimizer.planner import build_progression_plan
from tower_optimizer.battle_learning import build_battle_learning_report
from tower_optimizer.visual_models import build_sync_report, build_card_report, build_module_forge_report

ROOT = Path(__file__).resolve().parents[1]


def load_profile():
    return json.loads((ROOT / "sample_data" / "example_profile.json").read_text(encoding="utf-8"))


def test_sample_profile_runs_main_models():
    profile = load_profile()
    combined = build_combined_recommendations(profile, steps=3)
    assert combined.get("rows")
    plan = build_progression_plan(profile)
    assert plan.get("daily_actions")
    learning = build_battle_learning_report(profile)
    assert len(learning.get("runs", [])) == 3
    sync = build_sync_report(profile)
    assert sync.get("triple_overlap_seconds") == 600
    cards = build_card_report(profile)
    assert cards.get("slots") == 14
    forge = build_module_forge_report(profile)
    assert forge.get("module_names") >= 3
