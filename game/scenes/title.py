"""Title screen over the painted intro image, with the main menu as an overlay."""

from __future__ import annotations

import random

import pygame

from game.art import effects
from game.engine import config
from game.engine.scene import Scene
from game.ui import theme
from game.ui.text import font
from game.ui.widgets import Menu, draw_panel
from game.world.zone_data import debrief_index

ITEMS = ["New Game", "Continue", "Case Files", "Settings", "How to Play", "Quit"]


def spot_rect(fitted, values) -> pygame.Rect:
    x, y, w, h = values
    x0, y0 = fitted.point(x, y)
    x1, y1 = fitted.point(x + w, y + h)
    return pygame.Rect(x0, y0, x1 - x0, y1 - y0)


class TitleScene(Scene):
    def on_enter(self, **kwargs) -> None:
        self.time = 0.0
        self.bg = self.app.assets.background("intro", (config.WIDTH, config.HEIGHT), "cover")
        self.spots = self.app.assets.hotspots("intro")
        self.particles = effects.Particles((config.WIDTH, config.HEIGHT), 50, seed=11)
        self.menu_open = bool(kwargs.get("menu", False))
        self.rng = random.Random(5)
        self.glitch_t = 0.0
        self._build_menu()
        theme.set_accent(config.CYAN)
        self.app.audio.play_music("title")

    def _build_menu(self) -> None:
        has_save = self.app.saves.has_run()
        self.menu = Menu(ITEMS, [True, has_save, True, True, True, True], size=22, spacing=40)
        if has_save:
            self.menu.index = 1

    def handle_event(self, event) -> None:
        if not self.menu_open:
            if (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)) \
                    or (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
                self.menu_open = True
                self._build_menu()
                self.app.audio.play("confirm")
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.app.quit()
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.menu_open = False
            self.app.audio.play("back")
            return
        choice = self.menu.handle_event(event)
        if self.menu.moved:
            self.app.audio.play("move")
        if choice is None:
            return
        self.app.audio.play("confirm")
        item = ITEMS[choice]
        if item == "New Game":
            self.app.scenes.switch("cinematic")
        elif item == "Continue":
            if self.app.continue_run():
                self.app.scenes.switch("zone" if self.app.run.zone < debrief_index() else "debrief")
            else:
                self.app.audio.play("error")
                self._build_menu()
        elif item == "Case Files":
            self.app.scenes.switch("character_select", mode="custom")
        elif item == "Settings":
            self.app.scenes.push("settings")
        elif item == "How to Play":
            self.app.scenes.push("how_to_play")
        elif item == "Quit":
            self.app.quit()

    def update(self, dt: float) -> None:
        self.time += dt
        self.particles.update(dt)
        self.glitch_t -= dt
        if self.glitch_t < -6 - self.rng.random() * 4:
            self.glitch_t = 0.18

    def draw(self, surface) -> None:
        w, h = surface.get_size()
        surface.blit(self.bg.surface, (0, 0))
        self.particles.draw(surface)
        p = effects.pulse(self.time, 1.2)
        if self.bg.placeholder:
            logo = self.app.assets.logo(config.TITLE, config.SUBTITLE)
            max_w = int(w * 0.62)
            if logo.get_width() > max_w:
                scale = max_w / logo.get_width()
                logo = pygame.transform.smoothscale(
                    logo, (max_w, max(1, round(logo.get_height() * scale))))
            surface.blit(logo, logo.get_rect(center=(w // 2, int(h * 0.2))))
        else:
            sub = font(20, bold=True).render(config.SUBTITLE.upper(), True, config.MAGENTA)
            sub.set_alpha(int(170 + 85 * p))
            pos = self.bg.point(0.5, 0.222)
            surface.blit(sub, sub.get_rect(center=pos))
        if "press_start" in self.spots and not self.bg.placeholder:
            r = spot_rect(self.bg, self.spots["press_start"])
            glow = tuple(int(c * (0.5 + 0.5 * p)) for c in config.CYAN)
            effects.glow_rect(surface, r.inflate(10, 8), glow, width=2, radius=6, layers=4, alpha=int(60 + 80 * p))
        if not self.menu_open:
            text = font(26, bold=True).render("PRESS ENTER TO JACK IN", True, config.CYAN)
            text.set_alpha(int(110 + 145 * p))
            surface.blit(text, text.get_rect(center=(w // 2, int(h * 0.935))))
        else:
            veil = pygame.Surface((w, h), pygame.SRCALPHA)
            veil.fill((0, 0, 0, 130))
            surface.blit(veil, (0, 0))
            panel = pygame.Rect(0, 0, 460, 360)
            panel.center = (w // 2, int(h * 0.56))
            draw_panel(surface, panel, "Main Menu", accent=config.CYAN, alpha=235)
            self.menu.draw(surface, panel.centerx, panel.y + 58, accent=config.CYAN, width=380)
            best = self.app.saves.load_profile().get("best", {})
            if best:
                parts = [f"{c.title()}: {b['rank']} ({b['score']})" for c, b in best.items()]
                t = font(15, mono=True).render("BEST  " + "   ".join(parts), True, theme.color("amber"))
                surface.blit(t, t.get_rect(center=(w // 2, panel.bottom + 22)))
        foot = font(13, mono=True).render("F11 fullscreen   F8 mute   Offline training game. All names, "
                                          "IPs and domains are fictional.", True, theme.color("dim"))
        surface.blit(foot, foot.get_rect(bottomright=(w - 10, h - 6)))
        if self.glitch_t > 0:
            effects.glitch(surface, 0.35, self.rng)
