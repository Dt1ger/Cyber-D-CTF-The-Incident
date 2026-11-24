"""Local JSON saves: autosave (current run), profile (best ranks), settings."""

from __future__ import annotations

import json
import os
from pathlib import Path

from game.systems.scoring import rank_value

SAVE_VERSION = 1


def read_json(path: Path) -> dict | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_json(path: Path, data: dict) -> bool:
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError as exc:
        print(f"[save] could not write {path.name}: {exc}")
        return False


class SaveStore:
    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.autosave = self.folder / "autosave.json"
        self.profile = self.folder / "profile.json"
        self.settings = self.folder / "settings.json"

    def has_run(self) -> bool:
        return self.load_run() is not None

    def save_run(self, run: dict) -> bool:
        return write_json(self.autosave, {"version": SAVE_VERSION, "run": run})

    def load_run(self) -> dict | None:
        data = read_json(self.autosave)
        if not data or data.get("version") != SAVE_VERSION:
            return None
        run = data.get("run")
        if not isinstance(run, dict) or "character" not in run:
            return None
        return run

    def clear_run(self) -> None:
        try:
            self.autosave.unlink(missing_ok=True)
        except OSError:
            pass

    def load_profile(self) -> dict:
        data = read_json(self.profile) or {}
        data.setdefault("best", {})
        return data

    def record_result(self, character: str, rank: str, score: int) -> bool:
        """Store the result if it beats the character's best. Returns True if it did."""
        profile = self.load_profile()
        best = profile["best"].get(character)
        better = best is None or (rank_value(rank), score) > (rank_value(best.get("rank", "")),
                                                              best.get("score", -1))
        if better:
            profile["best"][character] = {"rank": rank, "score": score}
        if better or not profile.get("cleared"):
            profile["cleared"] = True
            write_json(self.profile, profile)
        return better

    def hunt_cleared(self) -> bool:
        profile = self.load_profile()
        return bool(profile.get("cleared") or profile.get("best"))

    def custom_solved(self) -> list[str]:
        done = self.load_profile().get("custom", [])
        return [item for item in done if isinstance(item, str)] if isinstance(done, list) else []

    def mark_custom_solved(self, challenge_id: str) -> None:
        profile = self.load_profile()
        done = profile.get("custom")
        if not isinstance(done, list):
            done = []
        if challenge_id not in done:
            done.append(challenge_id)
            profile["custom"] = done
            write_json(self.profile, profile)
