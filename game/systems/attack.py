"""Bundled MITRE ATT&CK subset used by the matrix panel and mappings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Tactic:
    id: str
    name: str


@dataclass
class Technique:
    id: str
    name: str
    tactics: list[str]
    description: str
    detection: str
    mitigation: str

    @property
    def label(self) -> str:
        return f"{self.id} {self.name}"


class AttackDB:
    def __init__(self, data: dict):
        self.tactics = [Tactic(t["id"], t["name"]) for t in data["tactics"]]
        self.techniques = {
            t["id"]: Technique(t["id"], t["name"], list(t["tactics"]), t.get("description", ""),
                               t.get("detection", ""), t.get("mitigation", ""))
            for t in data["techniques"]
        }
        self._tactic_by_id = {t.id: t for t in self.tactics}

    @classmethod
    def load(cls, path: Path) -> "AttackDB":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def tactic(self, tactic_id: str) -> Tactic | None:
        return self._tactic_by_id.get(tactic_id)

    def technique(self, technique_id: str) -> Technique | None:
        return self.techniques.get(technique_id)

    def columns(self) -> list[tuple[Tactic, list[Technique]]]:
        return [(tac, [t for t in self.techniques.values() if tac.id in t.tactics])
                for tac in self.tactics]
