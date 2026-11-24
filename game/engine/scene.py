"""Scene base class and a stack-based scene manager.

Scenes are registered by name with a factory so they are created fresh on
entry. ``switch`` replaces the whole stack (with a fade); ``push``/``pop``
layer overlays such as pause or settings on top of the current scene.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pygame

if TYPE_CHECKING:
    from game.engine.app import App


class Scene:
    """Override any of the hooks. ``opaque`` overlays hide scenes beneath them."""

    opaque = True

    def __init__(self, app: "App"):
        self.app = app

    def on_enter(self, **kwargs) -> None:
        pass

    def on_exit(self) -> None:
        pass

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        pass


class SceneManager:
    FADE_TIME = 0.25

    def __init__(self, app: "App"):
        self.app = app
        self.factories: dict[str, Callable[["App"], Scene]] = {}
        self.stack: list[Scene] = []
        self._pending: tuple[str, dict] | None = None
        self._fade = 0.0
        self._fade_dir = 0

    def register(self, name: str, factory: Callable[["App"], Scene]) -> None:
        self.factories[name] = factory

    @property
    def current(self) -> Scene | None:
        return self.stack[-1] if self.stack else None

    def _make(self, name: str) -> Scene:
        if name not in self.factories:
            raise KeyError(f"unknown scene '{name}'")
        return self.factories[name](self.app)

    def switch(self, name: str, fade: bool = True, **kwargs) -> None:
        if not fade or not self.stack:
            self._replace(name, kwargs)
            return
        self._pending = (name, kwargs)
        self._fade_dir = 1

    def _replace(self, name: str, kwargs: dict) -> None:
        while self.stack:
            self.stack.pop().on_exit()
        scene = self._make(name)
        self.stack.append(scene)
        scene.on_enter(**kwargs)

    def push(self, name: str, **kwargs) -> None:
        scene = self._make(name)
        self.stack.append(scene)
        scene.on_enter(**kwargs)

    def pop(self) -> None:
        if len(self.stack) > 1:
            self.stack.pop().on_exit()

    @property
    def transitioning(self) -> bool:
        return self._fade_dir != 0

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.current and not self.transitioning:
            self.current.handle_event(event)

    def update(self, dt: float) -> None:
        if self._fade_dir:
            self._fade += self._fade_dir * dt / self.FADE_TIME
            if self._fade >= 1.0 and self._pending:
                self._fade = 1.0
                name, kwargs = self._pending
                self._pending = None
                self._replace(name, kwargs)
                self._fade_dir = -1
            elif self._fade <= 0.0:
                self._fade = 0.0
                self._fade_dir = 0
        if self.current:
            self.current.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        start = 0
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i].opaque:
                start = i
                break
        for scene in self.stack[start:]:
            scene.draw(surface)
        if self._fade > 0:
            veil = pygame.Surface(surface.get_size())
            veil.fill((0, 0, 0))
            veil.set_alpha(int(255 * min(1.0, self._fade)))
            surface.blit(veil, (0, 0))
