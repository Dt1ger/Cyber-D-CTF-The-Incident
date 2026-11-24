"""A playable zone: walk the Grid, investigate hosts, and work the hunt tools."""

from __future__ import annotations

import math
import random

import pygame

from game.art.effects import translucent
from game.engine import config
from game.engine.camera import Camera
from game.engine.scene import Scene
from game.entities.npc import CacheView, NodeView, Oracle
from game.entities.player import Player
from game.systems.campaign import RunState
from game.systems.terminal import TerminalSession
from game.systems.zone_state import ZoneState
from game.ui import theme
from game.ui.dialogue import DialogueBox
from game.ui.hud import HUD, TOOL_KEYS
from game.ui.panels import TOOL_PANELS, EvidencePanel, InfoPanel
from game.ui.text import font, glow_text, rendered
from game.world.atmosphere import Atmosphere
from game.world.render import MapRenderer
from game.world.tilemap import TILE, Fog, generate
from game.world.zone_data import debrief_index, load_zone

REACH = 84
TEXT_PANELS = ("terminal", "journal")


class ZoneScene(Scene):
    def on_enter(self, zone: int | None = None, **kwargs) -> None:
        app = self.app
        if getattr(app, "run", None) is None:
            app.run = RunState(character=kwargs.get("character", "sasha"))
        run = app.run
        idx = run.zone if zone is None else int(zone)
        if idx >= debrief_index():
            app.scenes.switch("debrief")
            return
        run.zone = idx
        run.reset_zone(idx)
        app.saves.save_run(run.to_dict())

        app.audio.play_music("game")
        self.char = app.character(run.character)
        theme.set_accent(self.char.accent)
        self.zone = load_zone(idx)
        self.state = ZoneState(self.zone, run, self.char, app.attack)
        self.terminal = TerminalSession(self.state)
        puzzle = self.zone.puzzle if self.state.flag_sense else None
        self.map = generate(self.zone.nodes, self.zone.map_seed, with_cache=bool(puzzle))
        self.renderer = MapRenderer(self.map, self.zone.accent, app.assets, self.zone.id)
        tier = app.assets.tier_for_zone(idx, self.char.id)
        self.player = Player(app.assets.sprites(self.char.id, tier, palette=self.char.palette), self.map.start)
        self.oracle = Oracle(self.map.oracle, app.assets.cast_portrait("oracle", 0, height=150))
        self.node_views = [NodeView(n, self.map.node_tiles[n["id"]]) for n in self.zone.nodes
                           if n["id"] in self.map.node_tiles]
        self.cache = CacheView(self.map.cache) if puzzle and self.map.cache else None
        if self.cache:
            self.cache.solved = self.state.puzzle_solved
        self.camera = Camera((config.WIDTH, config.HEIGHT), self.map.pixel_size)
        self.camera.snap(self.player.x, self.player.y)
        self.fog = Fog(self.map)
        self.fog.update(*self.player.tile)
        self.backdrop = app.assets.optional_background(self.zone.id, (config.WIDTH, config.HEIGHT))
        self.atmosphere = None if self.backdrop else Atmosphere(self.zone.id, self.zone.accent)
        self.dialogue = DialogueBox(app)
        self.hud = HUD(self)
        self.panel = None
        self.timeline_orders: dict[str, list[str]] = {}
        self.deferred: list[list[str]] = []
        self.thoughts_seen: set[str] = set()
        self.pending_thought: str | None = None
        self.click_target = None
        self.banner = 3.2
        self.flag_banner = 0.0
        self._banner_parts = {}
        self.exiting = False
        self.time = 0.0
        self.idle_i = random.Random(idx).randrange(5)
        self.intro_started = False

    # Helpers ---------------------------------------------------------------

    def say(self, keys: list[str], on_done=None) -> None:
        keys = [k for k in keys if k]
        if keys or on_done:
            self.dialogue.say_keys(keys, on_done)

    def defer(self, keys: list[str]) -> None:
        if keys:
            self.deferred.append(list(keys))

    def open_tool(self, name: str) -> None:
        if self.panel is not None and self.panel.name == name:
            self.close_panel()
            return
        self.close_panel(silent=True)
        self.panel = TOOL_PANELS[name](self)
        self.state.opened_panel(name)
        self.app.audio.play("confirm")

    def close_panel(self, silent: bool = False) -> None:
        if self.panel is None:
            return
        if self.panel.name in TEXT_PANELS:
            pygame.key.stop_text_input()
        if not silent and not self.panel.closed:
            self.app.audio.play("back")
        self.panel = None
        if self.pending_thought:
            self.defer([self.pending_thought])
            self.pending_thought = None

    def interactable(self):
        px, py = self.player.x, self.player.y
        best, best_d = None, REACH
        for nv in self.node_views:
            d = math.hypot(nv.x - px, nv.y - py)
            if d < best_d:
                best, best_d = ("node", nv), d
        d = math.hypot(self.oracle.x - px, self.oracle.y - py)
        if d < best_d:
            best, best_d = ("oracle", self.oracle), d
        if self.cache:
            d = math.hypot(self.cache.x - px, self.cache.y - py)
            if d < best_d:
                best, best_d = ("cache", self.cache), d
        if best is None and not self.map.gate_open:
            for gx, gy in self.map.gate:
                if math.hypot((gx + 0.5) * TILE - px, (gy + 0.5) * TILE - py) < REACH:
                    return ("gate", None)
        return best

    def prompt_for(self, target) -> str | None:
        if target is None:
            return None
        kind, obj = target
        if kind == "node":
            return f"[E] Investigate {obj.node['host']}"
        if kind == "oracle":
            return "[E] Talk to Oracle"
        if kind == "cache":
            return "[E] Open CTF cache" if not obj.solved else "[E] CTF cache (cracked)"
        if kind == "gate":
            return "Exit gate sealed: finish this zone's objectives"
        return None

    def interact(self, target) -> None:
        kind, obj = target
        st = self.state
        if kind == "node":
            st.visit_node(obj.id)
            obj.investigated = True
            self.player.interact()
            self.app.audio.play("blip")
            self.close_panel(silent=True)
            self.panel = EvidencePanel(self, obj.node)
            key = f"z{self.zone.index}_node_{obj.id}"
            if key not in self.thoughts_seen and self.app.dialogue.line(key, self.char.id):
                self.thoughts_seen.add(key)
                self.pending_thought = key
        elif kind == "oracle":
            first = not st.talked
            st.talk_oracle()
            self.oracle.has_news = False
            talk = self.zone.dialogue.get("talk", [])
            if first and talk:
                self.say(talk)
            else:
                self.dialogue.say(self.oracle_lines())
        elif kind == "cache":
            self.open_cache()
        elif kind == "gate":
            self.app.audio.play("error")
            self.hud.toast("Gate sealed. Finish the objectives first.", "warn")

    def oracle_lines(self) -> list[dict]:
        obj = self.state.current
        if obj is None:
            return [{"speaker": "oracle", "text": "This zone is secure. The exit gate is east, past the last host."}]
        idle = self.app.dialogue.sequence("oracle_idle")
        lines = [{"speaker": "oracle", "text": f"Right now: {obj['title']}. {obj.get('desc', '')}"}]
        if idle:
            self.idle_i = (self.idle_i + 1) % len(idle)
            lines.append({"speaker": "oracle", "text": idle[self.idle_i] + "  (Press H any time for a hint.)"})
        return lines

    def open_cache(self) -> None:
        pz = self.zone.puzzle
        lines = [(pz.get("clue", ""), "normal"), ("", "normal"),
                 ("CIPHERTEXT", "header"), (pz["ciphertext"], "accent"), ("", "normal")]
        if pz.get("key"):
            lines.append((f"Key: {pz['key']}", "warn"))
        if self.state.puzzle_solved:
            lines.append(("Cracked. Nice work.", "ok"))
        else:
            lines.append(("Decode it in the terminal (T): decode <kind> cache  then  submit <flag>", "dim"))
        self.close_panel(silent=True)
        self.panel = InfoPanel(self, pz.get("title", "CTF Cache"), lines)
        self.panel.footer = "Enter / Esc close"
        self.app.audio.play("confirm")

    # Events from the rules ------------------------------------------------

    def process_events(self) -> None:
        for ev in self.state.drain():
            k = ev.kind
            if k == "objective_done":
                self.hud.toast(ev.text, "ok")
                self.app.audio.play("confirm")
            elif k == "evidence":
                self.hud.toast(ev.text, "accent", 2.6)
            elif k == "dialogue":
                self.defer(ev.data.get("keys", []))
            elif k == "zone_complete":
                self.map.gate_open = True
                self.hud.toast(ev.text, "ok", 5.0)
                self.app.audio.play("success")
                self.defer(["zone_complete"])
            elif k == "tipoff":
                self.hud.toast(ev.text, "bad", 5.0)
                self.hud.breach_flash = 2.0
                self.app.audio.play("alarm")
                if self.app.settings.screen_shake:
                    self.camera.shake(16, 0.6)
                self.defer(["seer_tipoff", "tipoff"])
            elif k == "dataloss":
                self.hud.toast(ev.text, "bad", 6.0)
                self.hud.breach_flash = 3.0
                self.app.audio.play("alarm")
                if self.app.settings.screen_shake:
                    self.camera.shake(22, 0.9)
                self.defer(["seer_dataloss", "dataloss"])
            elif k == "spread":
                self.hud.toast(ev.text, "warn")
                self.app.audio.play("glitch")
            elif k == "mapped":
                self.hud.toast(ev.text, "accent")
            elif k == "flag":
                self.flag_banner = 4.0
                self.app.audio.play("flag")
            elif k == "puzzle":
                self.hud.toast(ev.text, "ok", 4.0)
                self.app.audio.play("flag")
                if self.cache:
                    self.cache.solved = True

    # Scene hooks ---------------------------------------------------------

    def handle_event(self, event) -> None:
        if self.exiting and not self.dialogue.active:
            return
        if self.dialogue.handle_event(event):
            return
        if self.panel is not None:
            if (event.type == pygame.KEYDOWN and self.panel.name not in TEXT_PANELS and event.key in TOOL_KEYS
                    and TOOL_KEYS[event.key] != self.panel.name and self.panel.name in TOOL_PANELS):
                self.open_tool(TOOL_KEYS[event.key])
                return
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.panel.name in TOOL_PANELS):
                tool = self.hud.tool_at(event.pos)
                if tool and not self.panel.frame(self.app.screen).collidepoint(event.pos):
                    self.open_tool(tool)
                    return
            self.panel.handle_event(event)
            if self.panel is not None and self.panel.closed:
                self.close_panel(silent=True)
            return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.app.audio.play("back")
                self.app.scenes.push("pause")
            elif event.key in (pygame.K_e, pygame.K_RETURN, pygame.K_KP_ENTER):
                target = self.interactable()
                if target:
                    self.interact(target)
            elif event.key in TOOL_KEYS:
                self.open_tool(TOOL_KEYS[event.key])
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            tool = self.hud.tool_at(event.pos)
            if tool:
                self.open_tool(tool)
                return
            wx, wy = self.camera.to_world(*event.pos)
            self.click_target = self.target_at(wx, wy)
            if self.click_target and self.click_target[0] != "gate":
                obj = self.click_target[1]
                self.player.go_to(obj.x, obj.y + TILE, self.map)
            else:
                self.click_target = None
                self.player.go_to(wx, wy, self.map)

    def target_at(self, wx: float, wy: float):
        for nv in self.node_views:
            if abs(nv.x - wx) < 34 and -90 < wy - nv.y < 30:
                return ("node", nv)
        if abs(self.oracle.x - wx) < 40 and -100 < wy - self.oracle.y < 30:
            return ("oracle", self.oracle)
        if self.cache and math.hypot(self.cache.x - wx, self.cache.y - 16 - wy) < 30:
            return ("cache", self.cache)
        return None

    def update(self, dt: float) -> None:
        if not hasattr(self, "state"):
            return
        self.time += dt
        busy = self.dialogue.active or self.panel is not None or self.exiting
        if self.banner > 0:
            self.banner -= dt
            if self.banner <= 1.0 and not self.intro_started:
                self.intro_started = True
                self.say(self.zone.dialogue.get("intro", []))
        axis = (0, 0) if busy or self.banner > 1.0 else self.app.input.axis()
        self.player.update(dt, axis, self.map)
        if self.click_target and not self.player.path:
            kind, obj = self.click_target
            if math.hypot(obj.x - self.player.x, obj.y - self.player.y) < REACH + 10 and not busy:
                self.interact(self.click_target)
            self.click_target = None
        self.fog.update(*self.player.tile)
        self.camera.follow(self.player.x, self.player.y, dt)
        self.renderer.update(dt)
        self.oracle.update(dt)
        self.oracle.has_news = not self.state.talked
        for nv in self.node_views:
            nv.update(dt)
            ids = [e for e in nv.node.get("evidence", []) if e in self.zone.evidence]
            nv.done = nv.investigated and all(self.state.has_evidence(e) for e in ids)
        if self.cache:
            self.cache.update(dt)
        self.dialogue.update(dt)
        if self.panel is not None:
            self.panel.update(dt)
            if self.panel.closed:
                self.close_panel(silent=True)
        if not self.dialogue.active and self.intro_started and not self.exiting:
            self.state.update(dt)
        self.process_events()
        self.hud.update(dt)
        self.flag_banner = max(0.0, self.flag_banner - dt)
        if self.deferred and not self.dialogue.active and self.panel is None and not self.exiting:
            self.say(self.deferred.pop(0))
        if (self.map.gate_open and not self.exiting and self.map.gate
                and self.player.x > (self.map.gate[0][0] + 1) * TILE):
            self.exit_zone()

    def exit_zone(self) -> None:
        self.exiting = True
        self.close_panel(silent=True)
        self.deferred.clear()
        self.app.audio.play("success")
        self.say(self.zone.dialogue.get("outro", []), on_done=self.finish)

    def finish(self) -> None:
        run = self.app.run
        run.zone = self.zone.index + 1
        if run.zone >= debrief_index():
            run.finished = True
            self.app.saves.save_run(run.to_dict())
            self.app.scenes.switch("debrief")
        else:
            self.app.saves.save_run(run.to_dict())
            self.app.scenes.switch("zone", zone=run.zone)

    # Drawing -------------------------------------------------------------

    def draw(self, surface) -> None:
        if not hasattr(self, "state"):
            return
        if self.backdrop:
            surface.blit(self.backdrop.surface, self.backdrop.rect)
            surface.blit(translucent(surface.get_size(), (2, 4, 10, 200)), (0, 0))
        elif self.atmosphere:
            self.atmosphere.draw(surface, self.time)
        cam = self.camera.pos
        self.renderer.draw(surface, cam)
        self.renderer.draw_gate(surface, cam, self.map.gate_open, theme.color("ok"), theme.color("bad"))
        if self.map.gate:
            gx, gy = self.map.gate[0]
            sx, sy = self.camera.to_screen((gx + 0.5) * TILE, gy * TILE - 10)
            col = theme.color("ok") if self.map.gate_open else theme.color("bad")
            label = rendered(font(15, mono=True, bold=True), "EXIT  >>" if self.map.gate_open else "EXIT", col)
            surface.blit(label, label.get_rect(midbottom=(sx, sy)))
        drawables = [(nv.y, "node", nv) for nv in self.node_views]
        drawables.append((self.oracle.y, "oracle", self.oracle))
        if self.cache:
            drawables.append((self.cache.y, "cache", self.cache))
        drawables.append((self.player.y + 1, "player", self.player))
        corruption = self.state.adversary.corruption
        for _, kind, obj in sorted(drawables, key=lambda d: d[0]):
            if kind == "node":
                obj.draw(surface, self.camera, self.zone.accent, corruption.get(obj.id, 0.0))
            else:
                obj.draw(surface, self.camera)
        self.renderer.draw_fog(surface, cam, self.fog)

        busy = self.dialogue.active or self.panel is not None
        prompt = None if busy or self.banner > 1.0 else self.prompt_for(self.interactable())
        self.hud.draw(surface, prompt)
        if self.panel is not None:
            self.panel.draw(surface)
        self.dialogue.draw(surface)
        if self.banner > 0:
            self._banner(surface)
        if self.flag_banner > 0:
            self._flag(surface)

    def _faded(self, key, make, alpha: float) -> pygame.Surface:
        """A banner piece built once per zone; only its alpha changes from frame to frame."""
        surf = self._banner_parts.get(key)
        if surf is None:
            surf = self._banner_parts[key] = make()
        surf.set_alpha(int(255 * alpha))
        return surf

    @staticmethod
    def _band(width: int, height: int, rgba) -> pygame.Surface:
        band = pygame.Surface((width, height), pygame.SRCALPHA)
        band.fill(rgba)
        return band

    def _banner(self, surface) -> None:
        a = min(1.0, self.banner / 0.6, (3.2 - self.banner) / 0.4)
        w, h = surface.get_size()
        z = self.zone
        band = self._faded(("band", w), lambda: self._band(w, 170, (2, 4, 12, 220)), a)
        surface.blit(band, (0, h // 2 - 120))
        sub = self._faded("sub", lambda: font(18, mono=True).render(
            f"ZONE {z.index}  //  {z.phase}", True, theme.color("dim")), a)
        surface.blit(sub, sub.get_rect(center=(w // 2, h // 2 - 88)))
        title = self._faded("title", lambda: glow_text(z.name.upper(), font(52, bold=True), z.accent), a)
        surface.blit(title, title.get_rect(center=(w // 2, h // 2 - 40)))
        if z.lesson:
            les = self._faded("lesson", lambda: font(18).render(z.lesson, True, theme.color("text")), a)
            surface.blit(les, les.get_rect(center=(w // 2, h // 2 + 14)))

    def _flag(self, surface) -> None:
        w, h = surface.get_size()
        a = min(1.0, self.flag_banner / 0.6)
        band = self._faded(("flag_band", w), lambda: self._band(w, 130, (0, 0, 0, 210)), a)
        surface.blit(band, (0, h // 2 - 65))
        t = self._faded("captured", lambda: glow_text("FLAG CAPTURED", font(46, bold=True), (57, 255, 20)), a)
        surface.blit(t, t.get_rect(center=(w // 2, h // 2 - 18)))
        f = self._faded("flag", lambda: font(22, mono=True, bold=True).render(
            self.zone.flag or "", True, theme.color("amber")), a)
        surface.blit(f, f.get_rect(center=(w // 2, h // 2 + 30)))
