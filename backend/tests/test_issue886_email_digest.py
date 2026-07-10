"""Issue #886 (Faza N4 of #602) — overdue-turn email digest fallback.

Overdue collecting round → one email per absentee, de-duped per round; a member
who already submitted, or has no email, gets nothing; a fresh round gets nothing.
"""
import sqlite3

import pytest

from app.services import notification_service as ns
from app.services import notify_digest_service as digest


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "t886.db")
    conn = sqlite3.connect(path)
    for sql in ns.SCHEMA_SQL + digest.SCHEMA_SQL:
        conn.execute(sql)
    conn.execute(
        """CREATE TABLE campaign_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, round_number INTEGER,
            status TEXT, created_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE campaign_members (campaign_id INTEGER, user_id INTEGER, status TEXT)"""
    )
    conn.execute(
        """CREATE TABLE campaign_round_actions (round_id INTEGER, user_id INTEGER, action_text TEXT)"""
    )
    conn.commit()
    conn.close()
    # get_prefs / _log_delivery inside the service resolve the real DB unless db_path
    # is threaded — the service passes db_path through, so no global patch needed.
    return path


def _round(db, rid, camp=7, status="collecting", age_min=60):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO campaign_rounds (id, campaign_id, round_number, status, created_at) "
        "VALUES (?,?,1,?, datetime('now', ?))",
        (rid, camp, status, f"-{age_min} minutes"),
    )
    conn.commit()
    conn.close()


def _member(db, uid, camp=7, status="accepted"):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO campaign_members (campaign_id, user_id, status) VALUES (?,?,?)",
        (camp, uid, status),
    )
    conn.commit()
    conn.close()


def _submit(db, rid, uid, text="atakuję"):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO campaign_round_actions (round_id, user_id, action_text) VALUES (?,?,?)",
        (rid, uid, text),
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def capture_email(monkeypatch):
    sent = []
    import app.services.email_service as es
    monkeypatch.setattr(es, "send_email", lambda to, subj, html: (sent.append(to) or True))
    return sent


def test_overdue_round_emails_absentee(db, capture_email):
    _round(db, 100, age_min=45)
    _member(db, 1)
    ns.set_prefs(1, db_path=db, email="p1@x.pl")
    res = digest.send_overdue_turn_digests(db_path=db)
    assert res == {"rounds": 1, "emails": 1}
    assert capture_email == ["p1@x.pl"]


def test_second_tick_does_not_resend(db, capture_email):
    _round(db, 100, age_min=45)
    _member(db, 1)
    ns.set_prefs(1, db_path=db, email="p1@x.pl")
    digest.send_overdue_turn_digests(db_path=db)
    capture_email.clear()
    res = digest.send_overdue_turn_digests(db_path=db)
    assert res["rounds"] == 0
    assert capture_email == []


def test_fresh_round_not_emailed(db, capture_email):
    _round(db, 100, age_min=5)  # under threshold
    _member(db, 1)
    ns.set_prefs(1, db_path=db, email="p1@x.pl")
    res = digest.send_overdue_turn_digests(db_path=db)
    assert res["rounds"] == 0
    assert capture_email == []


def test_submitted_member_not_emailed(db, capture_email):
    _round(db, 100, age_min=45)
    _member(db, 1)
    ns.set_prefs(1, db_path=db, email="p1@x.pl")
    _submit(db, 100, 1)
    res = digest.send_overdue_turn_digests(db_path=db)
    assert res["emails"] == 0
    assert capture_email == []


def test_member_without_email_skipped(db, capture_email):
    _round(db, 100, age_min=45)
    _member(db, 1)  # no prefs → no email
    res = digest.send_overdue_turn_digests(db_path=db)
    assert res["emails"] == 0
    assert capture_email == []


def test_only_collecting_rounds(db, capture_email):
    _round(db, 100, status="done", age_min=90)
    _member(db, 1)
    ns.set_prefs(1, db_path=db, email="p1@x.pl")
    res = digest.send_overdue_turn_digests(db_path=db)
    assert res["rounds"] == 0


def test_custom_threshold(db, capture_email):
    _round(db, 100, age_min=15)
    _member(db, 1)
    ns.set_prefs(1, db_path=db, email="p1@x.pl")
    assert digest.send_overdue_turn_digests(threshold_minutes=10, db_path=db)["emails"] == 1
