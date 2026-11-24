from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = ROOT / "assets"
DATA_DIR = ROOT / "data"
SAVES_DIR = ROOT / "saves"
CHALLENGES_DIR = ROOT / "challenges"

TITLE = "CyberD CTF: The Incident"
SUBTITLE = "Hunt for VELVET LOCUST"
STUDIO = "LYMBO STUDIOS"

WIDTH, HEIGHT = 1280, 720
FPS = 60

BG = (6, 8, 16)
CYAN = (0, 240, 255)
MAGENTA = (255, 0, 170)
AMBER = (255, 176, 0)
TEXT = (210, 230, 240)
DIM = (90, 110, 130)
