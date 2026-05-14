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

# ── Level-based enemy scaling ─────────────────────────────────────────────────

_SCALE_TABLE = [
    (2, 0.75),   # level 1-2
    (4, 1.0),    # level 3-4
    (6, 1.25),   # level 5-6
    (8, 1.5),    # level 7-8
    (99, 2.0),   # level 9+
]

_DIE_PROGRESSION = ["d4", "d6", "d8", "d10", "d12"]


def _level_multiplier(hero_level: int) -> float:
    for max_level, mult in _SCALE_TABLE:
        if hero_level <= max_level:
            return mult
    return 2.0


def _scale_die_up(die_expr: str) -> str:
    """Step a damage die up one size: d4→d6→d8→d10→d12."""
    import re
    m = re.match(r"^(\d*)d(\d+)$", (die_expr or "1d6").strip().lower())
    if not m:
        return die_expr
    n = m.group(1) or "1"
    sides = int(m.group(2))
    base = f"d{sides}"
    try:
        idx = _DIE_PROGRESSION.index(base)
        next_die = _DIE_PROGRESSION[min(idx + 1, len(_DIE_PROGRESSION) - 1)]
        return f"{n}{next_die}"
    except ValueError:
        return die_expr


def scale_enemy_stats(base: dict, hero_level: int, is_boss: bool = False) -> dict:
    """Apply level multiplier to enemy stats. Boss is one tier above."""
    mult = _level_multiplier(hero_level)
    if is_boss:
        # Boss: one tier higher
        tiers = [t[1] for t in _SCALE_TABLE]
        idx = tiers.index(mult) if mult in tiers else 0
        mult = tiers[min(idx + 1, len(tiers) - 1)]

    scaled = dict(base)
    scaled["hp_base"] = max(1, round(int(base.get("hp_base", 5)) * mult))
    scaled["ac_base"] = max(5, round(int(base.get("ac_base", 8)) * (1 + (mult - 1) * 0.3)))

    if mult >= 1.5:
        # Scale die up once
        scaled["damage_die"] = _scale_die_up(str(base.get("damage_die", "1d6")))
    return scaled


# ── Dungeon instance generation ───────────────────────────────────────────────

def generate_dungeon_instance(dungeon_key: str, hero_level: int) -> dict:
    """
    Generate a fresh dungeon run instance for session_flags.dungeon_run.
    Scales enemies to hero_level. Returns the dungeon_run dict.
    """
    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        raise ValueError(f"Dungeon not found: {dungeon_key}")

    pool = json.loads(dungeon.get("enemy_pool") or "[]")
    num_rooms = int(dungeon.get("rooms") or 5)
    boss_key = dungeon.get("boss_enemy") or (pool[-1] if pool else None)
    atmosphere = dungeon.get("atmosphere") or ""
    cooldown_hours = int(dungeon.get("cooldown_hours") or 72)

    # Fetch enemy base stats for scaling
    conn = _get_db()
    try:
        enemy_cache: dict[str, dict] = {}
        all_keys = list(set(pool + ([boss_key] if boss_key else [])))
        for ek in all_keys:
            row = conn.execute(
                "SELECT key, label, hp_base, ac_base, attack_bonus, damage_die, "
                "damage_bonus, dex_modifier, tier FROM game_config_enemies WHERE key = ?",
                (ek,),
            ).fetchone()
            if row:
                enemy_cache[ek] = dict(row)
    finally:
        conn.close()

    # Build rooms
    rooms = []
    for room_num in range(1, num_rooms + 1):
        is_boss = (room_num == num_rooms)
        if is_boss and boss_key:
            enemy_key = boss_key
        else:
            enemy_key = random.choice(pool) if pool else None

        # Enemy count: 1 + floor(level / 3), min 1, max 4
        enemy_count = min(4, max(1, 1 + hero_level // 3))
        if is_boss:
            enemy_count = 1  # Boss always alone

        base_stats = enemy_cache.get(enemy_key, {}) if enemy_key else {}
        scaled = scale_enemy_stats(base_stats, hero_level, is_boss) if base_stats else base_stats

        rooms.append({
            "room_id": room_num,
            "enemy_key": enemy_key,
            "enemy_count": enemy_count,
            "is_boss": is_boss,
            "cleared": False,
            "enemy_stats": scaled,
        })

    return {
        "dungeon_key": dungeon_key,
        "dungeon_label": dungeon.get("label", dungeon_key),
        "atmosphere": atmosphere,
        "rooms": rooms,
        "total_rooms": num_rooms,
        "current_room": 1,
        "completed": False,
        "hero_level_at_entry": hero_level,
        "cooldown_hours": cooldown_hours,
    }


def enter_dungeon(
    campaign_id: int,
    character_id: int,
    dungeon_key: str,
    hero_level: int,
) -> dict:
    """
    Enter a dungeon: check cooldown, generate instance, store in session_flags.
    Returns the dungeon_run instance.
    """
    # Check cooldown
    cd = check_cooldown(character_id, dungeon_key)
    if cd.get("on_cooldown"):
        raise PermissionError(
            f"dungeon_on_cooldown:{cd.get('cooldown_until')}:{cd.get('hours_remaining')}"
        )

    instance = generate_dungeon_instance(dungeon_key, hero_level)

    # Store in session_flags
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        flags = json.loads((row["session_flags"] if row else None) or "{}")
        flags["dungeon_run"] = instance
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (json.dumps(flags, ensure_ascii=False), campaign_id),
        )
        conn.commit()
    finally:
        conn.close()

    return instance


def advance_room(campaign_id: int) -> dict:
    """
    Mark current room cleared and move to next room.
    If last room cleared: mark dungeon completed.
    Returns updated dungeon_run.
    """
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("No active game session")
        flags = json.loads(row["session_flags"] or "{}")
        run = flags.get("dungeon_run")
        if not run:
            raise ValueError("No active dungeon run in session")

        current = int(run.get("current_room", 1))
        total = int(run.get("total_rooms", 1))

        # Mark current room cleared
        for r in run["rooms"]:
            if r["room_id"] == current:
                r["cleared"] = True
                break

        if current >= total:
            run["completed"] = True
            run["current_room"] = current
        else:
            run["current_room"] = current + 1

        flags["dungeon_run"] = run
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (json.dumps(flags, ensure_ascii=False), campaign_id),
        )
        conn.commit()
        return run
    finally:
        conn.close()


def get_active_dungeon_run(campaign_id: int) -> dict | None:
    """Return current dungeon_run from session_flags, or None."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not row:
            return None
        flags = json.loads(row["session_flags"] or "{}")
        return flags.get("dungeon_run")
    finally:
        conn.close()


def get_current_room(dungeon_run: dict) -> dict | None:
    """Return the current room dict from a dungeon_run instance."""
    current = int(dungeon_run.get("current_room", 1))
    for r in dungeon_run.get("rooms", []):
        if r["room_id"] == current:
            return r
    return None
