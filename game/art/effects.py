"""Screen effects: CRT scanlines, glitch slices, drifting data particles, vignette."""

from __future__ import annotations

import math
import random

import pygame

_scanline_cache: dict[tuple[int, int], pygame.Surface] = {}
_vignette_cache: dict[tuple[int, int], pygame.Surface] = {}


def scanlines(size: tuple[int, int]) -> pygame.Surface:
    if size not in _scanline_cache:
        w, h = size
        surf = pygame.Surface(size, pygame.SRCALPHA)
        for y in range(0, h, 3):
            surf.fill((0, 0, 0, 55), (0, y, w, 1))
        _scanline_cache[size] = surf
    return _scanline_cache[size]


def vignette(size: tuple[int, int]) -> pygame.Surface:
    if size not in _vignette_cache:
        w, h = size
        small = pygame.Surface((64, 36), pygame.SRCALPHA)
        for y in range(36):
            for x in range(64):
                dx, dy = (x - 31.5) / 32, (y - 17.5) / 18
                d = min(1.0, math.hypot(dx, dy))
                small.set_at((x, y), (0, 0, 0, int(170 * max(0.0, d - 0.55) / 0.45)))
        _vignette_cache[size] = pygame.transform.smoothscale(small, size)
    return _vignette_cache[size]


def glitch(surface: pygame.Surface, strength: float, rng: random.Random | None = None) -> None:
    """Shift random horizontal slices of the surface sideways, in place."""
    if strength <= 0:
        return
    rng = rng or random
    w, h = surface.get_size()
    copy = surface.copy()
    for _ in range(int(4 + strength * 10)):
        y = rng.randrange(h)
        sh = rng.randrange(2, max(3, int(6 + strength * 30)))
        dx = rng.randint(-int(strength * 40), int(strength * 40))
        surface.blit(copy, (dx, y), pygame.Rect(0, y, w, sh))
    if strength > 0.3:
        tint = pygame.Surface((w, h), pygame.SRCALPHA)
        tint.fill((255, 0, 170, int(30 * strength)))
        surface.blit(tint, (rng.randint(-6, 6), 0))


class Particles:
    """Data packets drifting along the screen (title, cinematic, zone ambience)."""

    def __init__(self, size: tuple[int, int], count: int = 70, seed: int = 1,
                 colors=((0, 240, 255), (255, 0, 170), (255, 176, 0))):
        self.w, self.h = size
        self.rng = random.Random(seed)
        self.colors = colors
        self.items = [self._spawn(initial=True) for _ in range(count)]

    def _spawn(self, initial: bool = False) -> list:
        r = self.rng
        x = r.uniform(0, self.w) if initial else -10
        return [x, r.uniform(0, self.h), r.uniform(20, 90), r.choice(self.colors),
                r.randint(2, 4), r.uniform(0, math.tau)]

    def update(self, dt: float) -> None:
        for p in self.items:
            p[0] += p[2] * dt
            p[5] += dt * 2
            if p[0] > self.w + 10:
                p[:] = self._spawn()

    def draw(self, surface: pygame.Surface, offset=(0, 0)) -> None:
        ox, oy = offset
        for x, y, speed, color, size, phase in self.items:
            a = int(120 + 100 * math.sin(phase))
            trail = int(speed / 6)
            pygame.draw.line(surface, (*color, 60) if surface.get_flags() & pygame.SRCALPHA else
                             tuple(c // 3 for c in color), (x - trail - ox, y - oy), (x - ox, y - oy), 1)
            surface.fill(tuple(min(255, c * a // 200) for c in color),
                         (int(x - ox), int(y - oy), size, size))


def pulse(t: float, speed: float = 2.0, low: float = 0.4) -> float:
    return low + (1 - low) * (0.5 + 0.5 * math.sin(t * speed * math.tau / 2))


def glow_rect(surface: pygame.Surface, rect: pygame.Rect, color, width: int = 3,
              radius: int = 8, layers: int = 4, alpha: int = 90) -> None:
    """A rectangle outline with a soft outer glow."""
    glow = pygame.Surface((rect.width + layers * 8, rect.height + layers * 8), pygame.SRCALPHA)
    for i in range(layers, 0, -1):
        a = int(alpha * (1 - i / (layers + 1)))
        r = pygame.Rect(layers * 4 - i * 4, layers * 4 - i * 4,
                        rect.width + i * 8, rect.height + i * 8)
        pygame.draw.rect(glow, (*color[:3], a), r, width + i, border_radius=radius + i * 2)
    surface.blit(glow, (rect.x - layers * 4, rect.y - layers * 4))
    pygame.draw.rect(surface, color, rect, width, border_radius=radius)
