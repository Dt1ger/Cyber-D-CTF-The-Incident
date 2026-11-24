from __future__ import annotations

import os
from pathlib import Path

import pygame

from game.art import effects
from game.art.icons import apply_window_icon
from game.art.loader import Assets
from game.audio.synth import Audio
from game.characters.character import Character, load_characters
from game.engine import config
from game.engine.input import Input
from game.engine.scene import SceneManager
from game.engine.settings import Settings
from game.systems.attack import AttackDB
from game.systems.campaign import RunState
from game.systems.dialogue_db import DialogueDB
from game.systems.save import SaveStore
from game.ui import theme
from game.ui.text import set_text_scale


class App:
    def __init__(self, start_scene: str = "splash", use_assets: bool = True,
                 snapshot: Path | None = None, frames: int | None = None,
                 saves_dir: Path | None = None, **scene_args):
        pygame.init()
        apply_window_icon()
        offscreen = os.environ.get("SDL_VIDEODRIVER") == "dummy"
        flags = 0 if offscreen else pygame.SCALED | pygame.RESIZABLE
        try:
            self.screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT), flags,
                                                  vsync=0 if offscreen else 1)
        except pygame.error:
            self.screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT))
        pygame.display.set_caption(f"{config.TITLE} - {config.SUBTITLE}")
        pygame.key.stop_text_input()
        self.clock = pygame.time.Clock()
        self.input = Input()
        self.saves = SaveStore(Path(saves_dir) if saves_dir else config.SAVES_DIR)
        self.settings = Settings.load(self.saves.settings)
        self.apply_settings()
        self.audio = Audio(self.settings)
        self.assets = Assets(config.ASSETS_DIR, use_files=use_assets)
        self.characters: list[Character] = load_characters(config.DATA_DIR / "characters.json")
        self.attack = AttackDB.load(config.DATA_DIR / "attack_techniques.json")
        self.dialogue = DialogueDB(config.DATA_DIR / "dialogue")
        self.run: RunState | None = None
        self.state: dict = {}
        self.snapshot = snapshot
        self.max_frames = frames if frames is not None else (90 if snapshot else None)
        self.running = True

        if "character" in scene_args and start_scene not in ("gallery", "character_select"):
            self.run = RunState(character=str(scene_args.pop("character")))
            if "zone" in scene_args:
                self.run.zone = int(scene_args["zone"])

        from game.scenes import register_all
        self.scenes = SceneManager(self)
        register_all(self.scenes)
        self.scenes.switch(start_scene, fade=False, **scene_args)

    def character(self, char_id: str) -> Character:
        return next((c for c in self.characters if c.id == char_id), self.characters[0])

    def apply_settings(self) -> None:
        set_text_scale(self.settings.text_scale)
        theme.set_colorblind(self.settings.colorblind)
        pygame.mouse.set_visible(not self.settings.keyboard_only)

    def save_settings(self) -> None:
        self.settings.save(self.saves.settings)

    def start_run(self, char_id: str) -> None:
        self.run = RunState(character=char_id)
        theme.set_accent(self.character(char_id).accent)
        self.saves.save_run(self.run.to_dict())

    def continue_run(self) -> bool:
        data = self.saves.load_run()
        if not data:
            return False
        try:
            self.run = RunState.from_dict(data)
        except (KeyError, TypeError, ValueError):
            return False
        theme.set_accent(self.character(self.run.character).accent)
        return True

    def quit(self) -> None:
        self.running = False

    def run_loop(self) -> None:
        frame = 0
        while self.running:
            dt = min(self.clock.tick(config.FPS) / 1000.0, 0.05)
            self.input.begin_frame()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                    continue
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F8:
                    self.settings.muted = not self.settings.muted
                    self.audio.apply_volume()
                    self.save_settings()
                    continue
                self.input.process(event)
                self.scenes.handle_event(event)
            self.scenes.update(dt)
            self.screen.fill(config.BG)
            self.scenes.draw(self.screen)
            if self.settings.scanlines:
                self.screen.blit(effects.scanlines(self.screen.get_size()), (0, 0))
            pygame.display.flip()
            frame += 1
            if self.max_frames is not None and frame >= self.max_frames:
                if self.snapshot:
                    self.snapshot.parent.mkdir(parents=True, exist_ok=True)
                    pygame.image.save(self.screen, str(self.snapshot))
                    print(f"[app] snapshot saved to {self.snapshot}")
                self.quit()
        pygame.quit()
