"""TDD: Issue #460 (E19c) — Tile compositor redesign.

Removes 70px stone wall frame → thin border 4-6px.
Replaces arch sprites → flat amber door markers on edges.
New endpoint: POST /{tile_id}/generate-description.
"""

import io
import sqlite3
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.services.tile_compositor import composite_tile, TILE_SIZE

client = TestClient(app)
DB_PATH = "/data/ai_gm.db"

# STONE_FILL from old compositor — should NOT appear after redesign
OLD_STONE_FILL_RGB = (34, 30, 34)
# Amber/orange door marker color: #f59e0b
DOOR_MARKER_RGB = (245, 158, 11)

_admin_token_cache = None


def _admin_token() -> str:
    global _admin_token_cache
    if not _admin_token_cache:
        r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
        assert r.status_code == 200
        _admin_token_cache = r.json()["token"]
    return _admin_token_cache


def _auth():
    return {"Authorization": f"Bearer {_admin_token()}"}


def _make_solid_png(color=(200, 100, 50), size=512) -> bytes:
    """Create solid-color PNG for testing compositor."""
    img = Image.new("RGB", (size, size), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _pixel_at(result_bytes: bytes, x: int, y: int) -> tuple:
    """Get RGB pixel at (x, y) from PNG bytes."""
    img = Image.open(io.BytesIO(result_bytes)).convert("RGB")
    return img.getpixel((x, y))


def _first_tile_with_id() -> int:
    """Return id of first active tile in DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id FROM dungeon_tiles WHERE is_active=1 ORDER BY id LIMIT 1"
        ).fetchone()
        return row["id"] if row else 1
    finally:
        conn.close()


# ── Compositor: no thick wall frame ──────────────────────────────────────────

class TestCompositorNoThickWall:
    """After redesign: old 70px STONE_FILL wall should NOT cover interior pixels."""

    def test_interior_pixel_not_stone_fill(self):
        """Pixel at (35, 35) must not be old STONE_FILL (inside old wall zone)."""
        raw = _make_solid_png(color=(200, 100, 50))
        result = composite_tile(raw, doors=[], overlays={})
        px = _pixel_at(result, 35, 35)
        assert px != OLD_STONE_FILL_RGB, (
            f"pixel at (35,35) is STONE_FILL {px} — old thick wall still active. "
            "Expected: close to original image color after redesign."
        )

    def test_interior_pixel_not_stone_fill_large_tile(self):
        """Same check at (60, 60) — well inside old 70px wall zone."""
        raw = _make_solid_png(color=(180, 90, 40))
        result = composite_tile(raw, doors=[], overlays={})
        px = _pixel_at(result, 60, 60)
        assert px != OLD_STONE_FILL_RGB, (
            f"pixel at (60,60) is STONE_FILL {px} — thick wall still present at 60px depth"
        )


# ── Compositor: flat amber door markers ──────────────────────────────────────

class TestCompositorDoorMarkers:
    """Active door sides should show amber flat rectangles at edge centers."""

    def test_north_door_has_amber_marker(self):
        """With N door: center-top pixel should be amber (#f59e0b)."""
        raw = _make_solid_png(color=(50, 50, 50))
        result = composite_tile(raw, doors=["N"], overlays={})
        # Center of N edge
        px = _pixel_at(result, TILE_SIZE // 2, 5)
        r, g, b = px
        assert r > 200 and g > 100 and b < 50, (
            f"N door pixel at (256, 5) is {px} — expected amber ~(245,158,11). "
            "No flat amber marker found."
        )

    def test_south_door_has_amber_marker(self):
        """With S door: center-bottom pixel should be amber."""
        raw = _make_solid_png(color=(50, 50, 50))
        result = composite_tile(raw, doors=["S"], overlays={})
        px = _pixel_at(result, TILE_SIZE // 2, TILE_SIZE - 5)
        r, g, b = px
        assert r > 200 and g > 100 and b < 50, (
            f"S door pixel at (256, 507) is {px} — expected amber. No marker found."
        )

    def test_east_door_has_amber_marker(self):
        """With E door: right-center pixel should be amber."""
        raw = _make_solid_png(color=(50, 50, 50))
        result = composite_tile(raw, doors=["E"], overlays={})
        px = _pixel_at(result, TILE_SIZE - 5, TILE_SIZE // 2)
        r, g, b = px
        assert r > 200 and g > 100 and b < 50, (
            f"E door pixel at (507, 256) is {px} — expected amber. No marker found."
        )

    def test_west_door_has_amber_marker(self):
        """With W door: left-center pixel should be amber."""
        raw = _make_solid_png(color=(50, 50, 50))
        result = composite_tile(raw, doors=["W"], overlays={})
        px = _pixel_at(result, 5, TILE_SIZE // 2)
        r, g, b = px
        assert r > 200 and g > 100 and b < 50, (
            f"W door pixel at (5, 256) is {px} — expected amber. No marker found."
        )

    def test_no_doors_no_markers(self):
        """With no doors: center edges should NOT be amber."""
        raw = _make_solid_png(color=(50, 50, 50))
        result = composite_tile(raw, doors=[], overlays={})
        # Check all 4 edge centers — should be original-ish, not amber
        checks = [
            (TILE_SIZE // 2, 5),        # N
            (TILE_SIZE // 2, TILE_SIZE - 5),  # S
            (TILE_SIZE - 5, TILE_SIZE // 2),  # E
            (5, TILE_SIZE // 2),        # W
        ]
        for x, y in checks:
            px = _pixel_at(result, x, y)
            r, g, b = px
            assert not (r > 200 and g > 100 and b < 50), (
                f"No doors but amber found at ({x},{y}) = {px}"
            )


# ── Compositor: thin border exists ───────────────────────────────────────────

class TestCompositorThinBorder:
    """A thin dark border should be present at edges."""

    def test_corner_pixel_is_dark(self):
        """Pixel at (0, 0) should be dark (border), not original image color."""
        raw = _make_solid_png(color=(200, 200, 200))  # bright white-ish
        result = composite_tile(raw, doors=[], overlays={})
        px = _pixel_at(result, 0, 0)
        brightness = sum(px) / 3
        assert brightness < 100, (
            f"Corner pixel (0,0) = {px} brightness={brightness:.0f} — expected dark border"
        )

    def test_output_correct_size(self):
        """Output is always TILE_SIZE × TILE_SIZE."""
        raw = _make_solid_png(size=256)  # different input size
        result = composite_tile(raw, doors=["N", "S"])
        img = Image.open(io.BytesIO(result))
        assert img.size == (TILE_SIZE, TILE_SIZE)


# ── generate-description endpoint ────────────────────────────────────────────

class TestGenerateDescriptionEndpoint:
    """POST /api/admin/dungeon-tiles/{id}/generate-description returns Polish description."""

    def _reset_description(self, tile_id: int):
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "UPDATE dungeon_tiles SET room_description = '' WHERE id = ?", (tile_id,)
            )
            conn.commit()
        finally:
            conn.close()

    def test_endpoint_returns_200_with_description(self):
        """Endpoint returns 200 and non-empty room_description string."""
        tile_id = _first_tile_with_id()
        self._reset_description(tile_id)
        r = client.post(
            f"/api/admin/dungeon-tiles/{tile_id}/generate-description",
            headers=_auth(),
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert "room_description" in body, f"missing room_description: {body}"
        assert len(body["room_description"]) > 20, "description too short"

    def test_endpoint_saves_to_db(self):
        """Generated description is persisted in dungeon_tiles.room_description."""
        tile_id = _first_tile_with_id()
        self._reset_description(tile_id)
        r = client.post(
            f"/api/admin/dungeon-tiles/{tile_id}/generate-description",
            headers=_auth(),
        )
        assert r.status_code == 200
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT room_description FROM dungeon_tiles WHERE id = ?", (tile_id,)
            ).fetchone()
            assert row and row["room_description"], "description not saved to DB"
            assert len(row["room_description"]) > 20
        finally:
            conn.close()

    def test_endpoint_requires_auth(self):
        """Unauthenticated → 401."""
        tile_id = _first_tile_with_id()
        r = client.post(f"/api/admin/dungeon-tiles/{tile_id}/generate-description")
        assert r.status_code == 401

    def test_nonexistent_tile_returns_404(self):
        """Unknown tile_id → 404."""
        r = client.post(
            "/api/admin/dungeon-tiles/999999/generate-description",
            headers=_auth(),
        )
        assert r.status_code == 404
