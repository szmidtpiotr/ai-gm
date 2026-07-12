"""Issue #883 (Faza N1 of #602) — Telegram easy-click linking.

Covers token mint → deep-link → /start webhook redeem → chat_id bound, plus the
guard rails: single-use, expiry, unknown token, non-/start updates, unlink.
No live bot needed — redeem_token / handle_update take plain dicts.
"""
import sqlite3

import pytest

from app.services import notification_service as ns
from app.services import telegram_link_service as tls


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "t883.db")
    conn = sqlite3.connect(path)
    for sql in ns.SCHEMA_SQL + tls.SCHEMA_SQL:
        conn.execute(sql)
    conn.commit()
    conn.close()
    return path


def test_create_link_token_persists_and_is_unique(db):
    a = tls.create_link_token(1, db_path=db)
    b = tls.create_link_token(2, db_path=db)
    assert a["token"] and b["token"] and a["token"] != b["token"]


def test_create_link_token_drops_prior_unused_for_same_user(db):
    first = tls.create_link_token(1, db_path=db)["token"]
    second = tls.create_link_token(1, db_path=db)["token"]
    # Old link must no longer redeem — only the latest works.
    assert tls.redeem_token(first, 555, db_path=db) is None
    assert tls.redeem_token(second, 555, db_path=db) == 1


def test_deep_link_and_username_from_env(db, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "@aigm_bot")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    res = tls.create_link_token(7, db_path=db)
    assert res["bot_username"] == "aigm_bot"
    assert res["configured"] is True
    assert res["deep_link"] == f"https://t.me/aigm_bot?start={res['token']}"


def test_deep_link_none_without_bot(db, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_USERNAME", raising=False)
    res = tls.create_link_token(7, db_path=db)
    assert res["deep_link"] is None
    assert res["configured"] is False


def test_redeem_binds_chat_id_to_user(db):
    token = tls.create_link_token(42, db_path=db)["token"]
    assert tls.redeem_token(token, 99887766, db_path=db) == 42
    prefs = ns.get_prefs(42, db_path=db)
    assert prefs["telegram_chat_id"] == "99887766"
    assert tls.is_connected(42, db_path=db) is True


def test_redeem_is_single_use(db):
    token = tls.create_link_token(42, db_path=db)["token"]
    assert tls.redeem_token(token, 111, db_path=db) == 42
    assert tls.redeem_token(token, 222, db_path=db) is None  # already used


def test_redeem_unknown_token_returns_none(db):
    assert tls.redeem_token("does-not-exist", 111, db_path=db) is None


def test_redeem_expired_token_returns_none(db):
    token = tls.create_link_token(42, db_path=db)["token"]
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE telegram_link_tokens SET created_at = datetime('now','-30 minutes') WHERE token = ?",
        (token,),
    )
    conn.commit()
    conn.close()
    assert tls.redeem_token(token, 111, db_path=db) is None


def test_redeem_requires_chat_id(db):
    token = tls.create_link_token(42, db_path=db)["token"]
    assert tls.redeem_token(token, None, db_path=db) is None
    assert tls.redeem_token(token, "", db_path=db) is None


def test_handle_update_start_command_links(db):
    token = tls.create_link_token(5, db_path=db)["token"]
    update = {"message": {"text": f"/start {token}", "chat": {"id": 424242}}}
    res = tls.handle_update(update, db_path=db)
    assert res == {"handled": True, "linked": True, "user_id": 5}
    assert ns.get_prefs(5, db_path=db)["telegram_chat_id"] == "424242"


def test_handle_update_ignores_non_start(db):
    res = tls.handle_update({"message": {"text": "hello", "chat": {"id": 1}}}, db_path=db)
    assert res["handled"] is False and res["linked"] is False


def test_handle_update_start_without_token_is_noop(db):
    res = tls.handle_update({"message": {"text": "/start", "chat": {"id": 1}}}, db_path=db)
    assert res["handled"] is False


def test_handle_update_bad_token_handled_not_linked(db):
    update = {"message": {"text": "/start bogus", "chat": {"id": 1}}}
    res = tls.handle_update(update, db_path=db)
    assert res["handled"] is True and res["linked"] is False


def test_handle_update_malformed_never_raises(db):
    assert tls.handle_update({}, db_path=db)["handled"] is False
    assert tls.handle_update({"message": None}, db_path=db)["handled"] is False


def test_unlink_clears_channel(db):
    token = tls.create_link_token(9, db_path=db)["token"]
    tls.redeem_token(token, 777, db_path=db)
    assert tls.is_connected(9, db_path=db) is True
    tls.unlink(9, db_path=db)
    assert tls.is_connected(9, db_path=db) is False


def test_edited_message_start_also_links(db):
    token = tls.create_link_token(3, db_path=db)["token"]
    update = {"edited_message": {"text": f"/start {token}", "chat": {"id": 5}}}
    assert tls.handle_update(update, db_path=db)["linked"] is True
