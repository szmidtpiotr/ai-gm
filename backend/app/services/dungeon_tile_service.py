"""Dungeon Tile Card System (issue #224) — tile-based dungeon generation.

Replaces the legacy procedural room-type generation with pre-authored visual tiles
that connect via N/S/E/W door matching, modeled after Betrayal at House on the Hill.

Path generation:
    - Tiles in a category are drawn into a sequence
    - Each consecutive pair must have matching doors (exit of A → entry of B = opposite direction)
    - Last tile is the boss
    - Spatial coordinates tracked; collisions retried

Active during runtime:
    - Per-tile active_states apply each turn (burning, flooding, etc.) via effect_json
    - exit_conditions gate which doors can be used (enemies_cleared, riddle_solved, etc.)

Selected by DUNGEON_SYSTEM env var (see dungeon_service.py router).
"""
from __future__ import annotations

import json
import random
import sqlite3
from typing import Any

from app.services.dungeon_service import (
    DB_PATH,
    _get_db,
    _load_flags,
    _save_flags,
    check_cooldown,
    complete_dungeon,
    get_dungeon,
    scale_enemy_stats,
)

# ── Spatial constants ─────────────────────────────────────────────────────────

DIRECTIONS = ("N", "S", "E", "W")
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
OFFSET = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}


# ── Tile draw ─────────────────────────────────────────────────────────────────

def _load_tiles(conn: sqlite3.Connection, category_key: str, include_boss: bool = False) -> list[dict]:
    sql = (
        "SELECT * FROM dungeon_tiles "
        "WHERE category_key = ? AND is_active = 1 AND is_boss_tile = ?"
    )
    rows = conn.execute(sql, (category_key, 1 if include_boss else 0)).fetchall()
    return [dict(r) for r in rows]


def _doors(tile: dict) -> list[str]:
    try:
        d = json.loads(tile.get("doors_json") or "[]")
        return [x for x in d if x in DIRECTIONS]
    except Exception:
        return []


def _try_build_path(
    tiles: list[dict],
    boss_pool: list[dict],
    tile_count: int,
    boss_tile_id: int | None,
) -> list[dict] | None:
    """Try to build a connected path. Returns None on dead-end / collision failure."""
    if not tiles:
        return None
    if tile_count < 2:
        return None

    # Pick entry tile (must have at least 1 door)
    entry_candidates = [t for t in tiles if _doors(t)]
    if not entry_candidates:
        return None
    first = random.choice(entry_candidates)

    sequence: list[dict] = [{
        "tile_id": first["id"],
        "entry_door": None,
        "exit_door": None,
        "position": (0, 0),
        "index": 0,
    }]
    used_positions = {(0, 0)}

    # Pool to draw next tiles from (excluding first)
    pool = [t for t in tiles if t["id"] != first["id"]]
    random.shuffle(pool)
    by_id = {t["id"]: t for t in tiles}
    current = first
    position = (0, 0)

    middle_count = tile_count - 2  # excluding first and boss
    for step in range(1, middle_count + 1):
        cdoors = _doors(current)
        last_entry = sequence[-1]["entry_door"]
        available_exits = [d for d in cdoors if d != last_entry]
        random.shuffle(available_exits)

        progressed = False
        for exit_dir in available_exits:
            dx, dy = OFFSET[exit_dir]
            next_pos = (position[0] + dx, position[1] + dy)
            if next_pos in used_positions:
                continue
            opp = OPPOSITE[exit_dir]
            # Find a pool tile with the required entry door
            for candidate in list(pool):
                if opp in _doors(candidate):
                    pool.remove(candidate)
                    sequence[-1]["exit_door"] = exit_dir
                    sequence.append({
                        "tile_id": candidate["id"],
                        "entry_door": opp,
                        "exit_door": None,
                        "position": next_pos,
                        "index": step,
                    })
                    used_positions.add(next_pos)
                    current = candidate
                    position = next_pos
                    progressed = True
                    break
            if progressed:
                break
        if not progressed:
            return None  # dead end

    # Final tile: boss. Must connect via a remaining exit of current
    cdoors = _doors(current)
    last_entry = sequence[-1]["entry_door"]
    available_exits = [d for d in cdoors if d != last_entry]
    random.shuffle(available_exits)

    # Determine boss candidate set
    if boss_tile_id:
        boss_candidates = [t for t in boss_pool if t["id"] == boss_tile_id]
        if not boss_candidates:
            # Boss tile not found in this category — fail this attempt
            return None
    else:
        boss_candidates = list(boss_pool)
        random.shuffle(boss_candidates)

    for exit_dir in available_exits:
        opp = OPPOSITE[exit_dir]
        dx, dy = OFFSET[exit_dir]
        next_pos = (position[0] + dx, position[1] + dy)
        if next_pos in used_positions:
            continue
        for boss in boss_candidates:
            if opp in _doors(boss):
                sequence[-1]["exit_door"] = exit_dir
                sequence.append({
                    "tile_id": boss["id"],
                    "entry_door": opp,
                    "exit_door": None,
                    "position": next_pos,
                    "index": middle_count + 1,
                    "is_boss": True,
                })
                return sequence

    return None


def draw_tile_sequence(
    category_key: str,
    tile_count: int,
    boss_tile_id: int | None = None,
    max_retries: int = 25,
) -> list[dict]:
    """Generate a connected path of `tile_count` tiles (including boss) in `category_key`.

    Raises ValueError if no valid sequence can be built (insufficient tile pool
    or all retries collide). Caller may catch and surface a friendly admin error.
    """
    conn = _get_db()
    try:
        non_boss = _load_tiles(conn, category_key, include_boss=False)
        boss_pool = _load_tiles(conn, category_key, include_boss=True)
        if not boss_pool:
            # Fallback: allow boss to be drawn from non-boss pool
            boss_pool = non_boss
        available = len(non_boss) + len(boss_pool)
        if available < 2:
            raise ValueError(
                f"Category '{category_key}' has fewer than 2 tiles — cannot build dungeon"
            )
        # Cap requested count to what's actually in the DB
        tile_count = min(tile_count, available)
    finally:
        conn.close()

    for _ in range(max_retries):
        seq = _try_build_path(non_boss, boss_pool, tile_count, boss_tile_id)
        if seq:
            return seq
    raise ValueError(
        f"Could not build valid dungeon path in '{category_key}' after {max_retries} retries — "
        f"pool may be too small or door distribution unbalanced"
    )


# ── Tile content resolution ───────────────────────────────────────────────────

_ITEM_TABLES = {
    "item_key": "game_config_items",
    "weapon_key": "game_config_weapons",
    "consumable_key": "game_config_consumables",
}


def resolve_tile_content(tile_id: int, hero_level: int) -> dict | None:
    """Join a tile row with referenced enemies, items, riddle. Scaling applied."""
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM dungeon_tiles WHERE id = ?", (tile_id,)).fetchone()
        if not row:
            return None
        tile = dict(row)

        doors = _doors(tile)
        try:
            enemies = json.loads(tile.get("enemies_json") or "[]")
        except Exception:
            enemies = []
        try:
            items = json.loads(tile.get("items_json") or "[]")
        except Exception:
            items = []
        try:
            active_states = json.loads(tile.get("active_states_json") or "[]")
        except Exception:
            active_states = []
        try:
            exit_conditions = json.loads(tile.get("exit_conditions_json") or "[]")
        except Exception:
            exit_conditions = []

        is_boss = bool(tile.get("is_boss_tile") or 0)

        resolved_enemies: list[dict] = []
        for entry in enemies:
            enemy_key = entry.get("enemy_key")
            count = int(entry.get("count") or 1)
            if not enemy_key:
                continue
            r = conn.execute(
                "SELECT key, label, hp_base, ac_base, attack_bonus, damage_die, damage_bonus, "
                "dex_modifier, tier FROM game_config_enemies WHERE key = ?",
                (enemy_key,),
            ).fetchone()
            if not r:
                continue
            base = dict(r)
            scaled = scale_enemy_stats(base, hero_level, is_boss=is_boss)
            resolved_enemies.append({
                "enemy_key": enemy_key,
                "label": base.get("label", enemy_key),
                "count": count,
                "stats": scaled,
            })

        resolved_items: list[dict] = []
        for entry in items:
            for k, table in _ITEM_TABLES.items():
                key = entry.get(k)
                if not key:
                    continue
                r = conn.execute(f"SELECT key, label FROM {table} WHERE key = ?", (key,)).fetchone()
                if r:
                    rd = dict(r)
                    resolved_items.append({
                        "type": k.replace("_key", ""),
                        "key": key,
                        "label": rd.get("label", key),
                        "chance": float(entry.get("chance", 1.0)),
                    })
                break

        riddle = None
        if tile.get("riddle_key"):
            r = conn.execute(
                "SELECT * FROM game_config_riddles WHERE key = ? AND is_active = 1",
                (tile["riddle_key"],),
            ).fetchone()
            if r:
                rd = dict(r)
                try:
                    answer_alts = json.loads(rd.get("answer_alts") or "[]")
                except Exception:
                    answer_alts = []
                try:
                    hints = json.loads(rd.get("hints") or "[]")
                except Exception:
                    hints = []
                riddle = {
                    "key": rd["key"],
                    "text": rd["text"],
                    "answer": rd["answer"],
                    "answer_alts": answer_alts,
                    "hints": hints,
                    "hints_used": 0,
                }

        return {
            "tile_id": tile["id"],
            "label": tile["label"],
            "image_url": tile.get("image_url"),
            "doors": doors,
            "room_description": tile.get("room_description") or "",
            "enemies": resolved_enemies,
            "items": resolved_items,
            "active_states": active_states,
            "riddle": riddle,
            "exit_conditions": exit_conditions,
            "is_boss_tile": is_boss,
        }
    finally:
        conn.close()


# ── Dungeon run orchestration (tile mode) ─────────────────────────────────────

def _tile_count_for_difficulty(dungeon: dict, hero_level: int) -> int:
    """Resolve tile count (non-boss tiles + 1 boss = total).

    Priority: dungeon.tile_count (explicit admin choice) → dungeon.rooms fallback.
    difficulty_config_json is ignored — tile count is an authoring decision, not a
    computed difficulty variable.
    """
    if dungeon.get("tile_count"):
        return int(dungeon["tile_count"])
    return int(dungeon.get("rooms") or 4)


def enter_dungeon_tiles(
    campaign_id: int,
    character_id: int,
    dungeon_key: str,
    hero_level: int,
    previous_campaign_id: int | None = None,
) -> dict:
    cd = check_cooldown(character_id, dungeon_key)
    if cd.get("on_cooldown"):
        raise PermissionError(
            f"dungeon_on_cooldown|{cd.get('cooldown_until')}|{cd.get('hours_remaining')}"
        )

    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        raise ValueError(f"Dungeon not found: {dungeon_key}")

    category_key = dungeon.get("tile_category_key")
    if not category_key:
        raise ValueError(
            f"Dungeon '{dungeon_key}' is not configured for the tile system "
            f"(tile_category_key is NULL). Set it in the admin panel or use legacy mode."
        )

    tile_count = _tile_count_for_difficulty(dungeon, hero_level)
    boss_tile_id = dungeon.get("boss_tile_id")

    sequence = draw_tile_sequence(category_key, tile_count, boss_tile_id)

    # Resolve every tile's content (snapshot at entry time)
    resolved_tiles: list[dict] = []
    for step in sequence:
        content = resolve_tile_content(step["tile_id"], hero_level)
        if not content:
            continue
        content.update({
            "step_index": step["index"],
            "entry_door": step["entry_door"],
            "exit_door": step.get("exit_door"),
            "position": list(step["position"]),
            "cleared": False,
            "states_applied_turns": 0,
        })
        resolved_tiles.append(content)

    run = {
        "system": "tiles",
        "dungeon_key": dungeon_key,
        "dungeon_label": dungeon.get("label", dungeon_key),
        "category_key": category_key,
        "tiles": resolved_tiles,
        "total_tiles": len(resolved_tiles),
        "current_index": 0,
        "discovered_positions": [list(resolved_tiles[0]["position"])] if resolved_tiles else [],
        "completed": False,
        "failed": False,
        "hero_level_at_entry": hero_level,
        "cooldown_hours": int(dungeon.get("cooldown_hours") or 72),
        "loot_collected": [],
    }

    conn, flags = _load_flags(campaign_id)
    try:
        flags["dungeon_run"] = run
        if previous_campaign_id:
            flags["dungeon_previous_campaign_id"] = previous_campaign_id
        _save_flags(conn, campaign_id, flags)
    finally:
        conn.close()

    return run


def get_current_tile(run: dict) -> dict | None:
    idx = int(run.get("current_index", 0))
    tiles = run.get("tiles") or []
    if 0 <= idx < len(tiles):
        return tiles[idx]
    return None


def check_exit_conditions(tile: dict, character_id: int) -> tuple[bool, str | None]:
    """Return (allowed, reason_if_blocked). Conditions are AND-ed."""
    conds = tile.get("exit_conditions") or []
    for c in conds:
        ctype = c.get("type")
        if ctype == "enemies_cleared":
            enemies = tile.get("enemies") or []
            if enemies and not tile.get("cleared"):
                return False, "Pokonaj wszystkich wrogów w tym pomieszczeniu."
        elif ctype == "riddle_solved":
            riddle = tile.get("riddle") or {}
            if riddle and not riddle.get("solved"):
                return False, "Rozwiąż zagadkę aby kontynuować."
        elif ctype == "item_in_inventory":
            required = c.get("item_key")
            if required:
                conn = _get_db()
                try:
                    row = conn.execute(
                        "SELECT 1 FROM character_inventory WHERE character_id = ? "
                        "AND item_key = ? LIMIT 1",
                        (character_id, required),
                    ).fetchone()
                    if not row:
                        return False, f"Potrzebujesz przedmiotu: {required}"
                finally:
                    conn.close()
        elif ctype == "stat_roll":
            # The roll itself is resolved client-side / by combat router;
            # exit_conditions only blocks the door until the roll is logged.
            if not tile.get(f"stat_roll_passed_{c.get('stat')}", False):
                return False, f"Wykonaj rzut {c.get('stat')} DC {c.get('dc')}"
        else:
            # Unknown condition type — block by default (admin error)
            return False, f"Nieznany warunek wyjścia: {ctype}"
    return True, None


def advance_room_tiles(campaign_id: int, character_id: int, door_chosen: str | None) -> dict:
    """Validate door choice, check exit_conditions, advance to next tile."""
    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run")
        if not run or run.get("system") != "tiles":
            raise ValueError("No active tile-based dungeon run")

        current = get_current_tile(run)
        if not current:
            raise ValueError("Current tile not found")

        # Validate door choice
        if door_chosen:
            if door_chosen not in DIRECTIONS:
                raise ValueError(f"Invalid door direction: {door_chosen}")
            if door_chosen not in current.get("doors", []):
                raise ValueError(f"Tile has no door in direction: {door_chosen}")
            entry = current.get("entry_door")
            if entry and door_chosen == entry:
                raise ValueError("Cannot exit through entry door")

        # Validate exit conditions
        allowed, reason = check_exit_conditions(current, character_id)
        if not allowed:
            return {"ok": False, "blocked": True, "reason": reason}

        current["cleared"] = True
        if door_chosen:
            current["exit_door_used"] = door_chosen

        # Advance
        new_idx = int(run.get("current_index", 0)) + 1
        total = int(run.get("total_tiles", 1))
        if new_idx >= total:
            run["completed"] = True
            flags["dungeon_run"] = run
            _save_flags(conn, campaign_id, flags)
            return {"ok": True, "completed": True, "run": run}

        run["current_index"] = new_idx
        # Discover new position
        next_tile = run["tiles"][new_idx]
        positions = run.get("discovered_positions") or []
        if next_tile["position"] not in positions:
            positions.append(next_tile["position"])
        run["discovered_positions"] = positions

        flags["dungeon_run"] = run
        _save_flags(conn, campaign_id, flags)
        return {"ok": True, "completed": False, "run": run, "current_tile": next_tile}
    finally:
        conn.close()


def apply_active_states_turn(campaign_id: int, character_id: int) -> list[dict]:
    """Apply per-tile active_states damage/effects each player turn.

    Returns list of effect results: [{state, damage_rolled, save_passed}]
    """
    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run")
        if not run or run.get("system") != "tiles":
            return []

        current = get_current_tile(run)
        if not current or current.get("cleared"):
            return []

        states = current.get("active_states") or []
        if not states:
            return []

        results: list[dict] = []
        for state in states:
            stype = state.get("type")
            dmg_die = state.get("damage_die") or state.get("damage") or ""
            save_stat = state.get("save_stat")
            dc = int(state.get("dc") or 0)

            damage_rolled = 0
            if dmg_die:
                # Simple die parse: NdM (+K)
                import re
                m = re.match(r"(\d*)d(\d+)(?:\s*\+\s*(\d+))?", str(dmg_die).strip().lower())
                if m:
                    n = int(m.group(1) or 1)
                    sides = int(m.group(2))
                    bonus = int(m.group(3) or 0)
                    damage_rolled = sum(random.randint(1, sides) for _ in range(n)) + bonus

            save_passed = False
            if save_stat and dc:
                # 50/50 placeholder — actual roll happens via combat router elsewhere
                save_passed = random.random() < 0.5
                if save_passed:
                    damage_rolled = damage_rolled // 2

            results.append({
                "state_type": stype,
                "damage_rolled": damage_rolled,
                "save_stat": save_stat,
                "dc": dc,
                "save_passed": save_passed,
                "narrative": state.get("narrative") or "",
            })

        # Track that states ticked this turn
        current["states_applied_turns"] = int(current.get("states_applied_turns", 0)) + 1
        flags["dungeon_run"] = run
        _save_flags(conn, campaign_id, flags)
        return results
    finally:
        conn.close()


# ── Riddle resolution (tile mode) ─────────────────────────────────────────────

def resolve_riddle_tiles(campaign_id: int, player_input: str) -> dict:
    """Check riddle answer on current tile, mark solved if correct."""
    from app.services.dungeon_service import _answer_matches

    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run")
        if not run or run.get("system") != "tiles":
            raise ValueError("No active tile-based dungeon run")

        current = get_current_tile(run)
        if not current:
            raise ValueError("Current tile not found")
        riddle = current.get("riddle")
        if not riddle:
            return {"ok": False, "reason": "Brak zagadki w tym pomieszczeniu"}

        answer = riddle.get("answer", "")
        alts = riddle.get("answer_alts", [])
        if _answer_matches(player_input, answer, alts):
            riddle["solved"] = True
            current["riddle"] = riddle
            flags["dungeon_run"] = run
            _save_flags(conn, campaign_id, flags)
            return {"ok": True, "solved": True, "narrative": "Zagadka rozwiązana!"}

        hints = riddle.get("hints", [])
        used = int(riddle.get("hints_used", 0))
        if used < len(hints):
            hint = hints[used]
            riddle["hints_used"] = used + 1
            current["riddle"] = riddle
            flags["dungeon_run"] = run
            _save_flags(conn, campaign_id, flags)
            return {"ok": True, "solved": False, "hint": hint,
                    "narrative": f"Błędna odpowiedź. Podpowiedź: {hint}"}

        return {"ok": True, "solved": False, "narrative": "Błędna odpowiedź. Brak podpowiedzi."}
    finally:
        conn.close()
