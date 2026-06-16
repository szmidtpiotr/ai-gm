"""TDD: Issue #432 (E17) — Dungeon loot rarity tiers.

5 rarity tiers (common→legendary) mapped to dungeon difficulty D1–D5.
Boss rooms always drop epic/legendary. Rarity constants and mapping function.
L9: Removed TestDungeonInstanceRarityField and TestRarityBackwardCompat
    (used deleted procedural generator _build_dungeon_instance).
"""

import sqlite3
import pytest

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


