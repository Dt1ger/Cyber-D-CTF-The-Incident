"""Preview how the game slices each character sprite sheet.

    python tools/preview_sprites.py                 contact sheets for every character/tier -> previews/
    python tools/preview_sprites.py --char sasha --tier lvl10
    python tools/preview_sprites.py --show          interactive window (arrows/Tab, Esc to quit)

Each contact sheet shows the original sheet with the measured row/column bands
from assets/manifest.json drawn on top (left), and every animation the game
will actually play, frame by frame (right). Use it after editing "layout" or
"animations" in the manifest, or after dropping in new art and rescanning.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ANIM_ORDER = ["idle_down", "idle_up", "idle_left", "idle_right", "walk_down", "walk_up", "walk_left",
              "walk_right", "interact"]
BG = (10, 12, 22)
GRID = (0, 240, 255)
TEXT = (220, 230, 240)
DIM = (110, 125, 145)
PREVIEW_SCALE = 0.45


def targets(assets, char: str | None, tier: str | None) -> list[tuple[str, str | None]]:
    out = []
    for cid, entry in assets.section("characters").items():
        if char and cid != char or not isinstance(entry, dict):
            continue
        tiers = list(entry.get("tiers", {})) or [entry.get("default_tier")]
        for t in tiers:
            if tier is None or t == tier:
                out.append((cid, t))
    return out


def contact_sheet(assets, char: str, tier: str | None):
    import pygame

    from game.art.loader import build_sprite_set

    entry = assets.character_entry(char, tier)
    sheet = assets.image(entry.get("spritesheet"))
    f = pygame.font.SysFont("consolas,dejavusansmono,monospace", 16)
    fb = pygame.font.SysFont("consolas,dejavusansmono,monospace", 22, bold=True)
    sprites = build_sprite_set(sheet, entry, PREVIEW_SCALE) if sheet else None
    notes = []
    if sheet is None:
        notes.append("No spritesheet found: the game uses the procedural placeholder.")
    elif sprites is None:
        notes.append("Sheet has no usable idle/walk animations: the game uses the placeholder.")

    left_h = 860
    left = pygame.Surface((1, left_h))
    if sheet is not None:
        s = left_h / sheet.get_height()
        left = pygame.Surface((round(sheet.get_width() * s), left_h))
        left.fill((40, 40, 48))
        for y in range(0, left_h, 16):
            for x in range((y // 16) % 2 * 16, left.get_width(), 32):
                left.fill((54, 54, 62), (x, y, 16, 16))
        left.blit(pygame.transform.smoothscale(sheet, left.get_size()), (0, 0))
        layout = entry.get("layout") or {}
        rows = layout.get("rows") or []
        cols = layout.get("cols") or []
        for ri, (y0, y1) in enumerate(rows):
            for ci, (x0, x1) in enumerate(cols):
                r = pygame.Rect(round(x0 * s), round(y0 * s), round((x1 - x0) * s), round((y1 - y0) * s))
                pygame.draw.rect(left, GRID, r, 1)
            left.blit(f.render(f"r{ri}", True, (255, 220, 0)), (2, round(y0 * s) + 2))
        for ci, (x0, _) in enumerate(cols):
            left.blit(f.render(f"c{ci}", True, (255, 220, 0)), (round(x0 * s) + 2, 2))
        if not rows or not cols:
            notes.append("No measured layout: frames come from frame_width/frame_height.")

    anims = sprites.animations if sprites else {}
    names = [n for n in ANIM_ORDER if n in anims] + sorted(n for n in anims if n not in ANIM_ORDER)
    fw, fh = sprites.size if sprites else (80, 120)
    right_w = max(720, 220 + max((len(anims[n].frames) for n in names), default=1) * (fw + 8))
    right_h = max(left_h, 90 + len(names) * (fh + 28) + 24 * len(notes))
    out = pygame.Surface((left.get_width() + right_w + 30, right_h))
    out.fill(BG)
    out.blit(left, (10, 10))
    x0 = left.get_width() + 24
    out.blit(fb.render(f"{char}  {tier or ''}", True, TEXT), (x0, 12))
    src = entry.get("spritesheet", "-")
    out.blit(f.render(f"{src}   bg={((entry.get('layout') or {}).get('background') or 'alpha')}", True, DIM),
             (x0, 40))
    y = 70
    for note in notes:
        out.blit(f.render(note, True, (255, 120, 120)), (x0, y))
        y += 24
    spec = entry.get("animations") or {}
    for name in names:
        a = anims[name]
        src_spec = spec.get(name)
        how = (f"row {src_spec.get('row', 0)}, {len(a.frames)} frames @ {a.fps:g} fps" if src_spec
               else "derived (mirrored or fallback)")
        out.blit(f.render(f"{name:<11} {how}", True, TEXT if src_spec else DIM), (x0, y))
        y += 20
        for i, frame in enumerate(a.frames):
            fx = x0 + i * (fw + 8)
            pygame.draw.rect(out, (30, 34, 50), (fx - 1, y - 1, fw + 2, fh + 2), 1)
            out.blit(frame, (fx, y))
        y += fh + 8
    return out


def write_previews(char, tier, out_dir: Path) -> int:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    import pygame

    from game.art.loader import Assets
    from game.engine import config

    pygame.init()
    pygame.display.set_mode((1, 1))
    assets = Assets(config.ASSETS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    found = targets(assets, char, tier)
    if not found:
        print("No matching characters in assets/manifest.json. Run tools/scan_assets.py first.")
        return 1
    for cid, t in found:
        path = out_dir / f"{cid}_{t or 'default'}.png"
        pygame.image.save(contact_sheet(assets, cid, t), str(path))
        print(f"wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    pygame.quit()
    return 0


def show(char, tier) -> int:
    import pygame

    from game.art.loader import Assets
    from game.engine import config

    pygame.init()
    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    pygame.display.set_caption("Sprite preview - arrows: character/tier, Esc: quit")
    assets = Assets(config.ASSETS_DIR)
    found = targets(assets, char, tier)
    if not found:
        print("No matching characters in assets/manifest.json.")
        return 1
    i = 0
    cache = {}
    clock = pygame.time.Clock()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                return 0
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_TAB):
                i = (i + 1) % len(found)
            elif e.type == pygame.KEYDOWN and e.key in (pygame.K_LEFT, pygame.K_UP):
                i = (i - 1) % len(found)
        if found[i] not in cache:
            cache[found[i]] = contact_sheet(assets, *found[i])
        img = cache[found[i]]
        sw, sh = screen.get_size()
        s = min(sw / img.get_width(), sh / img.get_height())
        screen.fill(BG)
        screen.blit(pygame.transform.smoothscale(img, (int(img.get_width() * s), int(img.get_height() * s))), (0, 0))
        pygame.display.flip()
        clock.tick(30)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Preview sprite sheet slicing")
    p.add_argument("--char", help="character id (demetri, sasha)")
    p.add_argument("--tier", help="gear tier (lvl1, lvl10, lvl20)")
    p.add_argument("--out", type=Path, default=ROOT / "previews", help="output folder")
    p.add_argument("--show", action="store_true", help="open an interactive window instead")
    args = p.parse_args(argv)
    if args.show:
        return show(args.char, args.tier)
    return write_previews(args.char, args.tier, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
