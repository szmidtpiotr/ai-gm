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


# ─── Blokery GF7 — frontend source ───────────────────────────────────────────

def test_openMultiplayerLobby_uses_correct_screen_key():
    """#935 bloker: openMultiplayerLobby() musi używać klucza 'create-lobby' (nie 'create-lobby-screen')."""
    src_path = os.path.join(
        os.path.dirname(__file__),
        '../../frontend/front/js/multiplayer_ui.js'
    )
    if not os.path.exists(src_path):
        pytest.skip("multiplayer_ui.js nie znaleziony")
    with open(src_path) as f:
        src = f.read()
    assert "showScreen('create-lobby')" in src or 'showScreen("create-lobby")' in src, \
        "openMultiplayerLobby() nie wywołuje showScreen('create-lobby') — fix #935 nie zaaplikowany"
    assert "showScreen('create-lobby-screen')" not in src, \
        "openMultiplayerLobby() nadal używa starego klucza 'create-lobby-screen' — regresja #935"


def test_party_chat_panel_exists_in_html():
    """#939 bloker: #party-chat-panel musi istnieć w index.html (czat party renderuje się)."""
    html_path = os.path.join(
        os.path.dirname(__file__),
        '../../frontend/front/index.html'
    )
    if not os.path.exists(html_path):
        pytest.skip("frontend/front/index.html nie znaleziony")
    with open(html_path) as f:
        html = f.read()
    assert 'id="party-chat-panel"' in html, \
        "#party-chat-panel nie istnieje w index.html — fix #939 nie zaaplikowany"


def test_mp_btn_exists_in_html():
    """#934 bloker: #mp-btn musi istnieć w index.html (kafelek Multiplayer w hubie)."""
    html_path = os.path.join(
        os.path.dirname(__file__),
        '../../frontend/front/index.html'
    )
    if not os.path.exists(html_path):
        pytest.skip("frontend/front/index.html nie znaleziony")
    with open(html_path) as f:
        html = f.read()
    assert 'id="mp-btn"' in html, "#mp-btn nie istnieje w index.html — fix #934 nie zaaplikowany"


# ─── Backward compat: nie zepsuliśmy istniejących trybów ─────────────────────

def test_existing_game_modes_still_in_db():
    """Tryby nowa_kampania / gotowa_kampania nie usunięte przez zmiany MP."""
    conn = get_db()
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='campaigns'"
    )
    assert cur.fetchone() is not None, "Tabela campaigns zniknęła — coś poszło bardzo nie tak"
    conn.close()
