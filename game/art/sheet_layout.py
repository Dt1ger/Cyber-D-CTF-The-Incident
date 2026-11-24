"""Detect the frame layout of a sprite sheet from its pixels.

Hand-painted or AI-generated sheets rarely sit on an exact grid, so instead of
assuming ``width / cols`` we find the empty bands between sprites and record the
tight content extents of every row and column. The loader then crops each cell
and bottom-aligns it on a uniform canvas so feet stay planted between frames.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

ALPHA_THRESHOLD = 40
BG_TOLERANCE = 6
SAMPLE_STEP = 2
NOISE_PER_LINE = 1
MIN_GAP = 4
MIN_BAND = 24


@dataclass
class SheetLayout:
    rows: list[tuple[int, int]]
    cols: list[tuple[int, int]]
    background: str  # "alpha" or "flood"

    @property
    def frame_width(self) -> int:
        return max((b - a for a, b in self.cols), default=0)

    @property
    def frame_height(self) -> int:
        return max((b - a for a, b in self.rows), default=0)

    @property
    def is_sheet(self) -> bool:
        return len(self.rows) * len(self.cols) > 1


def has_transparency(surface: pygame.Surface) -> bool:
    if not surface.get_flags() & pygame.SRCALPHA:
        return False
    w, h = surface.get_size()
    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    return any(surface.get_at(c).a < 255 for c in corners)


def background_mask(surface: pygame.Surface, tolerance: int = BG_TOLERANCE) -> pygame.Mask:
    """Mask of the solid background connected to the top-left corner."""
    bg = surface.get_at((0, 0))
    near = pygame.mask.from_threshold(
        surface, bg, (tolerance, tolerance, tolerance, 255)
    )
    if near.get_at((0, 0)):
        return near.connected_component((0, 0))
    return near


def remove_background(surface: pygame.Surface, tolerance: int = BG_TOLERANCE) -> pygame.Surface:
    """Copy of ``surface`` with the corner-connected solid background made transparent."""
    out = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    out.blit(surface, (0, 0))
    background_mask(surface, tolerance).to_surface(out, setcolor=(0, 0, 0, 0), unsetcolor=None)
    return out


def content_mask(surface: pygame.Surface) -> tuple[pygame.Mask, str]:
    if has_transparency(surface):
        return pygame.mask.from_surface(surface, ALPHA_THRESHOLD), "alpha"
    bg = background_mask(surface)
    bg.invert()
    return bg, "flood"


def _bands(profile: list[int], step: int) -> list[tuple[int, int]]:
    bands: list[tuple[int, int]] = []
    start = None
    gap = 0
    for i, v in enumerate(profile):
        if v > NOISE_PER_LINE:
            if start is None:
                start = i
            gap = 0
        elif start is not None:
            gap += 1
            if gap * step >= MIN_GAP:
                bands.append((start, i - gap + 1))
                start = None
                gap = 0
    if start is not None:
        bands.append((start, len(profile) - gap))
    out = [(a * step, min(b * step, len(profile) * step)) for a, b in bands]
    return [(a, b) for a, b in out if b - a >= MIN_BAND]


def detect_layout(surface: pygame.Surface) -> SheetLayout:
    mask, background = content_mask(surface)
    w, h = mask.get_size()
    small = mask.scale((max(1, w // SAMPLE_STEP), max(1, h // SAMPLE_STEP)))
    sw, sh = small.get_size()
    row_profile = [0] * sh
    col_profile = [0] * sw
    get = small.get_at
    for y in range(sh):
        count = 0
        for x in range(sw):
            if get((x, y)):
                count += 1
                col_profile[x] += 1
        row_profile[y] = count
    pad = SAMPLE_STEP
    rows = [(max(0, a - pad), min(b + pad, h)) for a, b in _bands(row_profile, SAMPLE_STEP)]
    cols = [(max(0, a - pad), min(b + pad, w)) for a, b in _bands(col_profile, SAMPLE_STEP)]
    if not rows:
        rows = [(0, h)]
    if not cols:
        cols = [(0, w)]
    return SheetLayout(rows=rows, cols=cols, background=background)
