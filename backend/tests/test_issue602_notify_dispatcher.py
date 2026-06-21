"""TDD: Issue #602 (Faza N2) — unified multichannel notify() dispatcher.

notify(user_id, event, payload) must pick the most reliable channel the player
has enabled, walking channel_order (default telegram > web_push > email) and
falling through to the next channel when one is unavailable or fails. Every
attempt is logged to notify_delivery_log.

Channel SENDERS are stubbed here — these tests pin the *selection + fallback*
logic, not the network I/O of any single channel.
"""
import sqlite3
import sys

sys.path.insert(0, "/app")

import pytest  # noqa: E402

from app.services import notification_service as ns  # noqa: E402


# ─── helpers ─────────────────────────────────────────────────────────────────

def _prefs(**over):
    base = {
        "user_id": 999001,
        "web_push_enabled": 0,
        "telegram_chat_id": None,
        "email": None,
        "channel_order": "telegram,web_push,email",
    }
    base.update(over)
    return base


def _stub_all(monkeypatch, telegram=False, web_push=False, email=False):
    """Force each per-channel deliverer to a fixed bool result."""
    monkeypatch.setattr(ns, "_deliver_telegram", lambda *a, **k: telegram)
    monkeypatch.setattr(ns, "_deliver_web_push", lambda *a, **k: web_push)
    monkeypatch.setattr(ns, "_deliver_email", lambda *a, **k: email)
    # silence the DB delivery log during pure-logic tests
    monkeypatch.setattr(ns, "_log_delivery", lambda *a, **k: None)


PAYLOAD = {"title": "Twoja tura", "body": "Ruch należy do Ciebie.", "url": "/"}


# ─── Test główny: wybór kanału wg preferencji ────────────────────────────────

def test_prefers_telegram_when_connected(monkeypatch):
    """Telegram connected + first in order → delivered via telegram."""
    _stub_all(monkeypatch, telegram=True, web_push=True, email=True)
    prefs = _prefs(telegram_chat_id="12345", web_push_enabled=1, email="a@b.c")
    res = ns.notify(999001, "your_turn", PAYLOAD, prefs=prefs)
    assert res["delivered"] is True
    assert res["channel"] == "telegram"


def test_falls_back_to_web_push_when_telegram_off(monkeypatch):
    """No telegram_chat_id → telegram unavailable → web push wins."""
    _stub_all(monkeypatch, telegram=True, web_push=True, email=True)
    prefs = _prefs(telegram_chat_id=None, web_push_enabled=1, email="a@b.c")
    res = ns.notify(999001, "your_turn", PAYLOAD, prefs=prefs)
    assert res["channel"] == "web_push"


def test_falls_back_to_email_when_both_off(monkeypatch):
    """Telegram + web push both unavailable → email is the last resort."""
    _stub_all(monkeypatch, telegram=True, web_push=True, email=True)
    prefs = _prefs(telegram_chat_id=None, web_push_enabled=0, email="a@b.c")
    res = ns.notify(999001, "your_turn", PAYLOAD, prefs=prefs)
    assert res["channel"] == "email"


def test_falls_through_on_send_failure(monkeypatch):
    """Telegram enabled but its send FAILS → must fall through to web push."""
    _stub_all(monkeypatch, telegram=False, web_push=True, email=True)
    prefs = _prefs(telegram_chat_id="12345", web_push_enabled=1, email="a@b.c")
    res = ns.notify(999001, "your_turn", PAYLOAD, prefs=prefs)
    assert res["channel"] == "web_push"
    # telegram was attempted before web push succeeded
    attempted = [a["channel"] for a in res["attempts"]]
    assert attempted == ["telegram", "web_push"]


def test_undelivered_when_no_channel_available(monkeypatch):
    """No channel enabled → delivered False, channel None (no crash)."""
    _stub_all(monkeypatch, telegram=True, web_push=True, email=True)
    prefs = _prefs()  # all off
    res = ns.notify(999001, "your_turn", PAYLOAD, prefs=prefs)
    assert res["delivered"] is False
    assert res["channel"] is None


def test_channel_order_is_respected(monkeypatch):
    """Custom channel_order email,telegram → email tried first when available."""
    _stub_all(monkeypatch, telegram=True, web_push=True, email=True)
    prefs = _prefs(
        telegram_chat_id="12345", email="a@b.c",
        channel_order="email,telegram",
    )
    res = ns.notify(999001, "your_turn", PAYLOAD, prefs=prefs)
    assert res["channel"] == "email"


# ─── preview_channel — dry-run dla panelu/Playwright ─────────────────────────

def test_preview_channel_picks_first_enabled():
    """Dry-run returns the first enabled channel + the enabled set, no send."""
    prefs = _prefs(telegram_chat_id="123", web_push_enabled=1, email="a@b.c")
    p = ns.preview_channel(999001, prefs=prefs)
    assert p["channel"] == "telegram"
    assert p["enabled_channels"] == ["telegram", "web_push", "email"]


def test_preview_channel_none_when_all_off():
    p = ns.preview_channel(999001, prefs=_prefs())
    assert p["channel"] is None
    assert p["enabled_channels"] == []


# ─── Telegram sender — bezpieczny no-op bez tokenu ───────────────────────────

def test_send_telegram_noop_without_token(monkeypatch):
    """No bot token / no chat_id → returns False, never raises."""
    monkeypatch.setattr(ns, "_TELEGRAM_BOT_TOKEN", "")
    assert ns.send_telegram("12345", "t", "b") is False
    monkeypatch.setattr(ns, "_TELEGRAM_BOT_TOKEN", "tok")
    assert ns.send_telegram("", "t", "b") is False


# ─── Backward-safe: prefs roundtrip na realnej tabeli (N0 table) ─────────────

def test_prefs_roundtrip_and_default(tmp_path):
    """get_prefs returns sane defaults with no row; set_prefs persists + reloads."""
    db = str(tmp_path / "notify_test.db")
    conn = sqlite3.connect(db)
    for stmt in ns.SCHEMA_SQL:
        conn.execute(stmt)
    conn.commit()
    conn.close()

    uid = 999042
    # no row yet → defaults, telegram-first order, everything off
    d = ns.get_prefs(uid, db_path=db)
    assert d["channel_order"] == "telegram,web_push,email"
    assert not d["web_push_enabled"]
    assert d["telegram_chat_id"] is None

    ns.set_prefs(uid, web_push_enabled=1, email="player@x.io", db_path=db)
    d2 = ns.get_prefs(uid, db_path=db)
    assert d2["web_push_enabled"] == 1
    assert d2["email"] == "player@x.io"


def test_delivery_is_logged(tmp_path, monkeypatch):
    """A successful notify writes one 'delivered' row to notify_delivery_log."""
    db = str(tmp_path / "notify_log.db")
    conn = sqlite3.connect(db)
    for stmt in ns.SCHEMA_SQL:
        conn.execute(stmt)
    conn.commit()
    conn.close()

    monkeypatch.setattr(ns, "_deliver_telegram", lambda *a, **k: True)
    prefs = _prefs(telegram_chat_id="123")
    ns.notify(999001, "your_turn", PAYLOAD, prefs=prefs, db_path=db)

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT channel, status FROM notify_delivery_log WHERE event='your_turn'"
    ).fetchall()
    conn.close()
    assert ("telegram", "delivered") in rows
