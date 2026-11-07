"""Module slot level costs (game v29+: levels live on module slots, not on modules).

Source: The Tower wiki "Modules" page, cost of buying each slot level before lab
discounts. Each row gives the cost that applies from that level until the next row
starts. Verified against a real save: cumulative cost at slot level 126 is
56,395 shards / 360.3B coins, matching ``SlotShardsSpent`` / ``SlotCoinsSpent``.

Levels 3-10 are not listed individually on the wiki; they reuse the level-2 row,
which is approximate (irrelevant for mid/late-game slots).
"""
from __future__ import annotations

from typing import Tuple

SLOT_MAX_LEVEL = 300

# (first level, shards per level, coins per level)
SLOT_COST_STEPS: Tuple[Tuple[int, int, float], ...] = (
    (1, 7, 10_000),
    (11, 20, 45_000),
    (21, 40, 120_000),
    (31, 75, 350_000),
    (41, 120, 1e6),
    (51, 180, 3e6),
    (61, 250, 25e6),
    (71, 350, 100e6),
    (81, 500, 350e6),
    (91, 700, 350e6),
    (101, 1_000, 8e9),
    (111, 1_300, 8e9),
    (121, 1_800, 32e9),
    (131, 2_500, 32e9),
    (141, 3_000, 500e9),
    (151, 4_000, 500e9),
    (161, 5_000, 10e12),
    (162, 5_125, 60e12),
    (171, 6_250, 510e12),
    (181, 7_500, 1.01e15),
    (191, 8_750, 1.51e15),
    (201, 10_000, 2.5e15),
    (221, 15_000, 265e15),
    (241, 20_000, 1e18),
    (261, 30_000, 106e18),
    (281, 40_000, 411e18),
    (300, 49_500, 886e18),
)


def slot_level_cost(level: int) -> Tuple[int, float]:
    """Return (shards, coins) needed to buy ``level`` (i.e. go from level-1 to level)."""
    level = max(1, min(int(level), SLOT_MAX_LEVEL))
    shards, coins = SLOT_COST_STEPS[0][1], SLOT_COST_STEPS[0][2]
    for start, step_shards, step_coins in SLOT_COST_STEPS:
        if level < start:
            break
        shards, coins = step_shards, step_coins
    return shards, coins


def next_slot_level_cost(current_level: int) -> Tuple[int, float]:
    return slot_level_cost(int(current_level) + 1)
