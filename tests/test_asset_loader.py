import json
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from game.art.loader import Assets, fit_image
from game.engine.config import ASSETS_DIR

DIRS = ("down", "up", "left", "right")


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    yield
    pygame.quit()


class Log(list):
    def __call__(self, msg):
        self.append(msg)


def make_sheet(path, cols=4, rows=2, fw=16, fh=24, alpha=True, bg=(0, 0, 0)):
    """Uniform grid; each frame gets a unique color and a marker on its left side."""
    surf = pygame.Surface((cols * fw, rows * fh), pygame.SRCALPHA if alpha else 0)
    surf.fill((0, 0, 0, 0) if alpha else bg)
    for r in range(rows):
        for c in range(cols):
            x, y = c * fw, r * fh
            pygame.draw.rect(surf, (40 + r * 60, 40 + c * 50, 200, 255), (x + 4, y + 4, fw - 8, fh - 6))
            pygame.draw.rect(surf, (255, 255, 0, 255), (x + 4, y + 4, 2, 4))
    pygame.image.save(surf, str(path))


def write_manifest(root, character=None, **extra):
    data = {"backgrounds": {}, "ui": {}, "characters": {}}
    if character:
        data["characters"]["hero"] = character
    data.update(extra)
    (root / "manifest.json").write_text(json.dumps(data), encoding="utf-8")


def basic_character(**overrides):
    entry = {
        "spritesheet": "sheet.png",
        "frame_width": 16, "frame_height": 24, "scale": 1,
        "animations": {
            "idle_down": {"row": 0, "start": 0, "frames": 1},
            "walk_down": {"row": 1, "start": 0, "frames": 4},
            "walk_left": {"row": 1, "start": 0, "frames": 2},
        },
    }
    entry.update(overrides)
    return entry


def test_real_manifest_loads_both_characters():
    log = Log()
    assets = Assets(ASSETS_DIR, log=log)
    for char in ("demetri", "sasha"):
        for tier in ("lvl1", "lvl10", "lvl20"):
            sprites = assets.sprites(char, tier)
            assert not sprites.placeholder, (char, tier, log)
            for name in [f"{k}_{d}" for k in ("idle", "walk") for d in DIRS] + ["interact"]:
                assert name in sprites.animations
            assert len(sprites.get("walk_down").frames) == 4
    assert not any(char in m for m in log for char in ("demetri", "sasha"))


def test_app_logo_is_the_cyberd_mark_and_the_icon_is_square():
    from game.art.icons import square_icon

    assets = Assets(ASSETS_DIR, log=Log())
    logo = assets.ui("logo")
    assert logo is not None and logo.get_width() > logo.get_height()
    icon = square_icon(32)
    assert icon is not None and icon.get_size() == (32, 32)
    assert (ASSETS_DIR / "ui" / "favicon.ico").is_file()
    assert not any("logo" in m for m in assets._warned)


def test_oracle_and_seer_portraits_come_from_their_sheets():
    assets = Assets(ASSETS_DIR, log=Log())
    oracle = assets.cast_portrait("oracle", 0, height=150)
    seer = assets.cast_portrait("seer", 8, 132)
    glitch = assets.cast_portrait("seer", 10, 132)
    assert oracle is not None and oracle.get_height() == 150 and oracle.get_width() > 120
    assert seer is not None and seer.get_size() == (132, 132)
    assert glitch is not None and glitch.get_at((66, 66)).a == 255
    assert not any("Oracle" in m or "Seer" in m for m in assets._warned)


def test_empty_assets_folder_uses_placeholders_without_crashing(tmp_path):
    log = Log()
    assets = Assets(tmp_path, log=log)
    bg = assets.background("intro", (320, 180))
    assert bg.placeholder and bg.surface.get_size() == (320, 180)
    assert assets.logo("Title", "Sub").get_width() > 0
    assert assets.portrait("demetri", palette={"hoodie": "#c8102e"}).get_height() > 0
    sprites = assets.sprites("demetri", scale=0.5)
    assert sprites.placeholder
    assert all(f"walk_{d}" in sprites.animations for d in DIRS)
    assert len(sprites.get("walk_left").frames) == 4
    assert any("manifest.json not found" in m for m in log)


def test_missing_file_warns_once(tmp_path):
    write_manifest(tmp_path, backgrounds={"intro": "backgrounds/intro.png"})
    log = Log()
    assets = Assets(tmp_path, log=log)
    assets.background("intro", (100, 100))
    assets.background("intro", (200, 100))
    matches = [m for m in log if "intro.png not found" in m]
    assert matches == ["[assets] backgrounds/intro.png not found - using placeholder"]


def test_broken_image_falls_back(tmp_path):
    (tmp_path / "sheet.png").write_bytes(b"not really a png")
    write_manifest(tmp_path, basic_character())
    log = Log()
    sprites = Assets(tmp_path, log=log).sprites("hero")
    assert sprites.placeholder
    assert any("could not be loaded" in m for m in log)


def test_invalid_manifest_json_falls_back(tmp_path):
    (tmp_path / "manifest.json").write_text("{ nope", encoding="utf-8")
    log = Log()
    assets = Assets(tmp_path, log=log)
    assert assets.manifest == {}
    assert assets.sprites("hero").placeholder
    assert any("could not be read" in m for m in log)


def test_uniform_grid_and_right_flipped_from_left(tmp_path):
    make_sheet(tmp_path / "sheet.png")
    write_manifest(tmp_path, basic_character())
    sprites = Assets(tmp_path, log=Log()).sprites("hero")
    assert not sprites.placeholder
    assert sprites.size == (16, 24)
    assert len(sprites.get("walk_down").frames) == 4
    left = sprites.get("walk_left").frames[0]
    right = sprites.get("walk_right").frames[0]
    assert left.get_at((4, 4)) == pygame.Color(255, 255, 0, 255)
    assert right.get_at((15 - 4, 4)) == pygame.Color(255, 255, 0, 255)
    assert sprites.get("idle_up") is sprites.get("idle_down")  # missing direction falls back


def test_measured_layout_and_flood_background(tmp_path):
    make_sheet(tmp_path / "sheet.png", alpha=False)
    layout = {"rows": [[2, 24], [26, 48]], "cols": [[2, 14], [18, 30], [34, 46], [50, 62]],
              "background": "flood"}
    write_manifest(tmp_path, basic_character(layout=layout, frame_width=12, frame_height=22))
    sprites = Assets(tmp_path, log=Log()).sprites("hero")
    frame = sprites.get("walk_down").frames[0]
    assert frame.get_size() == (12, 22)
    assert frame.get_at((0, 0)).a == 0  # black background removed
    assert frame.get_at((6, 12)).a == 255


def test_scale_and_tier_overrides(tmp_path):
    make_sheet(tmp_path / "a.png")
    make_sheet(tmp_path / "b.png", fw=16, fh=24)
    entry = basic_character(spritesheet="a.png", default_tier="t1",
                            tiers={"t1": {"spritesheet": "a.png"}, "t2": {"spritesheet": "b.png"}})
    write_manifest(tmp_path, entry, tier_by_zone={"0": "t1", "5": "t2"})
    assets = Assets(tmp_path, log=Log())
    assert assets.character_entry("hero", "t2")["spritesheet"] == "b.png"
    assert assets.tier_for_zone(5) == "t2"
    assert assets.tier_for_zone(3, "hero") == "t1"
    assert assets.sprites("hero", "t1", scale=2).size == (32, 48)


def test_bad_animation_rows_fall_back_to_placeholder(tmp_path):
    make_sheet(tmp_path / "sheet.png")
    write_manifest(tmp_path, basic_character(animations={"idle_down": {"row": 9, "frames": 1}}))
    log = Log()
    assert Assets(tmp_path, log=log).sprites("hero").placeholder
    assert any("no usable" in m for m in log)


@pytest.mark.parametrize("fit,expected", [("contain", (200, 100)), ("cover", (400, 200))])
def test_fit_image_keeps_aspect(fit, expected):
    src = pygame.Surface((400, 200))
    fitted = fit_image(src, (200, 200), fit)
    assert fitted.surface.get_size() == (200, 200)
    assert fitted.rect.size == expected
    assert fitted.point(0.5, 0.5) == (100, 100)
