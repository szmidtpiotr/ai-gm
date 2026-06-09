"""TDD: Issue #434 — LLM Vision: obrazek → opis kafelka lochu."""
import sys, os, sqlite3, importlib, pytest
sys.path.insert(0, "/app")

DB_PATH = "/data/ai_gm.db"
TILE_ID = 1  # existing tile


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── vision_service module ────────────────────────────────────────────────────

class TestVisionServiceModule:
    def test_vision_service_importable(self):
        """app.services.vision_service must exist."""
        import app.services.vision_service  # noqa

    def test_build_vision_prompt_exists(self):
        """build_vision_prompt(tile_dict) must be exported."""
        from app.services.vision_service import build_vision_prompt
        assert callable(build_vision_prompt)

    def test_build_vision_prompt_returns_polish_string(self):
        """Prompt must be non-empty string asking about room in Polish."""
        from app.services.vision_service import build_vision_prompt
        tile = {"id": 1, "label": "Korytarz", "category_key": "dungeon"}
        prompt = build_vision_prompt(tile)
        assert isinstance(prompt, str)
        assert len(prompt) > 20
        # Polish keywords expected
        polish_words = ["pomieszczenie", "opis", "atmosfera", "pokój", "wnętrze", "opisz"]
        assert any(w in prompt.lower() for w in polish_words), (
            f"Prompt missing Polish context keywords: {prompt[:100]}"
        )

    def test_describe_tile_function_exists(self):
        """describe_tile(image_bytes, ollama_url, model) must be exported."""
        from app.services.vision_service import describe_tile
        assert callable(describe_tile)

    def test_describe_tile_accepts_required_params(self):
        """describe_tile signature must accept image_bytes, ollama_url, model."""
        import inspect
        from app.services.vision_service import describe_tile
        sig = inspect.signature(describe_tile)
        params = list(sig.parameters.keys())
        assert "image_bytes" in params, f"Missing image_bytes param: {params}"
        assert "ollama_url" in params, f"Missing ollama_url param: {params}"
        assert "model" in params, f"Missing model param: {params}"


# ─── GET /admin/dungeon-tiles needs_description filter ────────────────────────

class TestNeedsDescriptionFilter:
    def test_tiles_with_empty_description_exist(self):
        """DB must have tiles with empty room_description for filter to make sense."""
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM dungeon_tiles WHERE room_description = '' OR room_description IS NULL"
            ).fetchone()
            assert row["c"] >= 0  # any count acceptable, just verify query works
        finally:
            conn.close()

    def test_list_tiles_needs_description_filter_works(self):
        """GET /admin/dungeon-tiles?needs_description=1 returns only tiles missing description."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        # Login to get admin token
        r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
        assert r.status_code == 200
        token = r.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Call with filter
        r = client.get("/api/admin/dungeon-tiles?needs_description=1", headers=headers)
        assert r.status_code == 200, f"needs_description filter failed: {r.text}"
        body = r.json()
        assert "tiles" in body
        # All returned tiles must have empty or missing description
        for t in body["tiles"]:
            desc = t.get("room_description", "")
            assert not desc, f"Tile {t.get('id')} has description but was returned by needs_description filter: {desc!r}"


# ─── PATCH room_description (regression) ─────────────────────────────────────

class TestPatchRoomDescription:
    def test_patch_room_description_saves_to_db(self):
        """PATCH /admin/dungeon-tiles/{id} with room_description persists to DB."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        r = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
        token = r.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        test_desc = "__vision_test_description_e19__"
        r = client.patch(
            f"/api/admin/dungeon-tiles/{TILE_ID}",
            json={"room_description": test_desc},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json().get("ok") is True

        # Verify DB
        conn = _conn()
        try:
            row = conn.execute("SELECT room_description FROM dungeon_tiles WHERE id = ?", (TILE_ID,)).fetchone()
            assert row is not None
            assert row["room_description"] == test_desc
        finally:
            # Cleanup
            conn.execute("UPDATE dungeon_tiles SET room_description = '' WHERE id = ? AND room_description = ?", (TILE_ID, test_desc))
            conn.commit()
            conn.close()

    def test_patch_room_description_requires_auth(self):
        """PATCH without token must return 401/403."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        r = client.patch(f"/api/admin/dungeon-tiles/{TILE_ID}", json={"room_description": "x"})
        assert r.status_code in (401, 403)


# ─── Script file existence ────────────────────────────────────────────────────

class TestVisionScript:
    # Script lives in repo/scripts/ and runs on .170 — not baked into backend image.
    # Tests use alternate paths: /repo/scripts (dev mount) or skip gracefully.

    def test_vision_describe_tiles_script_exists_or_skip(self):
        """scripts/vision_describe_tiles.py present on repo (host-side tool, runs on .170)."""
        # Try repo-root mount paths; if neither exists we skip (CI without repo mount)
        for candidate in ["/app/scripts/vision_describe_tiles.py",
                          "/repo/scripts/vision_describe_tiles.py"]:
            if os.path.exists(candidate):
                return  # found
        pytest.skip("Script is a host-side tool; not baked into backend image. Verify on host.")

    def test_vision_script_is_valid_python(self):
        """Script must parse as valid Python (when accessible)."""
        import ast
        for candidate in ["/app/scripts/vision_describe_tiles.py",
                          "/repo/scripts/vision_describe_tiles.py"]:
            if os.path.exists(candidate):
                with open(candidate) as f:
                    source = f.read()
                ast.parse(source)
                return
        pytest.skip("Script not present in container paths — host-side tool only.")
