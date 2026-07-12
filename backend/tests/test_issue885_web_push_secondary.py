"""Issue #885 (Faza N3 of #602) — web push as dispatcher secondary, real e2e.

Verifies the web_push channel is chosen only when enabled AND a live subscription
exists, actually calls send_push, and falls through to email when push can't land.
"""
import sqlite3

import pytest

from app.services import notification_service as ns
from app.services import push_notification_service as pns


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "t885.db")
    conn = sqlite3.connect(path)
    for sql in ns.SCHEMA_SQL:
        conn.execute(sql)
    conn.execute(
        "CREATE TABLE user_push_subscriptions (user_id INTEGER, endpoint TEXT, p256dh TEXT, auth TEXT)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(pns, "_is_configured", lambda: True)
    return path


def _sub(db, uid):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO user_push_subscriptions (user_id, endpoint, p256dh, auth) VALUES (?,?,?,?)",
        (uid, "https://push/ep", "p", "a"),
    )
    conn.commit()
    conn.close()


def test_web_push_chosen_when_enabled_and_subscribed(db, monkeypatch):
    sent = {}
    monkeypatch.setattr(pns, "send_push", lambda uid, t, b, u: sent.setdefault("uid", uid) or True)
    ns.set_prefs(1, db_path=db, web_push_enabled=1, channel_order="telegram,web_push,email")
    _sub(db, 1)
    res = ns.notify(1, "twoja_tura", {"title": "T", "body": "B"}, db_path=db)
    assert res["channel"] == "web_push"
    assert res["delivered"] is True
    assert sent["uid"] == 1


def test_telegram_off_falls_to_web_push(db, monkeypatch):
    monkeypatch.setattr(pns, "send_push", lambda *a, **k: True)
    # telegram first in order but no chat_id → skipped; web_push enabled + subscribed
    ns.set_prefs(2, db_path=db, web_push_enabled=1)
    _sub(db, 2)
    res = ns.notify(2, "twoja_tura", {"title": "T", "body": "B"}, db_path=db)
    assert res["channel"] == "web_push"


def test_enabled_but_no_subscription_falls_to_email(db, monkeypatch):
    monkeypatch.setattr(pns, "send_push", lambda *a, **k: True)  # never called (no sub)
    from app.services import email_service
    monkeypatch.setattr(email_service, "send_email", lambda *a, **k: True)
    ns.set_prefs(3, db_path=db, web_push_enabled=1, email="p@x.pl")
    res = ns.notify(3, "twoja_tura", {"title": "T", "body": "B"}, db_path=db)
    assert res["channel"] == "email"


def test_push_send_failure_falls_to_email(db, monkeypatch):
    monkeypatch.setattr(pns, "send_push", lambda *a, **k: False)  # push didn't land
    from app.services import email_service
    monkeypatch.setattr(email_service, "send_email", lambda *a, **k: True)
    ns.set_prefs(4, db_path=db, web_push_enabled=1, email="p@x.pl")
    _sub(db, 4)
    res = ns.notify(4, "twoja_tura", {"title": "T", "body": "B"}, db_path=db)
    assert res["channel"] == "email"


def test_web_push_disabled_skips_even_with_subscription(db, monkeypatch):
    monkeypatch.setattr(pns, "send_push", lambda *a, **k: True)
    from app.services import email_service
    monkeypatch.setattr(email_service, "send_email", lambda *a, **k: True)
    ns.set_prefs(5, db_path=db, web_push_enabled=0, email="p@x.pl")
    _sub(db, 5)
    res = ns.notify(5, "twoja_tura", {"title": "T", "body": "B"}, db_path=db)
    assert res["channel"] == "email"  # web_push not enabled → skipped
