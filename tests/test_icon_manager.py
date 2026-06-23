"""Tests for TowerSmith-aware icon resolution."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from tower_optimizer.icon_manager import (
    item_icon_key,
    resolve_icon_path,
    towersmith_icon_paths_loaded,
)


@pytest.fixture
def towersmith_public(tmp_path: Path):
    public = tmp_path / "public"
    (public / "modules" / "generator").mkdir(parents=True)
    (public / "relics" / "epic").mkdir(parents=True)
    (public / "ultimate_weapons").mkdir(parents=True)
    (public / "cards").mkdir(parents=True)

    module_art = public / "modules" / "generator" / "generator_epic_1.webp"
    module_art.write_bytes(b"module")
    relic_art = public / "relics" / "epic" / "relic_RedPill_1.webp"
    relic_art.write_bytes(b"relic")
    uw_art = public / "ultimate_weapons" / "weapon_goldenTower.webp"
    uw_art.write_bytes(b"uw")
    card_art = public / "cards" / "Coins.webp"
    card_art.write_bytes(b"card")

    previous = os.environ.get("TOWER_SMITH_PUBLIC_DIR")
    os.environ["TOWER_SMITH_PUBLIC_DIR"] = str(public)
    try:
        yield public
    finally:
        if previous is None:
            os.environ.pop("TOWER_SMITH_PUBLIC_DIR", None)
        else:
            os.environ["TOWER_SMITH_PUBLIC_DIR"] = previous


def test_towersmith_metadata_is_bundled() -> None:
    assert towersmith_icon_paths_loaded() is True


def test_resolve_module_via_towersmith_mapping(towersmith_public) -> None:
    resolved = resolve_icon_path(
        "modules/black-hole-digestor",
        item_icon_key("modules", "Black Hole Digestor"),
        fallback_relative="systems/modules.svg",
        game_category="modules",
        game_name="Black Hole Digestor",
        module_slot="Generator",
    )
    assert resolved == towersmith_public / "modules" / "generator" / "generator_epic_1.webp"


def test_resolve_relic_via_towersmith_mapping(towersmith_public) -> None:
    resolved = resolve_icon_path(
        "relics/red-pill",
        item_icon_key("relics", "Red Pill"),
        fallback_relative="placeholders/relic.svg",
        game_category="relics",
        game_name="Red Pill",
        relic_rarity="2-Epic",
    )
    assert resolved == towersmith_public / "relics" / "epic" / "relic_RedPill_1.webp"


def test_resolve_uw_via_towersmith_mapping(towersmith_public) -> None:
    resolved = resolve_icon_path(
        "ultimate_weapons/golden_tower.svg",
        item_icon_key("ultimate_weapons", "Golden Tower"),
        fallback_relative="systems/modules.svg",
        game_category="ultimate_weapons",
        game_name="Golden Tower",
    )
    assert resolved == towersmith_public / "ultimate_weapons" / "weapon_goldenTower.webp"


def test_resolve_card_via_towersmith_convention(towersmith_public) -> None:
    resolved = resolve_icon_path(
        "cards/coins",
        item_icon_key("cards", "Coins"),
        fallback_relative="systems/cards.svg",
        game_category="cards",
        game_name="Coins",
    )
    assert resolved == towersmith_public / "cards" / "Coins.webp"
