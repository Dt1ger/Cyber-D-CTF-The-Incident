"""Oracle's hologram, host nodes, and Sasha's CTF caches, drawn procedurally."""

from __future__ import annotations

import math

import pygame

from game.ui import theme
from game.ui.dialogue import oracle_face
from game.ui.text import font
from game.world.tilemap import TILE


def tile_center(tile) -> tuple[float, float]:
    return tile[0] * TILE + TILE / 2, tile[1] * TILE + TILE / 2


class Oracle:
    def __init__(self, tile, portrait: pygame.Surface | None = None):
        self.x, self.y = tile_center(tile)
        self.time = 0.0
        self.has_news = True
        self.portrait = portrait

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, surface, cam) -> None:
        sx, sy = cam.to_screen(self.x, self.y)
        bob = math.sin(self.time * 2) * 4
        violet = (170, 110, 255)
        base = pygame.Surface((90, 30), pygame.SRCALPHA)
        pygame.draw.ellipse(base, (*violet, 70), base.get_rect())
        pygame.draw.ellipse(base, (*violet, 160), base.get_rect(), 2)
        surface.blit(base, base.get_rect(center=(sx, sy + 4)))
        if self.portrait is not None:
            figure = self.portrait
            surface.blit(figure, figure.get_rect(midbottom=(sx, sy + 6 + bob)))
        else:
            beam = pygame.Surface((56, 110), pygame.SRCALPHA)
            for i in range(110):
                beam.fill((0, 200, 255, int(50 * i / 110)), (0, i, 56, 1))
            surface.blit(beam, beam.get_rect(midbottom=(sx, sy + 4)))
            face = oracle_face(78, self.time)
            surface.blit(face, face.get_rect(midbottom=(sx, sy - 6 + bob)))
        if self.has_news:
            mark_y = sy - (self.portrait.get_height() if self.portrait is not None else 92) - 6 + bob
            t = font(20, bold=True).render("!", True, theme.color("amber"))
            surface.blit(t, t.get_rect(midbottom=(sx, mark_y)))


class NodeView:
    def __init__(self, node: dict, tile):
        self.node = node
        self.id = node["id"]
        self.x, self.y = tile_center(tile)
        self.time = 0.0
        self.investigated = False
        self.done = False

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, surface, cam, accent, corruption: float, label: bool = True) -> None:
        sx, sy = cam.to_screen(self.x, self.y)
        pulse = 0.5 + 0.5 * math.sin(self.time * 3 + self.x)
        glow_col = theme.color("corrupt") if corruption > 0.02 else accent
        ring = pygame.Surface((110, 44), pygame.SRCALPHA)
        a = int(60 + (90 * pulse if not self.done else 20))
        pygame.draw.ellipse(ring, (*glow_col, a), ring.get_rect())
        pygame.draw.ellipse(ring, (*glow_col, 200), ring.get_rect(), 2)
        surface.blit(ring, ring.get_rect(center=(sx, sy + 12)))
        body = pygame.Rect(0, 0, 40, 78)
        body.midbottom = (sx, sy + 14)
        pygame.draw.rect(surface, (14, 20, 36), body, border_radius=4)
        pygame.draw.rect(surface, glow_col, body, 2, border_radius=4)
        for i in range(6):
            y = body.y + 8 + i * 11
            pygame.draw.line(surface, (40, 54, 80), (body.x + 6, y), (body.right - 6, y), 1)
            on = (int(self.time * 4 + i * 1.7 + self.x) % 3) != 0
            surface.fill(glow_col if on else (30, 40, 60), (body.right - 11, y - 3, 4, 4))
        if corruption > 0.02:
            n = int(3 + corruption * 8)
            for i in range(n):
                ang = self.time * 1.5 + i * 2.1
                r = 26 + 8 * math.sin(self.time * 2 + i)
                px, py = sx + math.cos(ang) * r, sy - 30 + math.sin(ang) * r * 0.7
                surface.fill(theme.color("corrupt"), (int(px), int(py), 3, 3))
            crack = pygame.Surface(body.size, pygame.SRCALPHA)
            crack.fill((*theme.color("corrupt"), int(90 * corruption)))
            surface.blit(crack, body)
        if label:
            col = theme.color("dim") if self.done else theme.color("text")
            t = font(15, mono=True, bold=True).render(self.node["host"], True, col)
            bg = pygame.Rect(0, 0, t.get_width() + 10, t.get_height() + 4)
            bg.midbottom = (sx, body.y - 6)
            pygame.draw.rect(surface, (6, 10, 20), bg, border_radius=3)
            pygame.draw.rect(surface, glow_col, bg, 1, border_radius=3)
            surface.blit(t, t.get_rect(center=bg.center))
            if not self.investigated:
                mark = font(18, bold=True).render("?", True, theme.color("amber"))
                surface.blit(mark, mark.get_rect(midbottom=(bg.right + 10, bg.bottom)))
            elif self.done:
                pygame.draw.lines(surface, theme.color("ok"), False,
                                  [(bg.right + 4, bg.centery), (bg.right + 8, bg.centery + 4),
                                   (bg.right + 15, bg.centery - 4)], 2)


class CacheView:
    def __init__(self, tile):
        self.x, self.y = tile_center(tile)
        self.time = 0.0
        self.solved = False

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, surface, cam) -> None:
        sx, sy = cam.to_screen(self.x, self.y)
        col = theme.color("dim") if self.solved else (57, 255, 20)
        spin = self.time * 2
        pts = []
        for i in range(4):
            ang = spin + i * math.pi / 2
            pts.append((sx + math.cos(ang) * 14, sy - 16 + math.sin(ang) * 14 * 0.6))
        pygame.draw.polygon(surface, col, pts, 2)
        t = font(13, mono=True, bold=True).render("CTF", True, col)
        surface.blit(t, t.get_rect(center=(sx, sy - 16)))
