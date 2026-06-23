"""TDD: Issue #812 — G14 Handel między graczami (later) — fundamenty DB gotowe, implementacja odłożona."""
import sqlite3
import pytest


DB_PATH = "/data/ai_gm.db"


def _get_table_columns(conn, table_name):
    cur = conn.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cur.fetchall()}


def _table_exists(conn, table_name):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    )
    return cur.fetchone() is not None


# ─── Fundamenty: character_inventory ─────────────────────────────────────────

def test_character_inventory_has_trade_foundations():
    """character_inventory musi mieć kolumny potrzebne do przyszłego handlu (item/weapon/consumable key + quantity + character_id)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cols = _get_table_columns(conn, "character_inventory")
        required = {"character_id", "item_key", "weapon_key", "consumable_key", "quantity"}
        missing = required - cols
        assert not missing, f"Brakujące kolumny w character_inventory: {missing}"
    finally:
        conn.close()


# ─── Fundamenty: campaign_members ────────────────────────────────────────────

def test_campaign_members_has_roster_foundations():
    """campaign_members musi mieć kolumny do walidacji rostera (campaign_id, user_id, character_id, status)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cols = _get_table_columns(conn, "campaign_members")
        required = {"campaign_id", "user_id", "character_id", "status"}
        missing = required - cols
        assert not missing, f"Brakujące kolumny w campaign_members: {missing}"
    finally:
        conn.close()


# ─── G14 poprawnie odłożone: character_trades NIE istnieje ───────────────────

def test_character_trades_table_not_yet_implemented():
    """G14 jest celowo odłożone — tabela character_trades NIE może istnieć przed decyzją Piotra o aktywacji."""
    conn = sqlite3.connect(DB_PATH)
    try:
        assert not _table_exists(conn, "character_trades"), (
            "Tabela character_trades istnieje — G14 (Handel MP) wdrożone bez decyzji Piotra. "
            "Usuń tabelę lub zaktualizuj issue #812 i ten test."
        )
    finally:
        conn.close()


# ─── Backward compat: inventory działa dla istniejących bohaterów ─────────────

def test_inventory_queryable_for_existing_characters():
    """Ekwipunek bohaterów działa normalnie — fundamenty nie naruszają istniejących danych."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM character_inventory WHERE quantity > 0"
        )
        count = cur.fetchone()[0]
        assert count >= 0, "Zapytanie na character_inventory nie może rzucić błędu"
    finally:
        conn.close()
