"""Developer screen: every character tier and animation, real art vs placeholders."""

from __future__ import annotations

import pygame

from game.art.animation import AnimationPlayer
from game.art.loader import Assets
from game.engine import config
from game.engine.scene import Scene
from game.ui.text import font

ANIMS = ["idle_down", "walk_down", "walk_up", "walk_left", "walk_right", "interact"]
TIERS = ["lvl1", "lvl10", "lvl20"]
PREVIEW_SCALE = 0.75


class GalleryScene(Scene):
    def on_enter(self, **kwargs) -> None:
        self.real = self.app.assets
        self.fake = Assets(config.ASSETS_DIR, use_files=False)
        self.show_placeholders = bool(kwargs.get("placeholders", False))
        self.tier = 0
        self.anim = 1
        self._portraits: dict[tuple, pygame.Surface] = {}
        self._build()

    @property
    def assets(self) -> Assets:
        return self.fake if self.show_placeholders else self.real

    def _build(self) -> None:
        tier = TIERS[self.tier]
        self.players = []
        for c in self.app.characters:
            big = self.assets.sprites(c.id, tier, PREVIEW_SCALE, c.palette)
            small = self.assets.sprites(c.id, tier, None, c.palette)
            row = [AnimationPlayer(small, f"walk_{d}") for d in ("down", "up", "left", "right")]
            self.players.append((c, AnimationPlayer(big, ANIMS[self.anim]), row))

    def _portrait(self, char) -> pygame.Surface:
        key = (char.id, TIERS[self.tier], self.show_placeholders)
        if key not in self._portraits:
            src = self.assets.portrait(char.id, TIERS[self.tier], char.palette)
            h = 330
            w = round(src.get_width() * h / src.get_height())
            self._portraits[key] = pygame.transform.smoothscale(src, (w, h))
        return self._portraits[key]

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.app.quit()
        elif event.key == pygame.K_TAB:
            self.anim = (self.anim + 1) % len(ANIMS)
            for _, big, _ in self.players:
                big.play(ANIMS[self.anim], restart=True)
        elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.tier = event.key - pygame.K_1
            self._build()
        elif event.key == pygame.K_p:
            self.show_placeholders = not self.show_placeholders
            self._build()

    def update(self, dt: float) -> None:
        for _, big, row in self.players:
            big.update(dt)
            if big.finished:
                big.play(big.name, restart=True)
            for p in row:
                p.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        bg = self.assets.background("intro", surface.get_size())
        surface.blit(bg.surface, (0, 0))
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((4, 6, 14, 200))
        surface.blit(veil, (0, 0))

        logo = self.assets.logo(config.TITLE, config.SUBTITLE)
        if logo.get_width() > 520:
            logo = pygame.transform.smoothscale(
                logo, (520, round(logo.get_height() * 520 / logo.get_width())))
        surface.blit(logo, logo.get_rect(midtop=(surface.get_width() // 2, 8)))

        mode = "YOUR ART" if self.assets.use_files else "PLACEHOLDERS"
        info = (f"ASSET GALLERY  |  {mode}  |  tier {TIERS[self.tier]}  |  "
                f"animation: {ANIMS[self.anim]}")
        keys = "Tab: next animation   1/2/3: gear tier   P: art / placeholders   Esc: quit"
        f = font(18, mono=True)
        surface.blit(f.render(info, True, config.TEXT), (24, 124))
        surface.blit(f.render(keys, True, config.DIM), (24, 148))

        col_w = surface.get_width() // 2
        for i, (char, big, row) in enumerate(self.players):
            x0 = i * col_w
            pygame.draw.rect(surface, char.accent, (x0 + 16, 180, col_w - 32, 524), 2,
                             border_radius=10)
            surface.blit(font(28, bold=True).render(char.name.upper(), True, char.accent),
                         (x0 + 32, 190))
            tag = "placeholder" if big.sprites.placeholder else "sprite sheet"
            surface.blit(font(16, mono=True).render(f"{char.role}  [{tag}]", True, config.DIM),
                         (x0 + 32, 226))

            portrait = self._portrait(char)
            surface.blit(portrait, (x0 + 28, 256))

            frame = big.frame
            stage = pygame.Rect(x0 + 260, 256, col_w - 290, 300)
            pygame.draw.rect(surface, (12, 16, 30), stage, border_radius=8)
            surface.blit(frame, frame.get_rect(midbottom=(stage.centerx, stage.bottom - 10)))

            strip_y = 690
            step = (col_w - 290) // 4
            for j, p in enumerate(row):
                fr = p.frame
                surface.blit(fr, fr.get_rect(midbottom=(x0 + 260 + step * j + step // 2, strip_y)))
