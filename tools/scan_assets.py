"""Scan assets/ for images, guess what each one is, and keep manifest.json in sync.

Usage:
    python tools/scan_assets.py              # report only, changes nothing
    python tools/scan_assets.py --organize   # copy originals into the asset
                                             # layout and (re)write manifest.json

Originals are never moved, renamed, or deleted. Manual edits to manifest.json
(scale, fps, animations, smooth, extra entries) are preserved on re-scan.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from game.art.sheet_layout import detect_layout  # noqa: E402

ASSETS = ROOT / "assets"
MANIFEST = ASSETS / "manifest.json"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
CHARACTERS = ("demetri", "sasha", "aisha_256")
DEFAULT_TIER = "lvl1"
DEFAULT_SPRITE_SCALE = 0.4

# Matches the 4x6 layout of the provided sheets: row 0 holds one idle pose per
# direction (down, up, left, right), rows 1-4 are walk cycles, row 5 is the
# "working at the laptop" interact animation.
DEFAULT_ANIMATIONS = {
    "idle_down": {"row": 0, "start": 0, "frames": 1, "fps": 1},
    "idle_up": {"row": 0, "start": 1, "frames": 1, "fps": 1},
    "idle_left": {"row": 0, "start": 2, "frames": 1, "fps": 1},
    "idle_right": {"row": 0, "start": 3, "frames": 1, "fps": 1},
    "walk_down": {"row": 1, "start": 0, "frames": 4, "fps": 8},
    "walk_up": {"row": 2, "start": 0, "frames": 4, "fps": 8},
    "walk_left": {"row": 3, "start": 0, "frames": 4, "fps": 8},
    "walk_right": {"row": 4, "start": 0, "frames": 4, "fps": 8},
    "interact": {"row": 5, "start": 0, "frames": 4, "fps": 4, "loop": False},
}


@dataclass
class ImageInfo:
    path: Path
    width: int
    height: int
    transparent: bool
    kind: str = "unknown"
    character: str | None = None
    tier: str | None = None
    target: str | None = None
    layout: dict | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def rel(self) -> str:
        return self.path.relative_to(ASSETS).as_posix()


def find_images() -> list[Path]:
    return sorted(
        p for p in ASSETS.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def load_info(path: Path) -> ImageInfo | None:
    try:
        surf = pygame.image.load(str(path))
    except Exception as exc:  # broken or unsupported file
        print(f"[scan] could not read {path.relative_to(ASSETS)}: {exc}")
        return None
    w, h = surf.get_size()
    transparent = bool(surf.get_flags() & pygame.SRCALPHA) and surf.get_at((0, 0)).a < 255
    info = ImageInfo(path, w, h, transparent)
    info.layout = _layout_dict(surf)
    return info


def _layout_dict(surf: pygame.Surface) -> dict:
    layout = detect_layout(surf)
    return {
        "rows": [list(r) for r in layout.rows],
        "cols": [list(c) for c in layout.cols],
        "background": layout.background,
        "frame_width": layout.frame_width,
        "frame_height": layout.frame_height,
    }


def classify(info: ImageInfo) -> None:
    """Guess the role of an image from its name, folder, and shape."""
    name = info.path.stem.lower()
    rel = info.rel.lower()
    char = next((c for c in CHARACTERS if c in rel), None)
    tier_match = re.search(r"lvl\s*_?(\d+)", name)
    tier = f"lvl{tier_match.group(1)}" if tier_match else None
    grid = len(info.layout["rows"]) * len(info.layout["cols"])
    zone = re.search(r"zone[_\- ]?(\d+)", name)

    if char and any(k in name for k in ("motion", "sheet", "sprite", "walk")) or (
        char and grid >= 4 and "portrait" not in name
    ):
        info.kind, info.character, info.tier = "spritesheet", char, tier or DEFAULT_TIER
        info.target = f"characters/{char}/{info.tier}/spritesheet.png"
    elif char and info.height >= info.width * 0.9:
        info.kind, info.character, info.tier = "portrait", char, tier or DEFAULT_TIER
        info.target = f"characters/{char}/{info.tier}/portrait.png"
    elif any(k in name for k in ("intro", "title")):
        info.kind, info.target = "background:intro", "backgrounds/intro.png"
    elif "select" in name:
        info.kind, info.target = "background:character_select", "backgrounds/character_select.png"
    elif zone:
        n = int(zone.group(1))
        info.kind, info.target = f"background:zone_{n:02d}", f"backgrounds/zone_{n:02d}.png"
    elif "logo" in name:
        info.kind, info.target = "ui:logo", "ui/logo.png"
    elif name in ("icon", "favicon"):
        info.kind, info.target = "ui:icon", "ui/icon.png"
    elif "aisha" in name:
        info.kind = "reference"
        info.notes.append("hidden operative art; the manifest keeps her clips by hand")
    elif "oracle" in name and "poster" not in name and "variation" not in name:
        info.kind, info.target = "cast:oracle", info.rel
    elif "seer" in name and "poster" not in name:
        info.kind, info.target = "cast:seer", info.rel
    elif "tile" in name or rel.startswith("tiles/"):
        info.kind, info.target = "tile", f"tiles/{info.path.name.lower()}"
    else:
        info.notes.append("could not identify - please tell me what this is")

    if info.kind == "spritesheet" and info.layout["background"] == "flood":
        info.notes.append("no transparency - background removed by flood fill at load time")
    if info.kind == "spritesheet":
        rows, cols = len(info.layout["rows"]), len(info.layout["cols"])
        info.notes.append(f"{cols} cols x {rows} rows, frames up to "
                          f"{info.layout['frame_width']}x{info.layout['frame_height']}")


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {}
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[scan] manifest.json is not valid JSON ({exc}); it will be rebuilt")
        return {}


def manifest_paths(manifest: dict) -> set[str]:
    """Every asset path referenced anywhere in the manifest."""
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("sources", "unclassified", "reference"):
                    continue
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str) and Path(node).suffix.lower() in IMAGE_EXTS:
            found.add(node)

    walk(manifest)
    return found


def build_manifest(infos: list[ImageInfo], old: dict) -> dict:
    manifest: dict = {
        "_comment": "Generated by tools/scan_assets.py. Paths are relative to assets/. "
                    "Edit freely: scale, fps, animations and smooth survive re-scans.",
        "backgrounds": dict(old.get("backgrounds", {})),
        "ui": dict(old.get("ui", {})),
        "tiles": dict(old.get("tiles", {})),
        "cast": dict(old.get("cast", {})),
        "characters": {},
        "sources": dict(old.get("sources", {})),
        "unclassified": [],
        "reference": list(old.get("reference", [])),
    }
    old_chars = old.get("characters", {})

    for info in infos:
        if info.kind == "reference":
            if info.rel not in manifest["reference"]:
                manifest["reference"].append(info.rel)
            continue
        if info.target is None:
            continue
        manifest["sources"][info.target] = info.rel
        if info.kind.startswith("background:"):
            manifest["backgrounds"][info.kind.split(":", 1)[1]] = info.target
        elif info.kind == "ui:logo":
            manifest["ui"]["logo"] = info.target
        elif info.kind == "ui:icon":
            manifest["ui"]["icon"] = info.target
        elif info.kind == "tile":
            manifest["tiles"][Path(info.target).stem] = info.target
        elif info.kind.startswith("cast:"):
            who = info.kind.split(":", 1)[1]
            slot = manifest["cast"].setdefault(who, {})
            if isinstance(slot, dict):
                slot["sheet"] = info.target

    for char in CHARACTERS:
        prev = old_chars.get(char, {})
        prev_tiers = prev.get("tiers", {})
        tiers: dict = {}
        for info in infos:
            if info.character != char:
                continue
            tier = tiers.setdefault(info.tier, dict(prev_tiers.get(info.tier, {})))
            if info.kind == "portrait":
                tier["portrait"] = info.target
            elif info.kind == "spritesheet":
                tier["spritesheet"] = info.target
                tier["layout"] = {
                    "rows": info.layout["rows"],
                    "cols": info.layout["cols"],
                    "background": info.layout["background"],
                }
                tier["frame_width"] = info.layout["frame_width"]
                tier["frame_height"] = info.layout["frame_height"]
        if not tiers and not prev:
            continue
        ordered = dict(sorted(tiers.items(), key=lambda kv: int(re.sub(r"\D", "", kv[0]) or 0)))
        for name, values in prev_tiers.items():
            ordered.setdefault(name, values)
        default_tier = prev.get("default_tier", DEFAULT_TIER if DEFAULT_TIER in ordered
                                else next(iter(ordered), DEFAULT_TIER))
        base = ordered.get(default_tier, {})
        manifest["characters"][char] = {
            **prev,
            "portrait": base.get("portrait", prev.get("portrait")),
            "spritesheet": base.get("spritesheet", prev.get("spritesheet")),
            "frame_width": base.get("frame_width", prev.get("frame_width", 256)),
            "frame_height": base.get("frame_height", prev.get("frame_height", 256)),
            "layout": base.get("layout", prev.get("layout")),
            "scale": prev.get("scale", DEFAULT_SPRITE_SCALE),
            "smooth": prev.get("smooth", True),
            "default_tier": default_tier,
            "animations": prev.get("animations", DEFAULT_ANIMATIONS),
            "tiers": ordered,
        }

    for key, value in old.items():
        manifest.setdefault(key, value)

    referenced_sources = set(manifest["sources"].values())
    referenced_targets = set(manifest["sources"].keys())
    for info in infos:
        if info.kind == "manifest":
            continue
        if info.target is None and info.rel not in referenced_sources \
                and info.rel not in referenced_targets and info.rel not in manifest["reference"]:
            manifest["unclassified"].append(info.rel)
    return manifest


def dump_manifest(manifest: dict) -> str:
    text = json.dumps(manifest, indent=2)
    return re.sub(r"\[\s+(-?\d+),\s+(-?\d+)\s+\]", r"[\1, \2]", text) + "\n"


def organize(infos: list[ImageInfo]) -> list[str]:
    copied = []
    for info in infos:
        if info.target is None or info.rel == info.target:
            continue
        dest = ASSETS / info.target
        if dest.exists() and dest.stat().st_size == info.path.stat().st_size \
                and dest.read_bytes() == info.path.read_bytes():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(info.path, dest)
        copied.append(f"{info.rel} -> {info.target}")
    return copied


def diff_manifest(old: dict, new: dict) -> list[str]:
    before, after = manifest_paths(old), manifest_paths(new)
    changes = [f"+ {p}" for p in sorted(after - before)]
    changes += [f"- {p}" for p in sorted(before - after)]
    return changes


def report(infos: list[ImageInfo], manifest: dict) -> None:
    print(f"\nFound {len(infos)} image(s) under assets/\n")
    w_name = max((len(i.rel) for i in infos), default=10)
    print(f"{'file':<{w_name}}  {'size':>11}  {'alpha':5}  {'guess':<28} target")
    print("-" * (w_name + 80))
    for i in infos:
        alpha = "yes" if i.transparent else "no"
        guess = i.kind + (f" ({i.character} {i.tier})" if i.character else "")
        print(f"{i.rel:<{w_name}}  {i.width:>5}x{i.height:<5}  {alpha:5}  {guess:<28} "
              f"{i.target or '-'}")
        for note in i.notes:
            print(f"{'':<{w_name}}    · {note}")

    sources = manifest.get("sources", {})
    referenced = manifest_paths(manifest)
    organized = set(sources.values()) | set(sources.keys())
    pending = set(manifest.get("unclassified", []))
    reference = set(manifest.get("reference", []))
    unreferenced = [i.rel for i in infos if i.rel not in referenced
                    and i.rel not in organized and i.rel not in pending and i.rel not in reference]
    missing = sorted(p for p in referenced if not (ASSETS / p).exists())

    print()
    if pending:
        print("Awaiting identification (listed under 'unclassified', not used in game):")
        for p in sorted(pending):
            print(f"  ? {p}")
    if reference:
        print("Reference-only (kept, not used in game): " + ", ".join(sorted(reference)))
    if unreferenced:
        print("Images not referenced in manifest.json:")
        for p in unreferenced:
            print(f"  ? {p}")
    else:
        other = "other " if pending else ""
        print(f"Every {other}image is referenced in manifest.json (or is the original of a copy).")
    if missing:
        print("Manifest entries whose file is missing (placeholder will be used):")
        for p in missing:
            print(f"  ! {p}")
    else:
        print("Every manifest entry points to an existing file.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--organize", action="store_true",
                        help="copy images into the asset layout and write manifest.json")
    args = parser.parse_args(argv)

    if not ASSETS.exists():
        print("[scan] assets/ folder not found - the game will use placeholders only")
        return 0

    pygame.init()
    reference = set(load_manifest().get("reference", []))
    organized_targets = set(load_manifest().get("sources", {}).keys())
    organized_sources = set(load_manifest().get("sources", {}).values())
    by_hand = manifest_paths(load_manifest()) - organized_targets
    infos = []
    for path in find_images():
        rel = path.relative_to(ASSETS).as_posix()
        if rel in organized_targets:
            continue  # copies we made earlier; their originals are scanned instead
        info = load_info(path)
        if info is None:
            continue
        classify(info)
        if rel in reference:
            info.kind, info.target, info.notes = "reference", None, []
        elif rel in by_hand and rel not in organized_sources and info.target != rel:
            info.kind, info.target, info.character = "manifest", None, None
            info.notes = ["used directly by manifest.json - left as is"]
        infos.append(info)

    old = load_manifest()
    if args.organize:
        copied = organize(infos)
        new = build_manifest(infos, old)
        MANIFEST.write_text(dump_manifest(new), encoding="utf-8")
        print(f"[scan] copied {len(copied)} file(s)")
        for line in copied:
            print(f"  {line}")
        changes = diff_manifest(old, new)
        print(f"[scan] manifest.json written ({len(changes)} path change(s))")
        for line in changes:
            print(f"  {line}")
        report(infos, new)
    else:
        report(infos, old)
        if not old:
            print("\nNo manifest.json yet - run with --organize to create it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
