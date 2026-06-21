import json
from pathlib import Path

from tower_optimizer.build_archetypes import (
    ARCHETYPE_IDS,
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


def test_glass_cannon_prioritizes_damage_focus():
    report = build_archetype_report(load_profile(), "glass_cannon", steps=3, top_n=5)
    assert report["focus"] == "Damage"
    assert any(float(row.get("Archetype Boost", 0.0)) > 0 for row in report["next_steps"])


def test_economy_farmer_has_economy_priorities():
    report = build_archetype_report(load_profile(), "economy_farmer", steps=3, top_n=5)
    assert "Enemy Balance" in report["priority_cards"]
    assert report["focus"] == "Economy"
