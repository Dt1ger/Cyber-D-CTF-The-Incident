from __future__ import annotations

from game.engine.scene import SceneManager


def register_all(manager: SceneManager) -> None:
    from game.scenes.challenges import ChallengesScene
    from game.scenes.character_select import CharacterSelectScene
    from game.scenes.cinematic import CinematicScene
    from game.scenes.debrief import DebriefScene
    from game.scenes.gallery import GalleryScene
    from game.scenes.overlays import HowToPlayScene, PauseScene, SettingsScene
    from game.scenes.splash import SplashScene
    from game.scenes.title import TitleScene
    from game.scenes.zone import ZoneScene

    manager.register("splash", SplashScene)
    manager.register("title", TitleScene)
    manager.register("cinematic", CinematicScene)
    manager.register("character_select", CharacterSelectScene)
    manager.register("challenges", ChallengesScene)
    manager.register("zone", ZoneScene)
    manager.register("debrief", DebriefScene)
    manager.register("pause", PauseScene)
    manager.register("settings", SettingsScene)
    manager.register("how_to_play", HowToPlayScene)
    manager.register("gallery", GalleryScene)
