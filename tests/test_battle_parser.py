import pytest

from tower_optimizer.battle_parser import parse_battle_report_text


# Synthetic fixture using the current in-game report layout.
FULL_REPORT = r'''Battle Report
Battle Date Jan 15, 2026 12:34
Game Time 4h 20m 10s
Real Time 1h 5m 30s
Tier 7
Wave 777
Killed By Fast
Coins Earned 7.77B
Coins Per Hour 3.33B
Cells Earned 321
Cells Per Hour 123
Records
Highest Coins / Minute 333.33M
Damage
Damage Dealt 111.11Q
Projectiles 9.99Q
Death Ray 0
Thorns 22.22Q
Orbs 33.33Q
Black Hole 444.44q
Damage Taken
Tower 55.55T
Wall 4.44T
Health Regenerated
Lifesteal 222.22B
Utility
Recovery Packages 400
Free Attack Upgrade 401
Free Defense Upgrade 402
Free Utility Upgrade 403
Counts
Waves Skipped 150
Total Enemies
Total Enemies 99999
Basic 60000
Fast 12000
Tank 12000
Ranged 10000
Boss 88
Protector 111
Vampires 22
Rays 17
Scatters 18
Coins
Coins Earned 7.77B
Golden Tower 4.44B
Death Wave 555.55M
Spotlight 1.11B
Black Hole 3.33B
Cash
Cash Earned $999.99M
Currencies
Cells Earned 321
Reroll Shards Earned 222
Enemies Destroyed By
Projectiles 8000
Thorns 2000
Orbs 9999
Death Ray 0
Black Hole 44
'''


def test_current_battle_report_format_parses_core_and_sections():
    report = parse_battle_report_text(FULL_REPORT)
    assert report["tier"] == 7
    assert report["wave"] == 777
    assert report["killed_by"] == "Fast"
    assert report["coins_earned"] == pytest.approx(7.77e9)
    assert report["coins_per_hour"] == pytest.approx(3.33e9)
    assert report["cells_earned"] == 321
    assert report["cells_per_hour"] == 123
    metrics = report["metrics"]
    assert metrics["damage_taken"] == pytest.approx(55.55e12)
    assert metrics["damage_taken_wall"] == pytest.approx(4.44e12)
    assert metrics["coins_from_golden_tower"] == pytest.approx(4.44e9)
    assert metrics["coins_from_black_hole"] == pytest.approx(3.33e9)
    assert metrics["protectors"] == 111
    assert metrics["destroyed_by_orbs"] == 9999


def test_unicode_spaces_and_colon_variants_parse():
    text = "Battle Report\nTier:\u00a08\nWave:\u202f865\nKilled By: Fast\nCoins Earned 8.64B"
    report = parse_battle_report_text(text)
    assert report["tier"] == 8
    assert report["wave"] == 865
    assert report["killed_by"] == "Fast"


def test_flattened_clipboard_still_finds_tier_and_wave():
    text = "Battle Report Battle Date Jun 04, 2026 00:53 Tier 8 Wave 865 Killed By Fast"
    report = parse_battle_report_text(text)
    assert report["tier"] == 8
    assert report["wave"] == 865


def test_multiple_reports_parse_as_one_batch():
    from tower_optimizer.battle_parser import parse_battle_report_batch, split_battle_reports

    second = FULL_REPORT.replace("Jan 15, 2026 12:34", "Jan 16, 2026 12:34").replace("Tier 7", "Tier 8").replace("Wave 777", "Wave 888")
    payload = FULL_REPORT + "\n\n" + second

    chunks = split_battle_reports(payload)
    assert len(chunks) == 2

    batch = parse_battle_report_batch(payload)
    assert batch["total"] == 2
    assert batch["errors"] == []
    assert [(run["tier"], run["wave"]) for run in batch["parsed"]] == [(7, 777), (8, 888)]


def test_batch_keeps_valid_reports_when_one_report_is_invalid():
    from tower_optimizer.battle_parser import parse_battle_report_batch

    invalid = "Battle Report\nBattle Date Jan 17, 2026 12:34\nKilled By Fast"
    batch = parse_battle_report_batch(FULL_REPORT + "\n\n" + invalid)

    assert batch["total"] == 2
    assert len(batch["parsed"]) == 1
    assert len(batch["errors"]) == 1
    assert batch["errors"][0]["report"] == 2
