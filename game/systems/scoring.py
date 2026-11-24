"""Score and rank for a finished (or in-progress) run.

Points (max 1000 before bonus):
  accuracy     400 x correct / (correct + wrong) over every graded decision
  containment  300 = 3 x (100 - 12 per tip-off - 20 per data-loss event - 8 per bad action)
  time         150 at or under 120 minutes, falling to 25 at 220+ minutes
  completion   150 for capturing the flag
  hints        minus the cost of every hint revealed (10 / 15 / 25 by tier)
  bonus        +25 per CTF cache puzzle solved
"""

from __future__ import annotations

from dataclasses import dataclass

from game.systems.campaign import RunState, ZoneStats

RANKS = [(850, "Threat Hunt Lead"), (700, "Senior Hunter"), (500, "Hunter"), (0, "Junior Analyst")]
RANK_ORDER = ["Junior Analyst", "Hunter", "Senior Hunter", "Threat Hunt Lead"]
HINT_COSTS = (10, 15, 25)
PUZZLE_POINTS = 25


@dataclass
class Score:
    accuracy: float
    accuracy_pts: int
    containment: int
    containment_pts: int
    time_pts: int
    completion_pts: int
    hint_penalty: int
    bonus: int
    total: int
    rank: str


def rank_for(total: int) -> str:
    return next(name for threshold, name in RANKS if total >= threshold)


def rank_value(rank: str) -> int:
    return RANK_ORDER.index(rank) if rank in RANK_ORDER else -1


def hint_cost(tier: int) -> int:
    return HINT_COSTS[min(tier, len(HINT_COSTS) - 1)]


def time_points(minutes: float) -> int:
    if minutes <= 120:
        return 150
    return max(25, round(150 - (minutes - 120) * 1.25))


def compute(stats: list[ZoneStats], total_time: float, flag_captured: bool) -> Score:
    correct = sum(s.correct for s in stats)
    wrong = sum(s.wrong for s in stats)
    graded = correct + wrong
    accuracy = correct / graded if graded else 1.0
    accuracy_pts = round(400 * accuracy)

    containment = 100
    containment -= 12 * sum(s.tipoffs for s in stats)
    containment -= 20 * sum(s.data_loss for s in stats)
    containment -= 8 * sum(s.bad_actions for s in stats)
    containment = max(0, min(100, containment))
    containment_pts = containment * 3

    time_pts = time_points(total_time / 60) if flag_captured else 0
    completion = 150 if flag_captured else 0
    hint_penalty = sum(s.hint_points for s in stats)
    bonus = PUZZLE_POINTS * sum(s.puzzles for s in stats)
    total = round(accuracy_pts + containment_pts + time_pts + completion + bonus - hint_penalty)
    total = max(0, min(1000, total))
    return Score(accuracy, accuracy_pts, containment, containment_pts, time_pts, completion,
                 hint_penalty, bonus, total, rank_for(total))


def score_run(run: RunState) -> Score:
    return compute(list(run.stats.values()), run.total_time, run.flag_captured)
