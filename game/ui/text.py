"""Font cache and neon text rendering."""

from __future__ import annotations

import pygame

DISPLAY_FONTS = "bahnschrift,segoeui,helvetica,arial,dejavusans"
MONO_FONTS = "consolas,cascadiamono,menlo,dejavusansmono,couriernew,monospace"

_cache: dict[tuple, pygame.font.Font] = {}
_rendered: dict[tuple, pygame.Surface] = {}
RENDER_CACHE_LIMIT = 1024
text_scale = 1.0


def font(size: int, mono: bool = False, bold: bool = False) -> pygame.font.Font:
    size = max(8, int(size * text_scale))
    key = (size, mono, bold)
    if key not in _cache:
        if not pygame.font.get_init():
            pygame.font.init()
        try:
            _cache[key] = pygame.font.SysFont(MONO_FONTS if mono else DISPLAY_FONTS, size, bold=bold)
        except Exception:
            _cache[key] = pygame.font.Font(None, size)
    return _cache[key]


def rendered(fnt: pygame.font.Font, text: str, color) -> pygame.Surface:
    """``fnt.render(text, True, color)``, cached. The surface is shared: copy it before set_alpha."""
    key = (fnt, text, tuple(color))
    surf = _rendered.get(key)
    if surf is None:
        if len(_rendered) >= RENDER_CACHE_LIMIT:
            _rendered.clear()
        surf = _rendered[key] = fnt.render(text, True, color)
    return surf


def set_text_scale(scale: float) -> None:
    global text_scale
    text_scale = scale
    _cache.clear()
    _rendered.clear()


def glow_text(text: str, fnt: pygame.font.Font, color, glow_color=None,
              radius: int = 6) -> pygame.Surface:
    """Text with a soft blurred halo, built by downscaling and upscaling."""
    glow_color = glow_color or color
    core = fnt.render(text, True, color)
    w, h = core.get_size()
    pad = radius * 2
    out = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    halo = fnt.render(text, True, glow_color)
    base = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    base.blit(halo, (pad, pad))
    factor = max(2, radius)
    small = pygame.transform.smoothscale(
        base, (max(1, out.get_width() // factor), max(1, out.get_height() // factor)))
    blurred = pygame.transform.smoothscale(small, out.get_size())
    for _ in range(2):
        out.blit(blurred, (0, 0))
    out.blit(core, (pad, pad))
    return out
