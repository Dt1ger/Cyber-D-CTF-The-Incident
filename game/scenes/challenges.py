"""Case Files: built-in cases, played apart from the VELVET LOCUST hunt."""

from __future__ import annotations

import pygame

from game.characters.unlock import is_unlocked
from game.engine import config
from game.engine.scene import Scene
from game.systems.challenges import CaseSession, load_challenges, run_command
from game.ui import theme
from game.ui.panels.base import draw_wrapped
from game.ui.text import font
from game.ui.widgets import ListView, ScrollText, TextInput, draw_panel, key_hint


class ChallengesScene(Scene):
    def on_enter(self, **kwargs) -> None:
        self.character = self.app.character(self.app.state.get("analyst", "demetri"))
        theme.set_accent(self.character.accent)
        self.challenges, self.notes = load_challenges(config.CHALLENGES_DIR)
        self.solved = set(self.app.saves.custom_solved())
        self.list = ListView(size=18)
        self.logs: dict[str, list[tuple[str, str]]] = {}
        self.sessions: dict[str, CaseSession] = {}
        self.histories: dict[str, list[str]] = {}
        self.out = ScrollText(16)
        self.prompt = TextInput("run> ", 18)
        self.focus = "list"
        self._refresh_list()
        self._show_current()
        pygame.key.start_text_input()
        self.app.audio.play_music("game")

    def on_exit(self) -> None:
        pygame.key.stop_text_input()

    def _refresh_list(self) -> None:
        items = []
        for challenge in self.challenges:
            done = challenge.id in self.solved
            mark = "[+] " if done else "[ ] "
            items.append((f"{mark}Lv{challenge.difficulty}  {challenge.title}",
                          theme.color("ok") if done else theme.color("text")))
        self.list.set_items(items)

    @property
    def current(self):
        if self.list.selected is None or not self.challenges:
            return None
        return self.challenges[self.list.selected]

    def _show_current(self) -> None:
        challenge = self.current
        if challenge is None:
            self.out.set_lines([("The built-in case files could not be read.", "dim")])
            return
        layers = len(challenge.layers)
        log = self.logs.setdefault(challenge.id, [
            (f"{layers} layer{'s' if layers > 1 else ''} to peel. {len(challenge.evidence)} evidence "
             f"line(s). {len(challenge.hints)} hint(s).", "dim"),
            ("Start with identify and evidence. Type help for every command.", "dim"),
        ])
        self.out.set_lines(log, follow=True)

    def _session(self, challenge) -> CaseSession:
        if challenge.id not in self.sessions:
            self.sessions[challenge.id] = CaseSession.start(challenge)
        return self.sessions[challenge.id]

    def _run(self, line: str) -> None:
        challenge = self.current
        if challenge is None or not line.strip():
            return
        result = run_command(challenge, line, self._session(challenge))
        log = self.logs.setdefault(challenge.id, [])
        log.append((f"> {line.strip()}", "text"))
        log.extend(result.lines)
        if result.solved and challenge.id not in self.solved:
            had_recruit = is_unlocked(self.app, "aisha_256")
            self.solved.add(challenge.id)
            self.app.saves.mark_custom_solved(challenge.id)
            self._refresh_list()
            self.app.audio.play("success")
            if not had_recruit and is_unlocked(self.app, "aisha_256"):
                log.append(("Aisha_256 is on the roster.", "ok"))
        elif any(style == "bad" for _, style in result.lines):
            self.app.audio.play("error")
        elif line.strip():
            self.app.audio.play("query")
        self.out.set_lines(log, follow=True)

    def _open(self) -> None:
        """Move into the selected case: Up/Down now walk its command history."""
        challenge = self.current
        if challenge is None:
            return
        self.focus = "case"
        self.prompt.history = self.histories.setdefault(challenge.id, [])
        self.prompt.hist_i = len(self.prompt.history)
        self.prompt.set("")

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.audio.play("back")
            if self.focus == "case":
                self.focus = "list"
            else:
                self.app.scenes.switch("title", menu=True)
            return
        clicked = self.list.handle_event(event, keys=False)
        if clicked:
            self.app.audio.play("move" if clicked == "move" else "confirm")
            self._show_current()
            self._open()
            return
        if event.type == pygame.MOUSEWHEEL:
            self.out.handle_event(event, keys=False)
            return
        if self.focus == "list":
            self._list_event(event)
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.out.handle_event(event)
            return
        line = self.prompt.handle_event(event)
        if line is not None:
            self._run(line)

    def _list_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                if self.list.handle_event(event) == "move":
                    self.app.audio.play("move")
                    self._show_current()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_RIGHT):
                self.app.audio.play("confirm")
                self._open()
        elif event.type == pygame.TEXTINPUT and not event.text.isspace():
            self._open()
            self.prompt.handle_event(event)

    def update(self, dt: float) -> None:
        self.prompt.update(dt)

    def draw(self, surface) -> None:
        w, h = surface.get_size()
        surface.fill((6, 8, 16))
        panel = pygame.Rect(24, 20, w - 48, h - 56)
        cleared = sum(1 for c in self.challenges if c.id in self.solved)
        subtitle = (f"{self.character.name}  ·  {cleared}/{len(self.challenges)} cleared  ·  "
                    "separate from the hunt")
        inner = draw_panel(surface, panel, "Case Files", accent=self.character.accent,
                           subtitle=subtitle)
        note_h = 22 if self.notes else 0
        list_rect = pygame.Rect(inner.x, inner.y, 340, inner.height - note_h)
        body = pygame.Rect(list_rect.right + 18, inner.y, inner.right - list_rect.right - 18, inner.height)
        self.list.draw(surface, list_rect, accent=self.character.accent, focused=self.focus == "list")
        if self.notes:
            note = font(13, mono=True).render(f"{len(self.notes)} file(s) skipped", True, theme.color("warn"))
            surface.blit(note, (list_rect.x, list_rect.bottom + 4))
        self._detail(surface, body)
        hint = ("Up/Down choose    Enter open case    Esc menu" if self.focus == "list" else
                "Enter run    Up/Down history    PgUp/PgDn scroll    Esc back to cases")
        key_hint(surface, hint, (w - 16, h - 10))

    def _detail(self, surface, rect: pygame.Rect) -> None:
        challenge = self.current
        if challenge is None:
            draw_wrapped(
                surface,
                "Case Files ships with the game, apart from the VELVET LOCUST hunt. "
                "Your campaign save is untouched.\n\n"
                "The built-in cases could not be read. They normally sit in the challenges folder "
                "next to the game.",
                rect, 18)
            return
        y = draw_wrapped(surface, challenge.title, pygame.Rect(rect.x, rect.y, rect.width, 56),
                         22, self.character.accent) + 6
        y = draw_wrapped(surface, challenge.clue, pygame.Rect(rect.x, y, rect.width, 72), 17) + 8
        session = self._session(challenge)
        peeled = len(session.history)
        label = font(14, bold=True).render(
            f"WORKING TEXT  ·  {peeled} decode(s) applied  ·  {len(session.buffer)} chars  ·  "
            "show prints it all", True, theme.color("dim"))
        surface.blit(label, (rect.x, y))
        y += 22
        box = pygame.Rect(rect.x, y, rect.width, 88)
        pygame.draw.rect(surface, (4, 7, 14), box)
        pygame.draw.rect(surface, theme.color("panel_edge"), box, 1)
        draw_wrapped(surface, session.buffer, box.inflate(-16, -12), 16, theme.color("amber"), mono=True)
        y = box.bottom + 10
        out = pygame.Rect(rect.x, y, rect.width, rect.bottom - y - 46)
        pygame.draw.rect(surface, (4, 7, 14), out)
        self.out.draw(surface, out.inflate(-8, -8))
        prompt = pygame.Rect(rect.x, rect.bottom - 38, rect.width, 36)
        if self.focus == "case":
            self.prompt.draw(surface, prompt, self.character.accent)
            return
        pygame.draw.rect(surface, (6, 10, 20), prompt)
        pygame.draw.rect(surface, theme.color("panel_edge"), prompt, 1)
        idle = font(16, mono=True).render("Press Enter or start typing to open this case",
                                          True, theme.color("dim"))
        surface.blit(idle, idle.get_rect(midleft=(prompt.x + 10, prompt.centery)))
