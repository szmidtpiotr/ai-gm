"""TDD: Issue #511 U3 — Feature-flag Multiplayer w hubie kampanii.

Backend: get_available_modes() musi zwracać available=False dla trybu multiplayer
gdy flaga multiplayer_enabled=False (lub brak flagi). Admin może włączyć flagę.
"""
import json
import sqlite3
import sys
import os
sys.path.insert(0, '/app')

import pytest
from app.services.campaign_modes_service import get_available_modes

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _conn_with_flags(flags: dict) -> sqlite3.Connection:
    """In-memory DB z tabelą game_config_meta i zadanymi flagami."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_config_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    # Tabele potrzebne do count-ów
    conn.execute("CREATE TABLE campaign_templates (status TEXT, player_visible INTEGER)")
    conn.execute("CREATE TABLE game_dungeons (is_active INTEGER)")
    conn.execute("CREATE TABLE dungeon_tiles (is_active INTEGER)")
    if flags:
        conn.execute(
            "INSERT INTO game_config_meta (key, value) VALUES ('game_mode_flags', ?)",
            (json.dumps(flags),)
        )
    conn.commit()
    return conn


def _get_mode(modes, key):
    return next((m for m in modes if m["key"] == key), None)


# ─── Test główny: MP disabled gdy brak flagi ─────────────────────────────────

def test_multiplayer_disabled_when_no_flag():
    """Brak flagi w DB → multiplayer.available = False (default OFF)."""
    conn = _conn_with_flags({})
    modes = get_available_modes(conn)
    mp = _get_mode(modes, "multiplayer")
    assert mp is not None, "tryb 'multiplayer' musi być w liście trybów"
    assert mp["available"] is False, \
        f"multiplayer powinien być available=False gdy brak flagi, got: {mp['available']}"


def test_multiplayer_disabled_when_flag_explicitly_false():
    """Flaga multiplayer_enabled=false w DB → available = False."""
    conn = _conn_with_flags({"multiplayer_enabled": False})
    modes = get_available_modes(conn)
    mp = _get_mode(modes, "multiplayer")
    assert mp is not None
    assert mp["available"] is False, \
        f"multiplayer powinien być False gdy flaga=False, got: {mp['available']}"


# ─── Test: admin może włączyć MP ─────────────────────────────────────────────

def test_multiplayer_enabled_when_flag_true():
    """Flaga multiplayer_enabled=true → multiplayer.available = True."""
    conn = _conn_with_flags({"multiplayer_enabled": True})
    modes = get_available_modes(conn)
    mp = _get_mode(modes, "multiplayer")
    assert mp is not None
    assert mp["available"] is True, \
        f"multiplayer powinien być available=True gdy flaga=True, got: {mp['available']}"


# ─── Backward compat: inne tryby nie ucierpiały ──────────────────────────────

def test_other_modes_not_affected_by_mp_flag():
    """Ustawienie flagi MP nie wpływa na inne tryby (nowa zawsze dostępna)."""
    conn = _conn_with_flags({"multiplayer_enabled": False})
    modes = get_available_modes(conn)
    nowa = _get_mode(modes, "nowa")
    assert nowa is not None
    assert nowa["available"] is True, \
        f"tryb 'nowa' powinien być dostępny niezależnie od flagi MP, got: {nowa['available']}"


def test_all_four_modes_returned():
    """API zawsze zwraca 4 tryby (L9: usunięto proceduralny loch; L10: loch_kafelki→loch)."""
    conn = _conn_with_flags({})
    modes = get_available_modes(conn)
    keys = [m["key"] for m in modes]
    assert len(modes) == 4, f"oczekiwano 4 tryby, got: {len(modes)}"
    assert "multiplayer" in keys, "brak trybu 'multiplayer' w liście"
