"""The selected analyst: 4-direction movement, wall collision, click-to-move paths."""

from __future__ import annotations

import math

import pygame

from game.art.animation import AnimationPlayer, SpriteSet
from game.engine.pathfinding import astar, nearest_passable
from game.world.tilemap import TILE, TileMap

SPEED = 240.0
FOOT_W, FOOT_H = 22, 12


class Player:
    def __init__(self, sprites: SpriteSet, tile: tuple[int, int]):
        self.sprites = sprites
        self.anim = AnimationPlayer(sprites, "idle_down")
        self.x = tile[0] * TILE + TILE / 2
        self.y = tile[1] * TILE + TILE / 2
        self.facing = "down"
        self.path: list[tuple[int, int]] = []
        self.interacting = 0.0
        self.moving = False

    @property
    def tile(self) -> tuple[int, int]:
        return int(self.x // TILE), int(self.y // TILE)

    def set_sprites(self, sprites: SpriteSet) -> None:
        self.sprites = sprites
        self.anim = AnimationPlayer(sprites, self.anim.name)

    def _free(self, x: float, y: float, tmap: TileMap) -> bool:
        for px in (x - FOOT_W / 2, x + FOOT_W / 2):
            for py in (y - FOOT_H, y):
                if not tmap.passable(int(px // TILE), int(py // TILE)):
                    return False
        return True

    def go_to(self, wx: float, wy: float, tmap: TileMap) -> bool:
        goal = nearest_passable((int(wx // TILE), int(wy // TILE)), tmap.passable, 2)
        if goal is None:
            return False
        self.path = astar(self.tile, goal, tmap.passable)
        return bool(self.path)

    def interact(self) -> None:
        self.interacting = 1.0
        self.path = []
        self.anim.play("interact", restart=True)

    def update(self, dt: float, axis: tuple[int, int], tmap: TileMap) -> None:
        dx, dy = axis
        if dx or dy:
            self.path = []
            self.interacting = 0.0
        elif self.path:
            tx, ty = self.path[0]
            gx, gy = tx * TILE + TILE / 2, ty * TILE + TILE / 2
            vx, vy = gx - self.x, gy - self.y
            dist = math.hypot(vx, vy)
            if dist < 6:
                self.path.pop(0)
            else:
                dx, dy = vx / dist, vy / dist
        if self.interacting > 0:
            self.interacting -= dt
            self.anim.update(dt)
            if self.anim.finished or self.interacting <= 0:
                self.interacting = 0.0
                self.anim.play(f"idle_{self.facing}")
            return
        length = math.hypot(dx, dy)
        self.moving = length > 0
        if self.moving:
            dx, dy = dx / length, dy / length
            step = SPEED * dt
            nx = self.x + dx * step
            if self._free(nx, self.y, tmap):
                self.x = nx
            ny = self.y + dy * step
            if self._free(self.x, ny, tmap):
                self.y = ny
            if abs(dx) > abs(dy) + 0.1:
                self.facing = "right" if dx > 0 else "left"
            else:
                self.facing = "down" if dy > 0 else "up"
            self.anim.play(f"walk_{self.facing}")
        else:
            self.anim.play(f"idle_{self.facing}")
        self.anim.update(dt)

    def draw(self, surface, cam) -> None:
        frame = self.anim.frame
        sx, sy = cam.to_screen(self.x, self.y)
        pygame.draw.ellipse(surface, (0, 0, 0), (sx - 20, sy - 6, 40, 12))
        surface.blit(frame, frame.get_rect(midbottom=(sx, sy + 4)))
