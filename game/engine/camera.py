"""Camera that eases toward a target, stays inside the world, and can shake."""

from __future__ import annotations

import random


class Camera:
    def __init__(self, view: tuple[int, int], world: tuple[int, int]):
        self.vw, self.vh = view
        self.ww, self.wh = world
        self.x = 0.0
        self.y = 0.0
        self.shake_time = 0.0
        self.shake_power = 0.0
        self.offset = (0, 0)

    def _clamp(self, x: float, y: float) -> tuple[float, float]:
        if self.ww <= self.vw:
            x = (self.ww - self.vw) / 2
        else:
            x = max(0.0, min(x, self.ww - self.vw))
        if self.wh <= self.vh:
            y = (self.wh - self.vh) / 2
        else:
            y = max(0.0, min(y, self.wh - self.vh))
        return x, y

    def snap(self, tx: float, ty: float) -> None:
        self.x, self.y = self._clamp(tx - self.vw / 2, ty - self.vh / 2)

    def follow(self, tx: float, ty: float, dt: float, speed: float = 6.0) -> None:
        gx, gy = self._clamp(tx - self.vw / 2, ty - self.vh / 2)
        k = min(1.0, dt * speed)
        self.x += (gx - self.x) * k
        self.y += (gy - self.y) * k
        if self.shake_time > 0:
            self.shake_time -= dt
            p = self.shake_power * max(0.0, self.shake_time)
            self.offset = (random.uniform(-p, p), random.uniform(-p, p))
        else:
            self.offset = (0, 0)

    def shake(self, power: float = 14.0, time: float = 0.5) -> None:
        self.shake_time = time
        self.shake_power = power / max(0.01, time)

    @property
    def pos(self) -> tuple[int, int]:
        return int(self.x + self.offset[0]), int(self.y + self.offset[1])

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        cx, cy = self.pos
        return int(x - cx), int(y - cy)

    def to_world(self, sx: float, sy: float) -> tuple[float, float]:
        cx, cy = self.pos
        return sx + cx, sy + cy
