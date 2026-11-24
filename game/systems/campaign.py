"""Everything about one playthrough that survives between zones and saves."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields


@dataclass
class ZoneStats:
    correct: int = 0
    wrong: int = 0
    hints: int = 0
    hint_points: int = 0
    tipoffs: int = 0
    data_loss: int = 0
    bad_actions: int = 0
    queries: int = 0
    puzzles: int = 0
    time: float = 0.0
    completed: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ZoneStats":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class RunState:
    character: str
    zone: int = 0
    breach: float = 0.0
    journal: list[dict] = field(default_factory=list)
    mapped: dict[str, dict] = field(default_factory=dict)
    stats: dict[str, ZoneStats] = field(default_factory=dict)
    puzzles: list[str] = field(default_factory=list)
    flag_captured: bool = False
    total_time: float = 0.0
    finished: bool = False

    def zone_stats(self, zone: int) -> ZoneStats:
        return self.stats.setdefault(str(zone), ZoneStats())

    def has_evidence(self, evidence_id: str) -> bool:
        return any(e["id"] == evidence_id for e in self.journal)

    def add_evidence(self, evidence_id: str, zone: int) -> bool:
        if self.has_evidence(evidence_id):
            return False
        self.journal.append({"id": evidence_id, "zone": zone, "t": round(self.total_time, 1)})
        return True

    def reset_zone(self, zone: int) -> None:
        """Forget progress made inside ``zone`` so it can be replayed from its start."""
        self.journal = [e for e in self.journal if e["zone"] < zone]
        self.mapped = {k: v for k, v in self.mapped.items() if v.get("zone", 0) < zone}
        self.stats = {k: v for k, v in self.stats.items() if int(k) < zone}

    def to_dict(self) -> dict:
        data = asdict(self)
        data["stats"] = {k: asdict(v) for k, v in self.stats.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "RunState":
        run = cls(character=data["character"])
        for f in fields(cls):
            if f.name in data and f.name != "stats":
                setattr(run, f.name, data[f.name])
        run.stats = {str(k): ZoneStats.from_dict(v) for k, v in data.get("stats", {}).items()}
        return run
