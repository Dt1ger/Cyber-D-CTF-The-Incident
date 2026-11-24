"""Portrait sheets for the Oracle and the Seer.

The pixel sheets are a 4 by 3 grid of framed busts. An older 3 by 2 photo
sheet still resolves if one is put back, because those gutters are too thin
for the sprite-sheet detector.
"""

from __future__ import annotations

import pygame

# Measured on the 1536x1024 pixel sheets.
_PIXEL_COLS = ((18, 384), (402, 762), (776, 1140), (1156, 1518))
_PIXEL_ROWS = ((10, 338), (346, 672), (680, 1008))
# Measured on the earlier 1122x1402 sheets.
_LEGACY_COLS = ((12, 366), (384, 738), (756, 1110))
_LEGACY_ROWS = ((12, 690), (708, 1388))


def _grid(size: tuple[int, int]) -> tuple[tuple, tuple]:
    w, h = size
    if h <= w:
        return _PIXEL_COLS, _PIXEL_ROWS
    return _LEGACY_COLS, _LEGACY_ROWS


def cell_rect(frame: int, size: tuple[int, int]) -> pygame.Rect:
    cols, rows = _grid(size)
    frame %= len(cols) * len(rows)
    x0, x1 = cols[frame % len(cols)]
    y0, y1 = rows[frame // len(cols)]
    return pygame.Rect(x0, y0, x1 - x0, y1 - y0)


def square_bust(cell: pygame.Surface, size: int) -> pygame.Surface:
    """Whole framed cell, fitted inside a square. Nearest-neighbor keeps the pixels."""
    w, h = cell.get_size()
    scale = size / max(w, h)
    scaled = pygame.transform.scale(cell, (max(1, round(w * scale)), max(1, round(h * scale))))
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    out.blit(scaled, scaled.get_rect(center=(size // 2, size // 2)))
    return out


def standing(cell: pygame.Surface, height: int) -> pygame.Surface:
    w, h = cell.get_size()
    scale = height / h
    return pygame.transform.scale(cell, (max(1, round(w * scale)), height))
