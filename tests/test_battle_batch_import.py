from tower_optimizer.battle_learning import import_runs
from tower_optimizer.battle_parser import parse_battle_report_batch


REPORT_TEMPLATE = '''Battle Report
Battle Date Jun {day:02d}, 2026 00:53
Game Time 5h 11m 53s
Real Time 1h 17m 59s
Tier {tier}
Wave {wave}
Killed By Fast
Coins Earned 8.64B
Coins Per Hour 6.65B
Cells Earned 444
Cells Per Hour 342
'''


def test_batch_import_saves_all_unique_runs_and_skips_duplicates():
    payload = "\n\n".join([
        REPORT_TEMPLATE.format(day=4, tier=8, wave=865),
        REPORT_TEMPLATE.format(day=5, tier=8, wave=900),
    ])
    batch = parse_battle_report_batch(payload)
    profile = {"name": "Test", "runs": []}

    first = import_runs(profile, batch["parsed"], batch_label="test")
    assert len(first["added"]) == 2
    assert len(profile["runs"]) == 2

    second = import_runs(profile, batch["parsed"], batch_label="test duplicate")
    assert len(second["added"]) == 0
    assert len(second["duplicates"]) == 2
    assert len(profile["runs"]) == 2
