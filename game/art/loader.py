"""Load every image through assets/manifest.json, never crashing.

Anything missing, broken, or absent from the manifest is replaced by a
procedural placeholder and reported once on the console.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pygame

from game.art import placeholders
from game.art.animation import DIRECTIONS, Animation, SpriteSet
from game.art.cast import cell_rect, square_bust, standing
from game.art.sheet_layout import has_transparency, remove_background

DEFAULT_SCALE = 0.4
BG_FILL = (6, 8, 16)


@dataclass
class FittedImage:
    surface: pygame.Surface
    rect: pygame.Rect  # where the source image landed inside ``surface``
    placeholder: bool = False

    def point(self, nx: float, ny: float) -> tuple[int, int]:
        """Map a normalized (0-1) position on the source image to screen pixels."""
        return (round(self.rect.x + nx * self.rect.width),
                round(self.rect.y + ny * self.rect.height))


class Assets:
    def __init__(self, root: Path | str, log: Callable[[str], None] = print,
                 use_files: bool = True):
        self.root = Path(root)
        self.log = log
        self.use_files = use_files
        self._warned: set[str] = set()
        self._images: dict[str, pygame.Surface | None] = {}
        self._fitted: dict[tuple, FittedImage] = {}
        self._sprites: dict[tuple, SpriteSet] = {}
        self.manifest = self._load_manifest() if use_files else {}

    def warn(self, message: str) -> None:
        if message not in self._warned:
            self._warned.add(message)
            self.log(f"[assets] {message}")

    def _load_manifest(self) -> dict:
        path = self.root / "manifest.json"
        if not path.exists():
            self.warn("manifest.json not found - using placeholders for everything")
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.warn(f"manifest.json could not be read ({exc}) - using placeholders")
            return {}
        if not isinstance(data, dict):
            self.warn("manifest.json is not a JSON object - using placeholders")
            return {}
        return data

    def section(self, name: str) -> dict:
        value = self.manifest.get(name, {})
        return value if isinstance(value, dict) else {}

    def image(self, rel: str | None) -> pygame.Surface | None:
        """Load an image relative to assets/, or None (with one warning) on failure."""
        if not rel or not isinstance(rel, str):
            return None
        if rel in self._images:
            return self._images[rel]
        surf = None
        path = self.root / rel
        if not path.is_file():
            self.warn(f"{rel} not found - using placeholder")
        else:
            try:
                surf = pygame.image.load(str(path))
                if pygame.display.get_surface() is not None:
                    alpha = surf.get_flags() & pygame.SRCALPHA
                    surf = surf.convert_alpha() if alpha else surf.convert()
            except (pygame.error, OSError, ValueError) as exc:
                self.warn(f"{rel} could not be loaded ({exc}) - using placeholder")
                surf = None
        self._images[rel] = surf
        return surf

    # Backgrounds and UI -------------------------------------------------

    def background(self, key: str, size: tuple[int, int], fit: str = "contain") -> FittedImage:
        cache_key = (key, size, fit)
        if cache_key in self._fitted:
            return self._fitted[cache_key]
        rel = self.section("backgrounds").get(key)
        if rel is None and self.use_files:
            self.warn(f"no '{key}' background in manifest.json - using placeholder")
        src = self.image(rel)
        if src is None:
            fitted = FittedImage(placeholders.background(size, key),
                                 pygame.Rect(0, 0, *size), placeholder=True)
        else:
            fitted = fit_image(src, size, fit)
        self._fitted[cache_key] = fitted
        return fitted

    def optional_background(self, key: str, size: tuple[int, int],
                            fit: str = "cover") -> FittedImage | None:
        """A background that may legitimately be absent (zone art): no warning if unlisted."""
        rel = self.section("backgrounds").get(key)
        if not rel:
            return None
        cache_key = (key, size, fit)
        if cache_key not in self._fitted:
            src = self.image(rel)
            if src is None:
                return None
            self._fitted[cache_key] = fit_image(src, size, fit)
        return self._fitted[cache_key]

    def tile(self, key: str, size: int) -> pygame.Surface | None:
        """Optional floor/wall/node tile from manifest 'tiles', scaled to a square."""
        rel = self.section("tiles").get(key)
        if not rel:
            return None
        cache_key = ("tile", key, size)
        if cache_key not in self._images:
            src = self.image(rel)
            self._images[cache_key] = (pygame.transform.smoothscale(src, (size, size))
                                       if src is not None else None)
        return self._images[cache_key]

    def hotspots(self, key: str) -> dict:
        spots = self.manifest.get("hotspots", {})
        spots = spots.get(key, {}) if isinstance(spots, dict) else {}
        return spots if isinstance(spots, dict) else {}

    def ui(self, key: str) -> pygame.Surface | None:
        rel = self.section("ui").get(key)
        if rel is None and self.use_files:
            self.warn(f"no '{key}' ui image in manifest.json - using placeholder")
        return self.image(rel)

    def logo(self, title: str, subtitle: str = "") -> pygame.Surface:
        return self.ui("logo") or placeholders.logo(title, subtitle)

    def cast_portrait(self, name: str, frame: int = 0, size: int = 132,
                      height: int | None = None) -> pygame.Surface | None:
        """One cell of a cast sheet. ``height`` returns a tall figure; otherwise a square bust."""
        entry = self.section("cast").get(name, {})
        rel = entry.get("sheet") if isinstance(entry, dict) else entry
        cache_key = ("cast", name, frame % 12, size, height)
        if cache_key in self._images:
            return self._images[cache_key]
        sheet = self.image(rel) if isinstance(rel, str) else None
        portrait = None
        if sheet is not None:
            rect = cell_rect(frame, sheet.get_size()).clip(sheet.get_rect())
            if rect.width > 8 and rect.height > 8:
                cell = pygame.Surface(rect.size, pygame.SRCALPHA)
                cell.blit(sheet, (0, 0), rect)
                portrait = standing(cell, height) if height else square_bust(cell, size)
        self._images[cache_key] = portrait
        return portrait

    # Characters ---------------------------------------------------------

    def character_entry(self, char: str, tier: str | None = None) -> dict:
        """Manifest entry for a character with the given tier's overrides applied."""
        entry = self.section("characters").get(char)
        if not isinstance(entry, dict):
            return {}
        merged = {k: v for k, v in entry.items() if k != "tiers"}
        tier = tier or entry.get("default_tier")
        tiers = entry.get("tiers", {})
        if isinstance(tiers, dict) and isinstance(tiers.get(tier), dict):
            merged.update(tiers[tier])
        return merged

    def tier_for_zone(self, zone: int, char: str | None = None) -> str | None:
        tiers = self.manifest.get("tier_by_zone", {})
        if isinstance(tiers, dict) and str(zone) in tiers:
            return tiers[str(zone)]
        if char:
            return self.section("characters").get(char, {}).get("default_tier")
        return None

    def portrait(self, char: str, tier: str | None = None,
                 palette: dict | None = None) -> pygame.Surface:
        entry = self.character_entry(char, tier)
        cache_key = ("portrait", char, tier)
        if cache_key in self._images:
            return self._images[cache_key]
        if not entry and self.use_files:
            self.warn(f"no '{char}' character in manifest.json - using placeholder")
        src = self.image(entry.get("portrait")) if entry else None
        if src is not None and entry.get("portrait_rect"):
            rect = pygame.Rect(*entry["portrait_rect"]).clip(src.get_rect())
            src = src.subsurface(rect).copy()
        portrait = src or placeholders.portrait(palette)
        self._images[cache_key] = portrait
        return portrait

    def cutout(self, char: str, tier: str | None = None, palette: dict | None = None) -> pygame.Surface:
        """Portrait with a solid background removed and cropped to its content."""
        cache_key = ("cutout", char, tier)
        if cache_key not in self._images:
            src = self.portrait(char, tier, palette)
            matte = self.character_entry(char, tier).get("cutout")
            if isinstance(matte, dict) and not has_transparency(src):
                src = _matte(src, int(matte.get("tolerance", 16)), int(matte.get("open", 3)))
            elif not has_transparency(src):
                src = remove_background(src, tolerance=24)
            box = src.get_bounding_rect(min_alpha=40)
            if box.width < 4 or box.height < 4:
                box = src.get_rect()
            self._images[cache_key] = src.subsurface(box).copy()
        return self._images[cache_key]

    def face(self, char: str, tier: str | None = None, palette: dict | None = None,
             size: int = 160) -> pygame.Surface:
        """Square head-and-shoulders crop of the portrait for dialogue and the HUD."""
        cache_key = ("face", char, tier, size)
        entry = self.character_entry(char, tier)
        src = self.image(entry.get("portrait")) if entry.get("face_rect") else None
        if cache_key not in self._images and src is not None:
            crop = src.subsurface(pygame.Rect(*entry["face_rect"]).clip(src.get_rect())).copy()
            self._images[cache_key] = pygame.transform.smoothscale(crop, (size, size))
        if cache_key not in self._images:
            src = self.cutout(char, tier, palette)
            w, h = src.get_size()
            band_h = max(1, int(h * 0.12))
            mask = pygame.mask.from_surface(src.subsurface((0, 0, w, band_h)), 40)
            cx = mask.centroid()[0] if mask.count() else w // 2
            side = max(8, min(w, int(h * 0.27)))
            rect = pygame.Rect(0, 0, side, side)
            rect.center = (cx, int(side * 0.5))
            rect.top = max(0, rect.top)
            rect.clamp_ip(src.get_rect())
            crop = pygame.Surface((side, side), pygame.SRCALPHA)
            crop.blit(src, (0, 0), rect)
            self._images[cache_key] = pygame.transform.smoothscale(crop, (size, size))
        return self._images[cache_key]

    def sprites(self, char: str, tier: str | None = None, scale: float | None = None,
                palette: dict | None = None) -> SpriteSet:
        entry = self.character_entry(char, tier)
        scale = float(scale if scale is not None else entry.get("scale", DEFAULT_SCALE))
        cache_key = (char, tier, scale)
        if cache_key in self._sprites:
            return self._sprites[cache_key]
        if not entry and self.use_files:
            self.warn(f"no '{char}' character in manifest.json - using placeholder")
        sheet = self.image(entry.get("spritesheet"))
        result = None
        if sheet is not None:
            try:
                result = build_sprite_set(sheet, entry, scale)
            except Exception as exc:  # malformed layout or animation data
                self.warn(f"{entry.get('spritesheet')} layout is invalid ({exc}) "
                          "- using placeholder")
            if result is None:
                self.warn(f"{entry.get('spritesheet')} has no usable idle/walk "
                          "animations - using placeholder")
        if result is None:
            result = placeholders.character_sprites(palette, scale)
        self._sprites[cache_key] = result
        return result


def fit_image(src: pygame.Surface, size: tuple[int, int], fit: str = "contain") -> FittedImage:
    """Scale keeping aspect ratio: 'contain' letterboxes, 'cover' crops."""
    w, h = size
    iw, ih = src.get_size()
    ratio = (max if fit == "cover" else min)(w / iw, h / ih)
    sw, sh = max(1, round(iw * ratio)), max(1, round(ih * ratio))
    scaled = pygame.transform.smoothscale(src, (sw, sh))
    out = pygame.Surface(size)
    out.fill(BG_FILL)
    rect = pygame.Rect((w - sw) // 2, (h - sh) // 2, sw, sh)
    out.blit(scaled, rect)
    return FittedImage(out, rect)


def _bands(entry: dict, axis: str, length: int, frame: int) -> list[tuple[int, int]]:
    layout = entry.get("layout") or {}
    bands = layout.get(axis)
    if bands:
        return [(int(a), int(b)) for a, b in bands]
    return [(i * frame, (i + 1) * frame) for i in range(max(1, length // frame))]


def _fit_frame(cell: pygame.Surface, fw: int, fh: int, out_size: tuple[int, int],
               smooth: bool) -> pygame.Surface:
    canvas = pygame.Surface((fw, fh), pygame.SRCALPHA)
    canvas.blit(cell, ((fw - cell.get_width()) // 2, fh - cell.get_height()))
    if out_size == (fw, fh):
        return canvas
    resize = pygame.transform.smoothscale if smooth else pygame.transform.scale
    return resize(canvas, out_size)


def _finish_anims(anims: dict[str, Animation], size: tuple[int, int]) -> SpriteSet | None:
    for kind in ("idle", "walk"):
        for a, b in (("left", "right"), ("right", "left")):
            if f"{kind}_{b}" not in anims and f"{kind}_{a}" in anims:
                anims[f"{kind}_{b}"] = anims[f"{kind}_{a}"].flipped()
    for d in DIRECTIONS:
        if f"idle_{d}" not in anims and f"walk_{d}" in anims:
            anims[f"idle_{d}"] = Animation(anims[f"walk_{d}"].frames[:1], 1)
        if f"walk_{d}" not in anims and f"idle_{d}" in anims:
            anims[f"walk_{d}"] = anims[f"idle_{d}"]
    if "interact" not in anims and "idle_up" in anims:
        anims["interact"] = Animation(anims["idle_up"].frames, 1, loop=False)
    if "idle_down" not in anims:
        return None
    return SpriteSet(anims, placeholder=False, size=size)


def build_sprite_set(sheet: pygame.Surface, entry: dict, scale: float) -> SpriteSet | None:
    specs = entry.get("animations") or {}
    if any("rects" in spec for spec in specs.values()):
        return _build_from_rects(sheet, entry, scale, specs)
    layout = entry.get("layout") or {}
    if layout.get("background") == "flood":
        sheet = remove_background(sheet)
    sw, sh = sheet.get_size()
    fw0 = int(entry.get("frame_width") or 32)
    fh0 = int(entry.get("frame_height") or 32)
    rows = _bands(entry, "rows", sh, fh0)
    cols = _bands(entry, "cols", sw, fw0)
    fw = max(fw0, max(b - a for a, b in cols))
    fh = max(fh0, max(b - a for a, b in rows))
    smooth = bool(entry.get("smooth", False))
    out_size = (max(1, round(fw * scale)), max(1, round(fh * scale)))

    def frame(r: int, c: int) -> pygame.Surface | None:
        if r >= len(rows) or c >= len(cols):
            return None
        (y0, y1), (x0, x1) = rows[r], cols[c]
        cell = sheet.subsurface(pygame.Rect(x0, y0, x1 - x0, y1 - y0).clip(sheet.get_rect()))
        return _fit_frame(cell, fw, fh, out_size, smooth)

    anims: dict[str, Animation] = {}
    for name, spec in (entry.get("animations") or {}).items():
        row = int(spec.get("row", 0))
        start = int(spec.get("start", spec.get("col", 0)))
        count = int(spec.get("frames", 1))
        frames = [frame(row, start + i) for i in range(count)]
        frames = [f for f in frames if f is not None]
        if frames:
            anims[name] = Animation(frames, float(spec.get("fps", 8)), bool(spec.get("loop", True)))
    return _finish_anims(anims, out_size)


def _strip_frame_marks(cell: pygame.Surface) -> None:
    """Flood the panel's orange corner brackets away. Stop at pixels that touch the blue hair."""
    w, h = cell.get_size()

    def at(x: int, y: int):
        return cell.get_at((x, y))

    def touches_hair(x: int, y: int) -> bool:
        for ny in range(y - 1, y + 2):
            for nx in range(x - 1, x + 2):
                if not (0 <= nx < w and 0 <= ny < h):
                    continue
                r, g, b, a = at(nx, ny)
                if a > 10 and b > g and b > 45:
                    return True
        return False

    seen: set[tuple[int, int]] = set()
    stack = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    doomed = []
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
            continue
        seen.add((x, y))
        if not ((x <= 22 or x >= w - 23) and (y <= 22 or y >= h - 23)):
            continue
        r, g, b, a = at(x, y)
        line = a > 10 and r > 100 and r > g + 20 and b < 110
        open_pixel = a < 10 or (r < 100 and g < 75 and b < 70)
        if line and touches_hair(x, y):
            continue
        if not line and not open_pixel:
            continue
        if line:
            doomed.append((x, y))
        stack.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    for x, y in doomed:
        cell.set_at((x, y), (0, 0, 0, 0))


def _grow(mask: pygame.mask.Mask, radius: int) -> pygame.mask.Mask:
    out = pygame.mask.Mask(mask.get_size())
    kernel = pygame.mask.Mask((radius * 2 + 1, radius * 2 + 1), fill=True)
    mask.convolve(kernel, out, (-radius, -radius))
    return out


def _shrink(mask: pygame.mask.Mask, radius: int) -> pygame.mask.Mask:
    inverse = mask.copy()
    inverse.invert()
    out = _grow(inverse, radius)
    out.invert()
    return out


def _matte(src: pygame.Surface, tolerance: int, radius: int, hole: float = 0.004) -> pygame.Surface:
    """Background removal for art whose outlines match the background (black on black).

    Opening the background mask cuts the thin outline channels a plain flood leaks through;
    large enclosed background pockets (between the legs, inside a floor ring) are cleared too,
    and slivers of a neighbouring figure at the crop's side edges are dropped.
    """
    w, h = src.get_size()
    near = pygame.mask.from_threshold(src, src.get_at((0, 0)), (tolerance, tolerance, tolerance, 255))
    opened = _grow(_shrink(near, radius), radius)
    bg = pygame.mask.Mask((w, h))
    for comp in opened.connected_components():
        box = comp.get_bounding_rects()[0]
        edge = box.left == 0 or box.top == 0 or box.right == w or box.bottom == h
        if edge or comp.count() >= hole * w * h:
            bg.draw(comp, (0, 0))
    bg.draw(_grow(bg, radius).overlap_mask(near, (0, 0)), (0, 0))
    fg = bg.copy()
    fg.invert()
    pieces = fg.connected_components()
    biggest = max((p.count() for p in pieces), default=0)
    for piece in pieces:
        box = piece.get_bounding_rects()[0]
        if piece.count() < biggest * 0.02 and (box.left == 0 or box.right == w):
            bg.draw(piece, (0, 0))
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.blit(src, (0, 0))
    bg.to_surface(out, setcolor=(0, 0, 0, 0), unsetcolor=None)
    return out


def _cut_panel(cell: pygame.Surface, radius: int = 3, min_piece: int = 220) -> None:
    """Clear the flat gray panel behind a framed sprite, keeping panel-gray pixels inside her outline."""
    w, h = cell.get_size()
    edge = 9
    panel = pygame.mask.from_threshold(cell, (24, 23, 28, 255), (12, 12, 12, 255))
    body = pygame.mask.from_surface(cell, 10)
    body.erase(panel, (0, 0))
    inner = pygame.mask.Mask((w - edge * 2, h - edge * 2), fill=True)
    framed = pygame.mask.Mask((w, h))
    framed.draw(inner, (edge, edge))
    body = body.overlap_mask(framed, (0, 0))
    body = _shrink(_grow(body, radius), radius)
    gaps = body.copy()
    gaps.invert()
    outside = pygame.mask.Mask((w, h))
    border = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    for x, y in border:
        if gaps.get_at((x, y)) and not outside.get_at((x, y)):
            outside.draw(gaps.connected_component((x, y)), (0, 0))
    outside.invert()
    solid = _grow(_shrink(outside, 3), 3)
    outside = outside.overlap_mask(_grow(solid, 3), (0, 0))
    keep = pygame.mask.Mask((w, h))
    for piece in outside.connected_components(min_piece):
        keep.draw(piece, (0, 0))
    stencil = keep.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
    cell.blit(stencil, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)


def _build_from_rects(sheet: pygame.Surface, entry: dict, scale: float, specs: dict) -> SpriteSet | None:
    """Frames listed as rectangles, for a sheet that is not a uniform grid."""
    layout = entry.get("layout") or {}
    cut = layout.get("background") == "cell"
    smooth = bool(entry.get("smooth", False))
    sized = [(pygame.Rect(*box), float(spec.get("zoom", 1))) for spec in specs.values()
             for box in spec.get("rects", [])]
    if not sized:
        return None
    fw = max(round(r.width * z) for r, z in sized)
    fh = max(round(r.height * z) for r, z in sized)
    out_size = (max(1, round(fw * scale)), max(1, round(fh * scale)))

    def take(box, zoom: float) -> pygame.Surface:
        rect = pygame.Rect(*box).clip(sheet.get_rect())
        cell = sheet.subsurface(rect).copy()
        if cut:
            framed = pygame.Surface(cell.get_size(), pygame.SRCALPHA)
            framed.blit(cell, (0, 0))
            cell = framed
            _strip_frame_marks(cell)
            _cut_panel(cell)
        if zoom != 1:
            size = (max(1, round(cell.get_width() * zoom)), max(1, round(cell.get_height() * zoom)))
            cell = pygame.transform.smoothscale(cell, size)
        return _fit_frame(cell, fw, fh, out_size, smooth)

    anims: dict[str, Animation] = {}
    for name, spec in specs.items():
        zoom = float(spec.get("zoom", 1))
        frames = [take(box, zoom) for box in spec.get("rects", [])]
        if frames:
            anims[name] = Animation(frames, float(spec.get("fps", 8)), bool(spec.get("loop", True)))
    return _finish_anims(anims, out_size)
