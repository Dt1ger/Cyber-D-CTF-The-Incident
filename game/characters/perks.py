"""Character perks, looked up by perk id so new characters can reuse them."""

from __future__ import annotations

STEADY_HAND = "steady_hand"
FLAG_SENSE = "flag_sense"
PATTERN_BREAKER = "pattern_breaker"

TIPOFF_AVOID_CHANCE = {STEADY_HAND: 0.4}
CLOCK_SLOW_ON_GOOD = {STEADY_HAND: 0.9}


def tipoff_avoid_chance(perk_id: str) -> float:
    return TIPOFF_AVOID_CHANCE.get(perk_id, 0.0)


def clock_slow_on_good(perk_id: str) -> float:
    return CLOCK_SLOW_ON_GOOD.get(perk_id, 1.0)


def has_flag_sense(perk_id: str) -> bool:
    return perk_id == FLAG_SENSE


def has_pattern_breaker(perk_id: str) -> bool:
    return perk_id == PATTERN_BREAKER
