"""Procedural zone maps: a start room with Oracle, a data-bus corridor, one room per
host node, an exit gate, and fog of war that clears as the network is mapped.

Layouts are seeded per zone so they never change between runs.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

TILE = 48
VOID, FLOOR, WALL, BUS, GATE, RACK = range(6)
PASSABLE = {FLOOR, BUS}


@dataclass
class Room:
    rect: tuple[int, int, int, int]  # x, y, w, h in tiles
    kind: str  # start | node | exit | cache
    node_id: str | None = None

    @property
    def center(self) -> tuple[int, int]:
        x, y, w, h = self.rect
        return x + w // 2, y + h // 2

    def contains(self, tx: int, ty: int) -> bool:
        x, y, w, h = self.rect
        return x <= tx < x + w and y <= ty < y + h


@dataclass
class TileMap:
    width: int
    height: int
    tiles: list[list[int]]
    rooms: list[Room] = field(default_factory=list)
    node_tiles: dict[str, tuple[int, int]] = field(default_factory=dict)
    start: tuple[int, int] = (0, 0)
    oracle: tuple[int, int] = (0, 0)
    gate: list[tuple[int, int]] = field(default_factory=list)
    cache: tuple[int, int] | None = None
    bus_rows: tuple[int, int] = (0, 0)
    gate_open: bool = False

    @property
    def pixel_size(self) -> tuple[int, int]:
        return self.width * TILE, self.height * TILE

    def get(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x]
        return VOID

    def passable(self, x: int, y: int) -> bool:
        t = self.get(x, y)
        return t in PASSABLE or (t == GATE and self.gate_open)

    def room_at(self, tx: int, ty: int) -> Room | None:
        return next((r for r in self.rooms if r.contains(tx, ty)), None)


def _carve(tiles, x, y, w, h, kind=FLOOR):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if 0 <= yy < len(tiles) and 0 <= xx < len(tiles[0]):
                if kind == FLOOR and tiles[yy][xx] == BUS:
                    continue
                tiles[yy][xx] = kind


def generate(nodes: list[dict], seed: int, with_cache: bool = False) -> TileMap:
    rng = random.Random(seed)
    n = max(1, len(nodes))
    col = 10
    width = 14 + n * col + 16
    height = 28
    bus_top = 12
    tiles = [[VOID] * width for _ in range(height)]
    rooms: list[Room] = []

    _carve(tiles, 2, bus_top - 4, 10, 11)
    start_room = Room((2, bus_top - 4, 10, 11), "start")
    rooms.append(start_room)
    _carve(tiles, 10, bus_top, width - 22, 3, BUS)

    node_tiles = {}
    for i, node in enumerate(nodes):
        cx = 14 + i * col + col // 2 + rng.randint(-1, 1)
        rw, rh = rng.randint(7, 9), rng.randint(6, 7)
        up = i % 2 == 0
        ry = (bus_top - 3 - rh - rng.randint(0, 1)) if up else (bus_top + 6 + rng.randint(0, 1))
        rx = cx - rw // 2
        _carve(tiles, rx, ry, rw, rh)
        if up:
            _carve(tiles, cx - 1, ry + rh, 3, bus_top - (ry + rh))
        else:
            _carve(tiles, cx - 1, bus_top + 3, 3, ry - (bus_top + 3))
        room = Room((rx, ry, rw, rh), "node", node["id"])
        rooms.append(room)
        nx, ny = cx, ry + (2 if up else rh - 3)
        tiles[ny][nx] = RACK
        node_tiles[node["id"]] = (nx, ny)

    ex = width - 13
    _carve(tiles, ex, bus_top - 4, 10, 11)
    rooms.append(Room((ex, bus_top - 4, 10, 11), "exit"))
    gate = []
    gx = ex + 7
    for gy in range(bus_top - 1, bus_top + 4):
        tiles[gy][gx] = GATE
        gate.append((gx, gy))
    for gy in range(bus_top - 4, bus_top + 7):
        if tiles[gy][gx] == FLOOR:
            tiles[gy][gx] = VOID

    cache = None
    if with_cache:
        i = rng.randrange(max(1, n - 1)) if n > 1 else 0
        cx = 14 + i * col + col  # between two node columns, clear of their corridors
        if rng.random() < 0.5:
            _carve(tiles, cx - 1, bus_top - 2, 3, 2)
            cache = (cx, bus_top - 2)
            rooms.append(Room((cx - 1, bus_top - 2, 3, 2), "cache"))
        else:
            _carve(tiles, cx - 1, bus_top + 3, 3, 2)
            cache = (cx, bus_top + 4)
            rooms.append(Room((cx - 1, bus_top + 3, 3, 2), "cache"))

    for y in range(height):
        for x in range(width):
            if tiles[y][x] == VOID:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and tiles[ny][nx] in (FLOOR, BUS, RACK):
                        tiles[y][x] = WALL
                        break

    oracle = (start_room.rect[0] + 3, bus_top)
    start = (start_room.rect[0] + 6, bus_top + 1)
    return TileMap(width, height, tiles, rooms, node_tiles, start, oracle, gate, cache,
                   (bus_top, bus_top + 3))


class Fog:
    """Explored tiles. Rooms reveal fully the moment the player steps inside."""

    def __init__(self, tmap: TileMap, radius: int = 6):
        self.map = tmap
        self.radius = radius
        self.explored = [[False] * tmap.width for _ in range(tmap.height)]
        self.version = 0
        self._last = None
        self._changed = False

    def _reveal(self, xx: int, yy: int) -> None:
        row = self.explored[yy]
        if not row[xx]:
            row[xx] = True
            self._changed = True

    def _reveal_rect(self, x: int, y: int, w: int, h: int) -> None:
        for yy in range(max(0, y - 1), min(self.map.height, y + h + 1)):
            for xx in range(max(0, x - 1), min(self.map.width, x + w + 1)):
                self._reveal(xx, yy)

    def reveal_rect(self, x: int, y: int, w: int, h: int) -> None:
        self._changed = False
        self._reveal_rect(x, y, w, h)
        if self._changed:
            self.version += 1

    def update(self, tx: int, ty: int) -> None:
        """Reveal around the player. ``version`` only moves when a new tile is uncovered,
        so the fog and minimap aren't rebuilt for every step through known ground."""
        if (tx, ty) == self._last:
            return
        self._last = (tx, ty)
        self._changed = False
        r = self.radius
        for yy in range(max(0, ty - r), min(self.map.height, ty + r + 1)):
            for xx in range(max(0, tx - r), min(self.map.width, tx + r + 1)):
                if (xx - tx) ** 2 + (yy - ty) ** 2 <= r * r:
                    self._reveal(xx, yy)
        room = self.map.room_at(tx, ty)
        if room:
            self._reveal_rect(*room.rect)
        if self._changed:
            self.version += 1

    def is_explored(self, tx: int, ty: int) -> bool:
        return 0 <= ty < self.map.height and 0 <= tx < self.map.width and self.explored[ty][tx]

    def fraction(self) -> float:
        total = seen = 0
        for y in range(self.map.height):
            for x in range(self.map.width):
                if self.map.tiles[y][x] != VOID:
                    total += 1
                    seen += self.explored[y][x]
        return seen / max(1, total)
