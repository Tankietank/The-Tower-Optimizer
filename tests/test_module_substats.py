from tower_optimizer.module_substats import (
    format_substat_line,
    format_substats_for_editor,
    parse_substats_from_editor,
)


def test_format_substat_line_handles_dict_and_string():
    assert format_substat_line("Damage +12%") == "Damage +12%"
    assert format_substat_line({"name": "Attack Speed", "rarity": "Epic", "value": 0.12}) == "Attack Speed (Epic) = 0.12"
    assert format_substat_line({"name": "Health", "locked": True}) == "Health [locked]"


def test_format_substats_for_editor_joins_dict_rows():
    substats = [
        {"name": "Damage", "rarity": "Rare"},
        {"name": "Coins", "display": "Coin Bonus"},
    ]
    text = format_substats_for_editor(substats)
    assert "Damage (Rare)" in text
    assert "Coin Bonus" in text


def test_parse_substats_from_editor_preserves_imported_metadata():
    previous = [{"effect_id": 42, "name": "Damage", "rarity": "Epic", "display": "Damage (Epic)"}]
    parsed = parse_substats_from_editor("Damage (Epic)", previous)
    assert parsed[0]["effect_id"] == 42
    assert parsed[0]["rarity"] == "Epic"
    assert parsed[0]["display"] == "Damage (Epic)"
