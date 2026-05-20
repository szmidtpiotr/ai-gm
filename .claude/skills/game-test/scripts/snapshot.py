#!/usr/bin/env python3
"""Compact DB snapshot for a campaign. One JSON line on stdout.

Usage:
    snapshot.py --campaign <id> [--full]

Default snapshot covers location integrity + session state + last turn id.
--full also includes inventory, spells, and combat tables.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("/home/claude/projects/DEV_AIGM/data-dev/ai_gm.db")


def fetch_one(db, sql, params=()):
    r = db.execute(sql, params).fetchone()
    return dict(r) if r else None


def fetch_all(db, sql, params=()):
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def snapshot(campaign_id: int, full: bool) -> dict:
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    out = {"campaign_id": campaign_id}

    out["campaign"] = fetch_one(
        db,
        "SELECT id, title, status FROM campaigns WHERE id=?",
        (campaign_id,),
    )

    session = fetch_one(
        db,
        "SELECT id, current_location_id, ingame_hours FROM game_sessions "
        "WHERE campaign_id=? ORDER BY id DESC LIMIT 1",
        (campaign_id,),
    )
    out["session"] = session

    if session and session.get("current_location_id"):
        out["session_location"] = fetch_one(
            db,
            "SELECT id, key, label, parent_key, is_active FROM game_locations WHERE id=?",
            (session["current_location_id"],),
        )

    out["character"] = fetch_one(
        db,
        "SELECT id, name, status FROM characters WHERE campaign_id=? LIMIT 1",
        (campaign_id,),
    )
    if out["character"]:
        sheet_row = fetch_one(
            db,
            "SELECT sheet_json FROM characters WHERE id=?",
            (out["character"]["id"],),
        )
        try:
            sheet = json.loads(sheet_row["sheet_json"] or "{}")
            out["character_state"] = {
                "current_hp": sheet.get("current_hp"),
                "max_hp": sheet.get("max_hp"),
                "current_mana": sheet.get("current_mana"),
                "max_mana": sheet.get("max_mana"),
                "conditions": sheet.get("conditions"),
                "level": sheet.get("level"),
                "xp": sheet.get("xp"),
            }
        except Exception:
            out["character_state"] = None

    counts = fetch_one(
        db,
        "SELECT "
        "  (SELECT COUNT(*) FROM game_locations WHERE COALESCE(is_active,1)=1) AS active_locations, "
        "  (SELECT COUNT(*) FROM game_locations WHERE source_campaign_id=? AND ai_generated=1 AND COALESCE(is_active,1)=1) AS active_gm_locations_this_campaign, "
        "  (SELECT COUNT(*) FROM campaign_turns WHERE campaign_id=?) AS total_turns",
        (campaign_id, campaign_id),
    )
    out["counts"] = counts

    out["last_turn"] = fetch_one(
        db,
        "SELECT id, turn_number, route, substr(user_text,1,80) AS user_short "
        "FROM campaign_turns WHERE campaign_id=? ORDER BY id DESC LIMIT 1",
        (campaign_id,),
    )

    out["recent_gm_locations"] = fetch_all(
        db,
        "SELECT id, key, label, parent_id, biome, location_subtype, ai_generated, is_active, created_at "
        "FROM game_locations WHERE source_campaign_id=? "
        "ORDER BY id DESC LIMIT 10",
        (campaign_id,),
    )

    if full:
        out["combat"] = fetch_one(
            db,
            "SELECT id, status, current_turn FROM combat_state "
            "WHERE campaign_id=? AND status='active' ORDER BY id DESC LIMIT 1",
            (campaign_id,),
        )
        if out["character"]:
            out["inventory_count"] = fetch_one(
                db,
                "SELECT COUNT(*) AS n FROM character_inventory WHERE character_id=?",
                (out["character"]["id"],),
            )
            out["spell_count"] = fetch_one(
                db,
                "SELECT COUNT(*) AS n FROM character_spells WHERE character_id=?",
                (out["character"]["id"],),
            )

    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--campaign", type=int, required=True)
    p.add_argument("--full", action="store_true")
    args = p.parse_args()

    if not DB_PATH.exists():
        print(json.dumps({"error": f"DB not found at {DB_PATH}"}))
        return 2

    print(json.dumps(snapshot(args.campaign, args.full), ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
