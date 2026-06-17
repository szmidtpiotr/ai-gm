"""Dungeon run service — L9: tile-only system (procedural generator removed)."""
from __future__ import annotations
import json
import math
import random
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone

DB_PATH = "/data/ai_gm.db"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_cooldown_hours(dungeon: dict) -> int:
    """Resolve a dungeon's cooldown in hours, honoring an explicit 0 (= no cooldown).

    `int(x or 72)` is wrong here: 0 is falsy, so an admin who sets cooldown=0
    would silently get the 72h default. Only None/'' (unset) fall back to 72.
    """
    raw = dungeon.get("cooldown_hours")
    if raw is None or raw == "":
        return 72
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 72


def _normalize_answer(s: str) -> str:
    """Lowercase + strip diacritics for fuzzy comparison."""
    nfkd = unicodedata.normalize("NFKD", s.lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if ca == cb else 1)))
        prev = curr
    return prev[-1]


def _answer_matches(player: str, answer: str, alts: list[str]) -> bool:
    pn = _normalize_answer(player)
    candidates = [_normalize_answer(answer)] + [_normalize_answer(a) for a in alts]
    for cand in candidates:
        if not cand:
            continue
        if pn == cand:
            return True
        # Allow up to 20% edit distance relative to candidate length
        max_dist = max(1, round(len(cand) * 0.2))
        if _levenshtein(pn, cand) <= max_dist:
            return True
    return False


def _get_meta(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM game_config_meta WHERE key = ?", (key,)).fetchone()
    return str(row["value"] if row else default)


# ── Dungeon CRUD ──────────────────────────────────────────────────────────────

def get_dungeon(dungeon_key: str) -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM game_dungeons WHERE key = ? AND is_active = 1", (dungeon_key,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_dungeons(character_id: int | None = None) -> list[dict]:
    conn = _get_db()
    try:
        rows = conn.execute("SELECT * FROM game_dungeons WHERE is_active = 1 ORDER BY min_level, key").fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d["enemy_pool"] = json.loads(d.get("enemy_pool") or "[]")
            except Exception:
                d["enemy_pool"] = []
            d["cooldown"] = check_cooldown(character_id, d["key"]) if character_id else {"on_cooldown": False}
            result.append(d)
        return result
    finally:
        conn.close()


def check_cooldown(character_id: int, dungeon_key: str) -> dict:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT cooldown_until, run_count FROM character_dungeon_runs WHERE character_id = ? AND location_key = ?",
            (character_id, dungeon_key),
        ).fetchone()
        if not row:
            return {"on_cooldown": False, "run_count": 0}
        run_count = int(row["run_count"] or 0)
        # Honor the LIVE cooldown setting: if admin set cooldown_hours=0, the
        # dungeon has no cooldown — clear any stale cooldown_until snapshot that
        # was written by an earlier run under a non-zero setting.
        _dungeon = get_dungeon(dungeon_key)
        if _dungeon is not None and _resolve_cooldown_hours(_dungeon) == 0:
            return {"on_cooldown": False, "run_count": run_count}
        cooldown_until_str = str(row["cooldown_until"] or "")
        try:
            cooldown_until = datetime.fromisoformat(cooldown_until_str.replace("Z", "+00:00"))
            if cooldown_until.tzinfo is None:
                cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
        except Exception:
            return {"on_cooldown": False, "run_count": run_count}
        now = _now_utc()
        if now >= cooldown_until:
            return {"on_cooldown": False, "run_count": run_count, "cooldown_until": cooldown_until_str}
        remaining = cooldown_until - now
        return {
            "on_cooldown": True,
            "cooldown_until": cooldown_until_str,
            "hours_remaining": round(remaining.total_seconds() / 3600, 1),
            "run_count": run_count,
        }
    finally:
        conn.close()


def complete_dungeon(character_id: int, dungeon_key: str) -> dict:
    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        raise ValueError(f"Dungeon not found: {dungeon_key}")
    cooldown_hours = _resolve_cooldown_hours(dungeon)
    now = _now_utc()
    cooldown_until = now + timedelta(hours=cooldown_hours)
    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO character_dungeon_runs (character_id, location_key, cleared_at, cooldown_until, run_count)
               VALUES (?, ?, ?, ?, 1)
               ON CONFLICT(character_id, location_key) DO UPDATE SET
                   cleared_at=excluded.cleared_at, cooldown_until=excluded.cooldown_until, run_count=run_count+1""",
            (character_id, dungeon_key, now.isoformat(), cooldown_until.isoformat()),
        )
        conn.commit()
        return {"dungeon_key": dungeon_key, "cleared_at": now.isoformat(),
                "cooldown_until": cooldown_until.isoformat(), "cooldown_hours": cooldown_hours}
    finally:
        conn.close()


def get_run_history(character_id: int) -> list[dict]:
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM character_dungeon_runs WHERE character_id = ? ORDER BY cleared_at DESC", (character_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Loot helpers ──────────────────────────────────────────────────────────────

def _roll_loot_table(conn: sqlite3.Connection, table_key: str) -> list[dict]:
    """Roll items from a named loot table. Returns [{item_key/weapon_key/consumable_key, quantity}]."""
    if not table_key:
        return []
    rows = conn.execute(
        """SELECT e.item_key, e.consumable_key, e.weapon_key, e.weight, e.qty_min, e.qty_max
           FROM game_config_loot_entries e
           JOIN game_config_loot_tables t ON t.key = e.loot_table_key
           WHERE e.loot_table_key = ? AND t.is_active = 1""",
        (table_key,)
    ).fetchall()
    rolled = []
    for r in rows:
        chance = max(1, min(100, int(r["weight"] or 10))) / 100.0
        if random.random() < chance:
            qty = random.randint(max(1, int(r["qty_min"] or 1)), max(1, int(r["qty_max"] or 1)))
            rolled.append({
                "item_key": r["item_key"],
                "consumable_key": r["consumable_key"],
                "weapon_key": r["weapon_key"],
                "quantity": qty,
            })
    return rolled


# ── Rarity tier system (E17) ──────────────────────────────────────────────────

RARITY_TIERS: dict[str, dict] = {
    "common":    {"label": "Zwykły",    "color": "#9ca3af"},  # gray
    "uncommon":  {"label": "Ulepszony", "color": "#4ade80"},  # green
    "rare":      {"label": "Rzadki",    "color": "#60a5fa"},  # blue
    "epic":      {"label": "Epicki",    "color": "#c084fc"},  # purple
    "legendary": {"label": "Legendarny","color": "#fbbf24"},  # gold
}

# D1-D4 normal rooms → random pick between two adjacent tiers
# D5 / boss → always epic or legendary
_DIFFICULTY_TO_RANGE: dict[int, tuple[str, str]] = {
    1: ("common",   "uncommon"),
    2: ("uncommon", "rare"),
    3: ("rare",     "epic"),
    4: ("epic",     "legendary"),
    5: ("epic",     "legendary"),
}


def get_loot_rarity_for_difficulty(difficulty: int, is_boss: bool = False) -> str:
    """Return a rarity tier key for the given dungeon difficulty (1-5).

    Boss rooms always get epic/legendary regardless of dungeon difficulty.
    """
    if is_boss:
        lo, hi = "epic", "legendary"
    else:
        clamped = max(1, min(5, difficulty))
        lo, hi = _DIFFICULTY_TO_RANGE.get(clamped, ("common", "uncommon"))
    return random.choice([lo, hi])


# ── Session management ────────────────────────────────────────────────────────

def _load_flags(campaign_id: int) -> tuple[sqlite3.Connection, dict]:
    conn = _get_db()
    row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1", (campaign_id,)).fetchone()
    flags = json.loads((row["session_flags"] if row else None) or "{}")
    return conn, flags


def _save_flags(conn: sqlite3.Connection, campaign_id: int, flags: dict) -> None:
    conn.execute("UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                 (json.dumps(flags, ensure_ascii=False), campaign_id))
    conn.commit()


def get_active_dungeon_run(campaign_id: int) -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute("SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1", (campaign_id,)).fetchone()
        if not row:
            return None
        return json.loads(row["session_flags"] or "{}").get("dungeon_run")
    finally:
        conn.close()


def get_current_room(dungeon_run: dict) -> dict | None:
    current = int(dungeon_run.get("current_room", 1))
    for r in dungeon_run.get("rooms", []):
        if r["room_id"] == current:
            return r
    return None


def clear_dungeon_run(campaign_id: int) -> None:
    """Remove dungeon_run from session_flags after completion/failure."""
    conn, flags = _load_flags(campaign_id)
    try:
        flags.pop("dungeon_run", None)
        _save_flags(conn, campaign_id, flags)
    finally:
        conn.close()


def grant_dungeon_loot(
    character_id: int,
    campaign_id: int,
    loot_items: list[dict],
    loot_tier: str | None = None,
) -> list[dict]:
    """Grant loot items to character inventory. F2 (#462): passes loot_tier for affix rolling."""
    if not loot_items:
        return []
    try:
        from app.services.loot_service import grant_loot_to_character
        return grant_loot_to_character(character_id, loot_items, source="dungeon", loot_tier=loot_tier)
    except Exception:
        return []


def roll_boss_loot(dungeon_key: str) -> list[dict]:
    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        return []
    boss_table = dungeon.get("boss_loot_table_key") or ""
    if not boss_table:
        return []
    conn = _get_db()
    try:
        return _roll_loot_table(conn, boss_table)
    finally:
        conn.close()


# L8: Endless rarity progression
_RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]


def get_boss_loot_rarity_for_cycle(dungeon_tier: int, cycle: int) -> str:
    """L8: Boss loot rarity with endless cycle bonus (Numbers Policy).

    Base: get_loot_rarity_for_difficulty(tier, is_boss=True) → epic/legendary.
    Bonus: +1 rarity tier per 2 cycles (cap: legendary).
    Cycles 1-2 = base, cycles 3-4 = +1, cycles 5-6 = +2, ...
    """
    base = get_loot_rarity_for_difficulty(dungeon_tier, is_boss=True)
    bump = (cycle - 1) // 2
    if bump > 0 and base in _RARITY_ORDER:
        idx = _RARITY_ORDER.index(base)
        base = _RARITY_ORDER[min(idx + bump, len(_RARITY_ORDER) - 1)]
    return base


def roll_boss_loot_for_endless(dungeon_key: str, cycle: int = 1) -> tuple[list[dict], str]:
    """L8: Roll boss loot with endless cycle rarity bonus.

    Returns (loot_items, rarity_tier_str).
    """
    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        return [], "epic"
    boss_table = dungeon.get("boss_loot_table_key") or ""
    dungeon_tier = int(dungeon.get("dungeon_difficulty") or 1)
    rarity = get_boss_loot_rarity_for_cycle(dungeon_tier, cycle)
    if not boss_table:
        return [], rarity
    conn = _get_db()
    try:
        return _roll_loot_table(conn, boss_table), rarity
    finally:
        conn.close()


def roll_room_ambient_loot(dungeon_key: str, loot_chance: float) -> list[dict]:
    """Post-combat room search — small chance of ambient item find."""
    if random.random() > loot_chance:
        return []
    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        return []
    # Use chest table for ambient too, or a random common item
    chest_table = dungeon.get("chest_loot_table_key") or ""
    if not chest_table:
        return []
    conn = _get_db()
    try:
        loot = _roll_loot_table(conn, chest_table)
        # Ambient find: at most 1 item
        return loot[:1]
    finally:
        conn.close()


# ── L7: Checkpoint restore + cooldown helpers ─────────────────────────────────

def restore_dungeon_checkpoint(campaign_id: int, character_id: int) -> bool:
    """L7: Restore HP/mana/gold/XP/inventory from latest checkpoint snapshot.

    Checks dungeon_boss_checkpoint first (most recent), falls back to dungeon_enter.
    XP is rolled back to checkpoint value; level is recalculated.
    """
    conn = _get_db()
    try:
        row = conn.execute(
            """SELECT snapshot_json FROM world_state_snapshots
               WHERE campaign_id = ? AND snapshot_source IN ('dungeon_enter', 'dungeon_boss_checkpoint')
               ORDER BY id DESC LIMIT 1""",
            (campaign_id,),
        ).fetchone()
        if not row:
            return False
        snap = json.loads(row["snapshot_json"] or "{}")

        char = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        if not char:
            return False
        sheet = json.loads(char["sheet_json"] or "{}")

        if snap.get("current_hp") is not None:
            sheet["current_hp"] = snap["current_hp"]
        if snap.get("max_hp") is not None:
            sheet["max_hp"] = snap["max_hp"]
        if snap.get("current_mana") is not None:
            sheet["current_mana"] = snap["current_mana"]

        if snap.get("xp_lifetime_earned") is not None:
            from app.services.xp_service import get_xp_level_thresholds, level_from_xp
            checkpoint_xp = int(snap["xp_lifetime_earned"])
            sheet["xp_lifetime_earned"] = checkpoint_xp
            if snap.get("xp_available") is not None:
                sheet["xp_available"] = int(snap["xp_available"])
            thresholds = get_xp_level_thresholds(conn)
            sheet["level"] = max(1, level_from_xp(checkpoint_xp, thresholds))

        conn.execute(
            "UPDATE characters SET sheet_json = ?, gold = ?, gold_gp = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), snap.get("gold", 0), snap.get("gold_gp", 0), character_id),
        )

        inventory = snap.get("inventory") or []
        conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (character_id,))
        for item in inventory:
            conn.execute(
                """INSERT INTO character_inventory
                       (character_id, item_key, weapon_key, consumable_key, quantity, equipped)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (character_id, item.get("item_key"), item.get("weapon_key"),
                 item.get("consumable_key"), item.get("quantity", 1), item.get("equipped", 0)),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def start_dungeon_cooldown(character_id: int, dungeon_key: str, fraction: float = 1.0) -> dict:
    """L7: Set cooldown on character_dungeon_runs. fraction=0.5 = 50% (ceil hours)."""
    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        return {}
    cooldown_hours = _resolve_cooldown_hours(dungeon)
    partial_hours = 0 if cooldown_hours <= 0 else max(1, math.ceil(cooldown_hours * fraction))
    now = _now_utc()
    cooldown_until = now + timedelta(hours=partial_hours)
    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO character_dungeon_runs
                   (character_id, location_key, cleared_at, cooldown_until, run_count)
               VALUES (?, ?, ?, ?, 1)
               ON CONFLICT(character_id, location_key) DO UPDATE SET
                   cleared_at=excluded.cleared_at,
                   cooldown_until=excluded.cooldown_until,
                   run_count=run_count+1""",
            (character_id, dungeon_key, now.isoformat(), cooldown_until.isoformat()),
        )
        conn.commit()
        return {"cooldown_until": cooldown_until.isoformat(), "cooldown_hours": partial_hours}
    finally:
        conn.close()


def handle_dungeon_death(campaign_id: int, character_id: int) -> dict:
    """L7: Hero died in dungeon. Mark run failed, restore from last checkpoint, start cooldown.

    OVERRIDES E16: does NOT restart from tile 1.
    """
    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run")
        if not run:
            return {"ok": True, "restored": False, "failed": False}
        dungeon_key = run.get("dungeon_key", "")
        run["failed"] = True
        run["completed"] = False
        flags["dungeon_run"] = run
        _save_flags(conn, campaign_id, flags)
    finally:
        conn.close()

    restored = restore_dungeon_checkpoint(campaign_id, character_id)
    cooldown_info = start_dungeon_cooldown(character_id, dungeon_key, fraction=1.0)

    return {
        "ok": True,
        "dungeon_key": dungeon_key,
        "restored": restored,
        "failed": True,
        "cooldown_until": cooldown_info.get("cooldown_until"),
    }


def handle_dungeon_abandon(campaign_id: int, character_id: int) -> dict:
    """L7: Abandon dungeon run.

    Mid-segment (at_checkpoint=False): restore from last checkpoint + 50% cooldown.
    At checkpoint (boss defeated, at_checkpoint=True): full reward + 100% cooldown.
    """
    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run")
        if not run:
            return {"ok": True, "at_checkpoint": False, "restored": False}
        dungeon_key = run.get("dungeon_key", "")
        at_checkpoint = bool(run.get("at_checkpoint", False))

        if at_checkpoint:
            run["completed"] = True
            run["failed"] = False
        else:
            run["failed"] = True
            run["completed"] = False

        flags["dungeon_run"] = run
        _save_flags(conn, campaign_id, flags)
    finally:
        conn.close()

    if at_checkpoint:
        cooldown_info = start_dungeon_cooldown(character_id, dungeon_key, fraction=1.0)
        return {
            "ok": True,
            "at_checkpoint": True,
            "restored": False,
            "cooldown_until": cooldown_info.get("cooldown_until"),
        }

    restored = restore_dungeon_checkpoint(campaign_id, character_id)
    cooldown_info = start_dungeon_cooldown(character_id, dungeon_key, fraction=0.5)
    return {
        "ok": True,
        "at_checkpoint": False,
        "restored": restored,
        "cooldown_until": cooldown_info.get("cooldown_until"),
    }
