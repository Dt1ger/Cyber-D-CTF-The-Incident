"""Timeline: drag (or Space + arrows) events into the order they happened."""

from __future__ import annotations

import random

import pygame

from game.ui import theme
from game.ui.panels.base import Panel, draw_wrapped
from game.ui.text import font


class TimelinePanel(Panel):
    name = "timeline"
    title = "Timeline"
    hotkey = pygame.K_l
    footer = "Up/Down select   Space grab/drop (then Up/Down to move)   Drag with mouse   C check   Esc close"

    def __init__(self, scene):
        super().__init__(scene)
        self.obj = self.state.active_of("timeline")
        self.index = 0
        self.grabbed = False
        self.drag: int | None = None
        self.feedback: tuple[str, str] | None = None
        self.rows: list[pygame.Rect] = []
        if self.obj:
            orders = scene.timeline_orders
            if self.obj["id"] not in orders:
                ids = [e["id"] for e in self.obj["events"]]
                rng = random.Random(len(ids) * 97 + self.state.zone.index)
                shuffled = ids[:]
                while shuffled == ids:
                    rng.shuffle(shuffled)
                orders[self.obj["id"]] = shuffled
            self.order = orders[self.obj["id"]]
            self.labels = {e["id"]: e["label"] for e in self.obj["events"]}

    def subtitle(self) -> str:
        if not self.obj:
            return "No timeline to rebuild right now."
        return self.obj.get("desc", "Put the events in the order they happened, earliest at the top.")

    def _move(self, d: int) -> None:
        j = self.index + d
        if 0 <= j < len(self.order):
            self.order[self.index], self.order[j] = self.order[j], self.order[self.index]
            self.index = j
            self.app.audio.play("move")

    def _check(self) -> None:
        ok, right, msg = self.state.check_timeline(self.obj["id"], list(self.order))
        self.feedback = (msg, "ok" if ok else "warn")
        self.app.audio.play("success" if ok else "error")
        if ok:
            self.obj = None

    def on_event(self, event) -> None:
        if not self.obj:
            return
        if event.type == pygame.KEYDOWN:
            k = event.key
            if k in (pygame.K_UP, pygame.K_w):
                if self.grabbed:
                    self._move(-1)
                else:
                    self.index = max(0, self.index - 1)
            elif k in (pygame.K_DOWN, pygame.K_s):
                if self.grabbed:
                    self._move(1)
                else:
                    self.index = min(len(self.order) - 1, self.index + 1)
            elif k == pygame.K_SPACE:
                self.grabbed = not self.grabbed
                self.app.audio.play("blip")
            elif k in (pygame.K_c, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.grabbed = False
                self._check()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in enumerate(self.rows):
                if r.collidepoint(event.pos):
                    self.index = i
                    self.drag = i
        elif event.type == pygame.MOUSEMOTION and self.drag is not None:
            for i, r in enumerate(self.rows):
                if r.collidepoint(event.pos) and i != self.index:
                    self._move(1 if i > self.index else -1)
                    self.drag = self.index
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.drag = None
            if getattr(self, "check_rect", None) and self.check_rect.collidepoint(event.pos):
                self._check()

    def draw_body(self, surface, rect) -> None:
        if not self.obj:
            msg = self.feedback[0] if self.feedback else ("Timeline objectives appear when there's an attack "
                                                          "sequence to rebuild.")
            draw_wrapped(surface, msg, rect, 18, theme.style_color(self.feedback[1]) if self.feedback else
                         theme.color("dim"))
            return
        f = font(18)
        self.rows = []
        top = rect.y + 10
        h = min(56, (rect.height - 120) // max(1, len(self.order)))
        line_x = rect.x + 40
        pygame.draw.line(surface, theme.color("panel_edge"), (line_x, top), (line_x, top + h * len(self.order)), 2)
        surface.blit(font(13, mono=True).render("EARLIEST", True, theme.color("dim")), (rect.x, top - 4))
        for i, eid in enumerate(self.order):
            r = pygame.Rect(line_x + 30, top + i * h, rect.width - 120, h - 8)
            self.rows.append(r)
            sel = i == self.index
            bg = pygame.Surface(r.size, pygame.SRCALPHA)
            bg.fill((*theme.accent, 70 if sel and self.grabbed else 40 if sel else 14))
            surface.blit(bg, r)
            pygame.draw.rect(surface, theme.accent if sel else theme.color("panel_edge"), r, 2 if sel else 1,
                             border_radius=4)
            pygame.draw.circle(surface, theme.accent if sel else theme.color("dim"), (line_x, r.centery), 7)
            surface.blit(font(15, mono=True).render(f"{i + 1}", True, theme.color("dim")), (r.x + 10, r.centery - 9))
            t = f.render(self.labels[eid], True, theme.color("text"))
            surface.blit(t, (r.x + 40, r.centery - t.get_height() // 2))
            if sel and self.grabbed:
                surface.blit(font(14, bold=True).render("MOVING", True, theme.color("amber")),
                             (r.right - 80, r.centery - 9))
        self.check_rect = pygame.Rect(rect.right - 220, rect.bottom - 44, 200, 36)
        pygame.draw.rect(surface, theme.accent, self.check_rect, 2, border_radius=4)
        t = font(17, bold=True).render("CHECK ORDER [C]", True, theme.accent)
        surface.blit(t, t.get_rect(center=self.check_rect.center))
        if self.feedback:
            msg, style = self.feedback
            draw_wrapped(surface, msg, pygame.Rect(rect.x, rect.bottom - 40, rect.width - 240, 40), 17,
                         theme.style_color(style))
