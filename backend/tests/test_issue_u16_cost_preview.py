"""TDD: Issue #564 (U16) — Cost preview + durability presentation + affix-cost preview.

Zakres testów backendu (deterministyczne, conn-injectable):
- durability_service.durability_view(cur, max) → blok prezentacyjny {current,max,pct,broken,penalty_pct}
  lub None gdy przedmiot nie ma trwałości. Mechanika trwałości BEZ zmian (Zasada 1-5: tylko pokazujemy).
- crafter_service.get_affix_costs(conn, char_id, inv_id) → read-only podgląd kosztów kuźni
  (apply_costs z APPLY_COSTS, per-afiks reroll/upgrade, aktualne złoto). Bez potrącania złota.

Integracja (durability w /inventory/detail + komunikat anti-farm w sell_item) pokryta
Playwright spec issue_564_u16_cost_preview.spec.js na żywej bazie DEV.
"""
import sys
sys.path.insert(0, "/app")

import sqlite3
import pytest

from app.services.durability_service import durability_view, DEFAULT_PENALTY_PCT
from app.services import crafter_service


# ─── Test główny 1 — durability_view ─────────────────────────────────────────

def test_durability_view_full_item():
    """Broń 60/100 → pct 60.0, nie pęknięta, kara z konfiguracji."""
    v = durability_view(60, 100)
    assert v is not None
    assert v["current"] == 60
    assert v["max"] == 100
    assert v["pct"] == 60.0
    assert v["broken"] is False
    assert v["penalty_pct"] == DEFAULT_PENALTY_PCT


def test_durability_view_broken_at_zero():
    """Trwałość 0 → broken=True, pct 0.0 (frontend pokaże 'Pęknięta')."""
    v = durability_view(0, 150)
    assert v["broken"] is True
    assert v["pct"] == 0.0


def test_durability_view_none_when_no_durability():
    """Przedmiot bez trwałości (max NULL lub 0) → None (mikstury, questowe)."""
    assert durability_view(None, None) is None
    assert durability_view(None, 0) is None
    assert durability_view(5, 0) is None


def test_durability_view_negative_floored():
    """Ujemna trwałość nigdy nie wycieka do UI — podłoga 0."""
    v = durability_view(-3, 100)
    assert v["current"] == 0
    assert v["broken"] is True


# ─── Test główny 2 — affix-cost preview ──────────────────────────────────────

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE characters (id INTEGER PRIMARY KEY, gold_gp INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            weapon_key TEXT, item_key TEXT, consumable_key TEXT,
            affixes_json TEXT
        );
        CREATE TABLE game_config_affixes (
            key TEXT PRIMARY KEY, name TEXT, tier INTEGER,
            is_active INTEGER DEFAULT 1, allowed_item_types TEXT, effect_json TEXT
        );
        """
    )
    conn.execute("INSERT INTO characters (id, gold_gp) VALUES (1, 800)")
    conn.execute(
        "INSERT INTO game_config_affixes (key, name, tier, allowed_item_types) VALUES "
        "('sharp_t1','Ostry',1,'weapon'), ('keen_t2','Wyborny',2,'weapon')"
    )
    conn.commit()
    yield conn
    conn.close()


def test_get_affix_costs_clean_weapon(db):
    """Broń bez afiksów → podgląd kosztów nałożenia (apply) + złoto, brak per-afiks rerollów."""
    db.execute(
        "INSERT INTO character_inventory (id, character_id, weapon_key, affixes_json) "
        "VALUES (10, 1, 'sword', '[]')"
    )
    db.commit()
    res = crafter_service.get_affix_costs(db, 1, 10)
    assert res["ok"] is True
    assert res["item_type"] == "weapon"
    assert res["gold"] == 800
    assert res["apply_costs"] == crafter_service.APPLY_COSTS
    assert res["current_affixes"] == []


def test_get_affix_costs_with_existing_affix(db):
    """Broń z afiksem T1 → reroll/upgrade koszty wyliczone z tieru afiksu."""
    db.execute(
        "INSERT INTO character_inventory (id, character_id, weapon_key, affixes_json) "
        "VALUES (11, 1, 'sword', '[\"sharp_t1\"]')"
    )
    db.commit()
    res = crafter_service.get_affix_costs(db, 1, 11)
    assert res["ok"] is True
    rows = res["current_affixes"]
    assert len(rows) == 1
    row = rows[0]
    assert row["affix_key"] == "sharp_t1"
    assert row["tier"] == 1
    assert row["reroll_cost"] == crafter_service.REROLL_COSTS[1]
    assert row["upgrade_cost"] == crafter_service.UPGRADE_COSTS[1]


def test_get_affix_costs_item_not_found(db):
    """Brak przedmiotu → ok=False (nie wybucha)."""
    res = crafter_service.get_affix_costs(db, 1, 999)
    assert res["ok"] is False


def test_get_affix_costs_does_not_deduct_gold(db):
    """Podgląd jest read-only — złoto bohatera nietknięte (Zasada: mechanika decyduje)."""
    db.execute(
        "INSERT INTO character_inventory (id, character_id, weapon_key, affixes_json) "
        "VALUES (12, 1, 'sword', '[]')"
    )
    db.commit()
    crafter_service.get_affix_costs(db, 1, 12)
    gold = db.execute("SELECT gold_gp FROM characters WHERE id = 1").fetchone()["gold_gp"]
    assert gold == 800


# ─── Test główny 3 — durability init on grant (#467 aktywacja) ───────────────

@pytest.fixture
def items_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE game_items (
            key TEXT PRIMARY KEY, kind TEXT, rarity INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1, weapon_data TEXT
        );
        """
    )
    conn.execute("INSERT INTO game_items (key, kind, rarity, weapon_data) VALUES "
                 "('sword','weapon',1,NULL), "
                 "('rare_blade','weapon',3,NULL), "
                 "('custom_axe','weapon',1,'{\"durability_base\": 42}'), "
                 "('leatherarmor','armor',2,NULL), "
                 "('health_potion','consumable',1,NULL)")
    conn.commit()
    yield conn
    conn.close()


def test_starter_durability_rarity_default(items_db):
    """Broń bez durability_base → domyślna wg rzadkości (1→100, 3→200)."""
    from app.services.loot_service import _starter_durability
    assert _starter_durability(items_db, "sword", "weapon") == 100
    assert _starter_durability(items_db, "rare_blade", "weapon") == 200
    assert _starter_durability(items_db, "leatherarmor", "armor") == 150


def test_starter_durability_uses_config_base(items_db):
    """durability_base z configu nadpisuje domyślną wg rzadkości."""
    from app.services.loot_service import _starter_durability
    assert _starter_durability(items_db, "custom_axe", "weapon") == 42


def test_starter_durability_none_for_non_gear(items_db):
    """Konsumpcyjne/inne → None (trwałość nie śledzona)."""
    from app.services.loot_service import _starter_durability
    assert _starter_durability(items_db, "health_potion", "consumable") is None
    assert _starter_durability(items_db, "anything", "quest") is None
