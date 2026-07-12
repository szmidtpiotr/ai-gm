"""Issue #884 (Faza N2b of #602) — notify() fan-out into MP round events.

Covers notify_campaign_players: targets accepted members, anti-spam skips online
(in-session) members + explicitly excluded ids, dispatches over the preferred
channel, logs each attempt.
"""
import sqlite3

import pytest

from app.services import notification_service as ns


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "t884.db")
    conn = sqlite3.connect(path)
    for sql in ns.SCHEMA_SQL:
        conn.execute(sql)
    conn.execute(
        """CREATE TABLE campaign_members (
            campaign_id INTEGER, user_id INTEGER, status TEXT, last_seen TEXT
        )"""
    )
    conn.commit()
    conn.close()
    # Telegram send is a no-op network call — stub it so "delivered" is deterministic.
    monkeypatch.setattr(ns, "send_telegram", lambda chat_id, title, body: True)
    return path


def _member(db, uid, status="accepted", last_seen=None):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, status, last_seen) VALUES (7, ?, ?, ?)",
        (uid, status, last_seen),
    )
    conn.commit()
    conn.close()


def _enable_telegram(db, uid, chat="c" ):
    ns.set_prefs(uid, db_path=db, telegram_chat_id=str(chat))


def test_fans_out_to_offline_accepted_members(db):
    _member(db, 1)
    _member(db, 2)
    _enable_telegram(db, 1)
    _enable_telegram(db, 2)
    res = ns.notify_campaign_players(7, "twoja_tura", "T", "B", db_path=db)
    assert set(res["targeted"]) == {1, 2}
    assert set(res["delivered"]) == {1, 2}


def test_skips_online_members(db):
    _member(db, 1, last_seen="2099-01-01 00:00:00")  # far future → "online"
    _member(db, 2)  # no last_seen → offline
    _enable_telegram(db, 1)
    _enable_telegram(db, 2)
    res = ns.notify_campaign_players(7, "twoja_tura", "T", "B", db_path=db)
    assert res["targeted"] == [2]
    assert res["skipped_online"] == 1


def test_respects_exclude_user_ids(db):
    _member(db, 1)
    _member(db, 2)
    _enable_telegram(db, 1)
    _enable_telegram(db, 2)
    res = ns.notify_campaign_players(7, "twoja_tura", "T", "B", exclude_user_ids=[1], db_path=db)
    assert res["targeted"] == [2]


def test_ignores_non_accepted_members(db):
    _member(db, 1, status="invited")
    _member(db, 2, status="left")
    _member(db, 3, status="accepted")
    _enable_telegram(db, 3)
    res = ns.notify_campaign_players(7, "twoja_tura", "T", "B", db_path=db)
    assert res["targeted"] == [3]


def test_can_include_online_when_disabled(db):
    _member(db, 1, last_seen="2099-01-01 00:00:00")
    _enable_telegram(db, 1)
    res = ns.notify_campaign_players(7, "twoja_tura", "T", "B", exclude_online=False, db_path=db)
    assert res["targeted"] == [1]


def test_logs_each_attempt(db):
    _member(db, 1)
    _enable_telegram(db, 1)
    ns.notify_campaign_players(7, "twoja_tura", "T", "B", db_path=db)
    conn = sqlite3.connect(db)
    n = conn.execute(
        "SELECT COUNT(*) FROM notify_delivery_log WHERE user_id=1 AND event='twoja_tura'"
    ).fetchone()[0]
    conn.close()
    assert n >= 1


def test_member_without_channel_targeted_but_not_delivered(db):
    _member(db, 1)  # no prefs → no channel
    res = ns.notify_campaign_players(7, "twoja_tura", "T", "B", db_path=db)
    assert res["targeted"] == [1]
    assert res["delivered"] == []


def test_no_members_is_safe(db):
    res = ns.notify_campaign_players(7, "twoja_tura", "T", "B", db_path=db)
    assert res == {"targeted": [], "delivered": [], "skipped_online": 0}
