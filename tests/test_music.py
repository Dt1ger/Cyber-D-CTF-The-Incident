"""Title music stays on the start screen. The hunt bed is quieter and keeps playing."""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

from game.audio.synth import GAME_BED, TRACKS, Audio
from game.engine.app import App
from game.systems.campaign import RunState
from game.world.zone_data import debrief_index


@pytest.fixture
def app(tmp_path):
    game = App(start_scene="splash", saves_dir=tmp_path)
    yield game
    pygame.quit()


def test_splash_is_silent_and_the_title_plays_hackers_free_reign(app):
    assert app.audio.track is None

    app.scenes.switch("title", fade=False)

    assert app.audio.track == "title"
    assert app.audio.gain == 1.0
    assert app.audio._file_music
    assert TRACKS["title"][0].name == "hackers_free_reign.wav"
    assert pygame.mixer.music.get_volume() == pytest.approx(app.settings.music)


def test_cinematic_and_character_select_stop_the_title_song(app):
    app.scenes.switch("title", fade=False)
    app.scenes.switch("cinematic", fade=False)
    assert app.audio.track is None

    app.scenes.switch("title", fade=False)
    app.scenes.switch("character_select", fade=False)
    assert app.audio.track is None
    assert not app.audio._file_music


def test_a_hunt_plays_hack_your_dreams_quietly_and_does_not_restart(app, monkeypatch):
    loads = []
    real_load = pygame.mixer.music.load

    def spy(path):
        loads.append(str(path))
        return real_load(path)

    monkeypatch.setattr(pygame.mixer.music, "load", spy)
    app.run = RunState(character="sasha", zone=1)
    app.scenes.switch("zone", fade=False, zone=1)

    assert app.audio.track == "game"
    assert app.audio.gain == GAME_BED
    assert GAME_BED < 1
    assert loads and loads[-1].endswith("hack_your_dreams.wav")
    assert pygame.mixer.music.get_volume() == pytest.approx(app.settings.music * GAME_BED, abs=0.01)
    started = len(loads)

    app.scenes.switch("zone", fade=False, zone=2)
    app.run.zone = debrief_index()
    app.scenes.switch("debrief", fade=False)

    assert len(loads) == started
    assert app.audio.track == "game"
    assert app.audio.gain == GAME_BED


def test_mute_silences_the_current_song(app):
    app.scenes.switch("title", fade=False)
    app.settings.muted = True
    app.audio.apply_volume()
    assert pygame.mixer.music.get_volume() == 0

    app.settings.muted = False
    app.audio.apply_volume()
    assert pygame.mixer.music.get_volume() == pytest.approx(app.settings.music)


def test_a_missing_song_falls_back_instead_of_crashing(tmp_path, monkeypatch):
    monkeypatch.setitem(TRACKS, "title", (tmp_path / "missing.wav", 1.0, 0))
    monkeypatch.setattr(Audio, "_play_pad", lambda self, fade: None)
    game = App(start_scene="title", saves_dir=tmp_path)
    try:
        assert game.audio.track == "title"
        assert not game.audio._file_music
    finally:
        pygame.quit()
