"""Dialogue lookup: data/dialogue/<character>.json first, shared.json as fallback."""

from __future__ import annotations

import json
from pathlib import Path


class DialogueDB:
    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.shared = self._load("shared")
        self._chars: dict[str, dict] = {}

    def _load(self, name: str) -> dict:
        path = self.folder / f"{name}.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _char(self, char_id: str) -> dict:
        if char_id not in self._chars:
            self._chars[char_id] = self._load(char_id)
        return self._chars[char_id]

    def line(self, key: str, char_id: str) -> dict | None:
        for source in (self._char(char_id), self.shared):
            entry = source.get("lines", {}).get(key)
            if entry:
                if isinstance(entry, str):
                    entry = {"speaker": "player", "text": entry}
                return dict(entry)
        return None

    def lines(self, keys: list[str], char_id: str) -> list[dict]:
        return [ln for ln in (self.line(k, char_id) for k in keys) if ln]

    def sequence(self, name: str) -> list[str]:
        return list(self.shared.get(name, []))
