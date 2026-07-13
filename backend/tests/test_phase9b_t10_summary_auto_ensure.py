"""T10 — co N tur narracyjnych background ensure (respektuje T08 w run_ensure)."""

import sqlite3
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _fixtures_schema import table_sql

from app.api import turns as turns_mod
from app.api.turns import create_turn_log
from app.services import history_summary_service as hs_mod
from app.services.history_summary_service import (
    DEFAULT_SUMMARY_AUTO_ENSURE_EVERY_N_NARRATIVE_TURNS,
    META_KEY_SUMMARY_AUTO_ENSURE_EVERY_N,
    get_summary_auto_ensure_every_n_narrative_turns,
)


def _schema_t10() -> str:
    return """
    """ + table_sql("game_config_meta") + """
    INSERT INTO game_config_meta (key, value) VALUES
        ('summary_rollup_cooldown_turns', '3'),
        ('summary_auto_ensure_every_n_narrative_turns', '1');
    CREATE TABLE campaigns (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        system_id TEXT NOT NULL,
        model_id TEXT NOT NULL,
        owner_user_id INTEGER NOT NULL,
        language TEXT DEFAULT 'pl',
        mode TEXT DEFAULT 'solo',
        status TEXT DEFAULT 'active',
        created_at TEXT,
        gm_plan_json TEXT NOT NULL DEFAULT '{}',
        last_rollup_narrative_turn_count INTEGER
    );
    INSERT INTO campaigns (id, title, system_id, model_id, owner_user_id)
    VALUES (1, 't', 'fantasy', 'm', 10);
    CREATE TABLE campaign_turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        character_id INTEGER NOT NULL DEFAULT 1,
        user_text TEXT NOT NULL,
        route TEXT NOT NULL,
        assistant_text TEXT,
        turn_number INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """


def _init_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_schema_t10())
        conn.commit()
    finally:
        conn.close()


def test_get_auto_ensure_interval_meta():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        """ + table_sql("game_config_meta") + """
        """
    )
    assert (
        get_summary_auto_ensure_every_n_narrative_turns(conn)
        == DEFAULT_SUMMARY_AUTO_ENSURE_EVERY_N_NARRATIVE_TURNS
    )
    conn.execute(
        "INSERT INTO game_config_meta (key, value) VALUES (?, ?)",
        (META_KEY_SUMMARY_AUTO_ENSURE_EVERY_N, "0"),
    )
    conn.commit()
    assert get_summary_auto_ensure_every_n_narrative_turns(conn) == 0
    conn.execute(
        "INSERT OR REPLACE INTO game_config_meta (key, value) VALUES (?, ?)",
        (META_KEY_SUMMARY_AUTO_ENSURE_EVERY_N, "4"),
    )
    conn.commit()
    assert get_summary_auto_ensure_every_n_narrative_turns(conn) == 4
    conn.close()


def test_narrative_turn_triggers_ensure_when_n_mod_interval_zero(
    tmp_path, monkeypatch
):
    """Interval=1: pierwsza zapisana tura narracyjna → jedno wywołanie ensure w tle."""
    db = tmp_path / "t10.db"
    _init_db(db)
    monkeypatch.setattr(turns_mod, "DB_PATH", str(db))
    monkeypatch.setattr(hs_mod, "DB_PATH", str(db))

    calls: list[dict] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return {
            "campaign_id": kwargs["campaign_id"],
            "refreshed": False,
            "cooldown_active": True,
        }

    monkeypatch.setattr(
        "app.services.summary_ensure_automation.run_ensure_campaign_history_summary",
        fake_run,
    )

    class SyncThread(threading.Thread):
        def start(self) -> None:
            t = self._target
            if t is not None:
                t(*self._args, **(self._kwargs or {}))

    monkeypatch.setattr(
        "app.services.summary_ensure_automation.threading.Thread", SyncThread
    )

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    create_turn_log(conn, 1, 1, "u", "a", "narrative")
    conn.close()

    assert len(calls) == 1
    assert calls[0]["campaign_id"] == 1
    assert calls[0]["user_id"] == 10


def test_interval_zero_skips_ensure(tmp_path, monkeypatch):
    db = tmp_path / "t10_zero.db"
    _init_db(db)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT OR REPLACE INTO game_config_meta (key, value) VALUES (?, ?)",
        (META_KEY_SUMMARY_AUTO_ENSURE_EVERY_N, "0"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(turns_mod, "DB_PATH", str(db))
    monkeypatch.setattr(hs_mod, "DB_PATH", str(db))

    called: list[object] = []

    def fake_run(**kwargs):
        called.append(True)
        return {"refreshed": True, "campaign_id": kwargs["campaign_id"]}

    monkeypatch.setattr(
        "app.services.summary_ensure_automation.run_ensure_campaign_history_summary",
        fake_run,
    )

    class SyncThread(threading.Thread):
        def start(self) -> None:
            t = self._target
            if t is not None:
                t(*self._args, **(self._kwargs or {}))

    monkeypatch.setattr(
        "app.services.summary_ensure_automation.threading.Thread", SyncThread
    )

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    create_turn_log(conn, 1, 1, "u", "a", "narrative")
    conn.close()

    assert called == []
