from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pygame


@dataclass
class Perk:
    id: str
    name: str
    description: str


@dataclass
class Character:
    id: str
    name: str
    role: str
    bio: str
    accent: tuple[int, int, int]
    perk: Perk
    select_line: str = ""
    palette: dict = field(default_factory=dict)

    @property
    def sprite_key(self) -> str:
        return self.id

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        perk = data.get("perk") or {}
        try:
            accent = tuple(pygame.Color(data.get("accent", "#00f0ff")))[:3]
        except ValueError:
            accent = (0, 240, 255)
        return cls(
            id=data["id"],
            name=data.get("name", data["id"].title()),
            role=data.get("role", ""),
            bio=data.get("bio", ""),
            accent=accent,
            perk=Perk(perk.get("id", ""), perk.get("name", ""), perk.get("description", "")),
            select_line=data.get("select_line", ""),
            palette=data.get("palette") or {},
        )


def load_characters(path: Path) -> list[Character]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Character.from_dict(c) for c in data.get("characters", [])]
