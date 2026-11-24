"""Who is on the roster. Aisha_256 stays locked until the hunt or the case files are done."""

from __future__ import annotations

from game.engine import config
from game.systems.challenges import load_challenges

HIDDEN = "aisha_256"


def is_unlocked(app, char_id: str) -> bool:
    if char_id != HIDDEN:
        return True
    if app.saves.hunt_cleared():
        return True
    cases, _notes = load_challenges(config.CHALLENGES_DIR)
    ids = {case.id for case in cases}
    return bool(ids) and ids <= set(app.saves.custom_solved())
