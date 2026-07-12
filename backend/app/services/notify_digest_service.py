"""Overdue-turn email digest — Issue #886 (Faza N4 of #602).

A background tick (piggy-backed on the 30s MP sweep loop) finds collecting rounds
older than a threshold and emails the members who still owe an action: a gentle
"masz zaległą turę" nudge, the last-resort channel when Telegram / web push did
not reach them.

De-dup: one digest per round, tracked in `round_digest_sent`. A member who has
already submitted, or who has no email on file, is skipped.

Reuses `email_service.send_email` + `player_notify_prefs.email`. DDL for
`round_digest_sent` is mirrored in ADMIN_MIGRATIONS (migrations_admin.py).
"""
import sqlite3
from typing import Optional

from app.core.db_runtime import resolve_db_path
from app.core.logging import get_logger
from app.services import notification_service as ns

logger = get_logger(__name__)

# Minutes a round may sit in 'collecting' before absentees get an email nudge.
# Starting value (#886 Numbers Policy); tune after testing.
DIGEST_THRESHOLD_MINUTES = 30

SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS round_digest_sent (
        round_id INTEGER PRIMARY KEY,
        sent_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
]


def _db(db_path: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _overdue_rounds(conn: sqlite3.Connection, threshold_minutes: int) -> list:
    return conn.execute(
        "SELECT id, campaign_id FROM campaign_rounds "
        "WHERE status='collecting' "
        "AND datetime(created_at) < datetime('now', ?) "
        "AND id NOT IN (SELECT round_id FROM round_digest_sent)",
        (f"-{threshold_minutes} minutes",),
    ).fetchall()


def _absent_members_with_email(conn: sqlite3.Connection, round_id: int, campaign_id: int) -> list:
    """Accepted members who owe an action this round and have an email on file."""
    submitted = {
        int(r["user_id"])
        for r in conn.execute(
            "SELECT user_id FROM campaign_round_actions "
            "WHERE round_id=? AND action_text != '[BRAK AKCJI]'",
            (round_id,),
        ).fetchall()
    }
    out = []
    for r in conn.execute(
        "SELECT m.user_id AS user_id, p.email AS email "
        "FROM campaign_members m "
        "LEFT JOIN player_notify_prefs p ON p.user_id = m.user_id "
        "WHERE m.campaign_id=? AND m.status='accepted'",
        (campaign_id,),
    ).fetchall():
        uid = int(r["user_id"])
        if uid in submitted:
            continue
        if r["email"]:
            out.append((uid, r["email"]))
    return out


def send_overdue_turn_digests(
    threshold_minutes: int = DIGEST_THRESHOLD_MINUTES, db_path: Optional[str] = None
) -> dict:
    """Scan overdue rounds, email each absentee once. Returns {rounds, emails}."""
    conn = _db(db_path)
    try:
        rounds = _overdue_rounds(conn, threshold_minutes)
    finally:
        conn.close()

    from app.services.email_service import send_email

    rounds_done, emails = 0, 0
    for rnd in rounds:
        round_id = int(rnd["id"])
        campaign_id = int(rnd["campaign_id"])
        conn = _db(db_path)
        try:
            absentees = _absent_members_with_email(conn, round_id, campaign_id)
        finally:
            conn.close()

        for uid, email in absentees:
            try:
                ok = send_email(
                    email,
                    "AI-GM — masz zaległą turę",
                    "<p>Twoja drużyna czeka. Wróć do gry i dodaj swoją akcję w tej rundzie.</p>",
                )
                ns._log_delivery(uid, "overdue_digest", "email",
                                 "delivered" if ok else "failed", db_path=db_path)
                if ok:
                    emails += 1
            except Exception as e:  # noqa: BLE001 — one bad email must not stop the sweep
                logger.warning("digest_email_failed", user_id=uid, error=str(e)[:120])

        # Mark the round digested even if it had zero absentees — one pass per round.
        conn = _db(db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO round_digest_sent (round_id) VALUES (?)", (round_id,)
            )
            conn.commit()
        finally:
            conn.close()
        rounds_done += 1

    if rounds_done:
        logger.info("overdue_digests_sent", rounds=rounds_done, emails=emails)
    return {"rounds": rounds_done, "emails": emails}
