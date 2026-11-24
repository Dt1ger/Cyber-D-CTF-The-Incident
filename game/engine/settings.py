"""Player settings, stored in saves/settings.json."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

from game.systems.save import read_json, write_json

TEXT_SIZES = [("Normal", 1.0), ("Large", 1.15), ("Extra large", 1.3)]
TYPE_SPEEDS = [("Slow", 30), ("Normal", 55), ("Fast", 110), ("Instant", 10000)]


@dataclass
class Settings:
    text_size: int = 0
    colorblind: bool = False
    scanlines: bool = True
    music: float = 0.5
    sfx: float = 0.7
    muted: bool = False
    type_speed: int = 1
    keyboard_only: bool = False
    screen_shake: bool = True

    @property
    def text_scale(self) -> float:
        return TEXT_SIZES[self.text_size % len(TEXT_SIZES)][1]

    @property
    def chars_per_second(self) -> float:
        return TYPE_SPEEDS[self.type_speed % len(TYPE_SPEEDS)][1]

    @classmethod
    def load(cls, path) -> "Settings":
        data = read_json(path) or {}
        known = {f.name: f.type for f in fields(cls)}
        clean = {}
        for k, v in data.items():
            if k in known and isinstance(v, (bool, int, float)):
                clean[k] = v
        try:
            return cls(**clean)
        except TypeError:
            return cls()

    def save(self, path) -> None:
        write_json(path, asdict(self))
