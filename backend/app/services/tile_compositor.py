"""Dungeon tile compositor — thin border + flat door markers.

Flow (E19c redesign): FLUX generates full 512×512 image with baked walls/interior.
Compositor adds only:
  1. Thin black border (BORDER_THICKNESS px) around entire tile
  2. Flat amber/orange rectangle markers at active door sides (N/S/E/W)

Previous 70px stone wall frame and arch sprites removed — they obscured ~14% of
the AI image and are no longer needed since FLUX generates complete room art.
"""

from __future__ import annotations

import io
from typing import Iterable

from PIL import Image, ImageDraw

# ── Geometry ──────────────────────────────────────────────────────────────────

TILE_SIZE = 512                    # output canvas (square)
WALL_BORDER = 0                    # kept for API compatibility; no longer used
BORDER_THICKNESS = 5               # thin black outline around tile
DOOR_MARKER_LONG = 100             # door marker length along edge (px)
DOOR_MARKER_SHORT = 22             # door marker depth perpendicular to edge (px)

# Canonical overlay positions kept for API compatibility with door overlay editor.
DEFAULT_DOOR_OVERLAYS: dict[str, dict[str, float]] = {
    "N": {"x": 0.50, "y": 0.02, "scale": 1.0, "rot": 0},
    "S": {"x": 0.50, "y": 0.98, "scale": 1.0, "rot": 180},
    "E": {"x": 0.98, "y": 0.50, "scale": 1.0, "rot": 270},
    "W": {"x": 0.02, "y": 0.50, "scale": 1.0, "rot": 90},
}

# ── Colors ────────────────────────────────────────────────────────────────────

BORDER_COLOR = (10, 10, 10, 255)           # thin tile outline
DOOR_MARKER_COLOR = (245, 158, 11, 255)    # amber #f59e0b — door passage indicator


# ── Public API ────────────────────────────────────────────────────────────────

def composite_tile(
    raw_png_bytes: bytes,
    doors: Iterable[str],
    overlays: dict[str, dict[str, float]] | None = None,
    tile_size: int = TILE_SIZE,
) -> bytes:
    """Composite raw AI image + thin border + flat door markers → final PNG bytes.

    Args:
        raw_png_bytes: Raw AI-generated image (any size, resized to tile_size).
        doors: Sides with active doors, subset of {"N","S","E","W"}.
        overlays: Accepted for API compatibility; not used for flat markers.
        tile_size: Output canvas dimensions (square).

    Returns:
        PNG-encoded bytes of the final composited tile.
    """
    raw = Image.open(io.BytesIO(raw_png_bytes)).convert("RGBA")
    if raw.size != (tile_size, tile_size):
        raw = raw.resize((tile_size, tile_size), Image.LANCZOS)

    canvas = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    canvas.paste(raw, (0, 0))

    border_layer = _build_thin_border(tile_size)
    canvas = Image.alpha_composite(canvas, border_layer)

    door_layer = _build_door_markers(tile_size, list(doors))
    canvas = Image.alpha_composite(canvas, door_layer)

    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def default_overlays_for(doors: Iterable[str]) -> dict[str, dict[str, float]]:
    """Return canonical per-side overlay dict for given active doors (API compat)."""
    return {d: dict(DEFAULT_DOOR_OVERLAYS[d]) for d in doors if d in DEFAULT_DOOR_OVERLAYS}


# ── Internal: thin border ─────────────────────────────────────────────────────

def _build_thin_border(size: int) -> Image.Image:
    """4-sided thin black outline at tile perimeter."""
    frame = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)
    b = BORDER_THICKNESS
    draw.rectangle([(0, 0), (size - 1, b - 1)], fill=BORDER_COLOR)           # top
    draw.rectangle([(0, size - b), (size - 1, size - 1)], fill=BORDER_COLOR)  # bottom
    draw.rectangle([(0, b), (b - 1, size - b - 1)], fill=BORDER_COLOR)        # left
    draw.rectangle([(size - b, b), (size - 1, size - b - 1)], fill=BORDER_COLOR)  # right
    return frame


# ── Internal: flat door markers ───────────────────────────────────────────────

def _build_door_markers(size: int, doors: list[str]) -> Image.Image:
    """Flat amber rectangle at center of each active door side.

    Markers are always at edge midpoints regardless of overlay positions —
    they indicate passage locations on the finished tile art.
    """
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    half = DOOR_MARKER_LONG // 2
    depth = DOOR_MARKER_SHORT
    mid = size // 2

    for side in doors:
        if side == "N":
            draw.rectangle([(mid - half, 0), (mid + half, depth)],
                           fill=DOOR_MARKER_COLOR)
        elif side == "S":
            draw.rectangle([(mid - half, size - depth), (mid + half, size)],
                           fill=DOOR_MARKER_COLOR)
        elif side == "E":
            draw.rectangle([(size - depth, mid - half), (size, mid + half)],
                           fill=DOOR_MARKER_COLOR)
        elif side == "W":
            draw.rectangle([(0, mid - half), (depth, mid + half)],
                           fill=DOOR_MARKER_COLOR)
    return layer
