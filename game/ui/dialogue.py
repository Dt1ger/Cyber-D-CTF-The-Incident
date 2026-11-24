"""Typewriter dialogue box with speaker portraits."""

from __future__ import annotations

import math

import pygame

from game.ui import theme
from game.ui.text import font
from game.ui.widgets import wrap

BOX_H = 176


def oracle_face(size: int, t: float = 0.0) -> pygame.Surface:
    """Procedural stand-in for Oracle when the portrait sheet is missing."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cyan = (0, 220, 255)
    c = size // 2
    pygame.draw.polygon(s, (0, 120, 160, 150), [(c, int(size * 0.08)), (int(size * 0.86), int(size * 0.62)),
                                                 (int(size * 0.78), size), (int(size * 0.22), size),
                                                 (int(size * 0.14), int(size * 0.62))])
    pygame.draw.ellipse(s, (0, 30, 50, 230), (int(size * 0.3), int(size * 0.3), int(size * 0.4), int(size * 0.46)))
    eye = 0.6 + 0.4 * math.sin(t * 3)
    for ex in (0.42, 0.58):
        pygame.draw.circle(s, (int(160 * eye), int(255 * eye), 255), (int(size * ex), int(size * 0.5)),
                           max(2, size // 28))
    for y in range(0, size, 4):
        s.fill((0, 0, 0, 40), (0, y, size, 1))
    pygame.draw.polygon(s, cyan, [(c, int(size * 0.08)), (int(size * 0.86), int(size * 0.62)),
                                  (int(size * 0.78), size - 1), (int(size * 0.22), size - 1),
                                  (int(size * 0.14), int(size * 0.62))], 2)
    return s


class DialogueBox:
    def __init__(self, app):
        self.app = app
        self.queue: list[dict] = []
        self.current: dict | None = None
        self.shown = 0.0
        self.time = 0.0
        self.on_done = []
        self._last_tick = 0

    @property
    def active(self) -> bool:
        return self.current is not None

    def say(self, lines: list[dict], on_done=None) -> None:
        self.queue.extend(dict(ln) for ln in lines if ln and ln.get("text"))
        if on_done:
            self.on_done.append(on_done)
        if self.current is None:
            self._next()

    def say_keys(self, keys: list[str], on_done=None) -> None:
        char = self.app.run.character if getattr(self.app, "run", None) else ""
        self.say(self.app.dialogue.lines(keys, char), on_done)

    def _next(self) -> None:
        self.current = self.queue.pop(0) if self.queue else None
        self.shown = 0.0
        self._last_tick = 0
        if self.current is None:
            callbacks, self.on_done = self.on_done, []
            for cb in callbacks:
                cb()

    def skip_all(self) -> None:
        self.queue.clear()
        self.current = None
        self._next()

    def advance(self) -> None:
        if self.current is None:
            return
        if self.shown < len(self.current["text"]):
            self.shown = len(self.current["text"])
        else:
            self.app.audio.play("blip")
            self._next()

    def handle_event(self, event) -> bool:
        """Consumes input while active. Returns True if the event was used."""
        if not self.active:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.skip_all()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_e):
                self.advance()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.advance()
            return True
        return event.type in (pygame.KEYUP, pygame.TEXTINPUT)

    def update(self, dt: float) -> None:
        self.time += dt
        if self.current is None:
            return
        before = int(self.shown)
        self.shown = min(len(self.current["text"]), self.shown + dt * self.app.settings.chars_per_second)
        if int(self.shown) // 3 > before // 3 and int(self.shown) < len(self.current["text"]):
            self.app.audio.play("type")

    def _speaker(self) -> tuple[str, tuple, pygame.Surface | None]:
        sp = self.current.get("speaker", "narrator")
        if sp == "player":
            run = getattr(self.app, "run", None)
            char = self.app.character(run.character) if run else self.app.characters[0]
            tier = self.app.assets.tier_for_zone(run.zone if run else 0, char.id)
            return char.name, char.accent, self.app.assets.face(char.id, tier, char.palette, 132)
        if sp == "oracle":
            frame = int(self.current.get("frame", 0))
            face = self.app.assets.cast_portrait("oracle", frame, 132) or oracle_face(132, self.time)
            return "ORACLE", (196, 140, 255), face
        if sp == "seer":
            frame = int(self.current.get("frame", 8))
            return "SEER", (255, 70, 150), self.app.assets.cast_portrait("seer", frame, 132)
        if sp == "system":
            return "SYSTEM", theme.color("amber"), None
        return "", theme.color("dim"), None

    def draw(self, surface: pygame.Surface) -> None:
        if self.current is None:
            return
        w, h = surface.get_size()
        rect = pygame.Rect(40, h - BOX_H - 24, w - 80, BOX_H)
        name, color, face = self._speaker()
        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        bg.fill((6, 10, 22, 236))
        surface.blit(bg, rect)
        pygame.draw.rect(surface, color, rect, 2, border_radius=8)
        x = rect.x + 20
        if face is not None:
            frame = pygame.Rect(rect.x + 18, rect.y + 20, 136, 136)
            pygame.draw.rect(surface, (12, 18, 34), frame, border_radius=6)
            surface.blit(face, face.get_rect(center=frame.center))
            pygame.draw.rect(surface, color, frame, 2, border_radius=6)
            x = frame.right + 22
        if name:
            surface.blit(font(22, bold=True).render(name.upper(), True, color), (x, rect.y + 16))
        fnt = font(21)
        text = self.current["text"][: int(self.shown)]
        style_italic = not name
        lines = wrap(text, fnt, rect.right - x - 24)
        top = rect.y + (52 if name else 30)
        for i, line in enumerate(lines[:5]):
            col = theme.color("text") if not style_italic else (190, 205, 220)
            surface.blit(fnt.render(line, True, col), (x, top + i * fnt.get_linesize()))
        if self.shown >= len(self.current["text"]):
            blink = (self.time * 2) % 2 < 1.3
            if blink:
                more = "ENTER >" if self.queue else "ENTER x"
                t = font(14, mono=True).render(more + "   ESC skip", True, theme.color("dim"))
                surface.blit(t, t.get_rect(bottomright=(rect.right - 14, rect.bottom - 10)))
