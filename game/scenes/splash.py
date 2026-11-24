"""Studio logo with a glitch. Skippable; goes to the title after ~2.6 s."""

from __future__ import annotations

import random

import pygame

from game.art import effects
from game.engine import config
from game.engine.scene import Scene
from game.ui import theme
from game.ui.text import font, glow_text

DURATION = 2.6


class SplashScene(Scene):
    def on_enter(self, **kwargs) -> None:
        self.time = 0.0
        self.rng = random.Random(7)
        self.glitched = False
        self.mark = None
        raw = self.app.assets.ui("logo")
        if raw is not None:
            max_w, max_h = int(config.WIDTH * 0.72), int(config.HEIGHT * 0.46)
            scale = min(max_w / raw.get_width(), max_h / raw.get_height())
            self.mark = pygame.transform.smoothscale(
                raw, (max(1, round(raw.get_width() * scale)), max(1, round(raw.get_height() * scale))))
        self.logo = glow_text(config.STUDIO, font(26 if self.mark else 58, bold=True),
                              (230, 240, 255), config.MAGENTA, 6 if self.mark else 8)
        self.particles = effects.Particles((config.WIDTH, config.HEIGHT), 40, seed=3)

    def handle_event(self, event) -> None:
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN) and self.time > 0.15:
            self.done()

    def done(self) -> None:
        if not self.app.scenes.transitioning:
            self.app.scenes.switch("title")

    def update(self, dt: float) -> None:
        self.time += dt
        self.particles.update(dt)
        if self.time > 0.7 and not self.glitched:
            self.glitched = True
            self.app.audio.play("glitch")
        if self.time >= DURATION:
            self.done()

    def draw(self, surface) -> None:
        w, h = surface.get_size()
        self.particles.draw(surface)
        a = min(1.0, self.time / 0.5, max(0.0, (DURATION - self.time) / 0.4))
        if self.mark is not None:
            plate = self.mark.copy()
            plate.set_alpha(int(255 * a))
            plate_rect = plate.get_rect(center=(w // 2, int(h * 0.40)))
            surface.blit(plate, plate_rect)
            anchor = plate_rect.bottom + 28
        else:
            anchor = h // 2 - 20
        logo = self.logo.copy()
        logo.set_alpha(int(255 * a))
        r = logo.get_rect(center=(w // 2, anchor if self.mark is None else anchor + 8))
        surface.blit(logo, r)
        line_w = int(min(1.0, self.time / 0.9) * (420 if self.mark is not None else 520))
        pygame.draw.line(surface, config.CYAN, (w // 2 - line_w // 2, r.bottom + 6), (w // 2 + line_w // 2, r.bottom + 6), 2)
        sub = font(16, mono=True).render("presents", True, theme.color("dim"))
        sub.set_alpha(int(255 * a))
        surface.blit(sub, sub.get_rect(center=(w // 2, r.bottom + 32)))
        if 0.7 < self.time < 1.05 or 1.6 < self.time < 1.75:
            effects.glitch(surface, 0.6, self.rng)
        surface.blit(effects.vignette((w, h)), (0, 0))
