"""Opening story: typewritten pages over the Grid. Enter advances, Esc skips."""

from __future__ import annotations

import math
import random

import pygame

from game.art import effects
from game.engine import config
from game.engine.scene import Scene
from game.ui import theme
from game.ui.text import font, rendered
from game.ui.widgets import wrap

HOLD = 5.4
CPS = 42


class CinematicScene(Scene):
    def on_enter(self, **kwargs) -> None:
        self.pages = self.app.dialogue.sequence("cinematic") or ["The Grid is under attack."]
        self.page = 0
        self.shown = 0.0
        self.hold = 0.0
        self.time = 0.0
        self.particles = effects.Particles((config.WIDTH, config.HEIGHT), 80, seed=21)
        self.rng = random.Random(9)
        self.glitch_t = 0.0
        self.bg = self.app.assets.optional_background("cinematic", (config.WIDTH, config.HEIGHT))
        self.leaving = False
        self.app.audio.stop_music()

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.finish()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.advance()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.advance()

    def advance(self) -> None:
        if self.shown < len(self.pages[self.page]):
            self.shown = len(self.pages[self.page])
        else:
            self.next_page()

    def next_page(self) -> None:
        self.page += 1
        self.shown = 0.0
        self.hold = 0.0
        if self.page >= len(self.pages):
            self.page = len(self.pages) - 1
            self.finish()
        else:
            self.app.audio.play("blip")
            if self.page in (3, 6):
                self.glitch_t = 0.3
                self.app.audio.play("glitch")

    def finish(self) -> None:
        if not self.leaving:
            self.leaving = True
            self.app.scenes.switch("character_select")

    def update(self, dt: float) -> None:
        self.time += dt
        self.particles.update(dt)
        self.glitch_t -= dt
        text = self.pages[self.page]
        before = int(self.shown)
        speed = CPS if self.app.settings.type_speed < 3 else 10000
        self.shown = min(len(text), self.shown + dt * speed)
        if int(self.shown) // 4 > before // 4 and self.shown < len(text):
            self.app.audio.play("type")
        if self.shown >= len(text):
            self.hold += dt
            if self.hold >= HOLD:
                self.next_page()

    def _grid(self, surface) -> None:
        w, h = surface.get_size()
        horizon = int(h * 0.58)
        col = (0, 70, 90)
        for i in range(-14, 15):
            x0 = w // 2 + i * 26
            x1 = w // 2 + i * 190
            pygame.draw.line(surface, col, (x0, horizon), (x1, h), 1)
        off = (self.time * 40) % 40
        for j in range(12):
            t = (j * 40 + off) / 480
            y = horizon + int((h - horizon) * t * t)
            pygame.draw.line(surface, col, (0, y), (w, y), 1)
        for i, x in enumerate(range(40, w, 70)):
            bh = 40 + (i * 37) % 150
            a = 0.5 + 0.5 * math.sin(self.time * 0.8 + i)
            pygame.draw.rect(surface, (0, int(40 + 50 * a), int(60 + 60 * a)), (x, horizon - bh, 34, bh), 1)

    def draw(self, surface) -> None:
        w, h = surface.get_size()
        if self.bg:
            surface.blit(self.bg.surface, (0, 0))
            surface.blit(effects.translucent((w, h), (0, 0, 0, 160)), (0, 0))
        else:
            self._grid(surface)
        self.particles.draw(surface)
        box = pygame.Rect(120, h // 2 - 150, w - 240, 250)
        surface.blit(effects.translucent(box.size, (2, 4, 12, 190)), box)
        pygame.draw.line(surface, config.CYAN, (box.x, box.y), (box.x + 120, box.y), 2)
        pygame.draw.line(surface, config.MAGENTA, (box.right - 120, box.bottom), (box.right, box.bottom), 2)
        fnt = font(27)
        text = self.pages[self.page][: int(self.shown)]
        lines = wrap(text, fnt, box.width - 80)
        y = box.y + 36
        for line in lines:
            surface.blit(rendered(fnt, line, theme.color("text")), (box.x + 40, y))
            y += fnt.get_linesize() + 4
        if self.shown < len(self.pages[self.page]) and int(self.time * 3) % 2 == 0:
            cx = box.x + 40 + (fnt.size(lines[-1])[0] if lines else 0) + 3
            pygame.draw.rect(surface, config.CYAN, (cx, y - fnt.get_linesize() - 2, 12, fnt.get_height()))
        dots = "".join("o" if i == self.page else "." for i in range(len(self.pages)))
        surface.blit(rendered(font(16, mono=True), dots, theme.color("dim")), (box.x, box.bottom + 14))
        hint = rendered(font(15, mono=True), "ENTER next    ESC skip", theme.color("dim"))
        surface.blit(hint, hint.get_rect(bottomright=(w - 24, h - 18)))
        if self.glitch_t > 0:
            effects.glitch(surface, 0.5, self.rng)
        surface.blit(effects.vignette((w, h)), (0, 0))
