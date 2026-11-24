"""Small UI toolkit: panels, menus, list views, scrolling text, and a text input.

Everything is keyboard-first; mouse support is layered on top.
"""

from __future__ import annotations

import pygame

from game.ui import theme
from game.ui.text import font


def wrap(text: str, fnt: pygame.font.Font, width: int) -> list[str]:
    lines: list[str] = []
    for para in str(text).split("\n"):
        if not para:
            lines.append("")
            continue
        indent = len(para) - len(para.lstrip(" "))
        words = para.split(" ")
        cur = ""
        for word in words:
            trial = word if not cur else f"{cur} {word}"
            if fnt.size(trial)[0] <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = " " * indent + word
            while fnt.size(cur)[0] > width and len(cur) > 1:
                cut = len(cur)
                while cut > 1 and fnt.size(cur[:cut])[0] > width:
                    cut -= 1
                lines.append(cur[:cut])
                cur = cur[cut:]
        lines.append(cur)
    return lines


def draw_text(surface, text, pos, size=18, color=None, mono=False, bold=False, anchor="topleft"):
    surf = font(size, mono, bold).render(str(text), True, color or theme.color("text"))
    rect = surf.get_rect(**{anchor: pos})
    surface.blit(surf, rect)
    return rect


def draw_panel(surface: pygame.Surface, rect: pygame.Rect, title: str | None = None,
               accent=None, alpha: int = 238, subtitle: str | None = None) -> pygame.Rect:
    accent = accent or theme.accent
    bg = pygame.Surface(rect.size, pygame.SRCALPHA)
    bg.fill((*theme.color("panel"), alpha))
    surface.blit(bg, rect.topleft)
    pygame.draw.rect(surface, theme.color("panel_edge"), rect, 1, border_radius=6)
    pygame.draw.line(surface, accent, (rect.x + 8, rect.y), (rect.right - 8, rect.y), 2)
    for cx, cy, dx, dy in ((rect.x, rect.y, 1, 1), (rect.right - 1, rect.y, -1, 1),
                           (rect.x, rect.bottom - 1, 1, -1), (rect.right - 1, rect.bottom - 1, -1, -1)):
        pygame.draw.line(surface, accent, (cx, cy), (cx + 14 * dx, cy), 2)
        pygame.draw.line(surface, accent, (cx, cy), (cx, cy + 14 * dy), 2)
    inner = rect.inflate(-28, -24)
    if title:
        t = font(22, bold=True).render(title.upper(), True, accent)
        surface.blit(t, (inner.x, inner.y))
        top = inner.y + t.get_height() + 2
        if subtitle:
            s = font(15, mono=True).render(subtitle, True, theme.color("dim"))
            surface.blit(s, (inner.x, top))
            top += s.get_height() + 2
        pygame.draw.line(surface, theme.color("panel_edge"), (inner.x, top + 4), (inner.right, top + 4))
        inner = pygame.Rect(inner.x, top + 12, inner.width, inner.bottom - top - 12)
    return inner


def key_hint(surface, text: str, pos, anchor="bottomright", size=14):
    return draw_text(surface, text, pos, size, theme.color("dim"), mono=True, anchor=anchor)


class Menu:
    """Vertical menu. handle_event returns the index chosen with Enter/click, else None."""

    def __init__(self, items: list[str], enabled: list[bool] | None = None, size: int = 26,
                 spacing: int = 44):
        self.items = items
        self.enabled = enabled or [True] * len(items)
        self.index = next((i for i, e in enumerate(self.enabled) if e), 0)
        self.size = size
        self.spacing = spacing
        self.rects: list[pygame.Rect] = []
        self.moved = False

    def _step(self, d: int) -> None:
        for _ in range(len(self.items)):
            self.index = (self.index + d) % len(self.items)
            if self.enabled[self.index]:
                break
        self.moved = True

    def handle_event(self, event) -> int | None:
        self.moved = False
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self._step(-1)
            elif event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_TAB):
                self._step(1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self.index if self.enabled[self.index] else None
        elif event.type == pygame.MOUSEMOTION:
            for i, r in enumerate(self.rects):
                if r.collidepoint(event.pos) and self.enabled[i] and i != self.index:
                    self.index = i
                    self.moved = True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in enumerate(self.rects):
                if r.collidepoint(event.pos) and self.enabled[i]:
                    self.index = i
                    return i
        return None

    def draw(self, surface, center_x: int, top: int, accent=None, width: int = 340) -> None:
        accent = accent or theme.accent
        self.rects = []
        for i, label in enumerate(self.items):
            y = top + i * self.spacing
            rect = pygame.Rect(0, 0, width, self.spacing - 8)
            rect.center = (center_x, y + self.spacing // 2)
            self.rects.append(rect)
            selected = i == self.index
            if selected:
                bg = pygame.Surface(rect.size, pygame.SRCALPHA)
                bg.fill((*accent, 46))
                surface.blit(bg, rect)
                pygame.draw.rect(surface, accent, rect, 2, border_radius=4)
            color = (accent if selected else theme.color("text")) if self.enabled[i] else (70, 80, 95)
            text = f"> {label} <" if selected else label
            draw_text(surface, text, rect.center, self.size, color, bold=selected, anchor="center")


class ListView:
    """Scrollable selectable list. Items are strings or (text, color) pairs."""

    def __init__(self, items=None, size: int = 17, mono: bool = False):
        self.items = list(items or [])
        self.index = 0
        self.scroll = 0
        self.size = size
        self.mono = mono
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.row_h = 0

    def set_items(self, items) -> None:
        self.items = list(items)
        self.index = min(self.index, max(0, len(self.items) - 1))

    @property
    def selected(self) -> int | None:
        return self.index if self.items else None

    def visible_rows(self) -> int:
        return max(1, self.rect.height // max(1, self.row_h)) if self.row_h else 10

    def _clamp(self) -> None:
        n = self.visible_rows()
        if self.index < self.scroll:
            self.scroll = self.index
        elif self.index >= self.scroll + n:
            self.scroll = self.index - n + 1
        self.scroll = max(0, min(self.scroll, max(0, len(self.items) - n)))

    def handle_event(self, event, keys=True) -> str | None:
        """Returns 'move', 'activate', or None."""
        if not self.items:
            return None
        if keys and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.index = max(0, self.index - 1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.index = min(len(self.items) - 1, self.index + 1)
            elif event.key == pygame.K_PAGEUP:
                self.index = max(0, self.index - self.visible_rows())
            elif event.key == pygame.K_PAGEDOWN:
                self.index = min(len(self.items) - 1, self.index + self.visible_rows())
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return "activate"
            else:
                return None
            self._clamp()
            return "move"
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(pygame.mouse.get_pos()):
            self.scroll = max(0, min(self.scroll - event.y * 2,
                                     max(0, len(self.items) - self.visible_rows())))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            i = self.scroll + (event.pos[1] - self.rect.y) // max(1, self.row_h)
            if 0 <= i < len(self.items):
                if i == self.index:
                    return "activate"
                self.index = i
                return "move"
        return None

    def draw(self, surface, rect: pygame.Rect, accent=None, focused: bool = True) -> None:
        accent = accent or theme.accent
        self.rect = rect
        fnt = font(self.size, self.mono)
        self.row_h = fnt.get_linesize() + 6
        self._clamp()
        clip = surface.get_clip()
        surface.set_clip(rect)
        n = self.visible_rows()
        for row, i in enumerate(range(self.scroll, min(len(self.items), self.scroll + n + 1))):
            item = self.items[i]
            text, color = (item if isinstance(item, tuple) else (item, theme.color("text")))
            y = rect.y + row * self.row_h
            if i == self.index:
                bg = pygame.Surface((rect.width, self.row_h), pygame.SRCALPHA)
                bg.fill((*accent, 60 if focused else 25))
                surface.blit(bg, (rect.x, y))
                if focused:
                    pygame.draw.rect(surface, accent, (rect.x, y, 3, self.row_h))
            label = text
            while fnt.size(label)[0] > rect.width - 14 and len(label) > 4:
                label = label[:-2]
            if label != text:
                label = label[:-1] + "~"
            surface.blit(fnt.render(label, True, color), (rect.x + 8, y + 3))
        surface.set_clip(clip)
        if len(self.items) > n:
            bar_h = max(20, rect.height * n // len(self.items))
            bar_y = rect.y + (rect.height - bar_h) * self.scroll // max(1, len(self.items) - n)
            pygame.draw.rect(surface, theme.color("panel_edge"), (rect.right - 4, bar_y, 3, bar_h))


class ScrollText:
    """Read-only lines of (text, style) that wrap to the width and scroll."""

    def __init__(self, size: int = 16, mono: bool = True):
        self.lines: list[tuple[str, str]] = []
        self.size = size
        self.mono = mono
        self.scroll = 0
        self.follow = True
        self.rect = pygame.Rect(0, 0, 0, 0)
        self._wrapped: list[tuple[str, str]] = []
        self._key = None

    def set_lines(self, lines, follow: bool = False) -> None:
        self.lines = list(lines)
        self.scroll = 0
        self.follow = follow
        self._key = None

    def add(self, lines) -> None:
        self.lines.extend(lines)
        self.follow = True
        self._key = None

    def _wrap(self, width: int) -> list[tuple[str, str]]:
        key = (len(self.lines), width, self.size, id(self.lines[-1]) if self.lines else 0)
        if key != self._key:
            fnt = font(self.size, self.mono)
            self._wrapped = [(part, style) for text, style in self.lines
                             for part in wrap(text, fnt, width)]
            self._key = key
        return self._wrapped

    def handle_event(self, event, keys=True) -> bool:
        step = 0
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(pygame.mouse.get_pos()):
            step = -event.y * 3
        elif keys and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_PAGEUP:
                step = -10
            elif event.key == pygame.K_PAGEDOWN:
                step = 10
            elif event.key in (pygame.K_UP,) and not (event.mod & pygame.KMOD_SHIFT):
                step = -1
            elif event.key in (pygame.K_DOWN,):
                step = 1
        if step:
            self.scroll += step
            self.follow = False
            return True
        return False

    def draw(self, surface, rect: pygame.Rect) -> None:
        self.rect = rect
        fnt = font(self.size, self.mono)
        lh = fnt.get_linesize()
        wrapped = self._wrap(rect.width - 10)
        n = max(1, rect.height // lh)
        max_scroll = max(0, len(wrapped) - n)
        if self.follow:
            self.scroll = max_scroll
        self.scroll = max(0, min(self.scroll, max_scroll))
        if self.scroll >= max_scroll:
            self.follow = True
        clip = surface.get_clip()
        surface.set_clip(rect)
        for i, (text, style) in enumerate(wrapped[self.scroll:self.scroll + n + 1]):
            surface.blit(fnt.render(text, True, theme.style_color(style)), (rect.x + 4, rect.y + i * lh))
        surface.set_clip(clip)
        if len(wrapped) > n:
            bar_h = max(20, rect.height * n // len(wrapped))
            bar_y = rect.y + (rect.height - bar_h) * self.scroll // max(1, max_scroll)
            pygame.draw.rect(surface, theme.color("panel_edge"), (rect.right - 4, bar_y, 3, bar_h))


# Hold Backspace: wait, then erase steadily. A tap still deletes one character.
BACKSPACE_DELAY = 0.35
BACKSPACE_INTERVAL = 0.025


class TextInput:
    """Single-line input with history. handle_event returns the text on Enter."""

    def __init__(self, prompt: str = "> ", size: int = 18, max_len: int = 400):
        self.prompt = prompt
        self.text = ""
        self.cursor = 0
        self.size = size
        self.max_len = max_len
        self.history: list[str] = []
        self.hist_i = 0
        self.blink = 0.0
        self._backspace_held = False
        self._backspace_time = 0.0

    def set(self, text: str) -> None:
        self.text = text[: self.max_len]
        self.cursor = len(self.text)

    def _backspace(self) -> None:
        if self.cursor <= 0:
            return
        self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
        self.cursor -= 1
        self.blink = 0

    def handle_event(self, event) -> str | None:
        if event.type == pygame.KEYUP and event.key == pygame.K_BACKSPACE:
            self._backspace_held = False
            return None
        if event.type == pygame.TEXTINPUT:
            if len(self.text) < self.max_len:
                self.text = self.text[:self.cursor] + event.text + self.text[self.cursor:]
                self.cursor += len(event.text)
            self.blink = 0
            return None
        if event.type != pygame.KEYDOWN:
            return None
        self.blink = 0
        k = event.key
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            text = self.text
            if text.strip():
                self.history.append(text)
            self.hist_i = len(self.history)
            self.text, self.cursor = "", 0
            return text
        if k == pygame.K_BACKSPACE:
            self._backspace()
            self._backspace_held = True
            self._backspace_time = 0.0
        elif k == pygame.K_DELETE:
            self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]
        elif k == pygame.K_LEFT:
            self.cursor = max(0, self.cursor - 1)
        elif k == pygame.K_RIGHT:
            self.cursor = min(len(self.text), self.cursor + 1)
        elif k == pygame.K_HOME:
            self.cursor = 0
        elif k == pygame.K_END:
            self.cursor = len(self.text)
        elif k == pygame.K_UP and self.history:
            self.hist_i = max(0, self.hist_i - 1)
            self.set(self.history[self.hist_i])
        elif k == pygame.K_DOWN and self.history:
            self.hist_i = min(len(self.history), self.hist_i + 1)
            self.set(self.history[self.hist_i] if self.hist_i < len(self.history) else "")
        elif k == pygame.K_v and event.mod & pygame.KMOD_CTRL:
            try:
                clip = pygame.scrap.get_text() if hasattr(pygame, "scrap") else ""
            except Exception:
                clip = ""
            if clip:
                clip = clip.replace("\r", " ").replace("\n", " ")
                self.text = (self.text[:self.cursor] + clip + self.text[self.cursor:])[: self.max_len]
                self.cursor = min(len(self.text), self.cursor + len(clip))
        return None

    def update(self, dt: float) -> bool:
        """Advance the cursor blink. Returns True when a held Backspace erased text."""
        self.blink += dt
        if not self._backspace_held:
            return False
        if not pygame.key.get_pressed()[pygame.K_BACKSPACE]:
            self._backspace_held = False
            return False
        self._backspace_time += dt
        if self._backspace_time < BACKSPACE_DELAY or self.cursor <= 0:
            return False
        self._backspace()
        self._backspace_time = BACKSPACE_DELAY - BACKSPACE_INTERVAL
        return True

    def draw(self, surface, rect: pygame.Rect, color=None) -> None:
        fnt = font(self.size, mono=True)
        color = color or theme.accent
        pygame.draw.rect(surface, (6, 10, 20), rect)
        pygame.draw.rect(surface, color, rect, 1)
        full = self.prompt + self.text
        cursor_x = fnt.size(self.prompt + self.text[:self.cursor])[0]
        shift = max(0, cursor_x - (rect.width - 20))
        clip = surface.get_clip()
        surface.set_clip(rect.inflate(-4, -2))
        surface.blit(fnt.render(full, True, theme.color("text")), (rect.x + 8 - shift, rect.y + 5))
        if (self.blink % 1.0) < 0.55:
            x = rect.x + 8 + cursor_x - shift
            pygame.draw.rect(surface, color, (x, rect.y + 5, 2, fnt.get_height()))
        surface.set_clip(clip)
