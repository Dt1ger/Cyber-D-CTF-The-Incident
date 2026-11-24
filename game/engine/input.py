"""Keyboard actions so every screen can be played without a mouse."""

from __future__ import annotations

import pygame

DEFAULT_BINDINGS: dict[str, tuple[int, ...]] = {
    "up": (pygame.K_UP, pygame.K_w),
    "down": (pygame.K_DOWN, pygame.K_s),
    "left": (pygame.K_LEFT, pygame.K_a),
    "right": (pygame.K_RIGHT, pygame.K_d),
    "confirm": (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE),
    "back": (pygame.K_ESCAPE, pygame.K_BACKSPACE),
    "interact": (pygame.K_e,),
    "pause": (pygame.K_p, pygame.K_ESCAPE),
    "terminal": (pygame.K_t,),
    "journal": (pygame.K_j,),
    "matrix": (pygame.K_m,),
    "hint": (pygame.K_h,),
    "next": (pygame.K_TAB,),
}


class Input:
    def __init__(self, bindings: dict[str, tuple[int, ...]] | None = None):
        self.bindings = dict(bindings or DEFAULT_BINDINGS)
        self._pressed: set[str] = set()

    def begin_frame(self) -> None:
        self._pressed.clear()

    def process(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self._pressed.update(self.actions_for(event.key))

    def actions_for(self, key: int) -> list[str]:
        return [a for a, keys in self.bindings.items() if key in keys]

    def is_action(self, event: pygame.event.Event, action: str) -> bool:
        return event.type == pygame.KEYDOWN and event.key in self.bindings.get(action, ())

    def pressed(self, action: str) -> bool:
        return action in self._pressed

    def held(self, action: str) -> bool:
        keys = pygame.key.get_pressed()
        return any(keys[k] for k in self.bindings.get(action, ()))

    def axis(self) -> tuple[int, int]:
        x = int(self.held("right")) - int(self.held("left"))
        y = int(self.held("down")) - int(self.held("up"))
        return x, y
