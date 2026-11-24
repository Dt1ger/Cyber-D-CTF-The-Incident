"""Modal panels opened inside a zone. The zone scene routes all input to the open panel."""

from __future__ import annotations

import pygame

from game.ui import theme
from game.ui.text import font
from game.ui.widgets import ScrollText, draw_panel, key_hint, wrap


class Panel:
    name = ""
    title = ""
    hotkey: int | None = None
    footer = "Esc close"

    def __init__(self, scene):
        self.scene = scene
        self.app = scene.app
        self.state = scene.state
        self.closed = False
        self.time = 0.0

    def frame(self, surface) -> pygame.Rect:
        w, h = surface.get_size()
        return pygame.Rect(36, 28, w - 72, h - 100)

    def close(self) -> None:
        self.closed = True
        self.app.audio.play("back")

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and (event.key == pygame.K_ESCAPE or
                                             (self.hotkey is not None and event.key == self.hotkey)):
            self.close()
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self.close()
            return
        self.on_event(event)

    def on_event(self, event) -> None:
        pass

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, surface) -> None:
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 140))
        surface.blit(veil, (0, 0))
        rect = self.frame(surface)
        inner = draw_panel(surface, rect, self.title, subtitle=self.subtitle())
        footer_h = font(14, mono=True).get_linesize() + 4
        inner.height -= footer_h
        self.draw_body(surface, inner)
        key_hint(surface, self.footer, (rect.right - 14, rect.bottom - 8))

    def subtitle(self) -> str | None:
        return None

    def draw_body(self, surface, rect: pygame.Rect) -> None:
        pass


def evidence_lines(ev: dict, eid: str = "") -> list[tuple[str, str]]:
    head = [(f"{ev.get('title', eid)}", "accent"),
            (f"{eid}  |  {ev.get('type', '').upper()}  |  host {ev.get('host', '?')}  |  {ev.get('time', '')}", "dim"),
            ("", "normal")]
    body = [(line, "normal") for line in ev.get("lines", [])]
    tip = [("", "normal"), (f"ANALYST TIP: {ev['tip']}", "warn")] if ev.get("tip") else []
    return head + body + tip


class InfoPanel(Panel):
    """A simple read-only panel (CTF cache clue, notices)."""

    def __init__(self, scene, title: str, lines: list[tuple[str, str]], width: int = 820, height: int = 380):
        super().__init__(scene)
        self.title = title
        self.text = ScrollText(17)
        self.text.set_lines(lines)
        self.size = (width, height)

    def frame(self, surface) -> pygame.Rect:
        r = pygame.Rect(0, 0, *self.size)
        r.center = (surface.get_width() // 2, surface.get_height() // 2 - 30)
        return r

    def on_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_e):
            self.close()
            return
        self.text.handle_event(event)

    def draw_body(self, surface, rect) -> None:
        self.text.draw(surface, rect)


def draw_wrapped(surface, text: str, rect: pygame.Rect, size: int = 17, color=None, mono=False,
                 line_gap: int = 0) -> int:
    """Draw wrapped text inside rect; returns the y after the last line."""
    fnt = font(size, mono)
    y = rect.y
    for line in wrap(text, fnt, rect.width):
        if y + fnt.get_linesize() > rect.bottom:
            break
        surface.blit(fnt.render(line, True, color or theme.color("text")), (rect.x, y))
        y += fnt.get_linesize() + line_gap
    return y
