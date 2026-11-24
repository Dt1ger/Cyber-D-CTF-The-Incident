"""CyberD CTF: The Incident - Hunt for VELVET LOCUST.

Run:  python main.py
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

if sys.version_info < (3, 11):
    sys.exit("This game needs Python 3.11 or newer.")

try:
    import pygame  # noqa: F401
except ImportError:
    sys.exit("pygame-ce is not installed. Run:  pip install -r requirements.txt")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CyberD CTF: The Incident")
    parser.add_argument("--scene", default="splash",
                        help="scene to start in (dev): splash, title, cinematic, character_select, zone, "
                             "debrief, gallery. Zone also takes --character=sasha --zone=3")
    parser.add_argument("--no-assets", action="store_true",
                        help="ignore assets/ and use procedural placeholders only")
    parser.add_argument("--snapshot", type=Path,
                        help="render off-screen, save a PNG after --frames frames, and exit")
    parser.add_argument("--frames", type=int, help="quit after this many frames")
    args, extra = parser.parse_known_args(argv)

    if args.snapshot:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"

    scene_args = {}
    for item in extra:
        if item.startswith("--") and "=" in item:
            k, v = item[2:].split("=", 1)
            scene_args[k.replace("-", "_")] = v.lower() in ("1", "true", "yes") if v.lower() in (
                "1", "0", "true", "false", "yes", "no") else v

    from game.engine.app import App

    saves_dir = Path(tempfile.mkdtemp(prefix="cyberd_snap_")) if args.snapshot else None
    App(start_scene=args.scene, use_assets=not args.no_assets, snapshot=args.snapshot,
        frames=args.frames, saves_dir=saves_dir, **scene_args).run_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
