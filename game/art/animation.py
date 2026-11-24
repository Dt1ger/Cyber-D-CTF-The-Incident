from __future__ import annotations

from dataclasses import dataclass, field

import pygame

DIRECTIONS = ("down", "up", "left", "right")


@dataclass
class Animation:
    frames: list[pygame.Surface]
    fps: float = 8.0
    loop: bool = True

    def flipped(self) -> "Animation":
        return Animation([pygame.transform.flip(f, True, False) for f in self.frames],
                         self.fps, self.loop)


@dataclass
class SpriteSet:
    """All animations for one character at one gear tier and scale."""

    animations: dict[str, Animation]
    placeholder: bool = False
    size: tuple[int, int] = (0, 0)

    def get(self, name: str) -> Animation:
        if name in self.animations:
            return self.animations[name]
        base = name.split("_")[0]
        for fallback in (f"{base}_down", "idle_down"):
            if fallback in self.animations:
                return self.animations[fallback]
        return next(iter(self.animations.values()))


@dataclass
class AnimationPlayer:
    sprites: SpriteSet
    name: str = "idle_down"
    time: float = 0.0
    finished: bool = field(default=False, init=False)

    def play(self, name: str, restart: bool = False) -> None:
        if name != self.name or restart:
            self.name = name
            self.time = 0.0
            self.finished = False

    def update(self, dt: float) -> None:
        self.time += dt

    @property
    def frame_index(self) -> int:
        anim = self.sprites.get(self.name)
        n = len(anim.frames)
        i = int(self.time * anim.fps)
        if anim.loop:
            return i % n
        if i >= n:
            self.finished = True
        return min(i, n - 1)

    @property
    def frame(self) -> pygame.Surface:
        return self.sprites.get(self.name).frames[self.frame_index]
