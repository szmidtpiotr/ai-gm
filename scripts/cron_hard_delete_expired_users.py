#!/usr/bin/env python3
"""F1.2 follow-up — Hard-delete users that have passed the 7-day soft-delete grace.

Runs from cron at 04:00 UTC (after the 03:00 backup so the pre-purge state is
captured). Companion to the soft-delete flow in `backend/app/api/auth.py`.

A user is eligible for hard-delete when:
- ``users.deleted_at IS NOT NULL``
- ``users.deleted_at`` is older than 7 days

For each eligible user, the script removes their owned data, anonymises audit
records, then deletes the user row. All cascade work for one user happens in a
single transaction so a mid-run failure leaves the DB consistent.

Usage:
    cron_hard_delete_expired_users.py [--dry-run] [--grace-days N] [--db PATH]

Exit codes: 0 on success (including no candidates), 1 on error.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import logging
import sqlite3
import sys

DEFAULT_DB = "/data/ai_gm.db"
GRACE_DAYS_DEFAULT = 7

log = logging.getLogger("hard_delete_expired_users")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    try:
        return any(r[1] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())
    except sqlite3.OperationalError:
        return False


def _find_candidates(conn: sqlite3.Connection, grace_days: int) -> list[sqlite3.Row]:
    cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=grace_days)).isoformat()
    return conn.execute(
        """
        SELECT id, username, deleted_at
        FROM users
        WHERE deleted_at IS NOT NULL AND deleted_at < ?
        ORDER BY deleted_at
        """,
        (cutoff,),
    ).fetchall()


def _delete_user_cascade(conn: sqlite3.Connection, user_id: int) -> dict[str, int]:
    """Remove all rows owned by *user_id* and anonymise audit references.

    Returns a per-table delete count. Caller wraps in a transaction.
    """
    counts: dict[str, int] = {}

    char_ids = [
        r["id"]
        for r in conn.execute("SELECT id FROM characters WHERE user_id = ?", (user_id,)).fetchall()
    ]
    campaign_ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM campaigns WHERE owner_user_id = ?", (user_id,)
        ).fetchall()
    ]

    def _delete(table: str, where: str, params: tuple) -> None:
        try:
            cur = conn.execute(f"DELETE FROM {table} WHERE {where}", params)
            if cur.rowcount:
                counts[table] = counts.get(table, 0) + cur.rowcount
        except sqlite3.OperationalError as exc:
            # Table may not exist in older snapshots — log and skip.
            log.warning("skip_missing_table %s: %s", table, exc)

    # Character-scoped cascade.
    if char_ids:
        placeholders = ",".join("?" * len(char_ids))
        for tbl in (
            "character_inventory",
            "character_spells",
            "character_conditions",
            "character_dungeon_runs",
            "character_quests",
            "character_xp_grants",
        ):
            _delete(tbl, f"character_id IN ({placeholders})", tuple(char_ids))

    # Campaign-scoped cascade. Some tables (e.g. campaign_ideas) don't carry
    # campaign_id directly — only delete when the column actually exists.
    if campaign_ids:
        placeholders = ",".join("?" * len(campaign_ids))
        campaign_tables = (
            "campaign_turns",
            "active_combat",
            "game_sessions",
            "campaign_known_npcs",
            "campaign_ideas",
            "campaign_catalog_state",
            "campaign_catalog_entities",
            "campaign_members",
            "combat_loot",
        )
        for tbl in campaign_tables:
            if _has_column(conn, tbl, "campaign_id"):
                _delete(tbl, f"campaign_id IN ({placeholders})", tuple(campaign_ids))
        # combat_turns FK is on combat.id — match via subquery on the to-be-deleted combats.
        # Already handled because active_combat is deleted, but combat_turns may outlive it.
        _delete(
            "combat_turns",
            f"combat_id IN (SELECT id FROM active_combat WHERE campaign_id IN ({placeholders}))",
            tuple(campaign_ids),
        )

    # Anonymise audit/log rows so historical traces remain but the user is unlinked.
    try:
        cur = conn.execute(
            "UPDATE game_events SET user_id = NULL WHERE user_id = ?", (user_id,)
        )
        if cur.rowcount:
            counts["game_events(anonymised)"] = cur.rowcount
    except sqlite3.OperationalError as exc:
        log.warning("skip_anonymise game_events: %s", exc)

    # Now delete the owner rows themselves.
    _delete("characters", "user_id = ?", (user_id,))
    _delete("campaigns", "owner_user_id = ?", (user_id,))

    # User-scoped cascade (after characters/campaigns so FK assumptions hold).
    for tbl in (
        "user_llm_settings",
        "email_verification_tokens",
        "password_reset_tokens",
        "user_invites",
    ):
        if _has_column(conn, tbl, "user_id"):
            _delete(tbl, "user_id = ?", (user_id,))

    # Friendships go both ways and via requester_id.
    _delete(
        "user_friendships",
        "user_a_id = ? OR user_b_id = ? OR requester_id = ?",
        (user_id, user_id, user_id),
    )

    _delete("users", "id = ?", (user_id,))

    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show candidates without deleting.")
    parser.add_argument(
        "--grace-days",
        type=int,
        default=GRACE_DAYS_DEFAULT,
        help=f"Days since deleted_at before purge (default {GRACE_DAYS_DEFAULT}).",
    )
    parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite DB path (default {DEFAULT_DB}).")
    args = parser.parse_args(argv)

    _setup_logging()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    candidates = _find_candidates(conn, args.grace_days)
    if not candidates:
        log.info("no_candidates grace_days=%d", args.grace_days)
        conn.close()
        return 0

    log.info("found_candidates count=%d grace_days=%d", len(candidates), args.grace_days)

    if args.dry_run:
        for row in candidates:
            log.info(
                "dry_run user_id=%d username=%s deleted_at=%s",
                row["id"],
                row["username"],
                row["deleted_at"],
            )
        conn.close()
        return 0

    for row in candidates:
        user_id = int(row["id"])
        try:
            conn.execute("BEGIN")
            counts = _delete_user_cascade(conn, user_id)
            conn.commit()
            log.info(
                "purged user_id=%d username=%s deleted_at=%s cascade=%s",
                user_id,
                row["username"],
                row["deleted_at"],
                counts,
            )
        except Exception as exc:
            conn.rollback()
            log.error("purge_failed user_id=%d error=%s", user_id, exc)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
