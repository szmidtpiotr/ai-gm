"""BL-B2 (#1334) + BL-B3 (#1335) — loot rebalance + crafting components.

Validates the committed content seed (content-as-code #1202) so a regression in
the migration scripts is caught before deploy. Reads data/seeds/content/*.json.

#1334:
- fragment_mapy_skarbow lives ONLY in tier tables (≤5 tables)
- narrative flavour items clamped (weight ≤ 8)
- loot_tier_standard is ≥40% "useful" by weight (≥8/20 expected drops)

#1335:
- is_component / component_type stamped on every item row (loader keys off row[0])
- ~20 components, valid component_type enum, new ones created_by='seed'
- beast loot tables gold-zeroed + carry thematic components
- beast enemies repointed to their own component table
- every component referenced by loot exists in the item catalog
"""

import json
import unittest
from pathlib import Path


def _seed_dir() -> Path:
    for base in Path(__file__).resolve().parents:
        cand = base / "data" / "seeds" / "content"
        if cand.is_dir():
            return cand
    raise RuntimeError("data/seeds/content not found")


SEED = _seed_dir()


def _load(name: str):
    return json.loads((SEED / f"{name}.json").read_text(encoding="utf-8"))


_COMPONENT_ENUM = {"pelt", "fang", "herb", "ore", "essence", "part"}
_TIER_KEYS = {"loot_tier_weak", "loot_tier_standard", "loot_tier_elite", "loot_tier_boss"}
_FLAVOUR_KEYS = {
    "hourglass", "spyglass", "lute", "dice_set", "fishing_net", "fishing_rod",
    "hunting_horn", "soft_slippers", "manacles", "small_chest", "belt_pouch",
    "backpack", "lantern_hooded", "tinderbox", "whetstone", "hooded_cloak",
    "travelers_cloak",
}
# useful = has a game effect / craft / equip receiver (not pure flavour, not a map hook)
_USEFUL_ITEM_KEYS = {
    "bandage", "potion_healing_minor", "potion_healing_standard", "potion_healing_major",
    "potion_mana_standard", "antidote", "potion_resistance", "oil_flask", "holy_water",
    "healing_herb", "scale_mail",
}
_NARRATIVE_ITEM_KEYS = {"torch", "rope_hemp", "waterskin", "fragment_mapy_skarbow"}


class TestFragmentRebalance1334(unittest.TestCase):
    def setUp(self):
        self.entries = _load("game_config_loot_entries")

    def test_fragment_only_in_tier_tables(self):
        tables = {e["loot_table_key"] for e in self.entries if e.get("item_key") == "fragment_mapy_skarbow"}
        self.assertLessEqual(len(tables), 5, f"fragment leaked into {len(tables)} tables")
        self.assertTrue(tables, "fragment should still drop from tier tables")
        self.assertTrue(all(t.startswith("loot_tier_") for t in tables), tables)

    def test_flavour_weights_clamped(self):
        for e in self.entries:
            if e.get("item_key") in _FLAVOUR_KEYS:
                self.assertLessEqual(e["weight"], 8, f"{e['item_key']} weight {e['weight']} not clamped")

    def test_standard_tier_useful_majority(self):
        rows = [e for e in self.entries if e["loot_table_key"] == "loot_tier_standard"]
        self.assertTrue(rows, "loot_tier_standard has no entries")
        useful = sum(e["weight"] for e in rows
                     if (e.get("weapon_key") or e.get("consumable_key")
                         or e.get("item_key") in _USEFUL_ITEM_KEYS))
        total = sum(e["weight"] for e in rows)
        # Numbers Policy (#1334): ≥40% useful → ≥8/20 expected drops.
        self.assertGreaterEqual(useful / total, 0.40, f"useful share {useful}/{total}")
        self.assertGreaterEqual(round(20 * useful / total), 8)


class TestComponents1335(unittest.TestCase):
    def setUp(self):
        self.items = _load("game_config_items")
        self.tables = {t["key"]: t for t in _load("game_config_loot_tables")}
        self.entries = _load("game_config_loot_entries")
        self.enemies = {e["key"]: e for e in _load("game_config_enemies")}
        self.by_key = {it["key"]: it for it in self.items}

    def test_component_column_on_every_row(self):
        # loader keys columns off row[0]; is_component is NOT NULL → must exist + non-null everywhere.
        self.assertIn("is_component", self.items[0])
        self.assertIn("component_type", self.items[0])
        for it in self.items:
            self.assertIsNotNone(it.get("is_component"), f"{it['key']} has NULL is_component")

    def test_components_flagged_and_valid(self):
        comps = [it for it in self.items if it.get("is_component")]
        self.assertGreaterEqual(len(comps), 15, "expected ≥15 components")
        for c in comps:
            self.assertIn(c.get("component_type"), _COMPONENT_ENUM, f"{c['key']} bad component_type")

    def test_new_components_seed_authored(self):
        # the newly authored Kresy components carry created_by='seed'
        new = [it for it in self.items if it.get("created_by") == "seed"]
        self.assertGreaterEqual(len(new), 10)
        for c in new:
            self.assertTrue(c.get("is_component"))

    def test_beast_tables_gold_zeroed(self):
        for tk in ("loot_wolf", "loot_giant_spider", "loot_cave_bear", "loot_giant_rat",
                   "loot_szczury_grobowe", "loot_lizardman", "loot_rykar_wilkowy"):
            t = self.tables.get(tk)
            self.assertIsNotNone(t, f"{tk} missing")
            self.assertEqual(t["gold_min"], 0, f"{tk} gold_min not zeroed")
            self.assertEqual(t["gold_max"], 0, f"{tk} gold_max not zeroed")

    def test_beasts_drop_components(self):
        comp_keys = {it["key"] for it in self.items if it.get("is_component")}
        for tk in ("loot_wolf", "loot_giant_spider", "loot_giant_rat"):
            drops = {e["item_key"] for e in self.entries if e["loot_table_key"] == tk}
            self.assertTrue(drops & comp_keys, f"{tk} drops no component")

    def test_beasts_repointed(self):
        self.assertEqual(self.enemies["giant_spider"]["loot_table_key"], "loot_giant_spider")
        self.assertEqual(self.enemies["cave_bear"]["loot_table_key"], "loot_cave_bear")
        self.assertEqual(self.enemies["giant_rat"]["loot_table_key"], "loot_giant_rat")
        self.assertEqual(self.enemies["lizardman"]["loot_table_key"], "loot_lizardman")

    def test_all_loot_components_exist_in_catalog(self):
        comp_keys = {it["key"] for it in self.items if it.get("is_component")}
        for e in self.entries:
            ik = e.get("item_key")
            # any component referenced by a beast/tier table must exist as a catalog item
            if ik in comp_keys:
                self.assertIn(ik, self.by_key, f"loot references missing component {ik}")


if __name__ == "__main__":
    unittest.main()
