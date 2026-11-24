"""A dim, screen-space room behind the map. One quiet note per zone.

The playable grid stays in front. This only keeps the space around it from
reading as a void. A supplied zone background image replaces it entirely.
"""

from __future__ import annotations

import math
import random

import pygame

from game.engine import config

# wash: the room's night color. light: the few points that show what the room is.
ROOMS = {
    "briefing_room": ((10, 18, 30), (0, 170, 190), "monitors"),
    "inbox_gate": ((22, 16, 12), (190, 130, 50), "mail"),
    "execution_fields": ((8, 22, 20), (40, 190, 150), "terminals"),
    "clockwork_tower": ((14, 16, 24), (130, 155, 185), "ticks"),
    "shadow_archives": ((8, 10, 20), (80, 100, 150), "quiet"),
    "recon_maze": ((10, 16, 22), (70, 140, 170), "nodes"),
    "bridges": ((10, 14, 26), (70, 120, 200), "cables"),
    "beacon_spire": ((18, 16, 8), (210, 170, 50), "pulse"),
    "core_vault": ((20, 8, 12), (190, 45, 70), "seal"),
}


def _mix(a, b, t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


class Atmosphere:
    def __init__(self, zone_id: str, accent: tuple[int, int, int]):
        self.zone_id = zone_id
        wash, light, self.motif = ROOMS.get(zone_id, ((10, 14, 22), accent, "nodes"))
        self.wash = wash
        self.light = light
        self.accent = accent
        self.plate = self._plate(config.WIDTH, config.HEIGHT)

    def _plate(self, w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h))
        wash = self.wash
        for y in range(h):
            t = y / h
            col = _mix((4, 6, 12), wash, 0.55 * (1 - t * 0.65))
            pygame.draw.line(surf, col, (0, y), (w, y))
        horizon = int(h * 0.62)
        pygame.draw.line(surf, _mix(wash, self.light, 0.25), (0, horizon), (w, horizon))
        rng = random.Random(self.zone_id)
        count = 8 if self.motif == "quiet" else 16
        for _ in range(count):
            x, y = rng.randrange(40, w - 40), rng.randrange(36, horizon - 10)
            alpha_col = _mix(wash, self.light, 0.35 + rng.random() * 0.4)
            if self.motif in ("monitors", "terminals", "mail") and rng.random() < 0.45:
                pygame.draw.rect(surf, alpha_col, (x, y, rng.choice((10, 16, 22)), 3))
            else:
                pygame.draw.circle(surf, alpha_col, (x, y), 1)
        if self.motif == "ticks":
            x = int(w * 0.82)
            for i in range(8):
                pygame.draw.line(surf, self.light, (x, 70 + i * 28), (x + 14, 70 + i * 28), 1)
        elif self.motif == "cables":
            for y in (int(h * 0.72), int(h * 0.78)):
                pygame.draw.line(surf, _mix(wash, self.light, 0.35), (0, y), (w, y), 1)
        elif self.motif == "seal":
            pygame.draw.line(surf, self.light, (int(w * 0.3), horizon + 24), (int(w * 0.7), horizon + 24), 2)
        return surf

    def draw(self, surface: pygame.Surface, time: float) -> None:
        surface.blit(self.plate, (0, 0))
        if self.motif != "pulse":
            return
        w, h = surface.get_size()
        phase = 0.5 + 0.5 * math.sin(time * 1.4)
        glow = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*self.light, int(40 + 80 * phase)), (9, 9), 4)
        surface.blit(glow, (w // 2 - 9, int(h * 0.22)))
