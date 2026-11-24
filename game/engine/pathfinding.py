"""A* on a tile grid (8 directions, no cutting corners)."""

from __future__ import annotations

import heapq
import math
from typing import Callable

STEPS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def astar(start: tuple[int, int], goal: tuple[int, int], passable: Callable[[int, int], bool],
          limit: int = 6000) -> list[tuple[int, int]]:
    """Tiles from start (exclusive) to goal (inclusive), or [] if unreachable."""
    if start == goal:
        return []
    if not passable(*goal):
        return []
    open_heap = [(0.0, start)]
    came: dict[tuple[int, int], tuple[int, int]] = {}
    g = {start: 0.0}
    seen = 0
    while open_heap and seen < limit:
        _, cur = heapq.heappop(open_heap)
        seen += 1
        if cur == goal:
            path = [cur]
            while path[-1] in came and came[path[-1]] != start:
                path.append(came[path[-1]])
            return path[::-1]
        cx, cy = cur
        for dx, dy in STEPS:
            nx, ny = cx + dx, cy + dy
            if not passable(nx, ny):
                continue
            if dx and dy and not (passable(cx + dx, cy) and passable(cx, cy + dy)):
                continue
            cost = g[cur] + (1.4142 if dx and dy else 1.0)
            if cost < g.get((nx, ny), math.inf):
                g[(nx, ny)] = cost
                came[(nx, ny)] = cur
                h = max(abs(goal[0] - nx), abs(goal[1] - ny))
                heapq.heappush(open_heap, (cost + h, (nx, ny)))
    return []


def nearest_passable(tile: tuple[int, int], passable: Callable[[int, int], bool],
                     radius: int = 3) -> tuple[int, int] | None:
    x, y = tile
    if passable(x, y):
        return tile
    best = None
    for r in range(1, radius + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) == r and passable(x + dx, y + dy):
                    d = dx * dx + dy * dy
                    if best is None or d < best[0]:
                        best = (d, (x + dx, y + dy))
        if best:
            return best[1]
    return None
