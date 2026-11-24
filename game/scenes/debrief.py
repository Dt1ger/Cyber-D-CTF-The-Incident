"""Zone 9: the after-action report. Score, rank, lessons, ATT&CK coverage."""

from __future__ import annotations

import pygame

from game.art import effects
from game.characters.unlock import HIDDEN, is_unlocked
from game.engine import config
from game.engine.scene import Scene
from game.systems.campaign import RunState
from game.systems.scoring import RANKS, score_run
from game.ui import theme
from game.ui.panels.base import draw_wrapped
from game.ui.text import font, glow_text
from game.ui.widgets import draw_panel
from game.world.zone_data import debrief_index, load_zone

PAGES = ["Incident Closed", "Zone by Zone", "ATT&CK Coverage", "Recommendations"]


def fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


class DebriefScene(Scene):
    def on_enter(self, **kwargs) -> None:
        app = self.app
        if app.run is None:
            app.run = RunState(character="demetri", zone=debrief_index())
        self.run = app.run
        self.char = app.character(self.run.character)
        theme.set_accent(self.char.accent)
        self.zone = load_zone(debrief_index())
        self.report = self.zone.debrief
        self.score = score_run(self.run)
        had_recruit = is_unlocked(app, HIDDEN)
        self.new_best = app.saves.record_result(self.run.character, self.score.rank, self.score.total)
        self.recruit = not had_recruit and is_unlocked(app, HIDDEN)
        app.saves.clear_run()
        self.page = 0
        self.time = 0.0
        self.particles = effects.Particles((config.WIDTH, config.HEIGHT), 60, seed=99)
        app.audio.play_music("game")
        app.audio.play("flag")

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.next()
            elif event.key in (pygame.K_LEFT, pygame.K_a) and self.page > 0:
                self.page -= 1
                self.app.audio.play("move")
            elif event.key == pygame.K_ESCAPE:
                self.leave()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.next()

    def next(self) -> None:
        if self.page < len(PAGES) - 1:
            self.page += 1
            self.app.audio.play("move")
        else:
            self.leave()

    def leave(self) -> None:
        self.app.audio.play("confirm")
        self.app.run = None
        self.app.scenes.switch("title", menu=True)

    def update(self, dt: float) -> None:
        self.time += dt
        self.particles.update(dt)

    def draw(self, surface) -> None:
        w, h = surface.get_size()
        self.particles.draw(surface)
        rect = pygame.Rect(50, 36, w - 100, h - 86)
        inner = draw_panel(surface, rect, f"After-Action Report  //  {PAGES[self.page]}",
                           subtitle=f"Analyst: {self.char.name}   Page {self.page + 1}/{len(PAGES)}")
        [self._summary, self._zones, self._attack, self._recs][self.page](surface, inner)
        hint = "<- back   -> / ENTER next" if self.page < len(PAGES) - 1 else "<- back   ENTER return to title"
        t = font(15, mono=True).render(hint, True, theme.color("dim"))
        surface.blit(t, t.get_rect(bottomright=(rect.right, h - 18)))

    def _summary(self, surface, r) -> None:
        s = self.score
        rank = glow_text(s.rank.upper(), font(48, bold=True), theme.color("amber"), radius=7)
        surface.blit(rank, rank.get_rect(midtop=(r.x + 300, r.y + 6)))
        total = font(30, bold=True).render(f"{s.total} / 1000", True, theme.color("text"))
        surface.blit(total, total.get_rect(midtop=(r.x + 300, r.y + 78)))
        if self.new_best:
            nb = font(17, bold=True).render(f"NEW BEST FOR {self.char.name.upper()}", True, self.char.accent)
            surface.blit(nb, nb.get_rect(midtop=(r.x + 300, r.y + 120)))
        if self.recruit:
            recruit = font(17, bold=True).render("AISHA_256 IS ON THE ROSTER", True, theme.color("amber"))
            surface.blit(recruit, recruit.get_rect(midtop=(r.x + 300, r.y + 146)))
        rows = [
            ("Accuracy", f"{s.accuracy * 100:.0f}% of graded decisions", s.accuracy_pts, 400),
            ("Containment", f"{s.containment}% (tip-offs, data loss, bad actions)", s.containment_pts, 300),
            ("Time", fmt_time(self.run.total_time), s.time_pts, 150),
            ("Completion", "Flag captured" if self.run.flag_captured else "No flag", s.completion_pts, 150),
            ("Hints", "Oracle's nudges", -s.hint_penalty, None),
            ("CTF bonus", f"{len(self.run.puzzles)} cache(s) cracked", s.bonus, None),
        ]
        y = r.y + 160
        detail_x = r.x + 32 + max(font(18, bold=True).size(row[0])[0] for row in rows)
        for label, detail, pts, mx in rows:
            surface.blit(font(18, bold=True).render(label, True, theme.accent), (r.x + 20, y))
            surface.blit(font(15).render(detail, True, theme.color("dim")), (detail_x, y + 2),
                         pygame.Rect(0, 0, r.x + 470 - detail_x, 30))
            val = f"{pts:+d}" if mx is None else f"{pts} / {mx}"
            t = font(18, mono=True, bold=True).render(val, True, theme.color("text"))
            surface.blit(t, t.get_rect(topright=(r.x + 590, y)))
            y += 34
        ladder = pygame.Rect(r.x + 650, r.y + 10, r.right - r.x - 650, r.height - 20)
        surface.blit(font(16, bold=True).render("RANKS", True, theme.accent), ladder.topleft)
        y = ladder.y + 28
        for threshold, name in RANKS:
            col = theme.color("amber") if name == s.rank else theme.color("dim")
            surface.blit(font(18, bold=name == s.rank).render(f"{threshold:>4}+  {name}", True, col), (ladder.x, y))
            y += 28
        y += 16
        surface.blit(font(16, bold=True).render("THE INCIDENT", True, theme.accent), (ladder.x, y))
        draw_wrapped(surface, self.report.get("summary", ""), pygame.Rect(ladder.x, y + 24, ladder.width, 260), 16)

    def _zones(self, surface, r) -> None:
        cols = 2
        zones = self.report.get("zones", [])
        cw = (r.width - 20) // cols
        ch = (r.height - 10) // ((len(zones) + 1) // cols or 1)
        for i, z in enumerate(zones):
            x = r.x + (i % cols) * (cw + 20)
            y = r.y + (i // cols) * ch
            st = self.run.stats.get(str(z["zone"]))
            surface.blit(font(17, bold=True).render(f"Z{z['zone']}  {z['title']}", True, theme.accent), (x, y))
            if st:
                info = (f"{st.correct} right  {st.wrong} wrong  {st.hints} hints  {st.tipoffs} tip-offs  "
                        f"{fmt_time(st.time)}")
                surface.blit(font(13, mono=True).render(info, True, theme.color("dim")), (x + 250, y + 3))
            yy = draw_wrapped(surface, "Lesson: " + z["lesson"], pygame.Rect(x, y + 24, cw, 40), 15)
            draw_wrapped(surface, "Fix: " + z["fix"], pygame.Rect(x, yy, cw, 40), 15, theme.color("ok"))

    def _attack(self, surface, r) -> None:
        mapped = self.run.mapped
        draw_wrapped(surface, f"You confirmed {len(mapped)} techniques. Every one maps to a detection you can "
                     "build on Monday morning.", pygame.Rect(r.x, r.y, r.width, 30), 17, theme.color("dim"))
        items = sorted(mapped.items(), key=lambda kv: (kv[1].get("zone", 0), kv[0]))
        y = r.y + 40
        col_w = (r.width - 20) // 2
        for i, (tid, info) in enumerate(items):
            x = r.x + (i % 2) * (col_w + 20)
            yy = y + (i // 2) * 52
            tech = self.app.attack.technique(tid)
            tac = self.app.attack.tactic(info.get("tactic", ""))
            name = tech.name if tech else tid
            surface.blit(font(17, bold=True).render(f"{tid}  {name}", True, theme.color("amber")), (x, yy))
            surface.blit(font(14, mono=True).render(f"Zone {info.get('zone')}  |  {tac.name if tac else ''}",
                                                    True, theme.color("dim")), (x, yy + 22))

    def _recs(self, surface, r) -> None:
        y = r.y
        for rec in self.report.get("recommendations", []):
            surface.blit(font(20, bold=True).render(">", True, theme.accent), (r.x, y))
            y = draw_wrapped(surface, rec, pygame.Rect(r.x + 26, y, r.width - 26, 60), 19) + 10
        y += 20
        surface.blit(font(18, bold=True).render("WHAT TO PRACTICE NEXT", True, theme.accent), (r.x, y))
        tips = ["Replay as the other analyst: Steady Hand and Flag Sense change how each zone feels.",
                "Try a no-hint run, or beat 120 minutes for full time points.",
                "Write each zone's detection as a real query for your own SIEM or EDR.",
                "Read MITRE ATT&CK's own pages for each technique you mapped, especially Detection."]
        y += 30
        for tip in tips:
            y = draw_wrapped(surface, "- " + tip, pygame.Rect(r.x + 10, y, r.width - 10, 50), 17) + 6
        thanks = font(16, mono=True).render(f"{config.TITLE}  //  {config.STUDIO}", True, theme.color("dim"))
        surface.blit(thanks, thanks.get_rect(bottomleft=(r.x, r.bottom)))
