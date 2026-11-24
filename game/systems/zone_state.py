"""Rules for one zone, independent of rendering so whole runs can be tested.

Objectives complete in order. Each objective type is satisfied by one kind of
player action; anything done early (evidence, a good query) still counts when
that objective comes up.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from game.characters import perks
from game.characters.character import Character
from game.entities.adversary import Adversary
from game.systems.attack import AttackDB
from game.systems.campaign import RunState
from game.systems.query import QueryError, QueryResult, execute
from game.systems.scoring import hint_cost
from game.world.zone_data import ZoneData

TABLE_ALIASES = {"process": "proc", "processes": "proc", "network": "net", "emails": "email",
                 "registry": "reg", "tasks": "task", "logons": "auth", "shares": "share",
                 "services": "svc", "files": "file"}
DATA_LOSS_RESET = 80.0


@dataclass
class Event:
    kind: str
    text: str = ""
    data: dict = field(default_factory=dict)


class ZoneState:
    def __init__(self, zone: ZoneData, run: RunState, character: Character, attack: AttackDB,
                 seed: int | None = None):
        self.zone = zone
        self.run = run
        self.character = character
        self.attack = attack
        self.perk = character.perk.id
        self.stats = run.zone_stats(zone.index)
        if seed is None:
            seed = zone.index * 7919 + sum(map(ord, character.id))
        self.rng = random.Random(seed)
        self.events: list[Event] = []
        self.done: list[str] = []
        self.satisfied: set[str] = set()
        self.mapped_findings: set[str] = set()
        self.used_actions: set[str] = set()
        self.done_actions: set[str] = set()
        self.action_log: list[tuple[str, str, str]] = []
        self.hints_shown: dict[str, int] = {}
        self.pins: set[str] = set()
        self.opened: set[str] = set()
        self.visited: set[str] = set()
        self.talked = False
        self.last_decoded = ""
        puzzle = zone.puzzle
        self.puzzle_solved = bool(puzzle and puzzle["id"] in run.puzzles)
        self.adversary = Adversary(zone.clock, [n["id"] for n in zone.nodes], self.rng)
        if self.adversary.rate > 0:
            run.breach = max(run.breach, float(zone.clock.get("start", 0)))
        self.complete_announced = False
        self._busy = False
        self._dirty = False
        self._refresh()

    # Queries about state -------------------------------------------------

    @property
    def objectives(self) -> list[dict]:
        return self.zone.objectives

    @property
    def current(self) -> dict | None:
        return next((o for o in self.objectives if o["id"] not in self.done), None)

    @property
    def complete(self) -> bool:
        return self.current is None

    def is_done(self, obj_id: str) -> bool:
        return obj_id in self.done

    def has_evidence(self, evidence_id: str) -> bool:
        return self.run.has_evidence(evidence_id)

    def zone_evidence(self) -> list[str]:
        return [e["id"] for e in self.run.journal if e["zone"] == self.zone.index]

    def required_actions(self) -> list[str]:
        return [a["id"] for a in self.zone.responses if a.get("required")]

    def pending(self, obj_type: str) -> list[dict]:
        return [o for o in self.objectives if o["type"] == obj_type and o["id"] not in self.satisfied]

    def active_of(self, obj_type: str) -> dict | None:
        """The current objective if it has this type, otherwise the first pending one."""
        cur = self.current
        if cur and cur["type"] == obj_type:
            return cur
        pending = self.pending(obj_type)
        return pending[0] if pending else None

    @property
    def flag_sense(self) -> bool:
        return perks.has_flag_sense(self.perk)

    # Events --------------------------------------------------------------

    def emit(self, kind: str, text: str = "", **data) -> None:
        self.events.append(Event(kind, text, data))

    def drain(self) -> list[Event]:
        events, self.events = self.events, []
        return events

    # Objective bookkeeping ----------------------------------------------

    def _is_satisfied(self, obj: dict) -> bool:
        kind = obj["type"]
        if kind == "talk":
            return self.talked
        if kind == "open":
            return obj["panel"] in self.opened
        if kind == "visit":
            return all(n in self.visited for n in obj["nodes"])
        if kind == "collect":
            return all(self.has_evidence(e) for e in obj["evidence"])
        if kind == "map":
            return all(f in self.mapped_findings for f in obj["findings"])
        if kind == "respond":
            return all(a in self.done_actions for a in self.required_actions())
        return obj["id"] in self.satisfied

    def _refresh(self) -> None:
        if self._busy:
            self._dirty = True
            return
        self._busy = True
        try:
            while True:
                self._dirty = False
                for obj in self.objectives:
                    if obj["id"] not in self.satisfied and self._is_satisfied(obj):
                        self.satisfied.add(obj["id"])
                while self.current and self.current["id"] in self.satisfied:
                    obj = self.current
                    self.done.append(obj["id"])
                    self.emit("objective_done", f"Objective complete: {obj['title']}", obj=obj)
                    for eid in obj.get("reward_evidence", []):
                        self.collect(eid)
                    if obj.get("dialogue"):
                        self.emit("dialogue", keys=list(obj["dialogue"]))
                if not self._dirty:
                    break
        finally:
            self._busy = False
        if self.complete and not self.complete_announced:
            self.complete_announced = True
            self.stats.completed = True
            self.adversary.contain()
            self.emit("zone_complete", "Zone secured. The exit gate is open.")

    # Player actions -------------------------------------------------------

    def collect(self, evidence_id: str) -> bool:
        if evidence_id not in self.zone.evidence:
            return False
        added = self.run.add_evidence(evidence_id, self.zone.index)
        if added:
            title = self.zone.evidence[evidence_id]["title"]
            extra = ""
            if perks.has_pattern_breaker(self.perk):
                self.run.breach = max(0.0, self.run.breach - 2)
                tip = self.zone.evidence[evidence_id].get("tip")
                if tip:
                    extra = f"  Weak point: {tip}"
            self.emit("evidence", f"Evidence logged: {title}{extra}", id=evidence_id)
            self._refresh()
        return added

    def visit_node(self, node_id: str) -> None:
        self.visited.add(node_id)
        self._refresh()

    def talk_oracle(self) -> None:
        self.talked = True
        self._refresh()

    def opened_panel(self, name: str) -> None:
        self.opened.add(name)
        self._refresh()

    def toggle_pin(self, evidence_id: str) -> bool:
        if evidence_id in self.pins:
            self.pins.discard(evidence_id)
            return False
        self.pins.add(evidence_id)
        return True

    def run_query(self, text: str) -> tuple[QueryResult | None, str | None, list[tuple[str, str]]]:
        try:
            result = execute(text, self.zone.tables, TABLE_ALIASES)
        except QueryError as exc:
            return None, str(exc), []
        self.stats.queries += 1
        feedback: list[tuple[str, str]] = []
        ids = result.matched_ids
        current = self.current
        for obj in self.pending("query"):
            if obj["table"] != result.table:
                continue
            required = set(obj["required"])
            limit = int(obj.get("max_rows", 10 ** 6))
            if required <= ids and len(result.matched) <= limit:
                self.satisfied.add(obj["id"])
                feedback.append(("ok", obj.get("success", "That's the one.")))
            elif obj is current and required <= ids:
                feedback.append(("warn", f"What you need is in there, but buried in "
                                         f"{len(result.matched)} rows. Tighten the filter "
                                         f"to {limit} rows or fewer."))
            elif obj is current and required & ids:
                feedback.append(("warn", "Close. Some of what you need is here, but not all of it."))
        self._refresh()
        return result, None, feedback

    def decoded(self, text: str) -> list[tuple[str, str]]:
        self.last_decoded = text
        feedback = []
        for obj in self.pending("decode"):
            if obj["answer_contains"].lower() in text.lower():
                self.satisfied.add(obj["id"])
                feedback.append(("ok", obj.get("success", "Decoded. That's the indicator.")))
        self._refresh()
        return feedback

    def submit_choice(self, obj_id: str, option_id: str, pins=None) -> tuple[bool, str]:
        obj = self.zone.objective(obj_id)
        if obj is None or obj["id"] in self.satisfied:
            return False, "That question is already answered."
        option = next((o for o in obj["options"] if o["id"] == option_id), None)
        if option is None:
            return False, "Pick one of the options."
        pins = set(self.pins if pins is None else pins)
        missing = [e for e in obj.get("pins", []) if e not in pins]
        if option.get("correct"):
            if missing:
                names = ", ".join(self.zone.evidence[e]["title"] for e in missing
                                  if e in self.zone.evidence)
                return False, f"Right idea, but a hypothesis needs proof. Pin: {names}."
            self.stats.correct += 1
            self.satisfied.add(obj_id)
            self._refresh()
            return True, option.get("feedback") or obj.get("success", "Correct.")
        self.stats.wrong += 1
        return False, option.get("feedback", "Not quite. Look at the evidence again.")

    def map_finding(self, finding_id: str, tactic_id: str, technique_id: str) -> tuple[bool, str]:
        finding = self.zone.findings.get(finding_id)
        if finding is None or finding_id in self.mapped_findings:
            return False, "That finding is already mapped."
        accepted = [finding["technique"]] + finding.get("accept", [])
        if technique_id in accepted and tactic_id in finding["tactics"]:
            self.stats.correct += 1
            self.mapped_findings.add(finding_id)
            self.run.mapped[technique_id] = {"tactic": tactic_id, "zone": self.zone.index,
                                             "finding": finding["text"]}
            tech = self.attack.technique(technique_id)
            self.emit("mapped", f"Mapped {tech.label if tech else technique_id}", technique=technique_id)
            self._refresh()
            return True, finding.get("success", "Mapped. The matrix lights up.")
        self.stats.wrong += 1
        if technique_id in accepted:
            names = " or ".join(t.name for t in (self.attack.tactic(x) for x in finding["tactics"]) if t)
            return False, (f"Right technique, wrong column. What did the adversary achieve here? "
                           f"Think {names}.")
        return False, finding.get("hint", "Not that one. Re-read the finding and the cell details.")

    def respond(self, action_id: str) -> tuple[str, str]:
        action = self.zone.response(action_id)
        if action is None or action_id in self.used_actions:
            return "none", "That action has already been taken."
        outcome = action.get("outcome", "bad")
        text = action.get("feedback", "")
        missing = [r for r in action.get("requires", []) if r not in self.done_actions]
        if outcome == "good" and missing:
            outcome = "premature"
            labels = ", ".join(self.zone.response(m)["label"] for m in missing if self.zone.response(m))
            text = action.get("too_early") or f"Too early. First: {labels}."
        elif outcome == "good":
            self.used_actions.add(action_id)
            self.done_actions.add(action_id)
            self.stats.correct += 1
            self.run.breach = max(0.0, self.run.breach - 1.5)
            self.adversary.slow(perks.clock_slow_on_good(self.perk))
            self.adversary.clear(action.get("clears", []))
        if outcome == "premature":
            if action.get("outcome") == "premature":
                self.used_actions.add(action_id)
            self.stats.wrong += 1
            if self.rng.random() < perks.tipoff_avoid_chance(self.perk):
                text += " Steady Hand: you moved quietly and VELVET LOCUST didn't notice."
            else:
                self.stats.tipoffs += 1
                self.run.breach += float(action.get("clock", 6))
                self.adversary.tip_off()
                self.emit("tipoff", self.zone.reaction or "VELVET LOCUST noticed. They're moving faster.")
                if action.get("reveals"):
                    self.collect(action["reveals"])
        elif outcome == "bad":
            self.used_actions.add(action_id)
            self.stats.wrong += 1
            self.stats.bad_actions += 1
            self.run.breach += float(action.get("clock", 3))
        self.action_log.append((action_id, outcome, text))
        self._check_breach()
        self._refresh()
        return outcome, text

    def check_timeline(self, obj_id: str, order: list[str]) -> tuple[bool, int, str]:
        obj = self.zone.objective(obj_id)
        correct = [e["id"] for e in obj["events"]]
        right = sum(a == b for a, b in zip(order, correct))
        if order == correct:
            self.stats.correct += 1
            self.satisfied.add(obj_id)
            self._refresh()
            return True, right, obj.get("success", "Timeline rebuilt. The story holds together.")
        self.stats.wrong += 1
        return False, right, f"{right} of {len(correct)} events are in the right place."

    def submit(self, text: str) -> tuple[bool, str]:
        answer = text.strip()
        if self.zone.flag and answer.lower() == self.zone.flag.lower():
            for obj in self.pending("flag"):
                self.satisfied.add(obj["id"])
            self.run.flag_captured = True
            self.stats.correct += 1
            self.emit("flag", f"FLAG CAPTURED: {self.zone.flag}")
            self._refresh()
            return True, f"Flag accepted: {self.zone.flag}"
        puzzle = self.zone.puzzle
        if puzzle and self.flag_sense and answer.lower() == puzzle["answer"].lower():
            if self.puzzle_solved:
                return False, "You already cracked this cache."
            self.puzzle_solved = True
            self.run.puzzles.append(puzzle["id"])
            self.stats.puzzles += 1
            self.emit("puzzle", f"Bonus flag! +{puzzle.get('points', 25)} points")
            return True, "Cache cracked. GG."
        return False, "Not accepted. Flags look like HALCYON{...} or FLAG{...}."

    def next_hint(self) -> tuple[str, int] | None:
        obj = self.current
        if obj is None:
            return None
        shown = self.hints_shown.get(obj["id"], 0)
        hints = obj.get("hints", [])
        if shown >= len(hints):
            return None
        cost = hint_cost(shown)
        self.hints_shown[obj["id"]] = shown + 1
        self.stats.hints += 1
        self.stats.hint_points += cost
        return hints[shown], cost

    def shown_hints(self, obj_id: str | None = None) -> list[str]:
        obj = self.zone.objective(obj_id) if obj_id else self.current
        if obj is None:
            return []
        return obj.get("hints", [])[: self.hints_shown.get(obj["id"], 0)]

    # Time ----------------------------------------------------------------

    def update(self, dt: float) -> None:
        self.stats.time += dt
        self.run.total_time += dt
        if self.complete:
            return
        delta, newly = self.adversary.update(dt)
        self.run.breach += delta
        for nid in newly:
            node = self.zone.node(nid)
            if node:
                self.emit("spread", f"Corruption detected on {node['host']}", node=nid)
        self._check_breach()

    def _check_breach(self) -> None:
        if self.run.breach >= 100.0:
            self.stats.data_loss += 1
            self.run.breach = float(self.zone.clock.get("reset", DATA_LOSS_RESET))
            self.emit("dataloss", "DATA LOSS: VELVET LOCUST pulled a batch of files out. "
                                  "Containment score reduced. Keep going.")
