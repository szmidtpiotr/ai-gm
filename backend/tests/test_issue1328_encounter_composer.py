"""TDD: Issue #1328 (BL-A2) — kompozycyjny generator spotkań.

Zamiast wyłącznie ręcznych szablonów: buduj spotkanie z puli wrogów pod budżet
zagrożenia. Pula TYLKO world_scope='global' AND review_status='permanent' AND
is_active=1 + dopasowanie terenu + pasmo poziomów. Wzorce solo/wataha/herszt.
"""
import random
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        """ + table_sql("game_config_enemies") + """
        """ + table_sql("game_config_meta") + """
        """
    )
    # #1345: te testy sprawdzają RDZEŃ filtra (pasmo+teren) przy delta=0 — wyłącz
    # poszerzanie puli (min_size=1), fallback #1345 pokrywa test_1345_pool_fallback.
    conn.execute(
        "INSERT INTO game_config_meta (key,value) VALUES ('encounter_pool_min_size','1')"
    )
    # 6 kwalifikujących się wrogów w lesie lvl 1 (global+permanent+active)
    good = [
        ("wolf", "Wilk", 10, 12, 3, "1d6", 0, 1, "standard", 1, 2, "forest,hills"),
        ("goblin", "Goblin", 8, 11, 2, "1d6", 1, 1, "weak", 1, 2, "forest,cave"),
        ("goblin_archer", "Goblin Łucznik", 8, 11, 2, "1d6", 0, 1, "weak", 1, 2, "forest"),
        ("bandit", "Bandyta", 12, 13, 4, "1d8", 0, 1, "standard", 1, 2, "forest,road"),
        ("bandit_thug", "Oprych", 10, 11, 2, "1d6", 0, 1, "weak", 1, 2, "forest,road"),
        ("boar", "Dzik", 14, 12, 3, "1d8", 1, 1, "elite", 1, 3, "forest"),
    ]
    for row in good:
        conn.execute(
            "INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,"
            "damage_die,damage_bonus,attacks_per_turn,tier,min_level,max_level,terrain_tags,"
            "world_scope,review_status,is_active) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (*row, "global", "permanent", 1),
        )
    # NIE powinny nigdy wystąpić: template / campaign / pending / discarded / inactive
    bad = [
        ("tmpl_ghoul", "Ghul (szablon)", 20, 13, 4, "1d8", 0, 1, "elite", 1, 5, "forest", "template", "permanent", 1),
        ("camp_boss", "Boss kampanii", 30, 14, 5, "1d10", 2, 2, "boss", 1, 9, "forest", "campaign", "permanent", 1),
        ("pending_wolf", "Wilk pending", 10, 12, 3, "1d6", 0, 1, "standard", 1, 2, "forest", "global", "pending_review", 1),
        ("discarded_x", "Odrzucony", 10, 12, 3, "1d6", 0, 1, "standard", 1, 2, "forest", "global", "discarded", 1),
        ("inactive_x", "Nieaktywny", 10, 12, 3, "1d6", 0, 1, "standard", 1, 2, "forest", "global", "permanent", 0),
    ]
    for row in bad:
        conn.execute(
            "INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,"
            "damage_die,damage_bonus,attacks_per_turn,tier,min_level,max_level,terrain_tags,"
            "world_scope,review_status,is_active) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            row,
        )
    conn.commit()


class TestEnemyThreatValue(unittest.TestCase):
    def test_stronger_enemy_has_higher_threat(self):
        from app.services.encounter_service import enemy_threat_value
        weak = {"hp_base": 6, "ac_base": 10, "attack_bonus": 1, "damage_die": "1d4",
                "damage_bonus": 0, "attacks_per_turn": 1}
        strong = {"hp_base": 30, "ac_base": 15, "attack_bonus": 6, "damage_die": "1d10",
                  "damage_bonus": 3, "attacks_per_turn": 2}
        self.assertLess(enemy_threat_value(weak), enemy_threat_value(strong))

    def test_die_notation_variants(self):
        from app.services.encounter_service import enemy_threat_value
        a = enemy_threat_value({"hp_base": 10, "ac_base": 10, "attack_bonus": 0,
                                "damage_die": "d6", "damage_bonus": 0, "attacks_per_turn": 1})
        b = enemy_threat_value({"hp_base": 10, "ac_base": 10, "attack_bonus": 0,
                                "damage_die": "1d6", "damage_bonus": 0, "attacks_per_turn": 1})
        self.assertEqual(a, b)  # 'd6' == '1d6'


class TestEligiblePool(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:"); self.conn.row_factory = sqlite3.Row
        _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_pool_excludes_non_global_non_permanent(self):
        from app.services.encounter_service import eligible_enemy_pool
        keys = {d["key"] for d in eligible_enemy_pool(self.conn, level=1, hex_type="forest")}
        # tylko 6 dobrych; żaden zły
        for bad in ("tmpl_ghoul", "camp_boss", "pending_wolf", "discarded_x", "inactive_x"):
            self.assertNotIn(bad, keys)
        self.assertEqual(len(keys), 6)

    def test_terrain_filter(self):
        from app.services.encounter_service import eligible_enemy_pool
        # cave: tylko goblin (forest,cave) pasuje
        keys = {d["key"] for d in eligible_enemy_pool(self.conn, level=1, hex_type="cave")}
        self.assertEqual(keys, {"goblin"})

    def test_level_band_filter(self):
        from app.services.encounter_service import eligible_enemy_pool
        # lvl 3: tylko boar (max_level=3) przechodzi; reszta max_level=2
        keys = {d["key"] for d in eligible_enemy_pool(self.conn, level=3, hex_type="forest")}
        self.assertEqual(keys, {"boar"})


class TestEncounterComposer(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:"); self.conn.row_factory = sqlite3.Row
        _schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_empty_pool_returns_none(self):
        from app.services.encounter_service import encounter_composer
        # #1345: teren bez wroga (swamp) jest teraz LUZOWANY, nie None. Pustka →
        # composer None tylko gdy w paśmie NIE MA żadnego wroga (poziom poza skalą).
        self.assertIsNone(encounter_composer(self.conn, level=99, hex_type="forest"))

    def test_composed_enemies_only_from_pool(self):
        from app.services.encounter_service import encounter_composer
        pool_keys = {"wolf", "goblin", "goblin_archer", "bandit", "bandit_thug", "boar"}
        rng = random.Random(0)
        for _ in range(200):
            enc = encounter_composer(self.conn, level=1, hex_type="forest", rng=rng)
            self.assertIsNotNone(enc)
            for e in enc["enemies"]:
                self.assertIn(e["enemy_key"], pool_keys)
                self.assertGreaterEqual(e["count"], 1)

    def test_variety_at_least_five_distinct_sets(self):
        from app.services.encounter_service import encounter_composer
        rng = random.Random(42)
        sets = set()
        for _ in range(200):
            enc = encounter_composer(self.conn, level=1, hex_type="forest", rng=rng)
            sig = tuple(sorted((e["enemy_key"], e["count"]) for e in enc["enemies"]))
            sets.add(sig)
        self.assertGreaterEqual(len(sets), 5)

    def test_patterns_reachable_and_valid_counts(self):
        from app.services.encounter_service import encounter_composer
        rng = random.Random(7)
        patterns = set()
        for _ in range(300):
            enc = encounter_composer(self.conn, level=1, hex_type="forest", rng=rng)
            patterns.add(enc["composition_pattern"])
            if enc["composition_pattern"] == "wataha":
                self.assertEqual(len(enc["enemies"]), 1)
                self.assertTrue(2 <= enc["enemies"][0]["count"] <= 4)
            if enc["composition_pattern"] == "herszt":
                self.assertGreaterEqual(len(enc["enemies"]), 1)
        self.assertEqual(patterns, {"solo", "wataha", "herszt"})

    def test_budget_scales_with_level(self):
        from app.services.encounter_service import threat_budget_for_level
        self.assertLess(
            threat_budget_for_level(self.conn, 1),
            threat_budget_for_level(self.conn, 5),
        )

    def test_split_read_from_meta(self):
        from app.services.encounter_service import _composition_split
        self.assertEqual(_composition_split(self.conn), 0.5)
        self.conn.execute("INSERT INTO game_config_meta (key,value) VALUES (?,?)",
                          ("encounter_composition_split", "0.8"))
        self.conn.commit()
        self.assertEqual(_composition_split(self.conn), 0.8)


if __name__ == "__main__":
    unittest.main()
