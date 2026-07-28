"""TDD: Issue #933 — Kresy hex_type registration + settlement location_key linkage."""
import sqlite3
import unittest

DB_PATH = "/data/ai_gm.db"

# #1551 MU-4: 'sea' scalone w 'morze' (duplikat 1:1)
KRESY_TYPES_REQUIRED = {"heath", "snow", "morze", "mountain", "village", "lake", "bridge"}

# Known settlement hexes from Kresy 50x50 import → expected game_location keys
SETTLEMENT_LINKS = [
    (33, 6, "strazyn"),    # Strażyn, Twierdza Graniczna
    (39, 9, "brzezino"),   # Brzezino, Wioska Drwali
    (21, 1, "wolanka"),    # Wolanka, Wioska Górnicza
]


class TestKresyHexTypeConfig(unittest.TestCase):

    def _conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def test_all_world_hex_types_have_config(self):
        """Every hex_type used in world_hexes (map_level=0) must have a hex_type_config entry."""
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT hex_type FROM world_hexes WHERE map_level=0")
        world_types = {row["hex_type"] for row in cur.fetchall()}
        cur.execute("SELECT hex_type FROM hex_type_config")
        config_types = {row["hex_type"] for row in cur.fetchall()}
        conn.close()

        missing = world_types - config_types
        self.assertFalse(
            missing,
            f"hex_types in world_hexes but missing from hex_type_config: {sorted(missing)}"
        )

    def test_kresy_new_types_all_registered(self):
        """Specific new Kresy types must each have a hex_type_config entry."""
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT hex_type FROM hex_type_config WHERE hex_type IN ({','.join('?' * len(KRESY_TYPES_REQUIRED))})",
            list(KRESY_TYPES_REQUIRED),
        )
        registered = {row["hex_type"] for row in cur.fetchall()}
        conn.close()

        missing = KRESY_TYPES_REQUIRED - registered
        self.assertFalse(
            missing,
            f"New Kresy hex_types not registered in hex_type_config: {sorted(missing)}"
        )

    def test_bridge_encounter_chance_nonzero(self):
        """Bridge hex must have encounter_base_chance > 0 (toll encounter)."""
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT encounter_base_chance FROM hex_type_config WHERE hex_type='bridge'")
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row, "bridge hex_type not found in hex_type_config")
        self.assertGreater(
            row["encounter_base_chance"], 0,
            f"bridge encounter_base_chance should be > 0 (toll), got {row['encounter_base_chance']}"
        )

    def test_sea_and_lake_not_passable(self):
        """Sea (morze) and lake must be is_passable=0 (water — cannot travel through)."""
        conn = self._conn()
        cur = conn.cursor()
        # #1551 MU-4: 'sea' scalone w 'morze'
        cur.execute("SELECT hex_type, is_passable FROM hex_type_config WHERE hex_type IN ('morze','lake')")
        rows = {row["hex_type"]: row["is_passable"] for row in cur.fetchall()}
        conn.close()

        for ht in ("morze", "lake"):
            self.assertIn(ht, rows, f"{ht} missing from hex_type_config")
            self.assertEqual(rows[ht], 0, f"{ht} should be is_passable=0, got {rows[ht]}")

    def test_settlement_hexes_linked_to_locations(self):
        """Town/village hexes matching a game_location key must have location_key set."""
        conn = self._conn()
        cur = conn.cursor()

        for q, r, expected_key in SETTLEMENT_LINKS:
            cur.execute(
                "SELECT location_key FROM world_hexes WHERE q=? AND r=? AND map_level=0",
                (q, r),
            )
            row = cur.fetchone()
            self.assertIsNotNone(row, f"world_hex ({q},{r}) not found in world_hexes")
            self.assertEqual(
                row["location_key"],
                expected_key,
                f"world_hex ({q},{r}) location_key={row['location_key']!r}, expected {expected_key!r}"
            )

        conn.close()

    def test_village_has_distinct_config_from_town(self):
        """village and town must both exist as separate hex_type_config entries."""
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT hex_type, map_color FROM hex_type_config WHERE hex_type IN ('village','town')")
        rows = {row["hex_type"]: row["map_color"] for row in cur.fetchall()}
        conn.close()

        self.assertIn("village", rows, "village missing from hex_type_config")
        self.assertIn("town", rows, "town missing from hex_type_config")
        self.assertNotEqual(
            rows["village"], rows["town"],
            "village and town should have distinct map colors"
        )

    # ── Backward compatibility ─────────────────────────────────────────────

    def test_existing_types_unchanged(self):
        """Original 12 hex_type_config entries still exist with correct colors."""
        original = {
            "road": "#c8a86c",
            "plains": "#7a9a4a",
            "forest": "#2d5a2d",
            "hills": "#8a7a5a",
            # #1551 MU-4: 'mountains' usunięte (0 hexów, duplikat 'mountain')
            "swamp": "#4a5a3a",
            "river": "#3a6a8a",
            "town": "#c8a44a",
            "ruins": "#6a5a4a",
        }
        conn = self._conn()
        cur = conn.cursor()
        for hex_type, expected_color in original.items():
            cur.execute(
                "SELECT map_color FROM hex_type_config WHERE hex_type=?", (hex_type,)
            )
            row = cur.fetchone()
            self.assertIsNotNone(row, f"Original hex_type {hex_type!r} missing from config")
            self.assertEqual(
                row["map_color"], expected_color,
                f"hex_type {hex_type!r} map_color changed: got {row['map_color']!r}"
            )
        conn.close()

    def test_world_hexes_count_unchanged(self):
        """2500 Kresy hexes must still be present (no accidental wipe)."""
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM world_hexes WHERE map_level=0")
        count = cur.fetchone()[0]
        conn.close()
        self.assertEqual(count, 2500, f"Expected 2500 world_hexes (map_level=0), got {count}")


if __name__ == "__main__":
    unittest.main()
