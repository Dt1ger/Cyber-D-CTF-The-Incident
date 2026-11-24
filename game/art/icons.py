"""Window icon built from the app logo. Never raises: a missing file means no icon."""

from __future__ import annotations

import pygame

from game.engine import config

LOGO_PATH = config.ASSETS_DIR / "ui" / "logo.png"


def square_icon(size: int = 32) -> pygame.Surface | None:
    """Fit the wide logo inside a square without stretching it."""
    if not LOGO_PATH.is_file():
        return None
    try:
        logo = pygame.image.load(str(LOGO_PATH))
    except (pygame.error, OSError, ValueError):
        return None
    canvas = pygame.Surface((size, size))
    canvas.fill(logo.get_at((1, 1))[:3])
    scale = min(size / logo.get_width(), size / logo.get_height())
    fitted = pygame.transform.smoothscale(
        logo, (max(1, round(logo.get_width() * scale)), max(1, round(logo.get_height() * scale))))
    canvas.blit(fitted, fitted.get_rect(center=canvas.get_rect().center))
    return canvas


def apply_window_icon() -> None:
    icon = square_icon(32)
    if icon is not None:
        pygame.display.set_icon(icon)
