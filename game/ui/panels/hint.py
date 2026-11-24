"""Oracle's tiered hints. Each costs a few points; none ever blocks progress."""

from __future__ import annotations

import pygame

from game.systems.scoring import hint_cost
from game.ui import theme
from game.ui.dialogue import oracle_face
from game.ui.panels.base import Panel, draw_wrapped
from game.ui.text import font


class HintPanel(Panel):
    name = "hint"
    title = "Oracle: Hints"
    hotkey = None
    footer = "H / Enter reveal next hint   Esc close"

    def frame(self, surface) -> pygame.Rect:
        r = pygame.Rect(0, 0, 860, 420)
        r.center = (surface.get_width() // 2, surface.get_height() // 2 - 30)
        return r

    def subtitle(self) -> str:
        obj = self.state.current
        return f"Objective: {obj['title']}" if obj else "All objectives complete."

    def on_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_h, pygame.K_RETURN, pygame.K_KP_ENTER,
                                                          pygame.K_SPACE):
            if self.time < 0.15:
                return
            result = self.state.next_hint()
            self.app.audio.play("blip" if result else "error")

    def draw_body(self, surface, rect) -> None:
        face = self.app.assets.cast_portrait("oracle", 0, 110) or oracle_face(110, self.time)
        surface.blit(face, (rect.x, rect.y))
        text_r = pygame.Rect(rect.x + 130, rect.y, rect.width - 130, rect.height)
        obj = self.state.current
        if obj is None:
            draw_wrapped(surface, "You're done here. Head for the exit gate.", text_r, 19)
            return
        shown = self.state.shown_hints()
        total = len(obj.get("hints", []))
        y = text_r.y
        if not shown:
            y = draw_wrapped(surface, "Stuck? Each hint gets more specific. Using hints lowers your score a "
                             "little, and it never locks you out of anything.", text_r, 18, theme.color("dim")) + 12
        for i, h in enumerate(shown):
            surface.blit(font(14, bold=True).render(f"HINT {i + 1}", True, theme.accent), (text_r.x, y))
            y = draw_wrapped(surface, h, pygame.Rect(text_r.x, y + 20, text_r.width, 90), 18,
                             theme.color("amber") if i == 2 else theme.color("text")) + 12
        if len(shown) < total:
            cost = hint_cost(len(shown))
            t = font(16, bold=True).render(f"Press H for hint {len(shown) + 1} of {total}  (-{cost} pts)", True,
                                           theme.color("warn"))
            surface.blit(t, (text_r.x, rect.bottom - 30))
        else:
            surface.blit(font(16).render("That's every hint for this objective.", True, theme.color("dim")),
                         (text_r.x, rect.bottom - 30))
