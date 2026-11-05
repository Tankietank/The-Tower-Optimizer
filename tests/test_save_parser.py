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
    assert patch["modules"]["Cannon"]["name"] == "Astral Deliverance"
    assert patch["modules"]["Cannon"]["rarity"] == "Epic"
    assert patch["modules"]["Cannon"].get("substats")
    assert any(row.get("name") for row in patch["modules"]["Cannon"].get("substats") or [])
    assert patch["modules"]["Armor"]["name"] == "Anti-Cube Portal"
    assert patch["uw"]["Chain Lightning"]["attributes"]["Chance"] == pytest.approx(0.08, rel=0.01)
    relic_names = list(patch["relics"]["items"])
    assert "Copper Badge" in relic_names
    assert patch["relics"]["items"]["Copper Badge"]["bonus_type"] == "Damage"
    assert len(patch.get("themes", {}).get("items", {})) > 0
    theme_items = list((patch.get("themes") or {}).get("items", {}).values())
    assert any(not str(item.get("name", "")).endswith(" 0") for item in theme_items)
    assert "Attack" in patch.get("guardians", {})
    assert len(patch.get("vault", {}).get("unlocks", {})) >= 0
    assert len(patch.get("runs", [])) > 0
    assert any(run.get("battle_date") for run in patch["runs"])
    assert any(str(run.get("killed_by") or "") in {"Fast", "Basic", "Boss", "Ray"} for run in patch["runs"])
    assert patch.get("save_import", {}).get("metadata", {}).get("field_count", 0) > 100
    assert len(patch.get("save_import", {}).get("raw_fields") or []) > 100
    assert len(patch.get("save_import", {}).get("module_registry") or []) > 0


def test_preview_player_save_round_trip(decoded_save):
    payload = gzip.compress(b"unused")
    if SAVE_PATH.exists():
        payload = SAVE_PATH.read_bytes()
    preview = preview_player_save(payload, "playerInfo.dat")
    assert preview["sections"]["workshop"] >= 10
    assert preview["sections"]["labs"] >= 20
    assert preview["sections"]["relics"] >= 10
    assert preview["patch"]["player"].get("farming_tier") is not None
    assert preview["highlights"]["modules"][0]["name"] != "Module 10"


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
    assert counts["relics"] >= 10
    assert profile["sources"]["player_save"]["filename"] == "test.dat"
    assert profile["workshop"]["Damage"] == patch["workshop"]["Damage"]
    assert profile["modules"]["Generator"]["name"] == "Galaxy Compressor"
    assert counts.get("runs", 0) > 0
    assert len(profile.get("runs") or []) > 0
    assert profile["runs"][0].get("imported_from_save") is True
    assert profile["runs"][0].get("battle_date")
    # Re-importing the same save refreshes save-sourced runs instead of deduping to zero.
    counts_again = apply_player_save_patch(profile, patch, source_name="test.dat")
    assert counts_again.get("runs", 0) > 0
    assert len(profile.get("runs") or []) > 0


def test_tool_export_json_is_decoded_like_player_save():
    import json

    from tower_optimizer.save_parser import decode_player_save_bytes

    export = {
        "ExportVersion": 1,
        "Coins": 1234.5,
        "Stones": 7,
        "CurrentTier": 3,
        "UpgradeWorkshopLevel": [10, 20],
        "ModuleInventory": [{"InfoIndex": 8, "CurrentRarity": 10, "Level": 0}],
        "BattleHistory": [{"Tier": 3, "Wave": 100}],
    }
    payload = json.dumps(export).encode("utf-8")
    for blob in (payload, b"\xef\xbb\xbf" + payload, gzip.compress(payload)):
        save = decode_player_save_bytes(blob)
        assert save["coins"] == 1234.5
        assert save["upgradeWorkshopLevel"] == [10, 20]
        assert save["battleHistory"][0]["wave"] == 100
        assert save["moduleRecords"] == [{"infoIndex": 8, "rarity": 10}]

    patch = build_profile_patch(decode_player_save_bytes(payload))
    assert patch["resources"]["stones"] == 7
    assert patch["player"]["farming_tier"] == 3


def test_card_levels_use_save_index_not_compact_order():
    from tower_optimizer.save_parser import _map_cards

    levels = [1] * 40
    unlocked = [False] * 40
    for idx in (0, 11, 18):  # Damage, Enemy Balance, Plasma Cannon
        levels[idx] = 7
        unlocked[idx] = True
    cards = _map_cards({"cardLevel": levels, "cardUnlocked": unlocked})
    assert cards["items"]["Damage"]["level"] == 7
    assert cards["items"]["Enemy Balance"]["level"] == 7
    assert cards["items"]["Plasma Cannon"]["level"] == 7
