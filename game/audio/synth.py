"""Sound effects are synthesized. Music is streamed from local WAV files.

Hackers Free Reign plays on the title screen. Hack Your Dreams plays quietly
under a hunt. If a file is missing, or the mixer cannot start, the game falls
back to a soft synthesized pad or to silence.
"""

from __future__ import annotations

import math
import random
from array import array
from pathlib import Path

import pygame

from game.engine import config

RATE = 48000
# The hunt bed is this fraction of the music slider, so it stays behind the action.
GAME_BED = 0.34
TRACKS = {
    "title": (config.ASSETS_DIR / "audio" / "hackers_free_reign.wav", 1.0, 700),
    "game": (config.ASSETS_DIR / "audio" / "hack_your_dreams.wav", GAME_BED, 1600),
}


def _tone(freqs, duration: float, volume: float = 0.4, wave: str = "sine",
          attack: float = 0.005, release: float = 0.08, slide: float = 0.0) -> array:
    n = int(RATE * duration)
    out = array("h", [0]) * n
    if isinstance(freqs, (int, float)):
        freqs = [freqs]
    phase = [0.0] * len(freqs)
    rng = random.Random(3)
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / attack) if attack > 0 else 1.0
        env *= min(1.0, (duration - t) / release) if release > 0 else 1.0
        s = 0.0
        for k, f in enumerate(freqs):
            f = f * (1 + slide * t / duration)
            phase[k] += f / RATE
            p = phase[k] % 1.0
            if wave == "square":
                s += 1.0 if p < 0.5 else -1.0
            elif wave == "tri":
                s += 4 * abs(p - 0.5) - 1
            elif wave == "noise":
                s += rng.uniform(-1, 1)
            else:
                s += math.sin(2 * math.pi * p)
        out[i] = int(max(-1.0, min(1.0, s / len(freqs) * volume * env)) * 32767)
    return out


def _concat(*parts: array) -> array:
    out = array("h")
    for p in parts:
        out.extend(p)
    return out


def _ambient() -> array:
    """An 8-second dark pad loop: slow minor chord with a soft pulse."""
    seconds = 8.0
    n = int(RATE * seconds)
    out = array("h", [0]) * n
    chord = [55.0, 65.41, 82.41, 110.0]
    for i in range(n):
        t = i / RATE
        swell = 0.55 + 0.45 * math.sin(2 * math.pi * t / seconds)
        s = sum(math.sin(2 * math.pi * f * t + k) for k, f in enumerate(chord)) / len(chord)
        shimmer = 0.15 * math.sin(2 * math.pi * 440.0 * t) * max(0.0, math.sin(2 * math.pi * t / 2.0)) ** 8
        pulse = 0.2 * math.sin(2 * math.pi * 55 * t) * (1 if (t % 1.0) < 0.08 else 0)
        out[i] = int(max(-1.0, min(1.0, (s * swell * 0.5 + shimmer + pulse) * 0.35)) * 32767)
    return out


RECIPES = {
    "blip": lambda: _tone(880, 0.05, 0.25, "square", release=0.03),
    "move": lambda: _tone(660, 0.04, 0.18, "tri", release=0.03),
    "confirm": lambda: _concat(_tone(660, 0.06, 0.3, "square"), _tone(990, 0.09, 0.3, "square")),
    "back": lambda: _tone(440, 0.08, 0.25, "square", slide=-0.4),
    "error": lambda: _concat(_tone(220, 0.09, 0.3, "square"), _tone(165, 0.14, 0.3, "square")),
    "type": lambda: _tone(1400, 0.012, 0.08, "square", attack=0.001, release=0.008),
    "evidence": lambda: _concat(_tone(784, 0.06, 0.3, "tri"), _tone(1046, 0.06, 0.3, "tri"),
                                _tone(1318, 0.1, 0.3, "tri")),
    "success": lambda: _concat(_tone([523, 659], 0.1, 0.3, "tri"), _tone([659, 784], 0.1, 0.3, "tri"),
                               _tone([784, 1046], 0.25, 0.3, "tri")),
    "alarm": lambda: _concat(*[_tone(f, 0.12, 0.35, "square") for f in (880, 660, 880, 660)]),
    "glitch": lambda: _tone(0, 0.18, 0.25, "noise", release=0.1),
    "query": lambda: _concat(_tone(1200, 0.03, 0.2, "square"), _tone(1500, 0.03, 0.2, "square")),
    "flag": lambda: _concat(*[_tone([f, f * 1.5], 0.12, 0.3, "tri") for f in (523, 659, 784, 1046)],
                            _tone([1046, 1568], 0.4, 0.3, "tri")),
}


class Audio:
    def __init__(self, settings):
        self.settings = settings
        self.enabled = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music: pygame.mixer.Sound | None = None
        self.music_channel = None
        self.track: str | None = None
        self.gain = 1.0
        self._file_music = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=RATE, size=-16, channels=2, buffer=1024)
            self.enabled = pygame.mixer.get_init() is not None
        except pygame.error as exc:
            print(f"[audio] sound disabled ({exc})")
        if self.enabled:
            channels = pygame.mixer.get_init()[2]
            for name, recipe in RECIPES.items():
                self.sounds[name] = self._sound(recipe(), channels)

    @staticmethod
    def _sound(samples: array, channels: int) -> pygame.mixer.Sound:
        if channels == 2:
            stereo = array("h", [0]) * (len(samples) * 2)
            stereo[0::2] = samples
            stereo[1::2] = samples
            samples = stereo
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def play(self, name: str) -> None:
        if not self.enabled or self.settings.muted:
            return
        snd = self.sounds.get(name)
        if snd:
            snd.set_volume(self.settings.sfx)
            snd.play()

    def play_music(self, name: str) -> None:
        """Loop a named track. The same track already playing is left alone."""
        if name == self.track and (self._file_music or self._busy()):
            self.apply_volume()
            return
        self.track = name
        self._halt()
        if not self.enabled or name not in TRACKS:
            return
        path, gain, fade = TRACKS[name]
        self.gain = gain
        if self._play_file(path, fade):
            return
        self._play_pad(fade)

    def stop_music(self) -> None:
        self.track = None
        self._halt()

    def _play_file(self, path: Path, fade: int) -> bool:
        if not path.is_file():
            print(f"[audio] {path.name} not found - using synthesized music")
            return False
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play(loops=-1, fade_ms=fade)
        except pygame.error as exc:
            print(f"[audio] {path.name} unavailable ({exc})")
            return False
        self._file_music = True
        self.apply_volume()
        return True

    def _play_pad(self, fade: int) -> None:
        if self.music is None:
            channels = pygame.mixer.get_init()[2]
            self.music = self._sound(_ambient(), channels)
        self.music_channel = self.music.play(loops=-1, fade_ms=fade)
        self.apply_volume()

    def _busy(self) -> bool:
        if not self.enabled:
            return False
        if self._file_music:
            return bool(pygame.mixer.music.get_busy())
        return self.music_channel is not None and self.music_channel.get_busy()

    def _halt(self) -> None:
        self._file_music = False
        if not self.enabled:
            return
        pygame.mixer.music.stop()
        if self.music_channel is not None:
            self.music_channel.stop()
            self.music_channel = None

    def apply_volume(self) -> None:
        volume = 0.0 if self.settings.muted else self.settings.music * self.gain
        if self._file_music:
            pygame.mixer.music.set_volume(volume)
        if self.music_channel is not None:
            self.music_channel.set_volume(volume)
