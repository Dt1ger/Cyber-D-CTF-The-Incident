"""Evidence Journal: every collected artifact, searchable, in event-time order."""

from __future__ import annotations

import pygame

from game.ui import theme
from game.ui.panels.base import Panel, evidence_lines
from game.ui.text import font
from game.ui.widgets import ListView, ScrollText, TextInput
from game.world.zone_data import evidence_index


def journal_entries(run) -> list[tuple[str, int, dict]]:
    index = evidence_index()
    out = []
    for entry in run.journal:
        eid = entry["id"]
        if eid in index:
            zone, ev = index[eid]
            out.append((eid, zone, ev))
    out.sort(key=lambda e: (e[2].get("time", ""), e[0]))
    return out


class JournalPanel(Panel):
    name = "journal"
    title = "Evidence Journal"
    hotkey = None
    footer = "Type to search   Up/Down select   PgUp/PgDn scroll   Esc close"

    def __init__(self, scene):
        super().__init__(scene)
        self.search = TextInput("search: ", 16)
        self.list = ListView(size=15, mono=True)
        self.view = ScrollText(16)
        self.entries: list[tuple[str, int, dict]] = []
        self._filter()
        pygame.key.start_text_input()

    def subtitle(self) -> str:
        return f"{len(self.app.run.journal)} artifacts collected. Sorted by when the event happened."

    def _filter(self) -> None:
        q = self.search.text.strip().lower()
        allx = journal_entries(self.app.run)
        if q:
            def hit(e):
                eid, zone, ev = e
                blob = " ".join([eid, ev.get("title", ""), ev.get("host", ""), ev.get("type", ""),
                                 " ".join(ev.get("lines", []))]).lower()
                return all(part in blob for part in q.split())
            allx = [e for e in allx if hit(e)]
        self.entries = allx
        items = []
        for eid, zone, ev in allx:
            t = ev.get("time", "")[11:19] or "--:--:--"
            col = theme.accent if zone == self.state.zone.index else theme.color("text")
            items.append((f"Z{zone} {t} {ev.get('title', eid)}", col))
        self.list.set_items(items)
        self._show()

    def _show(self) -> None:
        if not self.entries:
            msg = "No matches." if self.search.text.strip() else "Nothing collected yet. Investigate nodes with E."
            self.view.set_lines([(msg, "dim")])
            return
        eid, zone, ev = self.entries[self.list.index]
        self.view.set_lines(evidence_lines(ev, eid))

    def on_event(self, event) -> None:
        if event.type == pygame.TEXTINPUT:
            if self.time == 0.0:
                return
            self.search.handle_event(event)
            self._filter()
            return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_BACKSPACE, pygame.K_DELETE, pygame.K_LEFT, pygame.K_RIGHT,
                             pygame.K_HOME, pygame.K_END):
                self.search.handle_event(event)
                self._filter()
                return
            if event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                self.view.handle_event(event)
                return
            if event.key not in (pygame.K_UP, pygame.K_DOWN):
                return
        if self.view.handle_event(event, keys=False):
            return
        if self.list.handle_event(event) == "move":
            self.app.audio.play("move")
            self._show()

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.search.update(dt):
            self._filter()

    def draw_body(self, surface, rect) -> None:
        left = pygame.Rect(rect.x, rect.y, 470, rect.height)
        right = pygame.Rect(left.right + 18, rect.y, rect.right - left.right - 18, rect.height)
        self.search.draw(surface, pygame.Rect(left.x, left.y, left.width, 32))
        self.list.draw(surface, pygame.Rect(left.x, left.y + 42, left.width, left.height - 42))
        pygame.draw.line(surface, theme.color("panel_edge"), (right.x - 9, rect.y), (right.x - 9, rect.bottom))
        self.view.draw(surface, right)
        if not self.entries and not self.search.text:
            surface.blit(font(15).render("", True, theme.color("dim")), right.topleft)
