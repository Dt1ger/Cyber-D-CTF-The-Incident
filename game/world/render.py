"""Draws a TileMap: a pre-rendered static layer plus animated details and fog."""

from __future__ import annotations

import math
import random

import pygame

from game.world.atmosphere import ROOMS
from game.world.tilemap import BUS, FLOOR, GATE, RACK, TILE, WALL, Fog, TileMap


def _mix(a, b, t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def _floor_tile(accent, wash, rng) -> pygame.Surface:
    """A dark operations panel. One seam, and only occasionally a status light."""
    s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    base = _mix((12, 16, 28), wash, 0.4)
    s.fill((*base, 242))
    pygame.draw.rect(s, (*accent, 28), s.get_rect(), 1)
    pygame.draw.line(s, (*_mix(base, (0, 0, 0), 0.35), 180), (4, TILE - 8), (TILE - 4, TILE - 8))
    if rng.random() < 0.12:
        pygame.draw.rect(s, (*accent, 18), (10, 10, TILE - 20, TILE - 24), 1)
    if rng.random() < 0.07:
        s.fill((*accent, 160), (TILE - 10, 8, 3, 3))
    return s


def _bus_tile(accent) -> pygame.Surface:
    s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    s.fill((7, 10, 22, 240))
    pygame.draw.line(s, (*accent, 30), (0, 0), (TILE, 0))
    return s


class MapRenderer:
    def __init__(self, tmap: TileMap, accent, assets=None, zone_id: str = ""):
        self.map = tmap
        self.accent = tuple(accent)
        self.assets = assets
        self.wash = ROOMS.get(zone_id, ((10, 14, 22), accent, "nodes"))[0]
        self.static = self._build()
        self.time = 0.0
        self._fog_small = None
        self._fog_version = -1

    def _build(self) -> pygame.Surface:
        m = self.map
        surf = pygame.Surface(m.pixel_size, pygame.SRCALPHA)
        rng = random.Random(m.width * 31 + m.height)
        custom = {k: self.assets.tile(k, TILE) if self.assets else None
                  for k in ("floor", "wall", "bus")}
        bus = custom["bus"] or _bus_tile(self.accent)
        edge = tuple(min(255, c + 40) for c in self.accent)
        for y in range(m.height):
            for x in range(m.width):
                t = m.tiles[y][x]
                px, py = x * TILE, y * TILE
                if t in (FLOOR, RACK, GATE):
                    surf.blit(custom["floor"] or _floor_tile(self.accent, self.wash, rng), (px, py))
                elif t == BUS:
                    surf.blit(bus, (px, py))
                elif t == WALL:
                    if custom["wall"]:
                        surf.blit(custom["wall"], (px, py))
                    else:
                        wall = _mix((16, 18, 30), self.wash, 0.35)
                        surf.fill((*wall, 255), (px, py, TILE, TILE))
                        for dx, dy, a, b in ((0, -1, (0, 0), (TILE, 0)), (0, 1, (0, TILE - 2), (TILE, TILE - 2)),
                                             (-1, 0, (0, 0), (0, TILE)), (1, 0, (TILE - 2, 0), (TILE - 2, TILE))):
                            if m.get(x + dx, y + dy) in (FLOOR, BUS, RACK, GATE):
                                pygame.draw.line(surf, edge, (px + a[0], py + a[1]), (px + b[0], py + b[1]), 2)
                        if rng.random() < 0.05:
                            surf.fill((*self.accent, 255), (px + rng.randrange(8, 40), py + 6, 3, 3))
        b0, b1 = m.bus_rows
        y = int((b0 + b1) / 2 * TILE)
        for x in range(0, m.width * TILE, 24):
            if m.get(x // TILE, (b0 + b1) // 2) == BUS:
                pygame.draw.line(surf, (*self.accent, 60), (x, y), (x + 10, y), 2)
        return surf

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, surface: pygame.Surface, cam_pos) -> None:
        cx, cy = cam_pos
        surface.blit(self.static, (-cx, -cy))
        m = self.map
        b0, b1 = m.bus_rows
        lane_y = [b0 * TILE + 14, (b0 + b1) // 2 * TILE + TILE // 2, b1 * TILE - 14]
        x_end = (m.width - 12) * TILE
        for i in range(26):
            lane = i % 3
            speed = 120 + 40 * lane
            x = (i * 377 + self.time * speed) % max(1, x_end - 10 * TILE) + 10 * TILE
            sx, sy = int(x - cx), lane_y[lane] - cy
            if -20 < sx < surface.get_width() + 20:
                pygame.draw.line(surface, tuple(c // 3 for c in self.accent), (sx - 18, sy), (sx, sy), 2)
                surface.fill(self.accent, (sx, sy - 1, 4, 3))

    def draw_gate(self, surface, cam_pos, open_: bool, color_open, color_closed) -> None:
        cx, cy = cam_pos
        for gx, gy in self.map.gate:
            r = pygame.Rect(gx * TILE - cx, gy * TILE - cy, TILE, TILE)
            if open_:
                pygame.draw.rect(surface, color_open, r.inflate(-30, 0), 1)
            else:
                flick = 0.6 + 0.4 * math.sin(self.time * 6 + gy)
                col = tuple(int(c * flick) for c in color_closed)
                for i in range(0, TILE, 8):
                    pygame.draw.line(surface, col, (r.centerx - 6, r.y + i), (r.centerx + 6, r.y + i + 4), 2)
                pygame.draw.line(surface, color_closed, (r.centerx, r.y), (r.centerx, r.bottom), 2)

    def draw_fog(self, surface: pygame.Surface, cam_pos, fog: Fog) -> None:
        m = self.map
        if self._fog_version != fog.version:
            small = pygame.Surface((m.width, m.height), pygame.SRCALPHA)
            small.fill((*_mix((3, 4, 10), self.wash, 0.6), 186))
            for y in range(m.height):
                row = fog.explored[y]
                for x in range(m.width):
                    if row[x]:
                        small.set_at((x, y), (2, 3, 8, 0))
            self._fog_small = small
            self._fog_version = fog.version
        cx, cy = cam_pos
        vw, vh = surface.get_size()
        tx0, ty0 = max(0, cx // TILE - 1), max(0, cy // TILE - 1)
        tx1 = min(m.width, (cx + vw) // TILE + 2)
        ty1 = min(m.height, (cy + vh) // TILE + 2)
        if tx1 <= tx0 or ty1 <= ty0:
            return
        part = self._fog_small.subsurface((tx0, ty0, tx1 - tx0, ty1 - ty0))
        big = pygame.transform.smoothscale(part, ((tx1 - tx0) * TILE, (ty1 - ty0) * TILE))
        surface.blit(big, (tx0 * TILE - cx - TILE // 2, ty0 * TILE - cy - TILE // 2))
