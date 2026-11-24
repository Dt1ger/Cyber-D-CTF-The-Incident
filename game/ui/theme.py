"""Shared colors. The colorblind palette swaps red/green signals for blue/orange."""

from __future__ import annotations

from game.engine import config

BASE = {
    "bg": config.BG,
    "panel": (10, 14, 28),
    "panel_edge": (40, 60, 90),
    "text": config.TEXT,
    "dim": config.DIM,
    "cyan": config.CYAN,
    "magenta": config.MAGENTA,
    "amber": config.AMBER,
    "ok": (60, 230, 120),
    "bad": (255, 70, 90),
    "warn": (255, 190, 60),
    "corrupt": (255, 0, 170),
    "info": (120, 200, 255),
}
COLORBLIND = {
    "ok": (80, 170, 255),
    "bad": (255, 150, 30),
    "warn": (240, 228, 66),
    "corrupt": (204, 121, 167),
}

_colorblind = False
accent = config.CYAN


def set_colorblind(on: bool) -> None:
    global _colorblind
    _colorblind = bool(on)


def set_accent(color) -> None:
    global accent
    accent = tuple(color)[:3]


def color(name: str) -> tuple[int, int, int]:
    if _colorblind and name in COLORBLIND:
        return COLORBLIND[name]
    return BASE.get(name, BASE["text"])


STYLE_COLORS = {"normal": "text", "dim": "dim", "header": "cyan", "ok": "ok", "bad": "bad",
                "warn": "warn", "prompt": "amber", "amber": "amber", "accent": None}


def style_color(style: str) -> tuple[int, int, int]:
    name = STYLE_COLORS.get(style, "text")
    return accent if name is None else color(name)
