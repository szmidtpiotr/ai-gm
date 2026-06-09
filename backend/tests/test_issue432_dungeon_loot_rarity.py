"""TDD: Issue #432 (E17) — Dungeon loot rarity tiers.

5 rarity tiers (common→legendary) mapped to dungeon difficulty D1–D5.
Boss rooms always drop epic/legendary. Rarity field added to rooms
and loot rolls in dungeon instances.
"""

import json
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
DB_PATH = "/data/ai_gm.db"


# ── FAZA 1: Constants + mapping function ──────────────────────────────────────

class TestRarityTiersConstant:
    """RARITY_TIERS must be importable and have 5 tiers with required fields."""

    def test_rarity_tiers_importable(self):
        """dungeon_service.RARITY_TIERS must exist."""
        from app.services.dungeon_service import RARITY_TIERS
        assert RARITY_TIERS is not None

    def test_rarity_tiers_has_five_entries(self):
        """Exactly 5 tiers: common, uncommon, rare, epic, legendary."""
        from app.services.dungeon_service import RARITY_TIERS
        assert len(RARITY_TIERS) == 5, f"Expected 5 tiers, got {len(RARITY_TIERS)}: {list(RARITY_TIERS.keys())}"

    def test_rarity_tiers_keys(self):
        """Keys must be: common, uncommon, rare, epic, legendary."""
        from app.services.dungeon_service import RARITY_TIERS
        expected = {"common", "uncommon", "rare", "epic", "legendary"}
        assert set(RARITY_TIERS.keys()) == expected, f"Got: {set(RARITY_TIERS.keys())}"

    def test_rarity_tiers_have_label_and_color(self):
        """Each tier must have at least 'label' and 'color' fields."""
        from app.services.dungeon_service import RARITY_TIERS
        for key, tier in RARITY_TIERS.items():
            assert "label" in tier, f"Tier '{key}' missing 'label'"
            assert "color" in tier, f"Tier '{key}' missing 'color'"

    def test_rarity_tiers_labels_are_polish(self):
        """Labels must include Polish tier names (Zwykły, Ulepszony, Rzadki, Epicki, Legendarny)."""
        from app.services.dungeon_service import RARITY_TIERS
        labels = [t["label"] for t in RARITY_TIERS.values()]
        expected_labels = {"Zwykły", "Ulepszony", "Rzadki", "Epicki", "Legendarny"}
        assert set(labels) == expected_labels, f"Got labels: {labels}"


class TestGetLootRarityForDifficulty:
    """get_loot_rarity_for_difficulty(difficulty, is_boss) returns correct tier."""

    def test_d1_normal_returns_common_or_uncommon(self):
        """D1 (easiest) → common or uncommon."""
        from app.services.dungeon_service import get_loot_rarity_for_difficulty
        result = get_loot_rarity_for_difficulty(1, is_boss=False)
        assert result in ("common", "uncommon"), f"D1 non-boss: expected common/uncommon, got {result!r}"

    def test_d2_normal_returns_uncommon_or_rare(self):
        """D2 → uncommon or rare."""
        from app.services.dungeon_service import get_loot_rarity_for_difficulty
        result = get_loot_rarity_for_difficulty(2, is_boss=False)
        assert result in ("uncommon", "rare"), f"D2: expected uncommon/rare, got {result!r}"

    def test_d3_normal_returns_rare_or_epic(self):
        """D3 → rare or epic."""
        from app.services.dungeon_service import get_loot_rarity_for_difficulty
        result = get_loot_rarity_for_difficulty(3, is_boss=False)
        assert result in ("rare", "epic"), f"D3: expected rare/epic, got {result!r}"

    def test_d4_normal_returns_epic_or_legendary(self):
        """D4 → epic or legendary."""
        from app.services.dungeon_service import get_loot_rarity_for_difficulty
        result = get_loot_rarity_for_difficulty(4, is_boss=False)
        assert result in ("epic", "legendary"), f"D4: expected epic/legendary, got {result!r}"

    def test_d5_boss_returns_epic_or_legendary(self):
        """D5 boss → epic or legendary (guaranteed top tier)."""
        from app.services.dungeon_service import get_loot_rarity_for_difficulty
        result = get_loot_rarity_for_difficulty(5, is_boss=True)
        assert result in ("epic", "legendary"), f"D5 boss: expected epic/legendary, got {result!r}"

    def test_any_difficulty_boss_returns_epic_or_legendary(self):
        """Boss flag always elevates to epic/legendary regardless of dungeon difficulty."""
        from app.services.dungeon_service import get_loot_rarity_for_difficulty
        for d in range(1, 6):
            result = get_loot_rarity_for_difficulty(d, is_boss=True)
            assert result in ("epic", "legendary"), (
                f"Boss D{d}: expected epic/legendary, got {result!r}"
            )

    def test_d1_default_is_non_boss(self):
        """Default is_boss=False — function works without keyword arg."""
        from app.services.dungeon_service import get_loot_rarity_for_difficulty
        result = get_loot_rarity_for_difficulty(1)
        assert result in ("common", "uncommon", "rare", "epic", "legendary"), (
            f"Unexpected rarity: {result!r}"
        )

    def test_result_is_valid_tier_key(self):
        """Return value must always be a key in RARITY_TIERS."""
        from app.services.dungeon_service import RARITY_TIERS, get_loot_rarity_for_difficulty
        for d in range(1, 6):
            for is_boss in (False, True):
                result = get_loot_rarity_for_difficulty(d, is_boss=is_boss)
                assert result in RARITY_TIERS, (
                    f"D{d} boss={is_boss}: '{result}' not in RARITY_TIERS"
                )


# ── FAZA 1: DB schema — dungeon_difficulty column ──────────────────────────────

class TestDungeonDifficultyColumn:
    """game_dungeons must have dungeon_difficulty INTEGER column (default 1)."""

    def test_dungeon_difficulty_column_exists(self):
        """game_dungeons must have dungeon_difficulty column."""
        conn = sqlite3.connect(DB_PATH)
        try:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(game_dungeons)").fetchall()]
            assert "dungeon_difficulty" in cols, (
                f"game_dungeons missing 'dungeon_difficulty' column. Columns: {cols}"
            )
        finally:
            conn.close()

    def test_dungeon_difficulty_default_is_1(self):
        """Existing dungeons without explicit difficulty must have dungeon_difficulty=1."""
        conn = sqlite3.connect(DB_PATH)
        try:
            rows = conn.execute(
                "SELECT key, dungeon_difficulty FROM game_dungeons WHERE dungeon_difficulty IS NOT NULL LIMIT 5"
            ).fetchall()
            assert len(rows) > 0, "No dungeons found with dungeon_difficulty set"
            for key, diff in rows:
                assert diff >= 1, f"Dungeon {key!r} has invalid difficulty {diff}"
                assert diff <= 5, f"Dungeon {key!r} has out-of-range difficulty {diff}"
        finally:
            conn.close()


# ── FAZA 1: Dungeon instance rooms have rarity field ──────────────────────────

class TestDungeonInstanceRarityField:
    """Dungeon instances built by _build_dungeon_instance must tag rooms with rarity."""

    def test_boss_room_has_rarity_field(self):
        """Boss room in dungeon instance must have 'rarity' field."""
        from app.services.dungeon_service import _build_dungeon_instance
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            dungeon_row = conn.execute(
                "SELECT * FROM game_dungeons WHERE key = 'goblin_warren' LIMIT 1"
            ).fetchone()
            if not dungeon_row:
                pytest.skip("goblin_warren not found")
            instance = _build_dungeon_instance(dict(dungeon_row), hero_level=1)
        finally:
            conn.close()

        boss_room = next((r for r in instance["rooms"] if r.get("is_boss")), None)
        assert boss_room is not None, "No boss room found in dungeon instance"
        assert "rarity" in boss_room, f"Boss room missing 'rarity' field: {list(boss_room.keys())}"
        assert boss_room["rarity"] in ("epic", "legendary"), (
            f"Boss room rarity must be epic/legendary, got: {boss_room['rarity']!r}"
        )

    def test_chest_room_has_rarity_field(self):
        """Chest rooms must have 'rarity' field based on dungeon difficulty."""
        from app.services.dungeon_service import _build_dungeon_instance, RARITY_TIERS
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            dungeon_row = conn.execute(
                "SELECT * FROM game_dungeons WHERE key = 'goblin_warren' LIMIT 1"
            ).fetchone()
            if not dungeon_row:
                pytest.skip("goblin_warren not found")
            d = dict(dungeon_row)
            d["room_types_json"] = json.dumps({"combat": 0, "chest": 100, "trap": 0, "riddle": 0, "rest": 0})
            d["rooms"] = 3
            instance = _build_dungeon_instance(d, hero_level=1)
        finally:
            conn.close()

        chest_rooms = [r for r in instance["rooms"] if r.get("room_type") == "chest"]
        if not chest_rooms:
            pytest.skip("No chest rooms generated (random)")
        for room in chest_rooms:
            assert "rarity" in room, f"Chest room missing 'rarity': {list(room.keys())}"
            assert room["rarity"] in RARITY_TIERS, (
                f"Chest room rarity {room['rarity']!r} not a valid tier"
            )

    def test_dungeon_instance_has_dungeon_difficulty(self):
        """Dungeon instance dict must include 'dungeon_difficulty' field."""
        from app.services.dungeon_service import _build_dungeon_instance
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            dungeon_row = conn.execute(
                "SELECT * FROM game_dungeons WHERE key = 'goblin_warren' LIMIT 1"
            ).fetchone()
            if not dungeon_row:
                pytest.skip("goblin_warren not found")
            instance = _build_dungeon_instance(dict(dungeon_row), hero_level=1)
        finally:
            conn.close()

        assert "dungeon_difficulty" in instance, (
            f"Instance missing 'dungeon_difficulty': {list(instance.keys())}"
        )


# ── FAZA 1: Backward compat ───────────────────────────────────────────────────

class TestRarityBackwardCompat:
    """Existing dungeon enter endpoint must still work after rarity changes."""

    def setup_method(self):
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "DELETE FROM character_dungeon_runs WHERE character_id = 999377 AND location_key = 'goblin_warren'"
            )
            sf_row = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = 999445 LIMIT 1"
            ).fetchone()
            if sf_row and sf_row[0]:
                sf = json.loads(sf_row[0] or "{}")
                sf.pop("dungeon_run", None)
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = 999445",
                    (json.dumps(sf),),
                )
            conn.commit()
        finally:
            conn.close()

    def teardown_method(self):
        self.setup_method()

    def test_enter_dungeon_still_returns_ok(self):
        """POST /dungeons/{key}/enter must still return ok=True after rarity changes."""
        r = client.post("/api/auth/login", json={"username": "demo", "password": "demo"})
        assert r.status_code == 200
        token = r.json()["access_token"]

        r = client.post(
            "/api/dungeons/goblin_warren/enter",
            json={"campaign_id": 999445, "character_id": 999377},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, f"Enter dungeon failed: {r.text}"
        assert r.json().get("ok") is True
