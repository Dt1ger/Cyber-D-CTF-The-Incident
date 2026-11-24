"""Procedural stand-ins for any image that is missing or broken.

Characters are drawn at the same reference frame size as the real sheets so
the game looks the same size either way, then scaled like real art.
"""

from __future__ import annotations

import math
import random

import pygame

from game.art.animation import DIRECTIONS, Animation, SpriteSet
from game.ui.text import font, glow_text

FRAME_W, FRAME_H = 160, 272

DEFAULT_PALETTE = {
    "skin": "#c08a64",
    "hair": "#202028",
    "hair_style": "short",
    "beard": None,
    "hoodie": "#2a8cff",
    "hoodie_shade": "#1a5cb0",
    "legs": "#303848",
    "shoes": ["#e0e0e0", "#2a8cff", "#111111"],
    "accent": "#00f0ff",
}


def _c(value, default=(255, 0, 255)) -> pygame.Color:
    try:
        return pygame.Color(value)
    except (ValueError, TypeError):
        return pygame.Color(default)


def _palette(palette: dict | None) -> dict:
    merged = dict(DEFAULT_PALETTE)
    merged.update(palette or {})
    return merged


def draw_character_frame(palette: dict | None, direction: str = "down", phase: int = 0,
                         walking: bool = False, interact_stage: int | None = None) -> pygame.Surface:
    p = _palette(palette)
    skin, hair, hoodie = _c(p["skin"]), _c(p["hair"]), _c(p["hoodie"])
    shade, legs, accent = _c(p["hoodie_shade"]), _c(p["legs"]), _c(p["accent"])
    shoes = [_c(s) for s in (list(p["shoes"]) + ["#ffffff", "#000000", "#000000"])[:3]]
    surf = pygame.Surface((FRAME_W, FRAME_H), pygame.SRCALPHA)
    if interact_stage is not None:
        direction, walking = "up", False

    stride = [10, 0, -10, 0][phase % 4] if walking else 0
    bob = -5 if walking and phase % 2 == 1 else 0
    side = direction in ("left", "right")
    face = -1 if direction == "left" else 1

    pygame.draw.ellipse(surf, (0, 0, 0, 90), (34, 246, 92, 20))

    def leg(x, length, dx=0):
        top = 168 + bob
        pygame.draw.rect(surf, legs, (x + dx, top, 22, length), border_radius=6)
        sx, sy = x + dx - 3, top + length - 4
        pygame.draw.rect(surf, shoes[0], (sx, sy, 28, 16), border_radius=5)
        pygame.draw.rect(surf, shoes[1], (sx, sy, 28, 7), border_top_left_radius=5,
                         border_top_right_radius=5)
        pygame.draw.rect(surf, shoes[2], (sx, sy + 12, 28, 4))

    if side:
        leg(70, 70, -stride * face)
        leg(70, 70, stride * face)
    else:
        leg(52, 70 + stride)
        leg(86, 70 - stride)

    body = (52, 96 + bob, 56, 82) if side else (40, 96 + bob, 80, 82)
    pygame.draw.rect(surf, hoodie, body, border_radius=16)
    pygame.draw.rect(surf, shade, (body[0], body[1] + 58, body[2], 24),
                     border_bottom_left_radius=16, border_bottom_right_radius=16)

    swing = stride // 2
    if side:
        pygame.draw.rect(surf, shade, (72 + swing * face, 104 + bob, 18, 58), border_radius=8)
    else:
        pygame.draw.rect(surf, shade, (24, 104 + bob - swing, 18, 58), border_radius=8)
        pygame.draw.rect(surf, shade, (118, 104 + bob + swing, 18, 58), border_radius=8)
        if direction == "down":
            pygame.draw.line(surf, (235, 235, 235), (72, 104 + bob), (70, 128 + bob), 2)
            pygame.draw.line(surf, (235, 235, 235), (88, 104 + bob), (90, 128 + bob), 2)

    hx, hy = 80, 70 + bob
    if direction == "up":
        pygame.draw.ellipse(surf, shade, (46, 82 + bob, 68, 26))
    pygame.draw.circle(surf, skin, (hx, hy), 30)

    long_hair = p.get("hair_style") == "long"
    if direction == "up":
        pygame.draw.circle(surf, hair, (hx, hy - 2), 31)
        if long_hair:
            pygame.draw.rect(surf, hair, (48, hy, 64, 40), border_radius=14)
    elif side:
        back = hx - 12 * face
        pygame.draw.ellipse(surf, hair, (back - 26, hy - 34, 56, 44))
        if long_hair:
            pygame.draw.rect(surf, hair, (back - 22, hy - 6, 30, 44), border_radius=12)
        pygame.draw.circle(surf, (20, 20, 24), (hx + 14 * face, hy + 2), 3)
        if p.get("beard"):
            pygame.draw.ellipse(surf, _c(p["beard"]), (hx - 6 + 6 * face, hy + 12, 30, 16))
    else:
        pygame.draw.ellipse(surf, hair, (48, hy - 36, 64, 36))
        if long_hair:
            pygame.draw.rect(surf, hair, (44, hy - 20, 16, 56), border_radius=8)
            pygame.draw.rect(surf, hair, (100, hy - 20, 16, 56), border_radius=8)
        for ex in (hx - 11, hx + 11):
            pygame.draw.circle(surf, (20, 20, 24), (ex, hy + 2), 3)
        if p.get("beard"):
            pygame.draw.arc(surf, _c(p["beard"]), (hx - 24, hy - 10, 48, 40),
                            math.pi * 1.05, math.pi * 1.95, 6)

    if interact_stage is not None:
        pygame.draw.rect(surf, (24, 26, 34), (38, 2, 84, 52), border_radius=6)
        screen = pygame.Rect(44, 7, 72, 40)
        pygame.draw.rect(surf, accent.lerp((0, 0, 0), 0.7), screen, border_radius=3)
        for i in range(min(interact_stage + 1, 3)):
            pygame.draw.line(surf, accent, (50, 14 + i * 9), (50 + 18 + i * 12, 14 + i * 9), 2)
        if interact_stage >= 3:
            pygame.draw.lines(surf, accent, False, [(70, 28), (78, 36), (94, 16)], 4)
    return surf


def _scaled(surface: pygame.Surface, scale: float) -> pygame.Surface:
    if scale == 1.0:
        return surface
    w = max(1, round(surface.get_width() * scale))
    h = max(1, round(surface.get_height() * scale))
    return pygame.transform.smoothscale(surface, (w, h))


def character_sprites(palette: dict | None, scale: float = 0.4) -> SpriteSet:
    anims: dict[str, Animation] = {}
    for d in DIRECTIONS:
        idle = [draw_character_frame(palette, d, 0, False)]
        walk = [draw_character_frame(palette, d, i, True) for i in range(4)]
        anims[f"idle_{d}"] = Animation([_scaled(f, scale) for f in idle], 1)
        anims[f"walk_{d}"] = Animation([_scaled(f, scale) for f in walk], 8)
    anims["interact"] = Animation(
        [_scaled(draw_character_frame(palette, interact_stage=i), scale) for i in range(4)],
        4, loop=False)
    size = anims["idle_down"].frames[0].get_size()
    return SpriteSet(anims, placeholder=True, size=size)


def portrait(palette: dict | None) -> pygame.Surface:
    frame = draw_character_frame(palette, "down")
    return pygame.transform.smoothscale(frame, (FRAME_W * 3, FRAME_H * 3))


def background(size: tuple[int, int], label: str = "", seed: int = 7) -> pygame.Surface:
    """Static neon perspective grid. Scenes can animate particles on top."""
    w, h = size
    surf = pygame.Surface(size)
    top, bottom = pygame.Color(6, 8, 22), pygame.Color(24, 6, 40)
    for y in range(h):
        surf.fill(top.lerp(bottom, y / max(1, h - 1)), (0, y, w, 1))
    horizon = int(h * 0.48)
    vx = w // 2
    grid = pygame.Surface(size, pygame.SRCALPHA)
    cyan, magenta = (0, 240, 255), (255, 0, 170)
    for i in range(-14, 15):
        pygame.draw.line(grid, (*cyan, 70), (vx, horizon), (vx + i * w // 8, h), 1)
    y, gap = horizon, 4.0
    while y < h:
        pygame.draw.line(grid, (*magenta, 80), (0, int(y)), (w, int(y)), 1)
        gap *= 1.22
        y += gap
    pygame.draw.line(grid, (*cyan, 160), (0, horizon), (w, horizon), 2)
    rng = random.Random(seed)
    for _ in range(90):
        x, yy = rng.randrange(w), rng.randrange(horizon)
        grid.fill((*cyan, rng.randrange(40, 160)), (x, yy, 2, 2))
    surf.blit(grid, (0, 0))
    if label:
        tag = font(14, mono=True).render(f"placeholder: {label}", True, (90, 110, 130))
        surf.blit(tag, (w - tag.get_width() - 12, h - tag.get_height() - 8))
    return surf


def logo(title: str, subtitle: str = "") -> pygame.Surface:
    head = glow_text(title, font(64, bold=True), (240, 250, 255), (0, 240, 255), radius=8)
    if not subtitle:
        return head
    sub = glow_text(subtitle.upper(), font(26, mono=True), (255, 190, 60), (255, 0, 170), radius=5)
    out = pygame.Surface((max(head.get_width(), sub.get_width()),
                          head.get_height() + sub.get_height() - 12), pygame.SRCALPHA)
    out.blit(head, ((out.get_width() - head.get_width()) // 2, 0))
    out.blit(sub, ((out.get_width() - sub.get_width()) // 2, head.get_height() - 12))
    return out
