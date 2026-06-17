import gzip
from pathlib import Path

import pytest

from tower_optimizer.save_parser import (
    apply_player_save_patch,
    build_profile_patch,
    decode_player_save_file,
    preview_player_save,
)

ROOT = Path(__file__).resolve().parents[1]
SAVE_PATH = ROOT / "data" / "imports" / "save_probe" / "playerInfo.dat"


@pytest.fixture(scope="module")
def decoded_save():
    if not SAVE_PATH.exists():
        pytest.skip("Local playerInfo.dat fixture not available")
    return decode_player_save_file(SAVE_PATH)


def test_decode_local_player_save(decoded_save):
    assert decoded_save.get("coins") is not None
    assert "upgradeWorkshopLevel" in decoded_save
    assert "researchLevel" in decoded_save


def test_build_profile_patch_counts(decoded_save):
    patch = build_profile_patch(decoded_save)
    assert patch["workshop"]["Damage"] > 0
    assert patch["labs"]["Labs Speed"] > 0
    assert patch["resources"]["stones"] >= 0
    assert "Chain Lightning" in patch["uw"]
    assert patch["cards"]["slots"] >= 1
    assert len(patch["modules"]) == 4


def test_preview_player_save_round_trip(decoded_save):
    payload = gzip.compress(b"unused")
    if SAVE_PATH.exists():
        payload = SAVE_PATH.read_bytes()
    preview = preview_player_save(payload, "playerInfo.dat")
    assert preview["sections"]["workshop"] >= 10
    assert preview["sections"]["labs"] >= 20
    assert preview["patch"]["player"].get("farming_tier") is not None


def test_apply_player_save_patch_merges(decoded_save):
    profile = {
        "name": "save_test",
        "resources": {"coins": 0, "stones": 0, "gems": 0, "medals": 0, "keys": 0, "bits": 0},
        "player": {"player_id": "", "farming_tier": "", "tourney_league": "", "lifetime_coins": 0, "tiers": {}},
        "workshop": {},
        "labs": {},
        "enhancements": {},
        "uw": {},
        "modules": {},
        "module_inventory": {},
        "cards": {"slots": 0, "items": {}, "presets": {}},
        "bots": {},
        "relics": {"items": {}},
        "maxed": {"workshop": {}, "labs": {}, "enhancements": {}, "uw": {}},
        "sources": {},
        "import_audit": [],
        "metadata": {},
    }
    patch = build_profile_patch(decoded_save)
    counts = apply_player_save_patch(profile, patch, source_name="test.dat")
    assert counts["workshop"] >= 10
    assert counts["labs"] >= 20
    assert profile["sources"]["player_save"]["filename"] == "test.dat"
    assert profile["workshop"]["Damage"] == patch["workshop"]["Damage"]
