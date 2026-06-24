"""Validation for Tower Optimizer v2.0 visual preview 6.

This test covers the visual models plus persistent custom icon overrides and
icon-pack round trips. It does not start the Streamlit server.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image

from tower_optimizer import __version__
from tower_optimizer.navigation import NAVIGATION_SECTIONS, navigation_pages
from tower_optimizer.icon_manager import (
    custom_icon_count,
    custom_icon_path,
    export_custom_icon_pack,
    fixed_icon_status,
    import_custom_icon_pack,
    remove_custom_icon,
    resolve_icon_path,
    save_custom_icon,
)
from tower_optimizer.visual_models import (
    build_card_report,
    build_module_forge_report,
    build_overview_model,
    build_relic_report,
    build_sync_report,
)


def demo_profile() -> dict:
    return {
        "name": "Visual Preview Demo",
        "resources": {"coins": 4.6166e8, "stones": 1644, "gems": 640, "medals": 0, "keys": 0, "bits": 0},
        "uw": {
            "Golden Tower": {"owned": True, "attributes": {"Cooldown": 200, "Duration": 33}},
            "Black Hole": {"owned": True, "attributes": {"Cooldown": 200, "Duration": 21}},
            "Death Wave": {"owned": True, "attributes": {"Cooldown": 300, "Quantity": 1}},
        },
        "cards": {
            "slots": 13,
            "slot_target": 15,
            "items": {
                "Coins": {"level": 7, "mastery": 0},
                "Enemy Balance": {"level": 7, "mastery": 0},
                "Wave Skip": {"level": 6, "mastery": 0},
            },
        },
        "module_inventory": {
            "Generator::Black Hole Digestor": {
                "slot": "Generator", "name": "Black Hole Digestor", "rarity": "Epic",
                "level": 60, "copies": 2, "locked": True, "substats": [],
            },
            "Core::Multiverse Nexus": {
                "slot": "Core", "name": "Multiverse Nexus", "rarity": "Legendary",
                "level": 31, "copies": 1, "locked": True, "substats": [],
            },
        },
        "modules": {"Core": {"name": "Multiverse Nexus", "rarity": "Legendary", "level": 31}},
        "module_presets": {},
        "module_forge": {"fodder": {"Generator": {"Epic+": 2}}},
        "relics": {
            "items": {
                "Demo Relic": {"owned": True, "rarity": "2-Epic", "bonus_type": "Coins", "value": 0.02},
                "Missing Relic": {"owned": False, "rarity": "3-Legendary", "bonus_type": "Health", "value": 0.05},
            }
        },
        "vault": {"bonuses": {"Additional Card Slot": {"active": 1, "total": 6}}, "unlocks": {}},
        "runs": [
            {"tier": 10, "wave": 3000, "killed_by": "Vampire", "coins_per_hour": 2e10, "cells_per_hour": 500},
            {"tier": 10, "wave": 3200, "killed_by": "Fast", "coins_per_hour": 2.2e10, "cells_per_hour": 540},
        ],
    }


def validate_assets() -> list[str]:
    required = [
        "brand/tower_optimizer.svg",
        "ultimate_weapons/golden_tower.svg",
        "ultimate_weapons/black_hole.svg",
        "ultimate_weapons/death_wave.svg",
        "resources/coins.svg",
        "resources/stones.svg",
        "resources/gems.svg",
        "systems/cards.svg",
        "systems/modules.svg",
        "systems/relics.svg",
        "placeholders/relic.svg",
    ]
    validated = []
    for relative in required:
        path = ROOT / "assets" / relative
        assert path.exists(), f"Missing asset: {relative}"
        ET.parse(path)
        validated.append(relative)
    return validated


def png_payload() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (64, 64), (25, 220, 247, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def validate_custom_icons() -> dict:
    previous = os.environ.get("TOWER_CUSTOM_ICON_DIR")
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ["TOWER_CUSTOM_ICON_DIR"] = temp_dir
        payload = png_payload()
        result = save_custom_icon("resources/coins", "coins.png", payload)
        assert result["width"] == 64 and result["height"] == 64
        custom = custom_icon_path("resources/coins")
        assert custom and custom.exists()
        resolved = resolve_icon_path("resources/coins.svg")
        assert resolved == custom
        assert custom_icon_count() == 1
        pack = export_custom_icon_pack()
        assert len(pack) > len(payload)
        assert remove_custom_icon("resources/coins") is True
        assert custom_icon_count() == 0
        imported = import_custom_icon_pack(pack)
        assert len(imported["installed"]) == 1
        assert not imported["errors"]
        assert custom_icon_count() == 1
        outcome = {"saved": 1, "export_bytes": len(pack), "imported": len(imported["installed"])}
    if previous is None:
        os.environ.pop("TOWER_CUSTOM_ICON_DIR", None)
    else:
        os.environ["TOWER_CUSTOM_ICON_DIR"] = previous
    return outcome


def main() -> int:
    assert __version__ == "2.0.0-preview.8"
    pages = navigation_pages()
    assert len(NAVIGATION_SECTIONS) == 7
    assert len(pages) == 41
    assert len(pages) == len(set(pages)), "A navigation page appears more than once"
    application_text = (ROOT / "tower_optimizer" / "application.py").read_text(encoding="utf-8")
    rendered_pages = set(re.findall(r'(?:if|elif) page == "([^"]+)"', application_text))
    assert set(pages) == rendered_pages, {
        "missing_from_navigation": sorted(rendered_pages - set(pages)),
        "missing_page_handler": sorted(set(pages) - rendered_pages),
    }
    profile = demo_profile()
    sync = build_sync_report(profile)
    assert sync["status"] == "GT/BH exact; DW partial"
    assert sync["triple_overlap_seconds"] == 600
    assert sync["pairs"][0]["ratio"] == "1:1"
    assert sync["pairs"][1]["ratio"] == "3:2"
    assert sync["mvn_detected"] is True
    cards = build_card_report(profile)
    assert cards["slots"] == 13
    assert cards["target"] == 15
    assert cards["remaining_to_target"] == 2
    assert cards["vault_slots_reported"] == 1
    modules = build_module_forge_report(profile)
    assert modules["module_names"] == 2
    assert modules["total_copies"] == 3
    assert len(modules["exact_copy_candidates"]) == 1
    assert modules["fodder_total"] == 2
    relics = build_relic_report(profile)
    assert relics["owned"] == 1 and relics["total"] == 2
    overview = build_overview_model(profile, {"rows": [], "analysis": {"weakest": "Economy"}, "latest_death": "Fast"})
    assert overview["cards"]["slots"] == 13
    assets = validate_assets()
    status = fixed_icon_status()
    assert len(status) == len(assets)
    assert all(row["exists"] for row in status)
    custom = validate_custom_icons()
    result = {
        "status": "OK",
        "version": __version__,
        "sync": sync["status"],
        "triple_overlap_seconds": sync["triple_overlap_seconds"],
        "card_slots": cards["slots"],
        "module_candidates": len(modules["exact_copy_candidates"]),
        "relic_progress": relics["progress"],
        "assets_validated": len(assets),
        "navigation_sections": len(NAVIGATION_SECTIONS),
        "navigation_pages": len(pages),
        "custom_icon_round_trip": custom,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
