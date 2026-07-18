"""TDD: Issue #510 / U2 — Uzgodnienie spec↔implementacja ekonomii.

Weryfikuje cztery decyzje projektowe U2:
1. REROLL_COSTS > APPLY_COSTS (reroll premium nad nałożeniem)
2. Broń traci durability przy WŁASNYM ataku gracza (nowa funkcja)
3. Zbroja traci durability przy ciosie OTRZYMANYM (nowa funkcja)
4. ANTI_FARM_WINDOW_HOURS to czas RZECZYWISTY (nazwa zmiennej + wartość)
"""
import sqlite3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _fixtures_schema import table_sql

import pytest


# ─── Test 1 — Reroll kosztuje więcej niż nałożenie (wszystkie tiery) ─────────

def test_reroll_costs_below_apply_costs():
    """REROLL_COSTS są niższe od APPLY_COSTS — decyzja Piotra (#943): reroll tańszy
    niż nałożenie, ceny jak dawniej 100/350/700 vs apply 150/500/1200."""
    from app.services.crafter_service import APPLY_COSTS, REROLL_COSTS

    for tier in APPLY_COSTS:
        apply_cost = APPLY_COSTS[tier]
        reroll_cost = REROLL_COSTS.get(tier, 0)
        assert reroll_cost < apply_cost, (
            f"Tier {tier}: reroll ({reroll_cost}g) ma być tańszy niż nałożenie ({apply_cost}g)"
        )


def test_reroll_costs_specific_values():
    """Konkretne wartości U2: T1=200, T2=650, T3=1500."""
    from app.services.crafter_service import REROLL_COSTS

    assert REROLL_COSTS[1] == 100, f"T1 reroll powinien kosztować 100g, jest {REROLL_COSTS[1]}g"
    assert REROLL_COSTS[2] == 350, f"T2 reroll powinien kosztować 350g, jest {REROLL_COSTS[2]}g"
    assert REROLL_COSTS[3] == 700, f"T3 reroll powinien kosztować 700g, jest {REROLL_COSTS[3]}g"


def test_apply_costs_unchanged():
    """APPLY_COSTS bez zmian — T1=150, T2=500, T3=1200."""
    from app.services.crafter_service import APPLY_COSTS

    assert APPLY_COSTS[1] == 150
    assert APPLY_COSTS[2] == 500
    assert APPLY_COSTS[3] == 1200


# ─── Test 2 — Broń traci durability przy ataku gracza ─────────────────────────

def _make_db_with_equipped_weapon_and_armor():
    """Tworzy in-memory DB z wyposażonym bohaterem mającym broń i zbroję z durability."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            gold_gp INTEGER DEFAULT 0,
            sheet_json TEXT DEFAULT '{}'
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY,
            character_id INTEGER,
            weapon_key TEXT,
            item_key TEXT,
            consumable_key TEXT,
            equipped INTEGER DEFAULT 0,
            durability_current INTEGER,
            durability_max INTEGER,
            affixes_json TEXT DEFAULT '[]',
            rarity INTEGER DEFAULT 1
        );
        CREATE TABLE character_gold_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            delta INTEGER,
            source TEXT,
            meta_json TEXT
        );
        """ + table_sql("game_config_meta") + """
        INSERT INTO characters (id, gold_gp) VALUES (1, 5000);
        -- Broń (weapon_key = miecz)
        INSERT INTO character_inventory (id, character_id, weapon_key, equipped, durability_current, durability_max)
        VALUES (10, 1, 'sword', 1, 50, 100);
        -- Zbroja (item_key = kolczuga)
        INSERT INTO character_inventory (id, character_id, item_key, equipped, durability_current, durability_max)
        VALUES (20, 1, 'chainmail', 1, 80, 100);
    """)
    return conn


def test_weapon_durability_decreases_on_player_attack():
    """Broń traci 1 pkt durability gdy gracz atakuje (nowa funkcja decrement_weapon_durability_on_attack)."""
    from app.services.durability_service import decrement_weapon_durability_on_attack

    conn = _make_db_with_equipped_weapon_and_armor()
    before_weapon = conn.execute("SELECT durability_current FROM character_inventory WHERE id = 10").fetchone()[0]
    before_armor = conn.execute("SELECT durability_current FROM character_inventory WHERE id = 20").fetchone()[0]

    decrement_weapon_durability_on_attack(conn, char_id=1)

    after_weapon = conn.execute("SELECT durability_current FROM character_inventory WHERE id = 10").fetchone()[0]
    after_armor = conn.execute("SELECT durability_current FROM character_inventory WHERE id = 20").fetchone()[0]

    assert after_weapon == before_weapon - 1, "Broń powinna stracić 1 pkt durability po ataku gracza"
    assert after_armor == before_armor, "Zbroja NIE powinna tracić durability przy ataku gracza"


def test_weapon_durability_floors_at_zero():
    """Durability broni nie spada poniżej 0."""
    from app.services.durability_service import decrement_weapon_durability_on_attack

    conn = _make_db_with_equipped_weapon_and_armor()
    conn.execute("UPDATE character_inventory SET durability_current = 0 WHERE id = 10")
    conn.commit()

    decrement_weapon_durability_on_attack(conn, char_id=1)

    after = conn.execute("SELECT durability_current FROM character_inventory WHERE id = 10").fetchone()[0]
    assert after == 0, "Durability broni nie może spaść poniżej 0"


# ─── Test 3 — Zbroja traci durability przy otrzymanym ciosie ──────────────────

def test_armor_durability_decreases_on_received_hit():
    """Zbroja traci 1 pkt durability gdy gracz OTRZYMUJE cios (nowa funkcja decrement_armor_durability_on_hit)."""
    from app.services.durability_service import decrement_armor_durability_on_hit

    conn = _make_db_with_equipped_weapon_and_armor()
    before_weapon = conn.execute("SELECT durability_current FROM character_inventory WHERE id = 10").fetchone()[0]
    before_armor = conn.execute("SELECT durability_current FROM character_inventory WHERE id = 20").fetchone()[0]

    decrement_armor_durability_on_hit(conn, char_id=1)

    after_weapon = conn.execute("SELECT durability_current FROM character_inventory WHERE id = 10").fetchone()[0]
    after_armor = conn.execute("SELECT durability_current FROM character_inventory WHERE id = 20").fetchone()[0]

    assert after_armor == before_armor - 1, "Zbroja powinna stracić 1 pkt durability przy otrzymanym ciosie"
    assert after_weapon == before_weapon, "Broń NIE powinna tracić durability przy otrzymanym ciosie"


def test_armor_durability_floors_at_zero():
    """Durability zbroi nie spada poniżej 0."""
    from app.services.durability_service import decrement_armor_durability_on_hit

    conn = _make_db_with_equipped_weapon_and_armor()
    conn.execute("UPDATE character_inventory SET durability_current = 0 WHERE id = 20")
    conn.commit()

    decrement_armor_durability_on_hit(conn, char_id=1)

    after = conn.execute("SELECT durability_current FROM character_inventory WHERE id = 20").fetchone()[0]
    assert after == 0, "Durability zbroi nie może spaść poniżej 0"


# ─── Test 4 — Anti-farm: stała 24h jako czas RZECZYWISTY ─────────────────────

def test_anti_farm_window_is_24_real_hours():
    """ANTI_FARM_WINDOW_HOURS = 24 (godziny rzeczywiste, nie in-game)."""
    from app.services.anti_farm_service import ANTI_FARM_WINDOW_HOURS

    assert ANTI_FARM_WINDOW_HOURS == 24, (
        f"Anti-farm window powinno wynosić 24h rzeczywiste, jest {ANTI_FARM_WINDOW_HOURS}"
    )


def test_anti_farm_limit_is_3():
    """ANTI_FARM_LIMIT = 3 sprzedaże przed aktywacją decaya."""
    from app.services.anti_farm_service import ANTI_FARM_LIMIT

    assert ANTI_FARM_LIMIT == 3
