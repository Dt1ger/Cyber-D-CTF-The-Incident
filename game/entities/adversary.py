"""VELVET LOCUST: a small state machine that drives the Breach Clock and corruption.

dormant    tutorial, nothing happens
active     clock ticks at the zone's base rate, corruption creeps
spreading  after a while the clock ticks faster and corruption jumps nodes
alerted    a clumsy response tipped them off: double speed for a while
contained  the zone's response is complete, the clock stops
"""

from __future__ import annotations

import random

SPREAD_AFTER = 240.0
ALERT_TIME = 45.0


class Adversary:
    def __init__(self, clock: dict, node_ids: list[str], rng: random.Random | None = None):
        self.rate = float(clock.get("rate", 0.0)) / 60.0  # percent per second
        self.state = "active" if self.rate > 0 else "dormant"
        self.order = list(clock.get("spread", node_ids))
        self.corruption = {nid: 0.0 for nid in node_ids}
        for nid in clock.get("infected", self.order[:1]):
            if nid in self.corruption:
                self.corruption[nid] = 0.7
        self.rng = rng or random.Random(0)
        self.elapsed = 0.0
        self.alert_left = 0.0
        self.slow_factor = 1.0
        self.spread_timer = 0.0

    @property
    def multiplier(self) -> float:
        if self.state in ("dormant", "contained"):
            return 0.0
        m = self.slow_factor
        if self.state == "spreading":
            m *= 1.25
        if self.state == "alerted":
            m *= 2.0
        return m

    def update(self, dt: float) -> tuple[float, list[str]]:
        """Advance time. Returns (breach clock delta, newly corrupted node ids)."""
        if self.state in ("dormant", "contained"):
            return 0.0, []
        self.elapsed += dt
        if self.state == "alerted":
            self.alert_left -= dt
            if self.alert_left <= 0:
                self.state = "spreading" if self.elapsed > SPREAD_AFTER else "active"
        elif self.state == "active" and self.elapsed > SPREAD_AFTER:
            self.state = "spreading"

        newly = []
        speed = 0.012 * self.multiplier
        for nid, level in self.corruption.items():
            if 0 < level < 1:
                self.corruption[nid] = min(1.0, level + speed * dt)
        self.spread_timer += dt * self.multiplier
        if self.spread_timer >= 60.0:
            self.spread_timer = 0.0
            for nid in self.order:
                if self.corruption.get(nid, 0) == 0:
                    self.corruption[nid] = 0.25
                    newly.append(nid)
                    break
        return self.rate * dt * self.multiplier, newly

    def tip_off(self) -> None:
        if self.state != "dormant":
            self.state = "alerted"
            self.alert_left = ALERT_TIME
            self.spread_timer = 60.0

    def slow(self, factor: float) -> None:
        self.slow_factor = max(0.4, self.slow_factor * factor)

    def clear(self, node_ids: list[str]) -> None:
        for nid in node_ids:
            if nid in self.corruption:
                self.corruption[nid] = 0.0

    def contain(self) -> None:
        if self.state != "dormant":
            self.state = "contained"
        for nid in self.corruption:
            self.corruption[nid] = 0.0
