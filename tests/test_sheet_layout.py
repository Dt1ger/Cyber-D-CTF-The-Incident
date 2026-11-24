import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from game.art.sheet_layout import detect_layout


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    yield
    pygame.quit()


def _sheet(row_tops, col_lefts, size=(400, 300), sprite=(40, 50), alpha=True):
    flags = pygame.SRCALPHA if alpha else 0
    surf = pygame.Surface(size, flags)
    surf.fill((0, 0, 0, 0) if alpha else (0, 0, 0))
    for y in row_tops:
        for x in col_lefts:
            pygame.draw.rect(surf, (200, 30, 30, 255), (x, y, *sprite))
    return surf


def test_uneven_rows_are_detected_exactly():
    surf = _sheet(row_tops=[10, 75, 150], col_lefts=[20, 120, 230])
    layout = detect_layout(surf)
    assert len(layout.rows) == 3 and len(layout.cols) == 3
    for (top, bottom), sprite_top in zip(layout.rows, [10, 75, 150]):
        assert top <= sprite_top and bottom >= sprite_top + 50
        assert (bottom - top) - 50 <= 6
    for (left, right), sprite_left in zip(layout.cols, [20, 120, 230]):
        assert left <= sprite_left and right >= sprite_left + 40
    assert layout.background == "alpha"
    assert layout.is_sheet


def test_opaque_black_background_uses_flood_fill():
    surf = _sheet(row_tops=[20, 150], col_lefts=[30, 200], alpha=False)
    layout = detect_layout(surf)
    assert layout.background == "flood"
    assert (len(layout.rows), len(layout.cols)) == (2, 2)


def test_single_image_is_not_a_sheet():
    surf = _sheet(row_tops=[40], col_lefts=[60], sprite=(200, 200))
    layout = detect_layout(surf)
    assert not layout.is_sheet
    assert layout.frame_width >= 198 and layout.frame_height >= 198
