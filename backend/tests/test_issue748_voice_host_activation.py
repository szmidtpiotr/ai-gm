"""TDD: Issue #748 — podłączenie Whisper/.16 do gry.

Dwa zepsute kabelki:
  1. tabela `voice_config` nigdy nie powstała → POST /voice/config (zapis w panelu
     Głos) wykraszał na INSERT. Migracja musi ją tworzyć.
  2. host .16 ma is_active=0 → proxy fallbackuje na nieistniejący voice-service:8300.
     Self-heal: gdy żaden host nie jest aktywny, aktywuj .16 (jeśli istnieje).
     PROD nie ma wiersza .16 → no-op (szacunek dla 'no cutover').
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import migrations_admin


def _fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _make_voice_hosts(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE voice_hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL DEFAULT '',
            base_url TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL DEFAULT 'cpu',
            is_active INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


# ─── Test główny #1 — tabela voice_config powstaje i obsługuje upsert ─────────

def test_voice_config_table_created_and_upsertable():
    """Migracja tworzy voice_config; dokładny upsert z voice_proxy działa."""
    conn = _fresh_conn()
    migrations_admin._ensure_voice_config_table(conn)
    # dokładnie ten INSERT, którego używa voice_proxy._set_config_values
    conn.execute(
        "INSERT INTO voice_config (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("tts_speed", "1.25"),
    )
    conn.execute(
        "INSERT INTO voice_config (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("tts_speed", "1.50"),  # upsert — nadpisuje
    )
    conn.commit()
    val = conn.execute(
        "SELECT value FROM voice_config WHERE key = 'tts_speed'"
    ).fetchone()["value"]
    conn.close()
    assert val == "1.50"


# ─── Test główny #2 — .16 aktywowane gdy żaden host nie jest aktywny ──────────

def test_active_host_seeded_when_none_active():
    """Gdy istnieje host .16 i żaden nie jest aktywny → .16 zostaje aktywowany."""
    conn = _fresh_conn()
    _make_voice_hosts(conn)
    conn.execute(
        "INSERT INTO voice_hosts (label, base_url, is_active) VALUES (?, ?, 0)",
        ("Whisper", migrations_admin.WHISPER_GPU_HOST_URL),
    )
    conn.commit()

    migrations_admin._ensure_active_voice_host(conn)

    active = conn.execute(
        "SELECT base_url FROM voice_hosts WHERE is_active = 1"
    ).fetchall()
    conn.close()
    assert len(active) == 1
    assert active[0]["base_url"] == migrations_admin.WHISPER_GPU_HOST_URL


# ─── Backward-compat #1 — istniejący aktywny host NIE jest nadpisywany ────────

def test_existing_active_host_not_overridden():
    """Gdy admin wybrał inny aktywny host → self-heal go nie rusza."""
    conn = _fresh_conn()
    _make_voice_hosts(conn)
    conn.execute(
        "INSERT INTO voice_hosts (label, base_url, is_active) VALUES (?, ?, 0)",
        ("Whisper", migrations_admin.WHISPER_GPU_HOST_URL),
    )
    conn.execute(
        "INSERT INTO voice_hosts (label, base_url, is_active) VALUES (?, ?, 1)",
        ("Inny", "http://192.168.1.99:8300"),
    )
    conn.commit()

    migrations_admin._ensure_active_voice_host(conn)

    active = conn.execute(
        "SELECT base_url FROM voice_hosts WHERE is_active = 1"
    ).fetchall()
    conn.close()
    assert len(active) == 1
    assert active[0]["base_url"] == "http://192.168.1.99:8300"


# ─── Backward-compat #2 — PROD-guard: brak wiersza .16 → no-op ────────────────

def test_no_16_host_is_noop_prod_safe():
    """Brak hosta .16 (jak na PROD) i żaden aktywny → nic nie aktywujemy
    (proxy zostaje przy bundlowanym voice-service)."""
    conn = _fresh_conn()
    _make_voice_hosts(conn)
    conn.execute(
        "INSERT INTO voice_hosts (label, base_url, is_active) VALUES (?, ?, 0)",
        ("PROD bundled placeholder", "http://192.168.1.99:8300"),
    )
    conn.commit()

    migrations_admin._ensure_active_voice_host(conn)

    active = conn.execute(
        "SELECT COUNT(*) AS c FROM voice_hosts WHERE is_active = 1"
    ).fetchone()["c"]
    conn.close()
    assert active == 0


# ─── Backward-compat #3 — pusta tabela voice_hosts → bez wyjątku ──────────────

def test_empty_voice_hosts_is_noop():
    """Pusta tabela voice_hosts → helper nie rzuca i nic nie aktywuje."""
    conn = _fresh_conn()
    _make_voice_hosts(conn)
    migrations_admin._ensure_active_voice_host(conn)  # nie może rzucić
    active = conn.execute(
        "SELECT COUNT(*) AS c FROM voice_hosts WHERE is_active = 1"
    ).fetchone()["c"]
    conn.close()
    assert active == 0
