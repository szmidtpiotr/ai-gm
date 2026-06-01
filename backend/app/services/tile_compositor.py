"""Mechanical dungeon tile compositor.

Replaces unreliable AI-generated walls + doors with deterministic post-processing:
  1. Take raw AI image (interior decor only, no walls/doors)
  2. Overlay procedural stone wall frame (always consistent thickness)
  3. Overlay stone archway sprite at each active door side

This guarantees:
  - Walls always exactly `WALL_BORDER` pixels thick on each edge
  - Doors always appear at admin-defined positions (or canonical defaults)
  - Same visual language across all tile categories
"""

from __future__ import annotations

import io
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter

# ── Geometry ──────────────────────────────────────────────────────────────────

TILE_SIZE = 512                                # output canvas (square)
WALL_BORDER = 70                               # stone wall thickness in px
DOOR_W_DEFAULT = 90                            # arch width at scale=1.0
DOOR_H_DEFAULT = WALL_BORDER                   # arch height = wall thickness

# Canonical door anchor positions (relative 0..1 to tile size).
# Each door is centered on its wall midpoint, with the arch sitting *within*
# the wall thickness (rounded part at outer edge, opening at inner edge).
DEFAULT_DOOR_OVERLAYS: dict[str, dict[str, float]] = {
    "N": {"x": 0.50, "y": WALL_BORDER / 2 / TILE_SIZE,           "scale": 1.0, "rot": 0},
    "S": {"x": 0.50, "y": (TILE_SIZE - WALL_BORDER / 2) / TILE_SIZE, "scale": 1.0, "rot": 180},
    "E": {"x": (TILE_SIZE - WALL_BORDER / 2) / TILE_SIZE, "y": 0.50, "scale": 1.0, "rot": 270},
    "W": {"x": WALL_BORDER / 2 / TILE_SIZE,           "y": 0.50, "scale": 1.0, "rot": 90},
}

# ── Colors ────────────────────────────────────────────────────────────────────

STONE_FILL    = (34, 30, 34, 255)              # main wall stone color
STONE_HIGHLIGHT = (58, 52, 56, 255)            # subtle horizontal mortar lines
STONE_RIM     = (88, 82, 86, 255)              # arch rim highlight
INNER_SHADOW  = (6, 4, 8, 255)                 # boundary between wall and floor
ARCH_INNER    = (4, 3, 6, 255)                 # darkness inside door opening


# ── Public API ────────────────────────────────────────────────────────────────

def composite_tile(
    raw_png_bytes: bytes,
    doors: Iterable[str],
    overlays: dict[str, dict[str, float]] | None = None,
    tile_size: int = TILE_SIZE,
) -> bytes:
    """Composite raw AI image + procedural walls + door arches → final PNG bytes.

    Args:
        raw_png_bytes: Raw AI-generated image (any size, resized to tile_size).
        doors: Sides where doors are active, subset of {"N","S","E","W"}.
        overlays: Per-side overrides {side: {x, y, scale, rot}}. Missing entries
                  fall back to canonical defaults.
        tile_size: Output canvas dimensions (square).

    Returns:
        PNG-encoded bytes of the final composited tile.
    """
    raw = Image.open(io.BytesIO(raw_png_bytes)).convert("RGBA")
    if raw.size != (tile_size, tile_size):
        raw = raw.resize((tile_size, tile_size), Image.LANCZOS)

    canvas = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    canvas.paste(raw, (0, 0))

    wall_frame = _build_wall_frame(tile_size)
    canvas = Image.alpha_composite(canvas, wall_frame)

    door_layer = _build_door_layer(tile_size, list(doors), overlays or {})
    canvas = Image.alpha_composite(canvas, door_layer)

    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def default_overlays_for(doors: Iterable[str]) -> dict[str, dict[str, float]]:
    """Return the canonical per-side overlay dict for the given active doors."""
    return {d: dict(DEFAULT_DOOR_OVERLAYS[d]) for d in doors if d in DEFAULT_DOOR_OVERLAYS}


# ── Internal: procedural wall frame ───────────────────────────────────────────

def _build_wall_frame(size: int) -> Image.Image:
    """Dark stone border frame with transparent center.

    4 solid strips on each edge, 2px inner shadow at the wall→floor boundary,
    subtle horizontal mortar lines for texture.
    """
    border = int(round(WALL_BORDER * size / TILE_SIZE))
    frame = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)

    # 4 stone strips (top, bottom, left, right — corners share with top/bottom)
    draw.rectangle([(0, 0), (size, border)], fill=STONE_FILL)
    draw.rectangle([(0, size - border), (size, size)], fill=STONE_FILL)
    draw.rectangle([(0, border), (border, size - border)], fill=STONE_FILL)
    draw.rectangle([(size - border, border), (size, size - border)], fill=STONE_FILL)

    # Subtle horizontal mortar lines on top/bottom strips
    mortar_h = max(border // 3, 12)
    for y_off in (mortar_h, 2 * mortar_h):
        if y_off < border:
            draw.line([(0, y_off), (size, y_off)], fill=STONE_HIGHLIGHT, width=1)
            draw.line([(0, size - y_off - 1), (size, size - y_off - 1)],
                      fill=STONE_HIGHLIGHT, width=1)
    # Vertical mortar lines on left/right strips
    for x_off in (mortar_h, 2 * mortar_h):
        if x_off < border:
            draw.line([(x_off, border), (x_off, size - border)],
                      fill=STONE_HIGHLIGHT, width=1)
            draw.line([(size - x_off - 1, border), (size - x_off - 1, size - border)],
                      fill=STONE_HIGHLIGHT, width=1)

    # Inner shadow rectangle (wall→floor boundary)
    draw.rectangle(
        [(border - 1, border - 1), (size - border, size - border)],
        outline=INNER_SHADOW, width=2,
    )
    return frame


# ── Internal: door arch sprites ───────────────────────────────────────────────

def _build_door_arch(width: int, height: int) -> Image.Image:
    """N-facing stone archway sprite (rounded top, opens downward).

    Used as the base; rotated 90/180/270 for E/S/W sides.
    """
    arch = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(arch)

    # Outer stone frame — semicircle top + rectangle body
    radius = width // 2
    if height >= radius:
        draw.pieslice([(0, 0), (width, 2 * radius)], 180, 360, fill=STONE_FILL)
        draw.rectangle([(0, radius), (width, height)], fill=STONE_FILL)
    else:
        # Squat arch: scale semicircle vertically to fit
        draw.pieslice([(0, 0), (width, 2 * height)], 180, 360, fill=STONE_FILL)

    # Inner dark cutout (the "opening")
    pad = max(6, int(width * 0.22))
    in_w = width - 2 * pad
    in_h = height - pad
    in_r = in_w // 2
    if in_w > 0 and in_h > 0:
        if in_h >= in_r:
            draw.pieslice([(pad, pad), (pad + in_w, pad + 2 * in_r)],
                          180, 360, fill=ARCH_INNER)
            draw.rectangle([(pad, pad + in_r), (pad + in_w, height)],
                           fill=ARCH_INNER)
        else:
            draw.pieslice([(pad, pad), (pad + in_w, pad + 2 * in_h)],
                          180, 360, fill=ARCH_INNER)

    # Top rim highlight (gives the arch a chiseled-stone look)
    draw.arc([(0, 0), (width, 2 * radius)], 180, 360, fill=STONE_RIM, width=2)

    return arch


def _build_door_layer(
    size: int,
    doors: list[str],
    overlays: dict[str, dict[str, float]],
) -> Image.Image:
    """Composite a transparent layer with one arch sprite per active door."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for side in doors:
        if side not in DEFAULT_DOOR_OVERLAYS:
            continue
        # Merge default + admin override
        defaults = DEFAULT_DOOR_OVERLAYS[side]
        ov = {**defaults, **(overlays.get(side) or {})}
        scale = max(0.3, min(2.5, float(ov.get("scale", 1.0))))
        rot = float(ov.get("rot", defaults["rot"]))
        cx = int(float(ov.get("x", defaults["x"])) * size)
        cy = int(float(ov.get("y", defaults["y"])) * size)

        # Base sprite (N-facing) then rotate to requested orientation
        w = max(8, int(DOOR_W_DEFAULT * scale))
        h = max(8, int(DOOR_H_DEFAULT * scale))
        sprite = _build_door_arch(w, h)
        if rot:
            sprite = sprite.rotate(rot, expand=True, resample=Image.BICUBIC)

        # Paste centered at (cx, cy)
        sw, sh = sprite.size
        layer.alpha_composite(sprite, (cx - sw // 2, cy - sh // 2))
    return layer
