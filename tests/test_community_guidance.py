import json
from pathlib import Path

import pytest

from tower_optimizer.community_guidance import (
    load_community_guidance,
    match_footguns,
)
from tower_optimizer.explanations import recommendation_explanation

ROOT = Path(__file__).resolve().parents[1]
GUIDANCE_PATH = ROOT / "tower_optimizer" / "game_data" / "community_guidance.json"


def _bh_cooldown_row() -> dict:
    return {
        "Upgrade": "BH | Cooldown",
        "Path": "native_uw_stone",
        "Path Key": "native_uw_stone",
        "Path Rank": 2,
        "Domain": "Economy",
        "Resource": "Stones",
        "System": "Ultimate Weapons",
        "Confidence": "Medium",
        "Affordability": "Affordable",
        "Estimated Gain %": 0.0,
        "Next Level": 190,
        "Cost / Time": "910 stones",
        "Why": "Strategic cooldown step.",
    }


def _defense_absolute_row() -> dict:
    return {
        "Upgrade": "Defense Absolute",
        "Path": "native_health_lab",
        "Path Key": "native_health_lab",
        "Path Rank": 8,
        "Domain": "Survivability",
        "Resource": "Labs",
        "System": "Laboratory",
        "Confidence": "Medium",
        "Affordability": "Affordable",
        "Estimated Gain %": 0.42,
        "Next Level": 36,
        "Cost / Time": "12h",
        "Why": "Estimated 0.420% eHP gain per lab step.",
    }


def test_community_guidance_json_loads():
    payload = load_community_guidance()
    assert GUIDANCE_PATH.is_file()
    on_disk = json.loads(GUIDANCE_PATH.read_text(encoding="utf-8"))
    assert payload == on_disk
    assert payload.get("footguns")
    assert payload.get("build_archetypes")
    ids = {entry["id"] for entry in payload["footguns"]}
    assert "bh_cooldown_before_gt_sync" in ids
    assert "defense_absolute_late_game" in ids


def test_bh_cooldown_recommendation_triggers_sync_warning_when_gt_not_in_sync():
    profile = {
        "uw": {
            "Golden Tower": {
                "owned": True,
                "attributes": {"Multiplier": 15.0, "Duration": 38, "Cooldown": 300},
            },
            "Black Hole": {
                "owned": True,
                "attributes": {"Size": 48, "Duration": 26, "Cooldown": 200},
            },
        }
    }
    row = _bh_cooldown_row()

    matches = match_footguns(profile, row["Upgrade"], row)
    assert any(item["id"] == "bh_cooldown_before_gt_sync" for item in matches)

    explanation = recommendation_explanation(row, profile, {}, "")
    guidance_text = " ".join(explanation.get("Community guidance") or []).casefold()
    tradeoffs_text = " ".join(explanation.get("Trade-offs") or []).casefold()
    assert "community guide (fandom)" in guidance_text
    assert "black hole cooldown" in guidance_text or "gt/bh sync" in guidance_text
    assert "fandom.com/wiki/footguns" in guidance_text
    assert "community guide (fandom)" in tradeoffs_text


def test_defense_absolute_late_game_warning():
    profile = {
        "workshop": {"Defense Absolute": 250},
        "labs": {"Defense Absolute": 35},
        "enhancements": {"Defense Absolute +": 60},
    }
    row = _defense_absolute_row()

    matches = match_footguns(profile, row["Upgrade"], row)
    assert any(item["id"] == "defense_absolute_late_game" for item in matches)

    explanation = recommendation_explanation(row, profile, {"weakest": "Survivability"}, "")
    guidance_text = " ".join(explanation.get("Community guidance") or []).casefold()
    tradeoffs_text = " ".join(explanation.get("Trade-offs") or []).casefold()
    assert "community guide (fandom)" in guidance_text
    assert "defense absolute" in guidance_text
    assert "community guide (fandom)" in tradeoffs_text
