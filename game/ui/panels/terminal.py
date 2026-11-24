"""The Hunt Terminal panel."""

from __future__ import annotations

import pygame

from game.ui import theme
from game.ui.panels.base import Panel, draw_wrapped
from game.ui.text import font
from game.ui.widgets import ScrollText, TextInput


class TerminalPanel(Panel):
    name = "terminal"
    title = "Hunt Terminal"
    footer = "Enter run   Up/Down history   PgUp/PgDn scroll   Esc close"

    def __init__(self, scene):
        super().__init__(scene)
        self.session = scene.terminal
        self.out = ScrollText(16)
        self.out.set_lines(self.session.lines, follow=True)
        self.input = TextInput("hunt> ", 18)
        pygame.key.start_text_input()

    def close(self) -> None:
        super().close()

    def subtitle(self) -> str:
        return "Query the zone's telemetry. Type 'help' for the language, 'tables' for data sources."

    def on_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.out.handle_event(event)
            return
        if event.type == pygame.MOUSEWHEEL:
            self.out.handle_event(event, keys=False)
            return
        if event.type == pygame.TEXTINPUT and self.time == 0.0:
            return
        line = self.input.handle_event(event)
        if line is not None:
            out = self.session.execute(line)
            self.out.set_lines(self.session.lines, follow=True)
            styles = {s for _, s in out}
            if "ok" in styles:
                self.app.audio.play("success")
            elif "bad" in styles:
                self.app.audio.play("error")
            elif line.strip():
                self.app.audio.play("query")

    def update(self, dt: float) -> None:
        super().update(dt)
        self.input.update(dt)

    def draw_body(self, surface, rect) -> None:
        side_w = 300
        main = pygame.Rect(rect.x, rect.y, rect.width - side_w - 18, rect.height)
        side = pygame.Rect(main.right + 18, rect.y, side_w, rect.height)
        out_rect = pygame.Rect(main.x, main.y, main.width, main.height - 46)
        pygame.draw.rect(surface, (4, 7, 14), out_rect)
        self.out.draw(surface, out_rect.inflate(-8, -8))
        self.input.draw(surface, pygame.Rect(main.x, main.bottom - 38, main.width, 36))

        pygame.draw.line(surface, theme.color("panel_edge"), (side.x - 9, side.y), (side.x - 9, side.bottom))
        y = side.y
        f = font(16, bold=True)
        surface.blit(f.render("TABLES", True, theme.accent), (side.x, y))
        y += 24
        fm = font(15, mono=True)
        for t in self.state.zone.tables.values():
            surface.blit(fm.render(f"{t.name:<7}{len(t.rows):>4} rows", True, theme.color("text")), (side.x, y))
            y += 20
        y += 10
        obj = self.state.current
        if obj and obj["type"] in ("query", "decode", "flag"):
            surface.blit(f.render("CURRENT OBJECTIVE", True, theme.accent), (side.x, y))
            y = draw_wrapped(surface, obj["title"], pygame.Rect(side.x, y + 24, side_w, 60), 16,
                             theme.color("amber")) + 4
            y = draw_wrapped(surface, obj.get("desc", ""), pygame.Rect(side.x, y, side_w, 140), 15,
                             theme.color("text")) + 10
        if self.state.flag_sense and self.state.zone.pivot_tip:
            surface.blit(f.render("FLAG SENSE", True, (57, 255, 20)), (side.x, y))
            y = draw_wrapped(surface, self.state.zone.pivot_tip, pygame.Rect(side.x, y + 24, side_w, 120),
                             15, theme.color("text")) + 10
        cheat = ['search <table> where f="v"', 'f~"part"  f!="v"  n>100', 'a and b   a or b   not a',
                 'f in ("x", "y")', '| count by f   | head 10', '| fields a, b  | sort time',
                 'decode base64 <row-id>']
        surface.blit(f.render("CHEAT SHEET", True, theme.accent), (side.x, max(y, side.bottom - 190)))
        y = max(y, side.bottom - 190) + 24
        for c in cheat:
            surface.blit(font(14, mono=True).render(c, True, theme.color("dim")), (side.x, y))
            y += 19
