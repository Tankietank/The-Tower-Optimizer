import json
from pathlib import Path

from tower_optimizer.build_archetypes import (
    ARCHETYPE_IDS,
    PRESET_CONTEXT_IDS,
    build_all_archetype_reports,
    build_archetype_report,
)

ROOT = Path(__file__).resolve().parents[1]


def load_profile():
    return json.loads((ROOT / "sample_data" / "example_profile.json").read_text(encoding="utf-8"))


def test_all_archetypes_generate_reports():
    payload = build_all_archetype_reports(load_profile(), steps=3, top_n=4)
    assert len(payload["archetypes"]) == len(ARCHETYPE_IDS)
    assert payload["best_match_id"] in ARCHETYPE_IDS
    for report in payload["archetypes"]:
        assert report["fit_score"] >= 0
        assert report["next_steps"]
        assert report["gaps"]
        blueprint = report.get("blueprint") or {}
        assert blueprint.get("presets")
        assert len(blueprint["presets"]) == len(PRESET_CONTEXT_IDS)
        assert blueprint.get("cards", {}).get("recommended")
        assert len(blueprint.get("modules", {}).get("rows", [])) == 4
        assert blueprint.get("research", {}).get("labs")
        assert "rows" in blueprint.get("substats", {})
        assert blueprint.get("beast")
        assert blueprint.get("master_checklist")


def test_glass_cannon_tournament_drops_economy_cards():
    report = build_archetype_report(load_profile(), "glass_cannon", steps=3, top_n=5)
    tournament_cards = report["blueprint"]["presets"]["tournament"]["cards"]["recommended"]
    assert "Coins" not in tournament_cards
    assert "Wave Skip" not in tournament_cards
    assert "Damage" in tournament_cards


def test_glass_cannon_substat_targets_present():
    report = build_archetype_report(load_profile(), "glass_cannon", steps=3, top_n=5)
    rows = report["blueprint"]["substats"]["rows"]
    assert rows
    assert any(row.get("Slot") == "Cannon" for row in rows)
    assert any("Attack Speed" in str(row.get("Target")) for row in rows)


def test_farming_and_tournament_presets_differ_for_glass_cannon():
    report = build_archetype_report(load_profile(), "glass_cannon", steps=3, top_n=5)
    farming = report["blueprint"]["presets"]["farming"]["cards"]["recommended"]
    tournament = report["blueprint"]["presets"]["tournament"]["cards"]["recommended"]
    assert farming != tournament
    assert "Coins" in farming


def test_glass_cannon_blueprint_recommends_damage_cards():
    report = build_archetype_report(load_profile(), "glass_cannon", steps=3, top_n=5)
    cards = report["blueprint"]["cards"]["recommended"]
    assert "Damage" in cards
    assert "Attack Speed" in cards
    assert "Health" not in cards or "Health" in report["blueprint"]["cards"].get("avoid", [])


def test_glass_cannon_prioritizes_damage_focus():
    report = build_archetype_report(load_profile(), "glass_cannon", steps=3, top_n=5)
    assert report["focus"] == "Damage"
    assert any(float(row.get("Archetype Boost", 0.0)) > 0 for row in report["next_steps"])


def test_economy_farmer_has_economy_priorities():
    report = build_archetype_report(load_profile(), "economy_farmer", steps=3, top_n=5)
    assert "Enemy Balance" in report["priority_cards"]
    assert report["focus"] == "Economy"


def test_cells_farmer_prioritizes_kill_speed():
    report = build_archetype_report(load_profile(), "cells_farmer", steps=3, top_n=5)
    assert report["focus"] == "Damage"
    assert "Wave Skip" in report["priority_cards"]
    cards = report["blueprint"]["cards"]["recommended"]
    assert "Attack Speed" in cards
    assert "Damage" in cards


def test_tournament_specialist_avoids_economy_cards():
    report = build_archetype_report(load_profile(), "tournament_specialist", steps=3, top_n=5)
    tournament_cards = report["blueprint"]["presets"]["tournament"]["cards"]["recommended"]
    assert "Coins" not in tournament_cards
    assert "Wave Skip" not in tournament_cards
    assert "Cash" not in tournament_cards
    assert "Damage" in tournament_cards
    beast = report["blueprint"]["beast"]
    assert beast.get("bots", {}).get("rows")
    assert beast.get("ultimate_weapons", {}).get("rows") is not None


def test_module_pick_prefers_owned_equipped_armor():
    profile = load_profile()
    report = build_archetype_report(profile, "glass_cannon", steps=3, top_n=5)
    armor = next(row for row in report["blueprint"]["modules"]["rows"] if row["slot"] == "Armor")
    assert armor["recommended"] == profile["modules"]["Armor"]["name"]
    assert armor.get("owned") is True


def test_module_pick_marks_unowned_template_target():
    profile = load_profile()
    profile["modules"]["Armor"] = {"name": "", "rarity": "", "level": 0}
    profile["module_inventory"] = {
        key: value for key, value in profile["module_inventory"].items() if not key.startswith("Armor::")
    }
    report = build_archetype_report(profile, "glass_cannon", steps=3, top_n=5)
    armor = next(row for row in report["blueprint"]["modules"]["rows"] if row["slot"] == "Armor")
    assert armor["status"] == "Not owned"
    assert armor.get("owned") is False
