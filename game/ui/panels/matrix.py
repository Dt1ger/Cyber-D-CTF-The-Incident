"""ATT&CK matrix: pick a finding, then the technique cell under the right tactic."""

from __future__ import annotations

import pygame

from game.ui import theme
from game.ui.panels.base import Panel, draw_wrapped
from game.ui.text import font
from game.ui.widgets import wrap


class MatrixPanel(Panel):
    name = "matrix"
    title = "MITRE ATT&CK Matrix (Enterprise subset)"
    hotkey = pygame.K_m
    footer = "Arrows move   Tab next finding   Enter map finding to cell   Esc close"

    def __init__(self, scene):
        super().__init__(scene)
        self.columns = [(tac, techs) for tac, techs in self.app.attack.columns() if techs]
        self.col = 0
        self.row = 0
        self.finding_i = 0
        self.feedback: tuple[str, str] | None = None
        self.cell_rects: list[tuple[pygame.Rect, int, int]] = []
        self._findings()
        self._focus_relevant()

    def _findings(self) -> None:
        zone = self.state.zone
        self.findings = [fid for fid in zone.findings if fid not in self.state.mapped_findings]
        self.finding_i = min(self.finding_i, max(0, len(self.findings) - 1))

    def _focus_relevant(self) -> None:
        for ci, (tac, techs) in enumerate(self.columns):
            for ri, t in enumerate(techs):
                if t.id in self.app.run.mapped:
                    self.col, self.row = ci, ri
                    return

    def subtitle(self) -> str:
        n = len(self.app.run.mapped)
        return f"{n} technique{'s' if n != 1 else ''} confirmed in this incident. Lit cells are confirmed behavior."

    @property
    def cell(self):
        tac, techs = self.columns[self.col]
        self.row = min(self.row, len(techs) - 1)
        return tac, techs[self.row]

    def on_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            k = event.key
            if k in (pygame.K_LEFT, pygame.K_a):
                self.col = (self.col - 1) % len(self.columns)
            elif k in (pygame.K_RIGHT, pygame.K_d):
                self.col = (self.col + 1) % len(self.columns)
            elif k in (pygame.K_UP, pygame.K_w):
                self.row = max(0, self.row - 1)
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.row = min(len(self.columns[self.col][1]) - 1, self.row + 1)
            elif k == pygame.K_TAB and self.findings:
                self.finding_i = (self.finding_i + 1) % len(self.findings)
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._map()
                return
            else:
                return
            self.app.audio.play("move")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for r, ci, ri in self.cell_rects:
                if r.collidepoint(event.pos):
                    if (ci, ri) == (self.col, self.row):
                        self._map()
                    else:
                        self.col, self.row = ci, ri
                        self.app.audio.play("move")
                    return
            for r, i in getattr(self, "finding_rects", []):
                if r.collidepoint(event.pos):
                    self.finding_i = i
                    self.app.audio.play("move")

    def _map(self) -> None:
        if not self.findings:
            self.feedback = ("No unmapped findings in this zone. Explore the cells to learn each technique.", "dim")
            return
        tac, tech = self.cell
        fid = self.findings[self.finding_i]
        ok, msg = self.state.map_finding(fid, tac.id, tech.id)
        self.feedback = (msg, "ok" if ok else "bad")
        self.app.audio.play("success" if ok else "error")
        if ok:
            self._findings()

    def draw_body(self, surface, rect) -> None:
        grid_h = int(rect.height * 0.58)
        n = len(self.columns)
        gap = 4
        col_w = (rect.width - gap * (n - 1)) // n
        words = [w for tac, _ in self.columns for w in tac.name.split()]
        head_size = next((s for s in (12, 11, 10, 9, 8)
                          if all(font(s, bold=True).size(w)[0] <= col_w - 6 for w in words)), 8)
        head_f = font(head_size, bold=True)
        cell_f = font(12)
        self.cell_rects = []
        mapped = self.app.run.mapped
        max_rows = max(len(t) for _, t in self.columns)
        cell_h = min(46, (grid_h - 40) // max_rows - gap)
        for ci, (tac, techs) in enumerate(self.columns):
            x = rect.x + ci * (col_w + gap)
            hr = pygame.Rect(x, rect.y, col_w, 34)
            pygame.draw.rect(surface, (20, 28, 48), hr)
            for j, line in enumerate(wrap(tac.name, head_f, col_w - 6)[:2]):
                t = head_f.render(line, True, theme.color("text"))
                surface.blit(t, t.get_rect(midtop=(hr.centerx, hr.y + 2 + j * 15)))
            for ri, tech in enumerate(techs):
                r = pygame.Rect(x, rect.y + 40 + ri * (cell_h + gap), col_w, cell_h)
                self.cell_rects.append((r, ci, ri))
                lit = tech.id in mapped and mapped[tech.id].get("tactic") == tac.id
                lit_other = tech.id in mapped and not lit
                if lit:
                    pygame.draw.rect(surface, theme.accent, r, border_radius=3)
                    col = (8, 10, 18)
                else:
                    pygame.draw.rect(surface, (14, 20, 34), r, border_radius=3)
                    edge = theme.accent if lit_other else (40, 56, 84)
                    pygame.draw.rect(surface, edge, r, 1, border_radius=3)
                    col = theme.color("text") if lit_other else (150, 168, 188)
                label = f"{tech.id} {tech.name.split(': ')[-1]}"
                for j, line in enumerate(wrap(label, cell_f, col_w - 6)[: max(1, cell_h // 14)]):
                    surface.blit(cell_f.render(line, True, col), (r.x + 4, r.y + 3 + j * 14))
                if (ci, ri) == (self.col, self.row):
                    pygame.draw.rect(surface, theme.color("amber"), r.inflate(4, 4), 2, border_radius=4)

        bottom = pygame.Rect(rect.x, rect.y + grid_h + 8, rect.width, rect.height - grid_h - 8)
        left = pygame.Rect(bottom.x, bottom.y, 440, bottom.height)
        right = pygame.Rect(left.right + 20, bottom.y, bottom.right - left.right - 20, bottom.height)
        f = font(16, bold=True)
        surface.blit(f.render("FINDINGS TO MAP", True, theme.accent), left.topleft)
        y = left.y + 24
        self.finding_rects = []
        if not self.findings:
            draw_wrapped(surface, "All findings in this zone are mapped." if self.state.zone.findings else
                         "No findings in this zone. Browse the cells to study each technique.",
                         pygame.Rect(left.x, y, left.width, 60), 15, theme.color("dim"))
        for i, fid in enumerate(self.findings):
            text = self.state.zone.findings[fid]["text"]
            fnt = font(15)
            lines = wrap(text, fnt, left.width - 24)
            h = len(lines) * fnt.get_linesize() + 6
            r = pygame.Rect(left.x, y, left.width, h)
            if i == self.finding_i:
                bg = pygame.Surface(r.size, pygame.SRCALPHA)
                bg.fill((*theme.accent, 50))
                surface.blit(bg, r)
                pygame.draw.rect(surface, theme.accent, (r.x, r.y, 3, r.h))
            for j, line in enumerate(lines):
                surface.blit(fnt.render(line, True, theme.color("text")), (r.x + 10, r.y + 3 + j * fnt.get_linesize()))
            self.finding_rects.append((r, i))
            y += h + 6
        if self.feedback:
            msg, style = self.feedback
            draw_wrapped(surface, msg, pygame.Rect(left.x, left.bottom - 60, left.width, 60), 15,
                         theme.style_color(style))

        tac, tech = self.cell
        pygame.draw.line(surface, theme.color("panel_edge"), (right.x - 10, right.y), (right.x - 10, right.bottom))
        surface.blit(font(18, bold=True).render(f"{tech.id}  {tech.name}", True, theme.color("amber")), right.topleft)
        tactics = ", ".join(f"{t.name} ({t.id})" for t in (self.app.attack.tactic(x) for x in tech.tactics) if t)
        surface.blit(font(14, mono=True).render(f"Tactic: {tactics}", True, theme.color("dim")), (right.x, right.y + 26))
        y = draw_wrapped(surface, tech.description, pygame.Rect(right.x, right.y + 50, right.width, 70), 15) + 6
        lab_f = font(14, bold=True)
        indent = max(lab_f.size("DETECT")[0], lab_f.size("MITIGATE")[0]) + 10
        surface.blit(lab_f.render("DETECT", True, theme.color("ok")), (right.x, y))
        y = draw_wrapped(surface, tech.detection, pygame.Rect(right.x + indent, y, right.width - indent, 60), 15) + 6
        surface.blit(lab_f.render("MITIGATE", True, theme.color("info")), (right.x, y))
        y = draw_wrapped(surface, tech.mitigation, pygame.Rect(right.x + indent, y, right.width - indent, 60), 15) + 6
        if tech.id in mapped:
            m = mapped[tech.id]
            draw_wrapped(surface, f"Seen in zone {m.get('zone')}: {m.get('finding', '')}",
                         pygame.Rect(right.x, y, right.width, 40), 14, theme.accent)
