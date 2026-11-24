"""Pick an operative: the analysts stand on a turning carousel and the one in front fills the frame."""

from __future__ import annotations

import math

import pygame

from game.art import effects
from game.characters.unlock import is_unlocked
from game.engine import config
from game.engine.scene import Scene
from game.scenes.title import spot_rect
from game.ui import theme
from game.ui.dialogue import DialogueBox
from game.ui.panels.base import draw_wrapped
from game.ui.text import font, glow_text

PERK_DETAIL = {
    "steady_hand": "40% chance a premature action doesn't tip off VELVET LOCUST. Each correct "
                   "response slows the Breach Clock (x0.9).",
    "flag_sense": "Spots pivot tips in the terminal and a bonus CTF cache in every zone (+25 pts each).",
    "pattern_breaker": "Each piece of evidence you log pulls the Breach Clock back by 2 and, when the "
                       "file has one, shows its weak point.",
}
DEFAULT_SPOTS = {"frame": [0.29, 0.22, 0.42, 0.48], "left_pad": [0.07, 0.75, 0.28, 0.074],
                 "right_pad": [0.65, 0.75, 0.28, 0.074], "front": [0.5, 0.85]}
TURN_TIME = 0.35
FRONT_HEIGHT = 0.5  # fractions of the screen height
SIDE_HEIGHT = 0.4
SIDE_LIGHT = 0.6
RING_SCALE = 0.82
UNLOCK_HINT = "Finish the hunt once, or clear every Case File."
_PADS: dict = {}


def _ease(t: float) -> float:
    return 1 - (1 - t) ** 3


def _pad_glow(surface: pygame.Surface, rect: pygame.Rect, painted: bool) -> tuple[pygame.Rect, pygame.Surface]:
    """Pull the paint colour out of a platform on ``surface``; return its glow as a grey mask to re-tint."""
    area = rect.inflate(int(rect.width * 0.3), int(rect.height * 1.6)).clip(surface.get_rect())
    glow = pygame.Surface(area.size)
    cx, cy = rect.centerx - area.x, rect.centery - area.y
    if not painted:
        ring = pygame.Rect(0, 0, rect.width, rect.height)
        ring.center = (cx, cy)
        pygame.draw.ellipse(glow, (50, 50, 50), ring)
        pygame.draw.ellipse(glow, (230, 230, 230), ring, 4)
        return area, glow
    rx, ry = rect.width * 0.62, rect.height * 1.25
    for y in range(area.height):
        dy = ((y - cy) / ry) ** 2
        if dy >= 1.69:
            continue
        for x in range(area.width):
            weight = min(1.0, (1.3 - math.sqrt(((x - cx) / rx) ** 2 + dy)) / 0.3)
            if weight <= 0:
                continue
            pos = (area.x + x, area.y + y)
            r, g, b, _ = surface.get_at(pos)
            low = min(r, g, b)
            chroma = max(r, g, b) - low
            if not chroma:
                continue
            surface.set_at(pos, (round(r - (r - low) * weight), round(g - (g - low) * weight),
                                 round(b - (b - low) * weight)))
            v = round(chroma * weight)
            glow.set_at((x, y), (v, v, v))
    return area, glow


def _tint(surface: pygame.Surface, area: pygame.Rect, glow: pygame.Surface, color, gain: float = 1.0) -> None:
    tinted = glow.copy()
    tinted.fill(tuple(min(255, round(c * gain)) for c in color[:3]), special_flags=pygame.BLEND_RGB_MULT)
    surface.blit(tinted, area, special_flags=pygame.BLEND_RGB_ADD)


class CharacterSelectScene(Scene):
    def on_enter(self, **kwargs) -> None:
        app = self.app
        app.audio.stop_music()
        self.time = 0.0
        self.mode = kwargs.get("mode", "campaign")
        self.dialogue = DialogueBox(app)
        self.confirmed = False
        self.flash = 0.0
        self.chars = app.characters
        self.index = 0
        self.target = 0  # never wrapped, so going past the last analyst keeps turning the same way
        self.pos = 0.0
        self.turn_from = 0.0
        self.turn_t = 1.0
        self._layout()
        self._figures()
        self.hits: list[tuple[int, pygame.Rect]] = []
        self._place_hits()
        theme.set_accent(self.char.accent)

    def _layout(self) -> None:
        app = self.app
        bg = app.assets.background("character_select", (config.WIDTH, config.HEIGHT), "cover")
        spots = app.assets.hotspots("character_select")
        if bg.placeholder or "frame" not in spots:
            spots = DEFAULT_SPOTS
        self.placeholder = bg.placeholder
        self.frame = spot_rect(bg, spots["frame"])
        pads = [spot_rect(bg, spots["left_pad"]), spot_rect(bg, spots["right_pad"])]
        self.front = bg.point(*spots["front"])
        key = (app.assets.section("backgrounds").get("character_select"), bg.placeholder,
               tuple(tuple(r) for r in pads))
        if key not in _PADS:
            surface = bg.surface.copy()
            _PADS[key] = (surface, [_pad_glow(surface, r, not bg.placeholder) for r in pads])
        self.bg, self.pads = _PADS[key]
        area, glow = self.pads[0]
        ring = pygame.transform.smoothscale(glow, (round(area.width * RING_SCALE), round(area.height * RING_SCALE)))
        self.ring = (ring.get_rect(center=self.front), ring)

        n = max(1, len(self.chars))
        self.step = 360 / n
        side = math.radians(90 - self.step)
        side_y = (pads[0].centery + pads[1].centery) / 2
        self.cx = (pads[0].centerx + pads[1].centerx) / 2
        self.rx = (pads[1].centerx - pads[0].centerx) / 2 / max(0.2, math.cos(side))
        self.ry = (self.front[1] - side_y) / max(0.2, 1 - math.sin(side))
        self.cy = self.front[1] - self.ry
        side_depth = min(0.9, (math.sin(side) + 1) / 2)
        self.front_h = FRONT_HEIGHT * config.HEIGHT
        self.back_h = (SIDE_HEIGHT * config.HEIGHT - self.front_h * side_depth) / (1 - side_depth)
        self.back_light = (SIDE_LIGHT - side_depth) / (1 - side_depth)

    def _figures(self) -> None:
        app = self.app
        self.figures: dict[str, pygame.Surface] = {}
        self._sized: dict = {}
        for c in self.chars:
            tier = app.assets.tier_for_zone(0, c.id)
            art = None
            if not is_unlocked(app, c.id):
                art = app.assets.image(app.assets.character_entry(c.id, tier).get("locked_image"))
                if art is not None:
                    art = art.subsurface(art.get_bounding_rect())
                else:
                    art = app.assets.cutout(c.id, tier, c.palette).copy()
                    art.fill((22, 22, 28), special_flags=pygame.BLEND_RGB_MULT)
            if art is None:
                art = app.assets.cutout(c.id, tier, c.palette)
            scale = self.front_h / art.get_height()
            self.figures[c.id] = pygame.transform.smoothscale(
                art, (max(1, round(art.get_width() * scale)), round(self.front_h)))

    @property
    def char(self):
        return self.chars[self.index]

    def _angle(self, i: int) -> float:
        return 90 - self.step * (i - self.pos)

    def _placements(self) -> list[tuple[float, int, float, float, float, float]]:
        """(depth, index, x, feet y, height, light) for every analyst, farthest first."""
        out = []
        for i in range(len(self.chars)):
            a = math.radians(self._angle(i))
            depth = (math.sin(a) + 1) / 2
            out.append((depth, i, self.cx + self.rx * math.cos(a), self.cy + self.ry * math.sin(a),
                        self.back_h + (self.front_h - self.back_h) * depth,
                        self.back_light + (1 - self.back_light) * depth))
        out.sort(key=lambda p: p[0])
        return out

    def _place_hits(self) -> None:
        self.hits = []
        for _, i, x, y, h, _ in reversed(self._placements()):
            w = self.figures[self.chars[i].id].get_width() * h / self.front_h
            self.hits.append((i, pygame.Rect(round(x - w / 2), round(y - h), round(w), round(h))))

    def _figure(self, i: int, h: float, light: float) -> pygame.Surface:
        c = self.chars[i]
        key = (c.id, round(h), round(light * 24))
        if key not in self._sized:
            if len(self._sized) > 96:
                self._sized.clear()
            src = self.figures[c.id]
            img = pygame.transform.smoothscale(
                src, (max(1, round(src.get_width() * h / src.get_height())), max(1, round(h))))
            if light < 0.99:
                v = round(255 * light)
                img.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
            self._sized[key] = img
        return self._sized[key]

    def _color_at(self, angle: float) -> tuple[int, int, int]:
        """Accent of whoever stands at ``angle``, blended while they turn past it."""
        mix = [0.0, 0.0, 0.0]
        for i, c in enumerate(self.chars):
            off = (self._angle(i) - angle + 180) % 360 - 180
            weight = max(0.0, 1 - abs(off) / self.step)
            for k in range(3):
                mix[k] += c.accent[k] * weight
        return tuple(min(255, round(v)) for v in mix)

    def turn(self, delta: int) -> None:
        if not delta or len(self.chars) < 2:
            return
        self.turn_from = self.pos
        self.target += delta
        self.turn_t = 0.0
        self.index = self.target % len(self.chars)
        self.app.audio.play("move")
        theme.set_accent(self.char.accent)

    def select(self, i: int) -> None:
        n = len(self.chars)
        delta = (i - self.index) % n
        self.turn(delta - n if delta > n / 2 else delta)

    def confirm(self) -> None:
        if not is_unlocked(self.app, self.char.id):
            self.app.audio.play("error")
            return
        self.confirmed = True
        self.flash = 1.0
        self.app.audio.play("confirm")
        c = self.char
        line = self.app.dialogue.line("select", c.id) or {"speaker": "player", "text": c.select_line}
        if self.mode == "custom":
            self.app.state["analyst"] = c.id
            self.dialogue.say([line], on_done=lambda: self.app.scenes.switch("challenges"))
            return
        self.app.start_run(c.id)
        self.dialogue.say([line], on_done=lambda: self.app.scenes.switch("zone", zone=0))

    def handle_event(self, event) -> None:
        if self.dialogue.handle_event(event):
            return
        if self.confirmed:
            return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.turn(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_TAB):
                self.turn(1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.confirm()
            elif event.key == pygame.K_ESCAPE:
                self.app.audio.play("back")
                self.app.scenes.switch("title", menu=True)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in self.hits:
                if rect.collidepoint(event.pos):
                    if i == self.index and self.turn_t >= 1:
                        self.confirm()
                    else:
                        self.select(i)
                    return

    def update(self, dt: float) -> None:
        self.time += dt
        self.flash = max(0.0, self.flash - dt * 1.5)
        if self.turn_t < 1:
            self.turn_t = min(1.0, self.turn_t + dt / TURN_TIME)
            self.pos = self.turn_from + (self.target - self.turn_from) * _ease(self.turn_t)
            self._place_hits()
        self.dialogue.update(dt)

    def draw(self, surface) -> None:
        w, h = surface.get_size()
        surface.blit(self.bg, (0, 0))
        for (area, glow), angle in zip(self.pads, (90 + self.step, 90 - self.step)):
            _tint(surface, area, glow, self._color_at(angle))
        gain = (0.75 + 0.25 * effects.pulse(self.time, 1.2)) * (1 + self.flash)
        _tint(surface, *self.ring, self._color_at(90), gain)
        if self.placeholder:
            effects.glow_rect(surface, self.frame, self.char.accent, width=2, radius=10, layers=4, alpha=80)
            head = glow_text("SELECT OPERATIVE", font(30, bold=True), (240, 245, 255), self.char.accent, 5)
            surface.blit(head, head.get_rect(center=(w // 2, int(h * 0.1))))
            hint = font(15, mono=True).render("<- -> choose    ENTER confirm    ESC back", True, theme.color("dim"))
            surface.blit(hint, hint.get_rect(midbottom=(w // 2, h - 8)))
        self._info(surface)
        for _, i, x, y, fh, light in self._placements():
            img = self._figure(i, fh, light)
            surface.blit(img, img.get_rect(midbottom=(round(x), round(y))))
        self.dialogue.draw(surface)

    def _info(self, surface) -> None:
        c = self.char
        f = self.frame
        locked = not is_unlocked(self.app, c.id)
        if self.mode == "custom":
            banner = font(13, bold=True).render("CASE FILES  ·  every analyst plays this mode the same way",
                                                True, theme.color("amber"))
            surface.blit(banner, banner.get_rect(midbottom=(f.centerx, f.top - 4)))
        layer = pygame.Surface(f.size, pygame.SRCALPHA)
        name = glow_text(c.name.upper(), font(34, bold=True), c.accent, radius=5)
        layer.blit(name, name.get_rect(midtop=(f.width // 2, 20)))
        half = self.figures[c.id].get_width() // 2 + 14
        col_w = max(80, f.width // 2 - half - 18)
        left = pygame.Rect(18, 84, col_w, f.height - 96)
        right = pygame.Rect(f.width - 18 - col_w, 84, col_w, f.height - 96)
        y = draw_wrapped(layer, c.role, left, 14, theme.color("dim"), mono=True) + 12
        if locked:
            layer.blit(font(14, bold=True).render("LOCKED", True, c.accent), (left.x, y))
            draw_wrapped(layer, UNLOCK_HINT, pygame.Rect(left.x, y + 22, col_w, left.bottom - y - 22),
                         15, theme.color("amber"))
            draw_wrapped(layer, "File sealed.", right, 15, theme.color("dim"))
        else:
            layer.blit(font(14, bold=True).render("PERK", True, c.accent), (left.x, y))
            layer.blit(font(17, bold=True).render(c.perk.name, True, theme.color("amber")), (left.x, y + 18))
            draw_wrapped(layer, PERK_DETAIL.get(c.perk.id, c.perk.description),
                         pygame.Rect(left.x, y + 44, col_w, left.bottom - y - 44), 14)
            draw_wrapped(layer, c.bio, right, 15, theme.color("text"))
            best = self.app.saves.load_profile().get("best", {}).get(c.id)
            if best:
                t = font(13, mono=True).render(f"BEST: {best['rank']} ({best['score']})", True,
                                               theme.color("amber"))
                layer.blit(t, t.get_rect(bottomright=(right.right, right.bottom)))
        layer.set_alpha(round(255 * _ease(self.turn_t)))
        surface.blit(layer, f)
