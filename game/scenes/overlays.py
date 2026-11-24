"""Overlays pushed on top of other scenes: pause, settings, how to play."""

from __future__ import annotations

import pygame

from game.engine.scene import Scene
from game.engine.settings import TEXT_SIZES, TYPE_SPEEDS
from game.ui import theme
from game.ui.panels.base import draw_wrapped
from game.ui.text import font
from game.ui.widgets import Menu, draw_panel


class Overlay(Scene):
    opaque = False

    def veil(self, surface, alpha: int = 160) -> None:
        v = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        v.fill((0, 0, 0, alpha))
        surface.blit(v, (0, 0))

    def close(self) -> None:
        self.app.audio.play("back")
        self.app.scenes.pop()


class PauseScene(Overlay):
    ITEMS = ["Resume", "Settings", "How to Play", "Save & Quit to Title", "Quit Game"]

    def on_enter(self, **kwargs) -> None:
        self.menu = Menu(self.ITEMS, size=24, spacing=48)

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_p):
            self.close()
            return
        choice = self.menu.handle_event(event)
        if self.menu.moved:
            self.app.audio.play("move")
        if choice is None:
            return
        self.app.audio.play("confirm")
        item = self.ITEMS[choice]
        if item == "Resume":
            self.app.scenes.pop()
        elif item == "Settings":
            self.app.scenes.push("settings")
        elif item == "How to Play":
            self.app.scenes.push("how_to_play")
        elif item.startswith("Save"):
            if self.app.run:
                self.app.saves.save_run(self.app.run.to_dict())
            self.app.scenes.switch("title", menu=True)
        else:
            if self.app.run:
                self.app.saves.save_run(self.app.run.to_dict())
            self.app.quit()

    def draw(self, surface) -> None:
        self.veil(surface)
        w, h = surface.get_size()
        rect = pygame.Rect(0, 0, 440, 360)
        rect.center = (w // 2, h // 2)
        draw_panel(surface, rect, "Paused", subtitle="The Breach Clock is frozen.")
        self.menu.draw(surface, rect.centerx, rect.y + 78, width=340)
        t = font(13, mono=True).render("Progress saves at the start of each zone.", True, theme.color("dim"))
        surface.blit(t, t.get_rect(midbottom=(rect.centerx, rect.bottom - 10)))


def _onoff(v: bool) -> str:
    return "On" if v else "Off"


class SettingsScene(Overlay):
    def on_enter(self, **kwargs) -> None:
        self.index = 0
        self.rows: list[pygame.Rect] = []

    def options(self):
        s = self.app.settings
        return [
            ("Text size", TEXT_SIZES[s.text_size % len(TEXT_SIZES)][0], "text_size"),
            ("Colorblind palette", _onoff(s.colorblind), "colorblind"),
            ("CRT scanlines", _onoff(s.scanlines), "scanlines"),
            ("Music volume", f"{round(s.music * 100)}%", "music"),
            ("Sound volume", f"{round(s.sfx * 100)}%", "sfx"),
            ("Mute all (F8)", _onoff(s.muted), "muted"),
            ("Dialogue speed", TYPE_SPEEDS[s.type_speed % len(TYPE_SPEEDS)][0], "type_speed"),
            ("Screen shake", _onoff(s.screen_shake), "screen_shake"),
            ("Full-keyboard mode (hide mouse)", _onoff(s.keyboard_only), "keyboard_only"),
            ("Back", "", "back"),
        ]

    def change(self, key: str, d: int) -> None:
        s = self.app.settings
        if key == "back":
            self.leave()
            return
        if key == "text_size":
            s.text_size = (s.text_size + d) % len(TEXT_SIZES)
        elif key == "type_speed":
            s.type_speed = (s.type_speed + d) % len(TYPE_SPEEDS)
        elif key in ("music", "sfx"):
            setattr(s, key, round(max(0.0, min(1.0, getattr(s, key) + 0.1 * d)), 2))
        else:
            setattr(s, key, not getattr(s, key))
        self.app.apply_settings()
        self.app.audio.apply_volume()
        self.app.audio.play("blip")

    def leave(self) -> None:
        self.app.save_settings()
        self.close()

    def handle_event(self, event) -> None:
        opts = self.options()
        if event.type == pygame.KEYDOWN:
            k = event.key
            if k == pygame.K_ESCAPE:
                self.leave()
            elif k in (pygame.K_UP, pygame.K_w):
                self.index = (self.index - 1) % len(opts)
                self.app.audio.play("move")
            elif k in (pygame.K_DOWN, pygame.K_s, pygame.K_TAB):
                self.index = (self.index + 1) % len(opts)
                self.app.audio.play("move")
            elif k in (pygame.K_LEFT, pygame.K_a):
                self.change(opts[self.index][2], -1)
            elif k in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.change(opts[self.index][2], 1)
        elif event.type == pygame.MOUSEMOTION:
            for i, r in enumerate(self.rows):
                if r.collidepoint(event.pos):
                    self.index = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            for i, r in enumerate(self.rows):
                if r.collidepoint(event.pos):
                    self.index = i
                    self.change(opts[i][2], 1 if event.button == 1 else -1)

    def draw(self, surface) -> None:
        self.veil(surface, 180)
        w, h = surface.get_size()
        rect = pygame.Rect(0, 0, 680, 560)
        rect.center = (w // 2, h // 2)
        inner = draw_panel(surface, rect, "Settings", subtitle="Left/Right change   Up/Down move   Esc back")
        self.rows = []
        f = font(20)
        y = inner.y + 4
        for i, (label, value, key) in enumerate(self.options()):
            r = pygame.Rect(inner.x, y, inner.width, 40)
            self.rows.append(r)
            if i == self.index:
                bg = pygame.Surface(r.size, pygame.SRCALPHA)
                bg.fill((*theme.accent, 50))
                surface.blit(bg, r)
                pygame.draw.rect(surface, theme.accent, (r.x, r.y, 3, r.height))
            surface.blit(f.render(label, True, theme.color("text")), (r.x + 14, r.centery - f.get_height() // 2))
            if value:
                v = font(20, bold=True).render(f"<  {value}  >" if i == self.index else value, True, theme.accent)
                surface.blit(v, v.get_rect(midright=(r.right - 14, r.centery)))
            y += 44


HOW_TO_PLAY = [
    ("The Mission", [
        "Halcyon Dynamics has been breached by a threat actor tracked as VELVET LOCUST. You're the hunter.",
        "Each zone of the Grid is one stage of the attack, mapped to MITRE ATT&CK. Investigate hosts, "
        "collect evidence, prove what happened with queries, map it to ATT&CK, and contain it in the "
        "right order.",
        "Oracle, your hooded AI guide, waits at the start of every zone. Talk to Oracle any time for the "
        "current objective.",
    ]),
    ("Moving & Investigating", [
        "Move: WASD or arrow keys. Click the floor to walk there.",
        "Interact: E (or Enter) near a host, Oracle, or a CTF cache. Click a host to walk over and open it.",
        "Hosts with a ? haven't been investigated. A check mark means every artifact is collected. "
        "Magenta sparks mean VELVET LOCUST is spreading there.",
        "The exit gate (east) opens when every objective is done. Walk through it to move on.",
        "Pause: Esc or P. The Breach Clock freezes while paused or during dialogue.",
    ]),
    ("Your Tools", [
        "[T] Terminal: query telemetry.  search proc where parent=\"winword.exe\"  (type help inside)",
        "[J] Journal: every artifact you've collected, searchable, in time order.",
        "[B] Board: pin evidence cards and choose the hypothesis they prove.",
        "[M] Matrix: map findings to the right technique under the right tactic.",
        "[L] Timeline: drag events into the order they happened.",
        "[R] Respond: containment actions with tradeoffs. Order matters!",
        "[H] Hint: Oracle's tiered hints. Each costs a few points. They never lock you out.",
        "The toolbar button for your current objective glows.",
    ]),
    ("The Breach Clock", [
        "From Zone 1 on, the Breach Clock ticks while you work. At 100% VELVET LOCUST steals data: your "
        "containment score drops and the clock resets. You can't lose the game; you can lose points.",
        "Responding too early (killing a process before preserving evidence, blocking before you know "
        "every channel) tips them off: the clock jumps and they move faster for a while.",
        "Correct response actions push the clock back. Preserve, contain, eradicate, recover.",
    ]),
    ("Scoring & Ranks", [
        "Accuracy 400 + Containment 300 + Time 150 + Flag 150, minus hints, plus 25 per CTF cache.",
        "Ranks: Junior Analyst, Hunter (500+), Senior Hunter (700+), Threat Hunt Lead (850+). Your best "
        "rank is saved per character.",
        "Demetri's Steady Hand: premature actions often go unnoticed, and good responses slow the clock.",
        "Sasha's Flag Sense: pivot tips in the terminal and a bonus CTF cache in every zone.",
        "Aisha_256 stays locked until you finish the hunt once or clear every Case File. Pattern Breaker: "
        "each piece of evidence you log pulls the Breach Clock back and can show a weak point.",
    ]),
    ("Case Files", [
        "An alternate mode that ships with the game. These cases are not part of the VELVET LOCUST hunt. "
        "Your campaign save and rank stay where they are.",
        "On the title menu choose Case Files, then pick an analyst. Aisha_256 is on that list once she "
        "is unlocked. Every analyst plays these cases the same way. Their perks belong to the campaign.",
        "Each note is wrapped in layers. Type identify to see what the text looks like, then decode "
        "base64, hex, or rot13. Peel one layer at a time; undo steps back, reset starts over.",
        "Keyed layers need decode xor <key>. The key is never in the clue. Read the evidence.",
        "Every note lists several flags. Only one answers the clue's question. Hints cost a clean solve.",
    ]),
    ("Accessibility", [
        "Settings: text size, colorblind palette, CRT scanlines, music/sound volume, mute (F8), dialogue "
        "speed, screen shake, and full-keyboard mode.",
        "Everything can be played with the keyboard alone. F11 toggles fullscreen.",
        "All data is fictional: IPs come from documentation ranges, domains end in .example/.test/.invalid, "
        "and malicious commands are inert text for analysis.",
    ]),
]


class HowToPlayScene(Overlay):
    def on_enter(self, **kwargs) -> None:
        self.page = 0

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.close()
            elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if self.page < len(HOW_TO_PLAY) - 1:
                    self.page += 1
                    self.app.audio.play("move")
                elif event.key != pygame.K_RIGHT:
                    self.close()
            elif event.key in (pygame.K_LEFT, pygame.K_a) and self.page > 0:
                self.page -= 1
                self.app.audio.play("move")
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:
                self.close()
            elif self.page < len(HOW_TO_PLAY) - 1:
                self.page += 1
            else:
                self.close()

    def draw(self, surface) -> None:
        self.veil(surface, 190)
        w, h = surface.get_size()
        rect = pygame.Rect(0, 0, 940, 580)
        rect.center = (w // 2, h // 2)
        title, paras = HOW_TO_PLAY[self.page]
        inner = draw_panel(surface, rect, f"How to Play  //  {title}",
                           subtitle=f"Page {self.page + 1}/{len(HOW_TO_PLAY)}   <- ->  turn page   Esc close")
        y = inner.y + 6
        for p in paras:
            y = draw_wrapped(surface, p, pygame.Rect(inner.x + 6, y, inner.width - 12, inner.bottom - y), 19) + 14
