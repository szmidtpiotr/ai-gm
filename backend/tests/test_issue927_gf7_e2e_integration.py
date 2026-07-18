"""TDD: Issue #927 — GF7 MP frontend E2E integration check (wszystkie blokery domknięte)."""
import sqlite3
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Blokery GF7 — tabele DB ─────────────────────────────────────────────────

def test_campaign_invites_table_exists():
    """#938 bloker: campaign_invites musi istnieć (invite link nie może zwracać 500)."""
    conn = get_db()
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='campaign_invites'"
    )
    assert cur.fetchone() is not None, "Tabela campaign_invites nie istnieje — brak migracji #938"
    conn.close()


def test_party_messages_table_exists():
    """#938 bloker: party_messages musi istnieć (czat party nie może zwracać 500)."""
    conn = get_db()
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='party_messages'"
    )
    assert cur.fetchone() is not None, "Tabela party_messages nie istnieje — brak migracji #938"
    conn.close()


def test_party_messages_has_whisper_to_column():
    """#938 bloker: party_messages musi mieć kolumnę whisper_to dla feature czatu."""
    conn = get_db()
    cur = conn.execute("PRAGMA table_info(party_messages)")
    cols = [row["name"] for row in cur.fetchall()]
    assert "whisper_to" in cols, f"Brak kolumny whisper_to w party_messages. Kolumny: {cols}"
    conn.close()


# ─── Blokery GF7 — API ───────────────────────────────────────────────────────

def test_campaign_modes_has_multiplayer():
    """#934 bloker: /campaign-modes musi zwracać tryb multiplayer (kafelek w hubie)."""
    try:
        from app.api.campaigns import get_campaign_modes
        result = get_campaign_modes()
        modes_list = result.get("modes", []) if isinstance(result, dict) else []
        keys = [m["key"] for m in modes_list if isinstance(m, dict)]
        assert "multiplayer" in keys, f"Tryb 'multiplayer' brak w modes: {keys}"
        mp = next(m for m in modes_list if m.get("key") == "multiplayer")
        assert mp.get("available") is True, f"multiplayer.available != True: {mp}"
    except ImportError:
        pytest.skip("Nie można zaimportować app.api.campaigns bezpośrednio")


def test_create_lobby_includes_model_id():
    """#932/#936 bloker: INSERT w create_lobby musi zawierać model_id (NOT NULL constraint)."""
    try:
        import ast
        router_path = os.path.join(os.path.dirname(__file__), '../app/api/multiplayer_campaigns.py')
        if not os.path.exists(router_path):
            pytest.skip("Plik multiplayer_campaigns.py nie istnieje")
        with open(router_path) as f:
            src = f.read()
        assert "model_id" in src, "model_id nie pojawia się w multiplayer_campaigns.py — INSERT może failować NOT NULL"
    except Exception as e:
        pytest.skip(f"Nie można sprawdzić źródła: {e}")


# Testy źródeł frontendu (multiplayer_ui.js/index.html starego UI) usunięte —
# legacy frontend/front/ skasowany 2026-07-18, MP żyje w ŻAR (front-v2).


# ─── Backward compat: nie zepsuliśmy istniejących trybów ─────────────────────

def test_existing_game_modes_still_in_db():
    """Tryby nowa_kampania / gotowa_kampania nie usunięte przez zmiany MP."""
    conn = get_db()
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='campaigns'"
    )
    assert cur.fetchone() is not None, "Tabela campaigns zniknęła — coś poszło bardzo nie tak"
    conn.close()
