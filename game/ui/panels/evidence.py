"""Investigating a node: its artifacts on the left, the selected artifact on the right."""

from __future__ import annotations

import pygame

from game.ui import theme
from game.ui.panels.base import Panel, draw_wrapped, evidence_lines
from game.ui.widgets import ListView, ScrollText


class EvidencePanel(Panel):
    name = "evidence"
    footer = "Up/Down select   Enter collect & analyze   PgUp/PgDn scroll   Esc close"

    def __init__(self, scene, node: dict):
        super().__init__(scene)
        self.node = node
        self.title = f"{node['host']}  //  {node.get('label', '')}"
        self.ids = [e for e in node.get("evidence", []) if e in self.state.zone.evidence]
        self.list = ListView(size=17)
        self.view = ScrollText(16)
        self._refresh()
        self._show()

    def subtitle(self) -> str:
        return f"{self.node.get('ip', '')}   {self.node.get('role', '')}"

    def _refresh(self) -> None:
        items = []
        for eid in self.ids:
            ev = self.state.zone.evidence[eid]
            got = self.state.has_evidence(eid)
            mark = "[x]" if got else "[ ]"
            items.append((f"{mark} {ev['title']}", theme.color("text") if got else theme.accent))
        self.list.set_items(items)

    def _show(self) -> None:
        if not self.ids:
            self.view.set_lines([("Nothing of interest on this host.", "dim")])
            return
        eid = self.ids[self.list.index]
        if self.state.has_evidence(eid):
            self.view.set_lines(evidence_lines(self.state.zone.evidence[eid], eid))
        else:
            ev = self.state.zone.evidence[eid]
            self.view.set_lines([(ev["title"], "accent"), ("", "normal"),
                                 (f"Type: {ev.get('type', '')}   Host: {ev.get('host', '')}", "dim"),
                                 ("", "normal"), ("Press ENTER to collect and analyze this artifact.", "warn")])

    def on_event(self, event) -> None:
        if self.view.handle_event(event, keys=False):
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.view.handle_event(event)
            return
        action = self.list.handle_event(event)
        if action == "move":
            self.app.audio.play("move")
            self._show()
        elif action == "activate" and self.ids:
            eid = self.ids[self.list.index]
            if self.state.collect(eid):
                self.app.audio.play("evidence")
            self._refresh()
            self._show()

    def draw_body(self, surface, rect) -> None:
        left = pygame.Rect(rect.x, rect.y, 360, rect.height)
        right = pygame.Rect(left.right + 18, rect.y, rect.right - left.right - 18, rect.height)
        self.list.draw(surface, pygame.Rect(left.x, left.y, left.width, left.height - 90))
        draw_wrapped(surface, "Collected artifacts go to your Evidence Journal (J). "
                     "Read them closely: the next query usually hides in the details.",
                     pygame.Rect(left.x, left.bottom - 80, left.width, 80), 15, theme.color("dim"))
        pygame.draw.line(surface, theme.color("panel_edge"), (right.x - 9, rect.y), (right.x - 9, rect.bottom))
        self.view.draw(surface, right)
