"""In-zone HUD: objective, Breach Clock, minimap, toasts, and the tool bar."""

from __future__ import annotations

import math

import pygame

from game.art.effects import translucent
from game.ui import theme
from game.ui.panels.base import draw_wrapped
from game.ui.text import font, rendered
from game.world.tilemap import BUS, FLOOR, GATE, RACK, TILE

TOOLS = [("terminal", "T", "TERMINAL"), ("journal", "J", "JOURNAL"), ("board", "B", "BOARD"),
         ("matrix", "M", "MATRIX"), ("timeline", "L", "TIMELINE"), ("respond", "R", "RESPOND"),
         ("hint", "H", "HINT")]
TOOL_KEYS = {pygame.K_t: "terminal", pygame.K_j: "journal", pygame.K_b: "board", pygame.K_m: "matrix",
             pygame.K_l: "timeline", pygame.K_r: "respond", pygame.K_h: "hint"}
OBJECTIVE_TOOL = {"query": "terminal", "decode": "terminal", "flag": "terminal", "choice": "board",
                  "map": "matrix", "timeline": "timeline", "respond": "respond"}
ADVERSARY_LABEL = {"dormant": ("OFFLINE", "dim"), "active": ("ACTIVE", "warn"),
                   "spreading": ("SPREADING", "bad"), "alerted": ("ALERTED", "bad"),
                   "contained": ("CONTAINED", "ok")}
MINI_SCALE = 3


def relevant_tool(obj: dict | None) -> str | None:
    if obj is None:
        return None
    if obj["type"] == "open":
        return obj.get("panel")
    return OBJECTIVE_TOOL.get(obj["type"])


class HUD:
    def __init__(self, scene):
        self.scene = scene
        self.app = scene.app
        self.toasts: list[list] = []
        self.time = 0.0
        self.tool_rects: dict[str, pygame.Rect] = {}
        self._mini = None
        self._mini_version = -1
        self.breach_flash = 0.0

    @property
    def state(self):
        return self.scene.state

    def toast(self, text: str, style: str = "normal", duration: float = 3.6) -> None:
        if not text:
            return
        self.toasts.append([text, style, duration, duration])
        self.toasts = self.toasts[-4:]

    def update(self, dt: float) -> None:
        self.time += dt
        for t in self.toasts:
            t[2] -= dt
        self.toasts = [t for t in self.toasts if t[2] > 0]
        self.breach_flash = max(0.0, self.breach_flash - dt)

    def tool_at(self, pos) -> str | None:
        return next((name for name, r in self.tool_rects.items() if r.collidepoint(pos)), None)

    # Drawing ---------------------------------------------------------------

    def draw(self, surface: pygame.Surface, prompt: str | None = None) -> None:
        self._objective(surface)
        self._clock(surface)
        self._minimap(surface)
        self._toolbar(surface)
        self._toasts(surface)
        if prompt:
            t = rendered(font(18, bold=True), prompt, theme.color("text"))
            r = t.get_rect(midbottom=(surface.get_width() // 2, surface.get_height() - 64)).inflate(24, 12)
            surface.blit(translucent(r.size, (6, 10, 22, 220)), r)
            pygame.draw.rect(surface, theme.accent, r, 1, border_radius=4)
            surface.blit(t, t.get_rect(center=r.center))

    def _box(self, surface, rect, edge=None) -> None:
        surface.blit(translucent(rect.size, (6, 10, 22, 215)), rect)
        pygame.draw.rect(surface, edge or theme.color("panel_edge"), rect, 1, border_radius=5)

    def _objective(self, surface) -> None:
        st = self.state
        zone = st.zone
        rect = pygame.Rect(14, 12, 440, 132)
        self._box(surface, rect)
        pygame.draw.line(surface, zone.accent, (rect.x + 6, rect.y), (rect.right - 6, rect.y), 2)
        head = rendered(font(17, bold=True), f"ZONE {zone.index}  //  {zone.name.upper()}", zone.accent)
        surface.blit(head, (rect.x + 12, rect.y + 8))
        obj = st.current
        total = len(st.objectives)
        counter_w = 0
        if obj is not None:
            counter = rendered(font(13, mono=True), f"OBJECTIVE {len(st.done) + 1}/{total}", theme.accent)
            counter_w = counter.get_width() + 12
            surface.blit(counter, counter.get_rect(topright=(rect.right - 12, rect.y + 30)))
        if zone.phase:
            phase = rendered(font(13, mono=True), zone.phase, theme.color("dim"))
            surface.blit(phase, (rect.x + 12, rect.y + 30),
                         pygame.Rect(0, 0, rect.width - 24 - counter_w, phase.get_height()))
        if obj is None:
            draw_wrapped(surface, "Zone secured. Walk through the exit gate (east)." if total else
                         "Walk through the exit gate (east).",
                         pygame.Rect(rect.x + 12, rect.y + 52, rect.width - 24, 60), 17, theme.color("ok"))
        else:
            done = len(st.done)
            y = draw_wrapped(surface, obj["title"], pygame.Rect(rect.x + 12, rect.y + 50, rect.width - 24, 44), 17,
                             theme.color("amber"))
            draw_wrapped(surface, obj.get("desc", ""), pygame.Rect(rect.x + 12, y + 2, rect.width - 24,
                                                                    rect.bottom - y - 12), 14, theme.color("text"))
            bar = pygame.Rect(rect.x + 12, rect.bottom - 7, rect.width - 24, 3)
            pygame.draw.rect(surface, (30, 40, 60), bar)
            pygame.draw.rect(surface, zone.accent, (bar.x, bar.y, int(bar.width * done / max(1, total)), 3))

    def _clock(self, surface) -> None:
        st = self.state
        w = surface.get_width()
        rect = pygame.Rect(w - 404, 12, 390, 92)
        flash = self.breach_flash > 0 and int(self.time * 8) % 2 == 0
        self._box(surface, rect, theme.color("bad") if flash else None)
        app = self.app
        char = app.character(app.run.character)
        tier = app.assets.tier_for_zone(st.zone.index, char.id)
        face = app.assets.face(char.id, tier, char.palette, 72)
        fr = pygame.Rect(rect.x + 10, rect.y + 10, 72, 72)
        pygame.draw.rect(surface, (12, 18, 34), fr, border_radius=4)
        surface.blit(face, fr)
        pygame.draw.rect(surface, char.accent, fr, 2, border_radius=4)
        x = fr.right + 12
        surface.blit(rendered(font(16, bold=True), char.name.upper(), char.accent), (x, rect.y + 8))
        perk = rendered(font(13), f"Perk: {char.perk.name}", theme.color("dim"))
        surface.blit(perk, perk.get_rect(topright=(rect.right - 12, rect.y + 10)))
        breach = max(0.0, min(100.0, app.run.breach))
        label, style = ADVERSARY_LABEL.get(st.adversary.state, ("", "dim"))
        surface.blit(rendered(font(13, mono=True, bold=True), "BREACH CLOCK", theme.color("text")), (x, rect.y + 34))
        adv = rendered(font(13, mono=True, bold=True), f"LOCUST: {label}", theme.style_color(style))
        surface.blit(adv, adv.get_rect(topright=(rect.right - 12, rect.y + 34)))
        bar = pygame.Rect(x, rect.y + 56, rect.right - x - 12, 18)
        pygame.draw.rect(surface, (20, 26, 40), bar, border_radius=3)
        col = theme.color("ok") if breach < 50 else theme.color("warn") if breach < 80 else theme.color("bad")
        fill = pygame.Rect(bar.x, bar.y, int(bar.width * breach / 100), bar.height)
        pygame.draw.rect(surface, col, fill, border_radius=3)
        if st.adversary.state in ("active", "spreading", "alerted"):
            sx = bar.x + int((self.time * 60) % max(1, bar.width))
            pygame.draw.line(surface, (255, 255, 255), (sx, bar.y), (sx, bar.bottom), 1)
        for p in (25, 50, 75):
            px = bar.x + bar.width * p // 100
            pygame.draw.line(surface, (0, 0, 0), (px, bar.y), (px, bar.bottom), 1)
        pygame.draw.rect(surface, theme.color("panel_edge"), bar, 1, border_radius=3)
        if self.breach_flash > 0:
            seer = app.assets.cast_portrait("seer", 8, 52)
            if seer is not None:
                seer = seer.copy()
                seer.set_alpha(min(255, int(255 * min(1.0, self.breach_flash))))
                surface.blit(seer, seer.get_rect(midright=(rect.x - 8, rect.centery)))
        t = rendered(font(14, mono=True, bold=True), f"{breach:4.1f}%", (255, 255, 255))
        surface.blit(t, t.get_rect(center=bar.center))

    def _minimap(self, surface) -> None:
        scene = self.scene
        tmap, fog = scene.map, scene.fog
        if self._mini_version != fog.version:
            small = pygame.Surface((tmap.width, tmap.height), pygame.SRCALPHA)
            small.fill((0, 0, 0, 0))
            acc = tuple(c // 2 for c in scene.state.zone.accent)
            for y in range(tmap.height):
                row, ex = tmap.tiles[y], fog.explored[y]
                for x in range(tmap.width):
                    if not ex[x]:
                        continue
                    t = row[x]
                    if t == FLOOR:
                        small.set_at((x, y), (40, 54, 84, 255))
                    elif t == BUS:
                        small.set_at((x, y), (*acc, 255))
                    elif t == RACK:
                        small.set_at((x, y), (200, 220, 255, 255))
                    elif t == GATE:
                        small.set_at((x, y), (255, 190, 60, 255))
            self._mini = pygame.transform.scale(small, (tmap.width * MINI_SCALE, tmap.height * MINI_SCALE))
            self._mini_version = fog.version
        w = surface.get_width()
        mw, mh = self._mini.get_size()
        mw = min(mw, 390)
        rect = pygame.Rect(w - 14 - mw - 8, 112, mw + 8, mh + 8)
        self._box(surface, rect)
        px = scene.player.x / TILE * MINI_SCALE
        off = max(0, min(px - mw / 2, self._mini.get_width() - mw))
        surface.blit(self._mini, (rect.x + 4, rect.y + 4), pygame.Rect(off, 0, mw, mh))
        blink = int(self.time * 3) % 2 == 0
        for nv in scene.node_views:
            nx = rect.x + 4 + nv.x / TILE * MINI_SCALE - off
            ny = rect.y + 4 + nv.y / TILE * MINI_SCALE
            if rect.x < nx < rect.right and scene.fog.is_explored(int(nv.x // TILE), int(nv.y // TILE)):
                corrupt = self.state.adversary.corruption.get(nv.id, 0) > 0.02
                col = theme.color("corrupt") if corrupt else theme.color("ok") if nv.done else theme.color("amber")
                pygame.draw.circle(surface, col, (int(nx), int(ny)), 3)
        ox = rect.x + 4 + scene.oracle.x / TILE * MINI_SCALE - off
        if rect.x < ox < rect.right:
            pygame.draw.circle(surface, (0, 220, 255), (int(ox), int(rect.y + 4 + scene.oracle.y / TILE * MINI_SCALE)), 2)
        if blink:
            pygame.draw.circle(surface, theme.accent, (int(rect.x + 4 + px - off),
                                                       int(rect.y + 4 + scene.player.y / TILE * MINI_SCALE)), 3)

    def _toolbar(self, surface) -> None:
        w, h = surface.get_size()
        want = relevant_tool(self.state.current)
        f = font(14, bold=True)
        bw, gap = 128, 6
        total = len(TOOLS) * bw + (len(TOOLS) - 1) * gap
        x = (w - total) // 2
        y = h - 42
        self.tool_rects = {}
        pulse = 0.5 + 0.5 * math.sin(self.time * 5)
        mouse = pygame.mouse.get_pos()
        for name, key, label in TOOLS:
            r = pygame.Rect(x, y, bw, 32)
            self.tool_rects[name] = r
            hot = name == want
            surface.blit(translucent(r.size, (*theme.accent, int(40 + 60 * pulse)) if hot else (6, 10, 22, 215)), r)
            edge = theme.accent if hot or r.collidepoint(mouse) else theme.color("panel_edge")
            pygame.draw.rect(surface, edge, r, 2 if hot else 1, border_radius=4)
            k = rendered(f, f"[{key}]", theme.accent if not hot else (255, 255, 255))
            t = rendered(f, label, theme.color("text"))
            surface.blit(k, (r.x + 8, r.centery - k.get_height() // 2))
            surface.blit(t, (r.x + 14 + k.get_width(), r.centery - t.get_height() // 2))
            x += bw + gap

    def _toasts(self, surface) -> None:
        w = surface.get_width()
        y = 156
        f = font(17, bold=True)
        for text, style, left, total in self.toasts:
            alpha = min(1.0, left / 0.5, (total - left) / 0.15 + 0.2)
            t = rendered(f, text, theme.style_color(style) if style != "normal" else theme.color("text")).copy()
            r = t.get_rect(midtop=(w // 2, y)).inflate(26, 12)
            bg = pygame.Surface(r.size, pygame.SRCALPHA)
            bg.fill((6, 10, 22, int(225 * alpha)))
            surface.blit(bg, r)
            edge = theme.style_color(style) if style != "normal" else theme.accent
            pygame.draw.rect(surface, edge, r, 1, border_radius=4)
            t.set_alpha(int(255 * alpha))
            surface.blit(t, t.get_rect(center=r.center))
            y += r.height + 6
