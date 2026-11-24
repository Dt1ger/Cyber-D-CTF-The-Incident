"""Incident response actions with tradeoffs. Order matters."""

from __future__ import annotations

import pygame

from game.ui import theme
from game.ui.panels.base import Panel, draw_wrapped
from game.ui.text import font
from game.ui.widgets import ListView


class RespondPanel(Panel):
    name = "respond"
    title = "Incident Response"
    hotkey = pygame.K_r
    footer = "Up/Down select   Enter take action (press twice to confirm)   Esc close"

    def __init__(self, scene):
        super().__init__(scene)
        self.list = ListView(size=16)
        self.armed: str | None = None
        self.last: tuple[str, str] | None = None
        self._items()

    def subtitle(self) -> str:
        req = self.state.required_actions()
        done = sum(1 for a in req if a in self.state.done_actions)
        return (f"Required containment steps taken: {done}/{len(req)}.  Think about ORDER: "
                "preserve, contain, eradicate, recover.")

    def _items(self) -> None:
        items = []
        for a in self.state.zone.responses:
            if a["id"] in self.state.done_actions:
                items.append((f"[DONE] {a['label']}", theme.color("ok")))
            elif a["id"] in self.state.used_actions:
                items.append((f"[USED] {a['label']}", theme.color("dim")))
            else:
                items.append((f"       {a['label']}", theme.color("text")))
        self.list.set_items(items)

    def on_event(self, event) -> None:
        action = self.list.handle_event(event)
        if action == "move":
            self.armed = None
            self.app.audio.play("move")
        elif action == "activate":
            a = self.state.zone.responses[self.list.index]
            if a["id"] in self.state.used_actions:
                self.last = ("Already done.", "dim")
                return
            if self.armed != a["id"]:
                self.armed = a["id"]
                self.app.audio.play("blip")
                return
            self.armed = None
            outcome, text = self.state.respond(a["id"])
            style = {"good": "ok", "premature": "warn", "bad": "bad"}.get(outcome, "dim")
            self.last = (text, style)
            self.app.audio.play({"good": "success", "premature": "alarm", "bad": "error"}.get(outcome, "blip"))
            self._items()

    def draw_body(self, surface, rect) -> None:
        if not self.state.zone.responses:
            draw_wrapped(surface, "There's nothing to contain here. This room is for learning.",
                         rect, 18, theme.color("dim"))
            return
        left = pygame.Rect(rect.x, rect.y, 560, rect.height)
        right = pygame.Rect(left.right + 22, rect.y, rect.right - left.right - 22, rect.height)
        self.list.draw(surface, pygame.Rect(left.x, left.y, left.width, left.height - 150))
        log_r = pygame.Rect(left.x, left.bottom - 140, left.width, 140)
        surface.blit(font(14, bold=True).render("ACTION LOG", True, theme.color("dim")), log_r.topleft)
        y = log_r.y + 20
        for aid, outcome, text in self.state.action_log[-4:]:
            a = self.state.zone.response(aid)
            col = theme.style_color({"good": "ok", "premature": "warn", "bad": "bad"}.get(outcome, "dim"))
            surface.blit(font(14, mono=True).render(f"{outcome.upper():<9} {a['label'][:58]}", True, col), (log_r.x, y))
            y += 19

        a = self.state.zone.responses[self.list.index]
        pygame.draw.line(surface, theme.color("panel_edge"), (right.x - 11, rect.y), (right.x - 11, rect.bottom))
        y = draw_wrapped(surface, a["label"], pygame.Rect(right.x, right.y, right.width, 110), 20, theme.color("amber")) + 8
        y = draw_wrapped(surface, a.get("description", ""), pygame.Rect(right.x, y, right.width, 80), 16) + 10
        surface.blit(font(14, bold=True).render("TRADEOFF", True, theme.color("warn")), (right.x, y))
        y = draw_wrapped(surface, a.get("tradeoff", ""), pygame.Rect(right.x, y + 20, right.width, 80), 16) + 14
        if self.armed == a["id"]:
            t = font(18, bold=True).render("Press ENTER again to commit this action.", True, theme.accent)
            surface.blit(t, (right.x, y))
            y += 32
        if self.last:
            text, style = self.last
            surface.blit(font(14, bold=True).render("RESULT", True, theme.style_color(style)), (right.x, y))
            draw_wrapped(surface, text, pygame.Rect(right.x, y + 20, right.width, right.bottom - y - 20), 16,
                         theme.style_color(style))
