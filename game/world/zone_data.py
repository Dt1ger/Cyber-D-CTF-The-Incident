"""Load data/zones/zone_NN.json into a ZoneData, adding seeded background noise.

Strings anywhere in a zone file may contain encoding tokens that are expanded
at load time, so puzzles and encoded command lines never drift from their
answers:  [[base64:text]]  [[base64u16:text]]  [[hex:text]]  [[xor:0x2a:text]]
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pygame

from game.engine.config import DATA_DIR
from game.systems.decode import encode
from game.systems.query import Table

TOKEN_RE = re.compile(r"\[\[(base64u16|base64|hex|rot13|xor:(0x[0-9a-fA-F]+)):(.*?)\]\]")
FILL_RE = re.compile(r"\{(host|ip|user|int:(\d+)-(\d+)|hex:(\d+))\}")
DEFAULT_EVENT_IDS = {"proc": 1, "net": 3, "access": 10, "file": 11, "reg": 13, "dns": 22,
                     "task": 4698, "auth": 4624, "share": 5140, "svc": 7045}

_noise_cache: dict | None = None


def _noise_data(data_dir: Path) -> dict:
    global _noise_cache
    if _noise_cache is None:
        path = data_dir / "telemetry_noise.json"
        _noise_cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _noise_cache


def expand_tokens(value):
    if isinstance(value, str):
        def sub(m):
            kind = m.group(1)
            if kind.startswith("xor:"):
                return encode("xor", m.group(3), m.group(2))
            return encode(kind, m.group(3))
        return TOKEN_RE.sub(sub, value)
    if isinstance(value, list):
        return [expand_tokens(v) for v in value]
    if isinstance(value, dict):
        return {k: expand_tokens(v) for k, v in value.items()}
    return value


def parse_time(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def format_time(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fill(value, ctx: dict, rng: random.Random):
    if isinstance(value, list):
        value = rng.choice(value)
    if not isinstance(value, str):
        return value

    def sub(m):
        if m.group(1) in ("host", "ip", "user"):
            return str(ctx.get(m.group(1), ""))
        if m.group(2):
            return str(rng.randint(int(m.group(2)), int(m.group(3))))
        return "".join(rng.choice("0123456789abcdef") for _ in range(int(m.group(4))))

    out = FILL_RE.sub(sub, value)
    return int(out) if out.isdigit() and value.startswith("{int:") and value.endswith("}") else out


def _hosts_for(spec, env: dict) -> list[str]:
    hosts = env.get("hosts", {})
    if isinstance(spec, list):
        return spec
    groups = env.get("groups", {})
    if isinstance(spec, str) and spec in groups:
        return groups[spec]
    return list(hosts)


def generate_noise(table: str, count: int, window: tuple[datetime, datetime], env: dict,
                   rng: random.Random) -> list[dict]:
    templates = env.get("tables", {}).get(table, [])
    if not templates or count <= 0:
        return []
    weights = [t.get("w", 1) for t in templates]
    span = max(1, int((window[1] - window[0]).total_seconds()))
    rows = []
    for i in range(count):
        tpl = rng.choices(templates, weights)[0]
        host = rng.choice(_hosts_for(tpl.get("hosts", "workstations"), env))
        info = env.get("hosts", {}).get(host, {})
        ctx = {"host": host, "ip": info.get("ip", ""), "user": info.get("user", "SYSTEM")}
        row = {"id": f"n-{table}-{i + 1:03d}",
               "time": format_time(window[0] + timedelta(seconds=rng.randrange(span))),
               "host": host}
        if table in DEFAULT_EVENT_IDS:
            row["event_id"] = DEFAULT_EVENT_IDS[table]
        for k, v in tpl.items():
            if k in ("w", "hosts"):
                continue
            row[k] = _fill(v, ctx, rng)
        row.setdefault("user", ctx["user"])
        rows.append(row)
    return rows


def run_generator(gen: dict, rng: random.Random) -> list[dict]:
    start = parse_time(gen["start"])
    rows = []
    t = start
    for i in range(int(gen.get("count", 1))):
        jitter = int(gen.get("jitter", 0))
        row = {"id": f"{gen['id_prefix']}-{i + 1:03d}", "time": format_time(t)}
        for k, v in gen.get("row", {}).items():
            row[k] = _fill(v, {}, rng)
        rows.append(row)
        t += timedelta(seconds=int(gen.get("interval", 60)) + (rng.randint(-jitter, jitter) if jitter else 0))
    return rows


@dataclass
class ZoneData:
    raw: dict
    index: int
    id: str
    name: str
    lesson: str
    phase: str
    attack: list[str]
    accent: tuple[int, int, int]
    nodes: list[dict]
    evidence: dict[str, dict]
    tables: dict[str, Table]
    objectives: list[dict]
    findings: dict[str, dict]
    responses: list[dict]
    puzzle: dict | None
    dialogue: dict
    clock: dict
    pivot_tip: str = ""
    map_seed: int = 0
    flag: str | None = None
    reaction: str = ""
    debrief: dict = field(default_factory=dict)

    def objective(self, obj_id: str) -> dict | None:
        return next((o for o in self.objectives if o["id"] == obj_id), None)

    def node(self, node_id: str) -> dict | None:
        return next((n for n in self.nodes if n["id"] == node_id), None)

    def response(self, action_id: str) -> dict | None:
        return next((a for a in self.responses if a["id"] == action_id), None)


def zone_path(index: int, data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "zones" / f"zone_{index:02d}.json"


def zone_count(data_dir: Path = DATA_DIR) -> int:
    return len(list((data_dir / "zones").glob("zone_*.json")))


def debrief_index(data_dir: Path = DATA_DIR) -> int:
    """The last zone file is the debrief; every zone before it is playable."""
    return zone_count(data_dir) - 1


_evidence_cache: dict[Path, dict[str, tuple[int, dict]]] = {}


def evidence_index(data_dir: Path = DATA_DIR) -> dict[str, tuple[int, dict]]:
    """Every evidence item in every zone: id -> (zone index, evidence dict)."""
    if data_dir not in _evidence_cache:
        index: dict[str, tuple[int, dict]] = {}
        for path in sorted((data_dir / "zones").glob("zone_*.json")):
            try:
                raw = expand_tokens(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
            for eid, ev in raw.get("evidence", {}).items():
                index[eid] = (int(raw.get("index", 0)), ev)
        _evidence_cache[data_dir] = index
    return _evidence_cache[data_dir]


def load_zone(index: int, data_dir: Path = DATA_DIR) -> ZoneData:
    raw = expand_tokens(json.loads(zone_path(index, data_dir).read_text(encoding="utf-8")))
    env = _noise_data(data_dir)
    rng = random.Random(1000 + index)
    window = raw.get("window") or ["2026-11-17T08:00:00Z", "2026-11-17T12:00:00Z"]
    win = (parse_time(window[0]), parse_time(window[1]))

    tables: dict[str, Table] = {}
    for name, spec in raw.get("telemetry", {}).items():
        rows = [dict(r) for r in spec.get("rows", [])]
        for r in rows:
            if name in DEFAULT_EVENT_IDS:
                r.setdefault("event_id", DEFAULT_EVENT_IDS[name])
        rows += generate_noise(name, int(spec.get("noise", 0)), win, env, rng)
        tables[name] = Table(name, rows, list(spec.get("columns", [])), spec.get("description", ""))
    for gen in raw.get("generate", []):
        table = tables.setdefault(gen["table"], Table(gen["table"], [], []))
        table.rows += run_generator(gen, rng)
    for table in tables.values():
        table.rows.sort(key=lambda r: r.get("time", ""))

    puzzle = raw.get("puzzle")
    if puzzle:
        puzzle = dict(puzzle)
        puzzle.setdefault("id", f"puzzle_{index:02d}")
        puzzle["ciphertext"] = encode(puzzle["encoding"], puzzle["answer"], puzzle.get("key"))

    try:
        accent = tuple(pygame.Color(raw.get("accent", "#00f0ff")))[:3]
    except ValueError:
        accent = (0, 240, 255)

    return ZoneData(
        raw=raw, index=index, id=raw.get("id", f"zone_{index:02d}"), name=raw.get("name", ""),
        lesson=raw.get("lesson", ""), phase=raw.get("phase", ""), attack=raw.get("attack", []),
        accent=accent, nodes=raw.get("nodes", []), evidence=raw.get("evidence", {}),
        tables=tables, objectives=raw.get("objectives", []), findings=raw.get("findings", {}),
        responses=raw.get("responses", []), puzzle=puzzle, dialogue=raw.get("dialogue", {}),
        clock=raw.get("clock", {}), pivot_tip=raw.get("pivot_tip", ""),
        map_seed=int(raw.get("map_seed", index * 31 + 7)), flag=raw.get("flag"),
        reaction=raw.get("reaction", ""), debrief=raw.get("debrief", {}),
    )
