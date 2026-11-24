"""Plays a zone perfectly through the same calls the UI makes.

Used by the tests to prove every zone can be finished with each character,
and by `--autoplay` for quick visual checks.
"""

from __future__ import annotations

from game.systems.terminal import TerminalSession
from game.systems.zone_state import ZoneState


def response_order(state: ZoneState) -> list[str]:
    """Required good actions in an order that satisfies every 'requires'."""
    zone = state.zone
    pending = [a for a in zone.responses if a.get("required")]
    order: list[str] = []
    while pending:
        ready = [a for a in pending if all(r in order for r in a.get("requires", []))]
        if not ready:
            raise ValueError(f"zone {zone.index}: response 'requires' chain can't be satisfied")
        for a in ready:
            order.append(a["id"])
            pending.remove(a)
    return order


def solve_objective(state: ZoneState, terminal: TerminalSession, obj: dict) -> None:
    kind = obj["type"]
    zone = state.zone
    if kind == "talk":
        state.talk_oracle()
    elif kind == "open":
        state.opened_panel(obj["panel"])
    elif kind == "visit":
        for n in obj["nodes"]:
            state.visit_node(n)
    elif kind == "collect":
        for e in obj["evidence"]:
            state.collect(e)
    elif kind == "query":
        terminal.execute(obj["solution"])
    elif kind == "decode":
        terminal.execute(obj["solution"])
    elif kind == "choice":
        for e in obj.get("pins", []):
            if e not in state.pins:
                state.toggle_pin(e)
        correct = next(o["id"] for o in obj["options"] if o.get("correct"))
        state.submit_choice(obj["id"], correct)
    elif kind == "timeline":
        state.check_timeline(obj["id"], [e["id"] for e in obj["events"]])
    elif kind == "map":
        for fid in obj["findings"]:
            f = zone.findings[fid]
            state.map_finding(fid, f["tactics"][0], f["technique"])
    elif kind == "respond":
        for aid in response_order(state):
            state.respond(aid)
    elif kind == "flag":
        terminal.execute(f"submit {zone.flag}")


def solve_puzzle(state: ZoneState, terminal: TerminalSession) -> None:
    puzzle = state.zone.puzzle
    if not puzzle or not state.flag_sense or state.puzzle_solved:
        return
    key = f" {puzzle['key']}" if puzzle.get("key") else ""
    terminal.execute(f"decode {puzzle['encoding']} cache{key}")
    terminal.execute(f"submit {puzzle['answer']}")


def solve_zone(state: ZoneState, puzzle: bool = True, max_steps: int = 200) -> TerminalSession:
    terminal = TerminalSession(state)
    if puzzle:
        solve_puzzle(state, terminal)
    steps = 0
    while not state.complete:
        obj = state.current
        solve_objective(state, terminal, obj)
        steps += 1
        if state.current is obj:
            raise AssertionError(f"zone {state.zone.index}: objective {obj['id']} "
                                 f"({obj['type']}) did not complete with its solution")
        if steps > max_steps:
            raise AssertionError("autoplay did not converge")
    return terminal
