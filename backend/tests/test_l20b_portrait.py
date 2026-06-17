"""TDD: L20b #724 — image_url w stanie walki (combat combatants)."""
import sys, os, sqlite3, json, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services import combat_service as cs
from app.services.combat_service import _fetch_enemy_row


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_test_conn():
    import sqlite3
    conn = sqlite3.connect(os.environ.get("DB_PATH", "/data/ai_gm.db"))
    conn.row_factory = sqlite3.Row
    return conn


def _get_any_campaign_with_character(conn):
    """Zwraca (campaign_id, character_id) z aktywnej kampanii."""
    row = conn.execute(
        "SELECT c.id as campaign_id, ch.id as character_id "
        "FROM campaigns c "
        "JOIN characters ch ON ch.campaign_id = c.id "
        "WHERE c.status = 'active' "
        "LIMIT 1"
    ).fetchone()
    return row


def _get_any_enemy_key(conn):
    """Zwraca pierwszy klucz wroga z katalogu."""
    row = conn.execute(
        "SELECT key FROM game_config_enemies WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    return row["key"] if row else None


# ─── Test 1: _fetch_enemy_row musi zawierać image_url w selekcie ────────────

def test_fetch_enemy_row_includes_image_url():
    """_fetch_enemy_row musi zwracać kolumnę image_url (L20a dodała ją do DB)."""
    conn = _get_test_conn()
    try:
        key = _get_any_enemy_key(conn)
        assert key is not None, "Brak wrogów w katalogu — seed nie uruchomiony?"
        row = _fetch_enemy_row(conn, key)
        assert row is not None, f"_fetch_enemy_row zwróciło None dla {key}"
        # Kluczowa asercja: kolumna image_url MUSI być w wynikach
        cols = row.keys()
        assert "image_url" in cols, (
            f"_fetch_enemy_row nie selectuje image_url! Kolumny: {list(cols)}"
        )
    finally:
        conn.close()


# ─── Test 2: initiate_combat → combatants mają pole image_url ───────────────

def test_initiate_combat_enemy_combatant_has_image_url_field():
    """Każdy enemy combatant w stanie walki po initiate_combat musi mieć klucz image_url."""
    conn = _get_test_conn()
    try:
        pair = _get_any_campaign_with_character(conn)
        if not pair:
            pytest.skip("Brak aktywnej kampanii z postacią — uruchom seed kampanii")
        campaign_id = pair["campaign_id"]
        character_id = pair["character_id"]
        enemy_key = _get_any_enemy_key(conn)
        assert enemy_key, "Brak wrogów w katalogu"

        # Jeśli jest aktywna walka — usuń żeby zacząć świeżo
        conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
        conn.commit()
    finally:
        conn.close()

    combat_state = cs.initiate_combat(campaign_id, character_id, [enemy_key])
    assert combat_state is not None, "initiate_combat zwróciło None"

    combatants = combat_state.get("combatants", [])
    enemy_combatants = [c for c in combatants if c.get("type") == "enemy"]
    assert enemy_combatants, "Brak enemy combatants w stanie walki"

    for ec in enemy_combatants:
        assert "image_url" in ec, (
            f"Enemy combatant {ec.get('id')} nie ma pola image_url! Klucze: {list(ec.keys())}"
        )

    # Sprzątanie
    conn2 = _get_test_conn()
    try:
        conn2.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
        conn2.commit()
    finally:
        conn2.close()


# ─── Test 3: enemy BEZ portretu → image_url = None (nie brakuje klucza) ─────

def test_enemy_without_portrait_has_image_url_none():
    """Wróg bez przypisanego portretu (image_url = NULL w DB) musi mieć image_url: None w combatant."""
    conn = _get_test_conn()
    try:
        # Znajdź wroga BEZ portretu
        row = conn.execute(
            "SELECT key FROM game_config_enemies WHERE is_active = 1 AND (image_url IS NULL OR image_url = '') LIMIT 1"
        ).fetchone()
        if not row:
            pytest.skip("Wszyscy wrogowie mają portret — test nie ma sensu")
        enemy_key = row["key"]

        pair = _get_any_campaign_with_character(conn)
        if not pair:
            pytest.skip("Brak aktywnej kampanii z postacią")
        campaign_id = pair["campaign_id"]
        character_id = pair["character_id"]

        conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
        conn.commit()
    finally:
        conn.close()

    combat_state = cs.initiate_combat(campaign_id, character_id, [enemy_key])
    enemy_combatants = [c for c in combat_state.get("combatants", []) if c.get("type") == "enemy"]
    assert enemy_combatants, "Brak enemy combatants"

    for ec in enemy_combatants:
        assert "image_url" in ec, f"Brak klucza image_url w combatant {ec.get('id')}"
        assert ec["image_url"] is None or ec["image_url"] == "", (
            f"Wróg bez portretu powinien mieć image_url=None, ale ma: {ec['image_url']}"
        )

    # Sprzątanie
    conn2 = _get_test_conn()
    try:
        conn2.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
        conn2.commit()
    finally:
        conn2.close()
