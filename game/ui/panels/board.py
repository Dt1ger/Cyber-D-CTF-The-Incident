"""Hypothesis Board: pin evidence cards, then choose the hypothesis they support."""

from __future__ import annotations

import pygame

from game.ui import theme
from game.ui.panels.base import Panel, draw_wrapped
from game.ui.panels.journal import journal_entries
from game.ui.text import font
from game.ui.widgets import ListView, wrap


class BoardPanel(Panel):
    name = "board"
    title = "Hypothesis Board"
    hotkey = pygame.K_b
    footer = "Tab switch side   Space pin/unpin   Enter choose   Esc close"

    def __init__(self, scene):
        super().__init__(scene)
        self.cards = ListView(size=15)
        self.options = ListView(size=17)
        self.focus = "options"
        self.feedback: tuple[str, str] | None = None
        self.obj = None
        self._load()

    def _load(self) -> None:
        self.obj = self.state.active_of("choice")
        entries = [e for e in journal_entries(self.app.run)]
        entries.sort(key=lambda e: (e[1] != self.state.zone.index, e[2].get("time", "")))
        self.entries = entries
        self._cards()
        if self.obj:
            self.options.set_items([f"{chr(65 + i)}. {o['text']}" for i, o in enumerate(self.obj["options"])])
            if self.obj.get("pins"):
                self.focus = "cards"
        else:
            self.options.set_items([])

    def _cards(self) -> None:
        items = []
        for eid, zone, ev in self.entries:
            pinned = eid in self.state.pins
            items.append((("[PIN] " if pinned else "      ") + ev.get("title", eid),
                          theme.accent if pinned else theme.color("text")))
        self.cards.set_items(items)

    def subtitle(self) -> str:
        if not self.obj:
            return "No open question right now. Pin cards to keep your theory in view."
        need = len(self.obj.get("pins", []))
        return (f"Pin the {need} cards that prove it, then choose." if need else "Choose the best answer.")

    def on_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            self.focus = "cards" if self.focus == "options" else "options"
            self.app.audio.play("move")
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and self.focus == "cards":
            self._toggle_pin()
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.cards.rect.collidepoint(event.pos):
                self.focus = "cards"
            elif self.options.rect.collidepoint(event.pos):
                self.focus = "options"
        lst = self.cards if self.focus == "cards" else self.options
        action = lst.handle_event(event)
        if action == "move":
            self.app.audio.play("move")
        elif action == "activate":
            if self.focus == "cards":
                self._toggle_pin()
            else:
                self._choose()

    def _toggle_pin(self) -> None:
        if not self.entries:
            return
        eid = self.entries[self.cards.index][0]
        pinned = self.state.toggle_pin(eid)
        self.app.audio.play("blip" if pinned else "back")
        self._cards()

    def _choose(self) -> None:
        if not self.obj:
            return
        opt = self.obj["options"][self.options.index]
        ok, msg = self.state.submit_choice(self.obj["id"], opt["id"])
        self.feedback = (msg, "ok" if ok else "bad")
        self.app.audio.play("success" if ok else "error")
        if ok:
            self._load()

    def draw_body(self, surface, rect) -> None:
        left = pygame.Rect(rect.x, rect.y, 430, rect.height)
        right = pygame.Rect(left.right + 22, rect.y, rect.right - left.right - 22, rect.height)
        f = font(16, bold=True)
        surface.blit(f.render("EVIDENCE CARDS", True, theme.accent if self.focus == "cards" else theme.color("dim")),
                     left.topleft)
        self.cards.draw(surface, pygame.Rect(left.x, left.y + 26, left.width, left.height - 26),
                        focused=self.focus == "cards")
        pygame.draw.line(surface, theme.color("panel_edge"), (right.x - 11, rect.y), (right.x - 11, rect.bottom))
        y = right.y
        if self.obj:
            surface.blit(f.render("QUESTION", True, theme.accent if self.focus == "options" else theme.color("dim")),
                         (right.x, y))
            y = draw_wrapped(surface, self.obj["prompt"], pygame.Rect(right.x, y + 26, right.width, 90), 21,
                             theme.color("amber")) + 10
            fnt = font(17)
            opt_h = 0
            for o in self.obj["options"]:
                opt_h += (len(wrap(o["text"], fnt, right.width - 30)) * fnt.get_linesize()) + 10
            self.options.size = 17
            self._draw_options(surface, pygame.Rect(right.x, y, right.width, min(opt_h + 10, right.bottom - y - 90)))
            y = right.bottom - 84
        else:
            draw_wrapped(surface, "Nothing to decide yet. Keep investigating; the board lights up when "
                         "Oracle has a question for you.", pygame.Rect(right.x, y, right.width, 120), 18,
                         theme.color("dim"))
            y = right.bottom - 84
        pinned = [self.entries[i][2].get("title", "") for i in range(len(self.entries))
                  if self.entries[i][0] in self.state.pins]
        surface.blit(font(14, bold=True).render(f"PINNED ({len(pinned)})", True, theme.color("dim")), (right.x, y))
        draw_wrapped(surface, "  |  ".join(pinned) or "none", pygame.Rect(right.x, y + 18, right.width, 30), 14,
                     theme.color("text"))
        if self.feedback:
            msg, style = self.feedback
            draw_wrapped(surface, msg, pygame.Rect(right.x, right.bottom - 40, right.width, 40), 16,
                         theme.style_color(style))

    def _draw_options(self, surface, rect) -> None:
        self.options.rect = rect
        fnt = font(17)
        y = rect.y
        self.option_rects = []
        for i, o in enumerate(self.obj["options"]):
            lines = wrap(f"{chr(65 + i)}.  {o['text']}", fnt, rect.width - 30)
            h = len(lines) * fnt.get_linesize() + 8
            r = pygame.Rect(rect.x, y, rect.width, h)
            if i == self.options.index:
                bg = pygame.Surface(r.size, pygame.SRCALPHA)
                bg.fill((*theme.accent, 55 if self.focus == "options" else 22))
                surface.blit(bg, r)
                pygame.draw.rect(surface, theme.accent, (r.x, r.y, 3, r.height))
            for j, line in enumerate(lines):
                surface.blit(fnt.render(line, True, theme.color("text")), (r.x + 12, r.y + 4 + j * fnt.get_linesize()))
            self.option_rects.append(r)
            y += h + 4
        self.options.row_h = 0

    def handle_event(self, event) -> None:
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.obj
                and getattr(self, "option_rects", None)):
            for i, r in enumerate(self.option_rects):
                if r.collidepoint(event.pos):
                    self.focus = "options"
                    if self.options.index == i:
                        self._choose()
                    else:
                        self.options.index = i
                    return
        super().handle_event(event)
