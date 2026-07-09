"""TDD: Issue #1296 — campaign enemy roster (admin) + LLM enemy-knowledge parity.

Część A: get_campaign_plan_enemies — roster plan.key_enemies + status materializacji.
Część B: build_plan_enemy_keys_block — standalone (reużywalny przez MP), listuje
tylko realne, aktywne klucze [COMBAT_START] z planu.
"""
import sqlite3
import json

from app.services.world_service import get_campaign_plan_enemies
from app.services.context_injector import build_plan_enemy_keys_block


def _mkdb() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, gm_plan_json TEXT)")
    conn.execute(
        """CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY,
            label TEXT,
            tier TEXT,
            hp_base INTEGER,
            ac_base INTEGER,
            is_active INTEGER DEFAULT 1,
            review_status TEXT,
            loot_table_key TEXT,
            drop_chance REAL
        )"""
    )
    return conn


_PLAN = {
    "key_enemies": [
        {"key": "wyrostki_spod_mlyna", "name": "Wyrostki spod młyna",
         "tier": "standard", "importance": "supporting", "alive": True},
        {"key": "herszt_wyrostkow_harl", "name": "Harl",
         "tier": "elite", "importance": "critical", "alive": True},
        {"key": "widmo_z_planu", "name": "Widmo (nigdy nie zmaterializowane)",
         "tier": "boss", "importance": "critical", "alive": True},
    ]
}


def _seed(conn, cid=9998881):
    conn.execute(
        "INSERT INTO campaigns (id, gm_plan_json) VALUES (?, ?)",
        (cid, json.dumps(_PLAN)),
    )
    # tylko 2 z 3 są zmaterializowane w katalogu
    conn.execute(
        "INSERT INTO game_config_enemies (key,label,tier,hp_base,ac_base,is_active,review_status,loot_table_key,drop_chance) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        ("wyrostki_spod_mlyna", "Wyrostki spod młyna", "standard", 20, 12, 1, "pending", "loot_wyrostki_spod_mlyna", 0.5),
    )
    conn.execute(
        "INSERT INTO game_config_enemies (key,label,tier,hp_base,ac_base,is_active,review_status,loot_table_key,drop_chance) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        ("herszt_wyrostkow_harl", "Harl", "elite", 30, 12, 1, "pending", "loot_herszt_wyrostkow_harl", 1.0),
    )
    conn.commit()


# ─── Część A: roster ─────────────────────────────────────────────────────────

def test_roster_returns_all_plan_enemies():
    """Roster zawiera wszystkich wrogów z planu (także niezmaterializowanych)."""
    conn = _mkdb()
    _seed(conn)
    roster = get_campaign_plan_enemies(conn, 9998881)
    keys = {e["key"] for e in roster}
    assert keys == {"wyrostki_spod_mlyna", "herszt_wyrostkow_harl", "widmo_z_planu"}


def test_roster_flags_materialized_and_stats():
    """Zmaterializowany wróg ma materialized=True + statystyki z katalogu."""
    conn = _mkdb()
    _seed(conn)
    roster = {e["key"]: e for e in get_campaign_plan_enemies(conn, 9998881)}
    harl = roster["herszt_wyrostkow_harl"]
    assert harl["materialized"] is True
    assert harl["hp_base"] == 30
    assert harl["ac_base"] == 12
    assert harl["tier"] == "elite"
    assert harl["loot_table_key"] == "loot_herszt_wyrostkow_harl"


def test_roster_flags_missing_enemy():
    """Wróg z planu bez wiersza w katalogu → materialized=False."""
    conn = _mkdb()
    _seed(conn)
    roster = {e["key"]: e for e in get_campaign_plan_enemies(conn, 9998881)}
    widmo = roster["widmo_z_planu"]
    assert widmo["materialized"] is False
    # nazwa z planu zachowana mimo braku katalogu
    assert "Widmo" in widmo["name"]


def test_roster_empty_when_no_plan():
    conn = _mkdb()
    conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (?, ?)", (555, json.dumps({})))
    conn.commit()
    assert get_campaign_plan_enemies(conn, 555) == []


# ─── Część B: enemy-keys block (parytet LLM) ─────────────────────────────────

def test_block_lists_live_active_keys():
    """Blok listuje realne, aktywne klucze [COMBAT_START] z planu."""
    conn = _mkdb()
    _seed(conn)
    block = build_plan_enemy_keys_block(conn, 9998881)
    assert "WROGOWIE TEJ KAMPANII" in block
    assert "wyrostki_spod_mlyna" in block
    assert "herszt_wyrostkow_harl" in block


def test_block_omits_non_materialized_key():
    """Klucz z planu bez wiersza w katalogu NIE trafia do bloku (nie-playable)."""
    conn = _mkdb()
    _seed(conn)
    block = build_plan_enemy_keys_block(conn, 9998881)
    assert "widmo_z_planu" not in block


def test_block_omits_inactive_key():
    """is_active=0 → klucz pominięty."""
    conn = _mkdb()
    _seed(conn)
    conn.execute("UPDATE game_config_enemies SET is_active=0 WHERE key=?", ("herszt_wyrostkow_harl",))
    conn.commit()
    block = build_plan_enemy_keys_block(conn, 9998881)
    assert "herszt_wyrostkow_harl" not in block
    assert "wyrostki_spod_mlyna" in block


def test_block_empty_when_no_live_enemies():
    """Brak realnych wrogów → pusty string (bez nagłówka)."""
    conn = _mkdb()
    conn.execute("INSERT INTO campaigns (id, gm_plan_json) VALUES (?, ?)", (556, json.dumps({"key_enemies": []})))
    conn.commit()
    assert build_plan_enemy_keys_block(conn, 556) == ""
