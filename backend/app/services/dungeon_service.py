"""Dungeon run service — Task 41."""
from __future__ import annotations
import json
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

DB_PATH = "/data/ai_gm.db"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_dungeon(dungeon_key: str) -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT * FROM game_dungeons WHERE key = ? AND is_active = 1",
            (dungeon_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_dungeons(character_id: int | None = None) -> list[dict]:
    """List all active dungeons with cooldown status for a character."""
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM game_dungeons WHERE is_active = 1 ORDER BY min_level, key"
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d["enemy_pool"] = json.loads(d["enemy_pool"] or "[]")
            except Exception:
                d["enemy_pool"] = []
            if character_id:
                d["cooldown"] = check_cooldown(character_id, d["key"])
            else:
                d["cooldown"] = {"on_cooldown": False}
            result.append(d)
        return result
    finally:
        conn.close()


def check_cooldown(character_id: int, dungeon_key: str) -> dict:
    """Return cooldown status for a character + dungeon."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT cooldown_until, run_count FROM character_dungeon_runs"
            " WHERE character_id = ? AND location_key = ?",
            (character_id, dungeon_key),
        ).fetchone()
        if not row:
            return {"on_cooldown": False, "run_count": 0}
        cooldown_until_str = str(row["cooldown_until"] or "")
        run_count = int(row["run_count"] or 0)
        try:
            cooldown_until = datetime.fromisoformat(
                cooldown_until_str.replace("Z", "+00:00")
            )
            if cooldown_until.tzinfo is None:
                cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
        except Exception:
            return {"on_cooldown": False, "run_count": run_count}
        now = _now_utc()
        if now >= cooldown_until:
            return {
                "on_cooldown": False,
                "run_count": run_count,
                "cooldown_until": cooldown_until_str,
            }
        remaining = cooldown_until - now
        hours_remaining = remaining.total_seconds() / 3600
        return {
            "on_cooldown": True,
            "cooldown_until": cooldown_until_str,
            "hours_remaining": round(hours_remaining, 1),
            "run_count": run_count,
        }
    finally:
        conn.close()


def complete_dungeon(character_id: int, dungeon_key: str) -> dict:
    """Record a completed dungeon run, set cooldown, return result."""
    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        raise ValueError(f"Dungeon not found: {dungeon_key}")
    cooldown_hours = int(dungeon.get("cooldown_hours") or 72)
    now = _now_utc()
    cooldown_until = now + timedelta(hours=cooldown_hours)
    conn = _get_db()
    try:
        conn.execute(
            """
            INSERT INTO character_dungeon_runs
                (character_id, location_key, cleared_at, cooldown_until, run_count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(character_id, location_key) DO UPDATE SET
                cleared_at     = excluded.cleared_at,
                cooldown_until = excluded.cooldown_until,
                run_count      = run_count + 1
            """,
            (character_id, dungeon_key, now.isoformat(), cooldown_until.isoformat()),
        )
        conn.commit()
        return {
            "dungeon_key": dungeon_key,
            "cleared_at": now.isoformat(),
            "cooldown_until": cooldown_until.isoformat(),
            "cooldown_hours": cooldown_hours,
        }
    finally:
        conn.close()


def get_run_history(character_id: int) -> list[dict]:
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM character_dungeon_runs"
            " WHERE character_id = ? ORDER BY cleared_at DESC",
            (character_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def pick_encounter(dungeon_key: str, room_number: int) -> list[str]:
    """Pick enemies for a room from the dungeon's enemy_pool."""
    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        return []
    pool = json.loads(dungeon.get("enemy_pool") or "[]")
    if not pool:
        return []
    is_boss_room = (
        room_number >= int(dungeon.get("rooms") or 5) and dungeon.get("boss_enemy")
    )
    if is_boss_room:
        boss = dungeon["boss_enemy"]
        extras = random.sample(pool, min(1, len(pool)))
        return [boss] + extras
    count = random.randint(1, min(3, len(pool)))
    return random.choices(pool, k=count)
