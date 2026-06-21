import json
from pathlib import Path

from tower_optimizer.build_archetypes import build_archetype_report
from tower_optimizer.build_beast_mode import enrich_blueprint_beast_mode

ROOT = Path(__file__).resolve().parents[1]


def load_profile():
    profile = json.loads((ROOT / "sample_data" / "example_profile.json").read_text(encoding="utf-8"))
    profile["runs"] = profile.get("runs") or [
        {
            "id": "test-vampire",
            "battle_date": "2026-06-01 20:00",
            "tier": 8,
            "wave": 3800,
            "killed_by": "Vampire",
            "real_seconds": 7200,
            "coins_earned": 1e11,
            "cells_earned": 3000,
        }
    ]
    return profile


def test_beast_mode_enriches_blueprint():
    profile = load_profile()
    report = build_archetype_report(profile, "glass_cannon", steps=3, top_n=5)
    blueprint = report["blueprint"]
    assert blueprint.get("beast")
    assert blueprint.get("readiness_score") is not None
    assert blueprint.get("master_checklist")
    beast = blueprint["beast"]
    assert beast.get("bots", {}).get("rows")
    assert beast.get("guardians", {}).get("rows")
    assert beast.get("ultimate_weapons", {}).get("rows")
    assert beast.get("masteries", {}).get("rows")
    assert beast.get("vault", {}).get("rows")


def test_death_tweak_matches_vampire_runs():
    profile = load_profile()
    base = {"presets": {}, "substats": {"rows": []}, "research": {"labs": []}}
    enriched = enrich_blueprint_beast_mode(profile, "recovery_sustain", base, latest_death="Vampire")
    assert enriched["beast"]["death"]["matched"] == "Vampire"
    assert enriched["master_checklist"]


def test_master_checklist_prioritizes_missing_cards():
    profile = load_profile()
    report = build_archetype_report(profile, "glass_cannon", steps=3, top_n=5)
    checklist = report["blueprint"]["master_checklist"]
    assert checklist
    assert any(row.get("System") == "Cards" for row in checklist)
