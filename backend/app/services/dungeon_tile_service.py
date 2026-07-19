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
    _resolve_cooldown_hours,
    _save_flags,
    check_cooldown,
    complete_dungeon,
    get_dungeon,
    start_dungeon_cooldown,
)

# ── Spatial constants ─────────────────────────────────────────────────────────

DIRECTIONS = ("N", "S", "E", "W")
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
OFFSET = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}

# ── Numbers Policy (starting values — tuning after L19) ───────────────────────

BRANCH_CHANCE = 0.30     # chance of branch per main path tile with free doors
MAX_BRANCHES = 3         # max branches in the full graph
MAX_BRANCH_LENGTH = 2    # max tiles per branch (1 or 2)

# ── L5: Absolutna skala D1–D5 (Decyzja 8) ────────────────────────────────────
# (min_enemy_level, max_enemy_level, boss_level) per dungeon tier 1–5

TIER_ENEMY_LEVELS: dict[int, tuple[int, int, int]] = {
    1: (1, 2, 3),    # D1: enemy lvl 1–2, boss lvl 3
    2: (3, 4, 5),    # D2: enemy lvl 3–4, boss lvl 5
    3: (5, 6, 7),    # D3: enemy lvl 5–6, boss lvl 7
    4: (7, 8, 9),    # D4: enemy lvl 7–8, boss lvl 9
    5: (9, 10, 10),  # D5: enemy lvl 9–10, boss lvl 10 (+ endless %-modifier)
}

# L18 (#729): boss power scales with dungeon tier — a D1 boss is a weakened echo,
# a D5 boss its full self. Lets a strong undead (e.g. lich: 90 HP / AC17 / 2d8) be
# authored ONCE yet stay tier-appropriate, so a "Poz. 1+" dungeon never fields a
# 90-HP / +9 boss against a 12-HP hero. Starting values — tune after L19.
BOSS_TIER_FACTOR: dict[int, float] = {1: 0.45, 2: 0.62, 3: 0.78, 4: 0.90, 5: 1.0}


def _scale_damage_die(die: str, factor: float) -> str:
    """Scale the dice COUNT of an 'NdM(+k)' expression by `factor` (floor 1dM).

    Softens boss burst at low tiers (e.g. 2d8 → 1d8 at D1) without touching the die
    size or flat bonus. Returns the input unchanged if it can't be parsed.
    """
    import re
    m = re.match(r"\s*(\d*)d(\d+)\s*(?:\+\s*(\d+))?\s*$", str(die or "").lower())
    if not m:
        return die
    n = max(1, round(int(m.group(1) or 1) * factor))
    sides = int(m.group(2))
    bonus = int(m.group(3) or 0)
    return f"{n}d{sides}+{bonus}" if bonus else f"{n}d{sides}"


def scale_enemy_for_dungeon_tier(
    base: dict,
    dungeon_tier: int,
    is_boss: bool = False,
    cycle: int = 1,
) -> dict:
    """L5: Absolutna skala D1–D5 — wrogowie skalowani tierem lochu, nie poziomem bohatera.

    HP = max(1, hp_base + max(0, CON_mod) × effective_level).
    Attack bonus = base_attack_bonus + effective_level // 2.
    Damage bonus = base_damage_bonus + effective_level // 4.
    Endless (cycle > 1): +1 level per cycle up to cap 10; above 10 → +15% HP/dmg_bonus per cycle.
    """
    tier = max(1, min(5, int(dungeon_tier)))
    min_lvl, max_lvl, boss_lvl = TIER_ENEMY_LEVELS[tier]
    eff_level = boss_lvl if is_boss else random.randint(min_lvl, max_lvl)

    # Endless scaling (Decyzja 7)
    percent_bonus = 0.0
    if cycle > 1:
        extra = cycle - 1
        head_room = max(0, 10 - eff_level)
        level_bumps = min(extra, head_room)
        eff_level += level_bumps
        overflow = extra - level_bumps
        if overflow > 0:
            percent_bonus = overflow * 0.15

    # CON modifier from S2 stats_json (floor negative mods at 0 for enemies)
    try:
        stats = json.loads(base.get("stats_json") or "{}")
        con = int(stats.get("CON") or 10)
    except Exception:
        con = 10
    con_mod = max(0, (con - 10) // 2)

    # L18 (#729): tier-relative boss softening. A boss in a low-tier dungeon is a
    # weakened version of its full-power self (HP/AC/attack/damage all scaled).
    boss_factor = BOSS_TIER_FACTOR.get(tier, 1.0) if is_boss else 1.0

    base_hp = int(base.get("hp_base") or 5)
    if is_boss:
        base_hp = max(1, round(base_hp * boss_factor))
    hp = base_hp + con_mod * eff_level
    if percent_bonus > 0:
        hp = round(hp * (1 + percent_bonus))

    base_atk = int(base.get("attack_bonus") or 0)
    base_dmg = int(base.get("damage_bonus") or 0)
    if is_boss:
        base_atk = round(base_atk * boss_factor)
        base_dmg = round(base_dmg * boss_factor)
    atk = base_atk + eff_level // 2
    dmg_bonus = base_dmg + eff_level // 4
    if percent_bonus > 0:
        dmg_bonus = round(dmg_bonus * (1 + percent_bonus))

    scaled = dict(base)
    scaled["hp_base"] = max(1, hp)
    scaled["attack_bonus"] = atk
    scaled["damage_bonus"] = dmg_bonus
    if is_boss:
        # Soften boss AC toward 10 and burst dice at low tiers (D5 keeps full power).
        # Clamp so a naturally low-AC boss is never made TOUGHER by the softening.
        base_ac = int(base.get("ac_base") or 10)
        scaled["ac_base"] = min(base_ac, 10 + round((base_ac - 10) * boss_factor))
        if base.get("damage_die"):
            scaled["damage_die"] = _scale_damage_die(base.get("damage_die"), boss_factor)
    return scaled

_DOOR_HINTS = {
    "boss": "Czujesz lodowaty wiatr i słyszysz głęboki oddech.",
    "enemies": "Słyszysz odgłosy walki za drzwiami.",
    "riddle": "Czujesz aurę tajemnicy przy tych drzwiach.",
    "chest": "Widzisz metaliczny blask w szczelinie drzwi.",
    "empty": "Panuje cisza za tymi drzwiami.",
}


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


def _tile_has_enemies(tile: dict) -> bool:
    """True if the tile would start combat on entry (used to avoid combat entry tiles)."""
    try:
        return len(json.loads(tile.get("enemies_json") or "[]")) > 0
    except Exception:
        return False


def _tile_enemies_allowed(tile: dict, allowed_enemy_keys: set[str]) -> bool:
    """L18 (#729): True if the tile is drawable for a dungeon whose roster is
    `allowed_enemy_keys`. Enemy-free tiles are always allowed; combat tiles only when
    EVERY referenced enemy is in the dungeon's declared `enemy_pool`.

    This makes the author-declared pool gate combat content (not just repeat re-rolls),
    so a starter "Poz. 1+" dungeon never draws an endgame elite (shadow_stalker, etc.)
    from a shared tile category.
    """
    try:
        enemies = json.loads(tile.get("enemies_json") or "[]")
    except Exception:
        enemies = []
    if not enemies:
        return True
    keys = {e.get("enemy_key") for e in enemies if e.get("enemy_key")}
    return keys.issubset(allowed_enemy_keys)


# L18 (#733): ease-in difficulty for the first combat rooms of the MAIN PATH so a
# solo low-level hero survives the forced opening. #729 gates enemy TYPES; this caps
# enemy COUNT + total base HP on the first EASE_IN_ROOMS combat tiles. Deeper rooms
# keep the full pool (curve grows with depth). Endless segments (cycle>1) skip ease-in
# — the hero is already strong. Numbers Policy: starting values, tune after live play.
EASE_IN_ROOMS = 2
EASE_IN_COUNT_CAP: tuple[int, ...] = (1, 2)  # room1 ≤1 enemy, room2 ≤2
EASE_IN_HP_CAP_BY_TIER: dict[int, tuple[int, ...]] = {
    1: (16, 28),
    2: (28, 48),
    3: (40, 68),
    4: (52, 88),
    5: (64, 108),
}


def _tile_enemy_budget(tile: dict, enemy_hp: dict[str, int]) -> tuple[int, int]:
    """Return (enemy_count, total_base_hp) for a tile from its enemies_json."""
    try:
        enemies = json.loads(tile.get("enemies_json") or "[]")
    except Exception:
        enemies = []
    count = 0
    hp = 0
    for e in enemies:
        n = int(e.get("count") or 1)
        count += n
        hp += int(enemy_hp.get(e.get("enemy_key"), 12)) * n
    return count, hp


def _ease_in_caps(tier: int, combat_index: int) -> tuple[int, int]:
    """(max_count, max_total_hp) for the `combat_index`-th main-path combat room."""
    t = max(1, min(5, int(tier)))
    i = min(combat_index, EASE_IN_ROOMS - 1)
    return EASE_IN_COUNT_CAP[i], EASE_IN_HP_CAP_BY_TIER[t][i]


def _pick_path_candidate(
    matching: list[dict],
    enemy_hp: dict[str, int] | None,
    tier: int,
    combat_index: int,
    ease_in: bool,
) -> dict:
    """Pick the next main-path tile from door-matching candidates (already shuffled).

    Outside the ease-in window (or without `enemy_hp`) the first match is used (random,
    unchanged behaviour). Inside the window, prefer tiles that are enemy-free or within
    the room's count+HP budget; if none comply, fall back to the LIGHTEST combat tile
    (least total HP) so the path is never blocked and overshoot is minimised.
    """
    if not (ease_in and enemy_hp is not None and combat_index < EASE_IN_ROOMS):
        return matching[0]
    cap_count, cap_hp = _ease_in_caps(tier, combat_index)

    def _ok(c: dict) -> bool:
        cnt, hp = _tile_enemy_budget(c, enemy_hp)
        return cnt == 0 or (cnt <= cap_count and hp <= cap_hp)

    compliant = [c for c in matching if _ok(c)]
    if compliant:
        return compliant[0]
    return min(matching, key=lambda c: _tile_enemy_budget(c, enemy_hp)[1])


def _try_build_path(
    tiles: list[dict],
    boss_pool: list[dict],
    tile_count: int,
    boss_tile_id: int | None,
    enemy_hp: dict[str, int] | None = None,
    tier: int = 1,
    ease_in: bool = False,
) -> list[dict] | None:
    """Try to build a connected path. Returns None on dead-end / collision failure.

    L18 (#733): when `ease_in` and `enemy_hp` are provided, the first EASE_IN_ROOMS
    enemy-bearing tiles on the main path are budget-capped (count + total base HP) per
    `tier`, so a solo low-level hero can win the forced opening fights.
    """
    if not tiles:
        return None
    if tile_count < 2:
        return None

    # Pick entry tile (must have at least 1 door). L13c fix (#685): the entry node
    # never triggers combat (initiate_combat only fires on move_through_door INTO a
    # tile), and enemies_cleared exit conditions would then soft-lock the run with no
    # way to fight. So prefer an enemy-free entrance; fall back to any door tile only
    # when the whole category is combat tiles (authoring should always include one
    # safe entrance).
    entry_candidates = [t for t in tiles if _doors(t)]
    if not entry_candidates:
        return None
    safe_entries = [t for t in entry_candidates if not _tile_has_enemies(t)]
    first = random.choice(safe_entries or entry_candidates)

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
    combat_index = 0  # L18 (#733): count of enemy-bearing main-path tiles placed
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
            # Find a pool tile with the required entry door (ease-in budget-aware).
            matching = [c for c in pool if opp in _doors(c)]
            if not matching:
                continue
            candidate = _pick_path_candidate(matching, enemy_hp, tier, combat_index, ease_in)
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
            if _tile_has_enemies(candidate):
                combat_index += 1
            progressed = True
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


def resolve_tile_content(
    tile_id: int,
    dungeon_tier: int = 1,
    cycle: int = 1,
    hero_level: int = 1,  # kept for backward compat — ignored (L5: tier scales, not hero)
) -> dict | None:
    """Join a tile row with referenced enemies, items, riddle. L5: tier-based scaling."""
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
        # #722: auto-gate riddle tiles — safety net for seeds without exit_conditions_json set
        if tile.get("riddle_key") and not any(c.get("type") == "riddle_solved" for c in exit_conditions):
            exit_conditions.append({"type": "riddle_solved"})

        is_boss = bool(tile.get("is_boss_tile") or 0)

        resolved_enemies: list[dict] = []
        for entry in enemies:
            enemy_key = entry.get("enemy_key")
            count = int(entry.get("count") or 1)
            if not enemy_key:
                continue
            r = conn.execute(
                "SELECT key, label, hp_base, ac_base, attack_bonus, damage_die, damage_bonus, "
                "dex_modifier, tier, stats_json FROM game_config_enemies WHERE key = ?",
                (enemy_key,),
            ).fetchone()
            if not r:
                continue
            base = dict(r)
            scaled = scale_enemy_for_dungeon_tier(base, dungeon_tier, is_boss=is_boss, cycle=cycle)
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


# ── L5: Re-roll enemies on repeated tiles (Decyzja 9) ────────────────────────

def _reroll_repeated_tile_enemies(
    graph: dict,
    enemy_pool: list[str],
    conn: sqlite3.Connection,
) -> dict:
    """Re-roll enemies for nodes whose tile_id appears more than once in the graph.

    First occurrence keeps original enemies. Subsequent occurrences draw 1–2 random
    enemies from enemy_pool if available; otherwise original enemies are kept.
    """
    if not enemy_pool:
        return graph

    nodes = graph.get("nodes") or {}
    # Track which tile_ids have been seen (first occurrence = skip)
    seen_tile_ids: set[int] = set()

    # Validate pool enemies exist in DB
    valid_pool = []
    for ek in enemy_pool:
        r = conn.execute("SELECT key FROM game_config_enemies WHERE key = ?", (ek,)).fetchone()
        if r:
            valid_pool.append(ek)

    if not valid_pool:
        return graph

    for node_id, node in nodes.items():
        tile_id = node.get("tile_id")
        if tile_id is None:
            continue
        if tile_id in seen_tile_ids:
            # Re-roll: pick 1–2 random enemies from pool
            count = random.randint(1, min(2, len(valid_pool)))
            chosen = random.sample(valid_pool, count)
            node["content"]["enemies"] = [{"enemy_key": k, "count": 1} for k in chosen]
        else:
            seen_tile_ids.add(tile_id)

    graph["nodes"] = nodes
    return graph


# ── LB5 #824: Party-size enemy count scaling ─────────────────────────────────

def _dungeon_party_size(conn: sqlite3.Connection, campaign_id: int) -> int:
    """LB5 #824 — accepted campaign_members with assigned hero → party size."""
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM campaign_members "
            "WHERE campaign_id = ? AND status = 'accepted' AND character_id IS NOT NULL",
            (campaign_id,),
        ).fetchone()
        return max(1, int(row["cnt"] or 1))
    except Exception:
        return 1


_DUNGEON_MP_ENEMY_COUNT_CAP = 4  # hard cap on extra enemies per tile node


def _scale_tile_graph_enemy_counts(graph: dict, party_size: int) -> dict:
    """LB5 #824 — scale count in every tile node's enemies list by party_size.

    solo (party_size=1) → no change. Tier/enemy_key untouched.
    Formula mirrors encounter_service: clamp(base × party_size, base, base + CAP).
    """
    if party_size <= 1:
        return graph
    for node in (graph.get("nodes") or {}).values():
        content = node.get("content") or {}
        enemies = content.get("enemies") or []
        if not enemies:
            continue
        scaled = []
        for e in enemies:
            base = max(1, int(e.get("count") or 1))
            scaled.append({**e, "count": min(base * party_size, base + _DUNGEON_MP_ENEMY_COUNT_CAP)})
        content["enemies"] = scaled
        node["content"] = content
    return graph


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
    """Build a branching tile graph (v2) and store it in session_flags as dungeon_run.

    L3: replaces the linear tile sequence with draw_tile_graph(). The API endpoint
    /enter now calls this instead of legacy dungeon_service.enter_dungeon().
    """
    # AUDIT #1441: guard against cooldown bypass by re-entering without /exit.
    # If an unfinished dungeon_run is still parked in session_flags, burn it with a
    # reduced (abandonment) cooldown BEFORE it is overwritten below. If that abandoned
    # run is the SAME dungeon we're re-entering, the check_cooldown below will now
    # trip and reject the re-entry (forcing a real cooldown wait).
    _conn0, _flags0 = _load_flags(campaign_id)
    try:
        _existing_run = _flags0.get("dungeon_run")
    finally:
        _conn0.close()
    if isinstance(_existing_run, dict) and not _existing_run.get("completed") and not _existing_run.get("failed"):
        _prev_key = _existing_run.get("dungeon_key")
        if _prev_key:
            try:
                start_dungeon_cooldown(character_id, _prev_key, fraction=0.5)
            except Exception:
                pass

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
        raise ValueError("Loch nie ma skonfigurowanej kategorii kafelków.")

    tile_count = _tile_count_for_difficulty(dungeon, hero_level)
    boss_tile_id = dungeon.get("boss_tile_id")
    dungeon_difficulty = int(dungeon.get("dungeon_difficulty") or 1)

    # L18 (#729): the dungeon's enemy_pool gates which combat tiles are drawable, so a
    # starter dungeon can't pull endgame elites from a shared tile category.
    enemy_pool_raw = dungeon.get("enemy_pool") or "[]"
    try:
        enemy_pool = json.loads(enemy_pool_raw) if isinstance(enemy_pool_raw, str) else list(enemy_pool_raw)
    except Exception:
        enemy_pool = []
    allowed_enemy_keys = {k for k in enemy_pool if k} or None

    graph = draw_tile_graph(
        category_key, tile_count, boss_tile_id,
        allowed_enemy_keys=allowed_enemy_keys, tier=dungeon_difficulty,
    )

    # L5/Decyzja 9: re-roll enemies on repeated tiles using dungeon's enemy_pool
    conn, flags = _load_flags(campaign_id)
    try:
        graph = _reroll_repeated_tile_enemies(graph, enemy_pool, conn)
        # LB5 #824 — scale enemy count in each tile node by party size
        graph = _scale_tile_graph_enemy_counts(graph, _dungeon_party_size(conn, campaign_id))

        # L7: entry checkpoint — capture XP at dungeon start for rollback on death
        _char_row = None
        try:
            _char_conn = _get_db()
            try:
                _char_row = _char_conn.execute(
                    "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
                ).fetchone()
            finally:
                _char_conn.close()
        except Exception:
            _char_row = None
        if _char_row:
            _entry_sheet = json.loads(_char_row["sheet_json"] or "{}")
            entry_checkpoint: dict[str, Any] = {
                "cycle": 1,
                "source": "dungeon_enter",
                "xp_lifetime_earned": int(_entry_sheet.get("xp_lifetime_earned") or 0),
                "xp_available": int(_entry_sheet.get("xp_available") or 0),
            }
        else:
            entry_checkpoint = {"cycle": 1, "source": "dungeon_enter",
                                "xp_lifetime_earned": 0, "xp_available": 0}

        run = {
            "system": "tiles_v2",
            "dungeon_key": dungeon_key,
            "dungeon_label": dungeon.get("label", dungeon_key),
            "category_key": category_key,
            "dungeon_difficulty": dungeon_difficulty,  # L5: tier for enemy scaling
            "graph": graph,
            "positions": {str(character_id): graph["entry_node"]},
            "cycle": 1,
            "checkpoints": [entry_checkpoint],
            "at_checkpoint": False,
            "completed": False,
            "failed": False,
            "hero_level_at_entry": hero_level,
            "cooldown_hours": _resolve_cooldown_hours(dungeon),
            "loot_collected": [],
        }

        # L11/L12b: mark the entry node visited so the dungeon map renders the
        # starting room (+ fog neighbours) immediately — move_through_door only
        # flags subsequently-entered nodes, so without this the map is blank
        # until the first move.
        _entry_nid = graph.get("entry_node")
        if _entry_nid and _entry_nid in graph.get("nodes", {}):
            graph["nodes"][_entry_nid]["visited"] = True

        flags["dungeon_run"] = run
        if previous_campaign_id:
            flags["dungeon_previous_campaign_id"] = previous_campaign_id
        _save_flags(conn, campaign_id, flags)
    finally:
        conn.close()

    return run


def get_current_tile(run: dict) -> dict | None:
    """Return current tile/node for v2 graph runs or legacy v1 linear runs."""
    if run.get("system") == "tiles_v2":
        graph = run.get("graph") or {}
        nodes = graph.get("nodes") or {}
        positions = run.get("positions") or {}
        node_id = next(iter(positions.values()), None) or graph.get("entry_node")
        return nodes.get(node_id) if node_id else None
    # Legacy v1 linear format
    idx = int(run.get("current_index", 0))
    tiles = run.get("tiles") or []
    if 0 <= idx < len(tiles):
        return tiles[idx]
    return None


def get_current_node_id(run: dict, character_id: int) -> str | None:
    """Return node_id of character's current position in v2 run."""
    positions = run.get("positions") or {}
    node_id = positions.get(str(character_id))
    if node_id:
        return node_id
    graph = run.get("graph") or {}
    return graph.get("entry_node")


def mark_node_cleared(campaign_id: int, character_id: int) -> None:
    """L4: Mark current dungeon tile node cleared after combat victory."""
    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run")
        if not run or run.get("system") != "tiles_v2":
            return
        graph = run.get("graph") or {}
        nodes = graph.get("nodes") or {}
        node_id = get_current_node_id(run, character_id)
        if node_id and node_id in nodes:
            nodes[node_id]["cleared"] = True
            run["graph"]["nodes"] = nodes
            flags["dungeon_run"] = run
            _save_flags(conn, campaign_id, flags)
    finally:
        conn.close()


# ── L18 (#729 follow-up): dungeon-only victory sustain drop ───────────────────
# A solo low-level hero's HP melts across back-to-back tile fights with no town to
# restock. To keep dungeons winnable WITHOUT touching world-combat balance, every
# (non-boss) dungeon combat victory has a tier-scaled chance to drop a healing
# consumable. This is dungeon-only BY CONSTRUCTION: it only fires when an active
# tiles_v2 `dungeon_run` exists in session_flags — world combat never reaches it.
# Lower tiers are more generous (weaker heroes need more sustain). Boss tiles are
# skipped (they already grant boss loot). Numbers Policy: starting values — tune
# after live play.

_SUSTAIN_CHANCE_BY_TIER: dict[int, float] = {1: 0.40, 2: 0.33, 3: 0.27, 4: 0.20, 5: 0.15}
_SUSTAIN_KEYS_BY_TIER: dict[int, list[str]] = {
    1: ["potion_healing_minor", "bandage", "healing_herb"],
    2: ["potion_healing_minor", "potion_healing_standard"],
    3: ["potion_healing_standard"],
    4: ["potion_healing_standard", "potion_healing_major"],
    5: ["potion_healing_major"],
}


def grant_dungeon_victory_sustain(campaign_id: int, character_id: int) -> dict | None:
    """Roll AND grant a dungeon-only healing-consumable drop on a (non-boss) victory.

    Returns {key, label, quantity} of the granted consumable, or None. DUNGEON-ONLY:
    returns None unless an active tiles_v2 dungeon_run exists. Grants the consumable
    directly to the hero's inventory (server-side, like boss loot) — surfaced to the
    player via the combat-end response (`dungeon_sustain`), not the per-kill „co
    wypadło" reveal (that path maps every non-weapon to item_key and would mis-store a
    consumable). Call AFTER the victory commit so it never nests in the combat txn.
    """
    conn = _get_db()
    try:
        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not gs:
            return None
        flags = json.loads((gs["session_flags"] if gs else None) or "{}")
        run = flags.get("dungeon_run")
        if not run or run.get("system") != "tiles_v2":
            return None  # dungeon-only gate

        # Skip boss tiles — they already grant boss loot.
        node_id = get_current_node_id(run, character_id)
        node = ((run.get("graph") or {}).get("nodes") or {}).get(node_id) or {}
        if node.get("is_boss") or (node.get("content") or {}).get("is_boss_tile"):
            return None

        tier = max(1, min(5, int(run.get("dungeon_difficulty", 1))))
        if random.random() >= _SUSTAIN_CHANCE_BY_TIER.get(tier, 0.25):
            return None

        # Pick the first tier-appropriate consumable that actually exists/active;
        # fall back to any active heal_hp consumable so a missing key never no-ops.
        candidates = list(_SUSTAIN_KEYS_BY_TIER.get(tier, ["potion_healing_minor"]))
        random.shuffle(candidates)
        row = None
        for key in candidates:
            row = conn.execute(
                "SELECT key, label FROM game_config_consumables WHERE key = ? AND is_active = 1",
                (key,),
            ).fetchone()
            if row:
                break
        if not row:
            row = conn.execute(
                "SELECT key, label FROM game_config_consumables "
                "WHERE effect_type = 'heal_hp' AND is_active = 1 ORDER BY rarity LIMIT 1"
            ).fetchone()
        if not row:
            return None
        key = row["key"]
        label = row["label"] or key.replace("_", " ")
    finally:
        conn.close()

    # Grant directly (own connection inside grant_loot_to_character).
    try:
        from app.services.loot_service import grant_loot_to_character
        grant_loot_to_character(
            character_id, [{"consumable_key": key, "quantity": 1}], source="dungeon_sustain"
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("dungeon sustain grant failed")
        return None

    return {"key": key, "label": label, "quantity": 1}


def move_through_door(campaign_id: int, character_id: int, direction: str) -> dict:
    """L4: Move character through a door in the given direction.

    Validates direction, checks exit_conditions on current node, updates positions,
    marks visited, discovers fog, and starts combat deterministically (Decision 4).
    Backtracking to cleared nodes skips combat.
    """
    if direction not in DIRECTIONS:
        return {"ok": False, "blocked": True, "reason": f"Nieprawidłowy kierunek: {direction}"}

    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run")
        if not run or run.get("system") != "tiles_v2":
            raise ValueError("Brak aktywnego lochu kafelkowego (v2).")

        graph = run.get("graph") or {}
        nodes = graph.get("nodes") or {}
        positions = run.get("positions") or {}

        current_node_id = get_current_node_id(run, character_id)
        if not current_node_id:
            raise ValueError("Nie można określić bieżącej pozycji.")

        current_node = nodes.get(current_node_id)
        if not current_node:
            raise ValueError("Bieżący kafelek nie istnieje w grafie.")

        doors_open = current_node.get("doors_open") or {}
        target_node_id = doors_open.get(direction)
        if not target_node_id:
            return {"ok": False, "blocked": True, "reason": f"Brak drzwi w kierunku {direction}."}

        target_node = nodes.get(target_node_id)
        if not target_node:
            raise ValueError("Kafelek docelowy nie istnieje w grafie.")

        # #722: exit conditions gate forward movement only; backtracking to a visited
        # node is always allowed (prevents riddle soft-lock on the entry door).
        if not target_node.get("visited"):
            current_content = current_node.get("content") or {}
            tile_for_check = {**current_content, "cleared": current_node.get("cleared", False)}
            allowed, reason = check_exit_conditions(tile_for_check, character_id)
            if not allowed:
                return {"ok": False, "blocked": True, "reason": reason}
            # #847: mark cleared only on forward moves (exit conditions verified and passed).
            # Backtracking must not clear riddle/combat rooms that haven't been resolved.
            nodes[current_node_id]["cleared"] = True

        # Move character to target node
        nodes[target_node_id]["visited"] = True
        run["positions"] = {**positions, str(character_id): target_node_id}

        # Fog discovery: reveal outline of not-yet-visited neighbors of target
        target_doors = target_node.get("doors_open") or {}
        fog_discovered = [
            nbr_id
            for _d, nbr_id in target_doors.items()
            if nbr_id and nbr_id != current_node_id and not nodes.get(nbr_id, {}).get("visited")
        ]

        run["graph"]["nodes"] = nodes
        flags["dungeon_run"] = run
        _save_flags(conn, campaign_id, flags)

        # Decision 4: deterministic combat start on entering a tile with enemies
        target_content = target_node.get("content") or {}
        is_cleared = target_node.get("cleared", False)

        # L5: read dungeon tier + cycle for absolute scaling
        dungeon_tier = int(run.get("dungeon_difficulty", 1))
        cycle = int(run.get("cycle", 1))
        is_boss_tile = bool(target_content.get("is_boss_tile", False))

        combat_state = None
        if not is_cleared:
            raw_enemies = target_content.get("enemies") or []
            enemy_keys: list[str] = []
            for e in raw_enemies:
                key = e.get("enemy_key")
                count = int(e.get("count") or 1)
                if key:
                    enemy_keys.extend([key] * count)
            if enemy_keys:
                try:
                    from app.services.combat_service import initiate_combat
                    # LB2: first combat of the run gets soft-init (hero always first)
                    _is_first_combat = run.get("combats_started", 0) == 0
                    # L5: build tier-scaled stat overrides for each unique enemy key
                    _enemy_overrides: dict[str, dict] = {}
                    for ek in set(enemy_keys):
                        r = conn.execute(
                            "SELECT key, label, hp_base, ac_base, attack_bonus, damage_die, "
                            "damage_bonus, dex_modifier, tier, stats_json FROM game_config_enemies "
                            "WHERE key = ?",
                            (ek,),
                        ).fetchone()
                        if r:
                            _enemy_overrides[ek] = scale_enemy_for_dungeon_tier(
                                dict(r), dungeon_tier, is_boss=is_boss_tile, cycle=cycle
                            )
                    combat_state = initiate_combat(
                        campaign_id, character_id, enemy_keys,
                        _dungeon_enemy_overrides=_enemy_overrides if _enemy_overrides else None,
                        _dungeon_first_combat=_is_first_combat,
                        allow_pending=True,  # #1449: authored dungeon seed keys
                    )
                    run["combats_started"] = run.get("combats_started", 0) + 1
                    flags["dungeon_run"] = run
                    _save_flags(conn, campaign_id, flags)
                except Exception as exc:
                    combat_state = {"error": str(exc)}

        _resolve_riddle_in_content(conn, target_content)
        room_description = target_content.get("room_description") or ""
        return {
            "ok": True,
            "node_id": target_node_id,
            "node": target_node,
            "content": target_content,
            "room_description": room_description,
            "fog_discovered": fog_discovered,
            "is_cleared": is_cleared,
            "combat": combat_state,
            "narrative": room_description or "Wchodzisz do kolejnego pomieszczenia.",
        }
    finally:
        conn.close()


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
            # Graph stores riddle as a bare key string until first interaction;
            # a string key means unsolved. Only a dict carries the solved flag.
            solved = riddle.get("solved") if isinstance(riddle, dict) else False
            if riddle and not solved:
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


# ── L6: Non-combat tile actions (chest / riddle / rest) ───────────────────────

_MAX_CHEST_ATTEMPTS = 3
_TRAP_TRIGGER_CHANCE = 0.30
_MAX_RIDDLE_ATTEMPTS = 3
_MAX_RIDDLE_HINTS = 2
_REST_HEAL_PCT = 20


def _roll_die_expr(expr: str) -> int:
    """Roll NdM+k expression. Returns 0 on parse failure."""
    import re
    m = re.match(r"(\d*)d(\d+)(?:\s*\+\s*(\d+))?", str(expr).strip().lower())
    if m:
        n = int(m.group(1) or 1)
        sides = int(m.group(2))
        bonus = int(m.group(3) or 0)
        return sum(random.randint(1, sides) for _ in range(n)) + bonus
    return 0


def _get_char_dex_modifier(conn: sqlite3.Connection, character_id: int) -> int:
    """Return DEX modifier ((DEX-10)//2) from characters.sheet_json."""
    try:
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?",
                           (character_id,)).fetchone()
        if not row:
            return 0
        sheet = json.loads(row["sheet_json"] or "{}")
        dex = int(sheet.get("DEX", sheet.get("dex", 10)) or 10)
        return (dex - 10) // 2
    except Exception:
        return 0


def _apply_damage_to_character(conn: sqlite3.Connection, character_id: int, damage: int) -> int | None:
    """Subtract `damage` from characters.sheet_json.current_hp (clamp ≥0). Returns new HP."""
    if damage <= 0:
        return None
    try:
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (character_id,)).fetchone()
        if not row:
            return None
        sheet = json.loads(row["sheet_json"] or "{}")
        cur = int(sheet.get("current_hp", sheet.get("max_hp", 0)) or 0)
        new_hp = max(0, cur - int(damage))
        sheet["current_hp"] = new_hp
        conn.execute("UPDATE characters SET sheet_json = ? WHERE id = ?",
                     (json.dumps(sheet), character_id))
        conn.commit()
        return new_hp
    except Exception:
        import logging
        logging.getLogger(__name__).exception("trap damage apply failed")
        return None


def _trigger_trap_chance(content: dict, tier: int) -> dict | None:
    """Return trap dict at 30% chance, None otherwise.

    Checks content.active_states for trap-type states first; falls back to 1d4+tier.
    """
    if random.random() >= _TRAP_TRIGGER_CHANCE:
        return None
    active_states = content.get("active_states") or []
    for state in active_states:
        stype = str(state.get("type") or "").lower()
        if "trap" in stype:
            dmg_die = state.get("damage_die") or state.get("damage") or f"1d4+{tier}"
            damage = _roll_die_expr(str(dmg_die))
            return {
                "triggered": True,
                "type": stype,
                "description": state.get("narrative") or "Pułapka!",
                "damage": damage,
                "damage_die": str(dmg_die),
            }
    damage = random.randint(1, 4) + tier
    return {
        "triggered": True,
        "type": "trap",
        "description": "Ukryta pułapka!",
        "damage": damage,
        "damage_die": f"1d4+{tier}",
    }


def _roll_chest_loot_for_run(conn: sqlite3.Connection, dungeon_key: str, tier: int) -> list[dict]:
    """Roll chest loot from dungeon's chest_loot_table_key."""
    from app.services.dungeon_service import get_dungeon, get_loot_rarity_for_difficulty, _roll_loot_table
    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        return []
    chest_table = dungeon.get("chest_loot_table_key") or ""
    if not chest_table:
        return []
    loot = _roll_loot_table(conn, chest_table)
    rarity = get_loot_rarity_for_difficulty(tier)
    for item in loot:
        item["rarity"] = rarity
    return loot


def _empty_corridor_response(action: str) -> dict:
    """U22 fallback: return pusty_korytarz when tile node missing."""
    import logging
    logging.getLogger(__name__).warning("L6 U22 fallback: node missing, returning empty corridor")
    return {
        "ok": True,
        "action": action,
        "fallback": True,
        "tile_label": "Pusty korytarz",
        "room_description": "Wąski kamienny korytarz. Puste ściany. Cisza.",
        "narrative": "Stoisz w pustym korytarzu. Nie ma tu nic do zrobienia.",
        "trap": None,
    }


def _action_open_chest(
    conn: sqlite3.Connection,
    node: dict,
    content: dict,
    character_id: int,
    tier: int,
    run: dict,
) -> dict:
    chest_state = node.get("chest_state") or {}
    if chest_state.get("locked_forever"):
        return {
            "ok": True,
            "action": "open_chest",
            "chest_locked_forever": True,
            "loot": [],
            "trap": None,
            "narrative": "Skrzynia jest na zawsze zablokowana.",
        }
    # AUDIT #1441: a chest may only be looted once. Without this guard a player on a
    # chest tile could POST /resolve-tile {action:"open_chest"} repeatedly and re-roll
    # loot on every roll above DC (unbounded loot farming).
    if chest_state.get("opened"):
        return {
            "ok": True,
            "action": "open_chest",
            "chest_already_opened": True,
            "loot": [],
            "trap": None,
            "narrative": "Skrzynia jest już otwarta.",
        }

    attempts = int(chest_state.get("attempts", 0))
    dc = 12 + tier
    dex_mod = _get_char_dex_modifier(conn, character_id)
    d20 = random.randint(1, 20)
    total = d20 + dex_mod
    success = total >= dc
    attempts += 1
    chest_state["attempts"] = attempts

    trap = None
    loot: list[dict] = []

    if success:
        # NOTE: loot is GRANTED by the resolve-tile endpoint (grant_dungeon_loot) which
        # replaces result["loot"] with the granted entries (with labels). Do NOT grant
        # here too — that double-grants.
        loot = _roll_chest_loot_for_run(conn, run.get("dungeon_key", ""), tier)
        chest_state["opened"] = True
        narrative = f"Otwierasz skrzynię! (Rzut: {d20}{dex_mod:+}={total} vs DC {dc})"
        narrative += f" Znalazłeś {len(loot)} przedmiot(y)!" if loot else " Skrzynia jest pusta."
    else:
        if attempts >= _MAX_CHEST_ATTEMPTS:
            chest_state["locked_forever"] = True
            narrative = (
                f"Nieudana próba ({d20}{dex_mod:+}={total} vs DC {dc}). "
                "Mechanizm blokuje skrzynię na zawsze!"
            )
        else:
            remaining = _MAX_CHEST_ATTEMPTS - attempts
            narrative = (
                f"Nieudana próba ({d20}{dex_mod:+}={total} vs DC {dc}). "
                f"Pozostało prób: {remaining}."
            )
        trap = _trigger_trap_chance(content, tier)
        # L12b fix: actually apply trap damage to the hero's HP (was rolled, never applied).
        if trap and trap.get("damage"):
            hp_after = _apply_damage_to_character(conn, character_id, int(trap["damage"]))
            if hp_after is not None:
                trap["hp_after"] = hp_after
                narrative += f" Pułapka! Tracisz {trap['damage']} HP."

    node["chest_state"] = chest_state
    return {
        "ok": True,
        "action": "open_chest",
        "success": success,
        "roll": d20,
        "dex_mod": dex_mod,
        "total": total,
        "dc": dc,
        "attempt": attempts,
        "max_attempts": _MAX_CHEST_ATTEMPTS,
        "chest_locked_forever": chest_state.get("locked_forever", False),
        "loot": loot,
        "trap": trap,
        "narrative": narrative,
    }


def _resolve_riddle_in_content(conn: sqlite3.Connection, content: dict) -> None:
    """Normalize content["riddle"] to a dict in-place.

    The graph generator (`_get_tile_content`) stores `riddle` as a bare string key
    (e.g. "riddle_shadow"); the action handlers and exit checks expect the resolved
    dict shape produced by `_join_tile`. Resolve the key from game_config_riddles
    so riddles work at runtime (entry-run AND endless segments). No-op when already
    a dict or absent. (smoke-loch fix: AttributeError 'str'.get)
    """
    riddle = content.get("riddle")
    if not isinstance(riddle, str) or not riddle:
        return
    try:
        r = conn.execute(
            "SELECT * FROM game_config_riddles WHERE key = ? AND is_active = 1",
            (riddle,),
        ).fetchone()
    except Exception:
        r = None
    if not r:
        content["riddle"] = None
        return
    rd = dict(r)
    try:
        answer_alts = json.loads(rd.get("answer_alts") or "[]")
    except Exception:
        answer_alts = []
    try:
        hints = json.loads(rd.get("hints") or "[]")
    except Exception:
        hints = []
    content["riddle"] = {
        "key": rd["key"],
        "text": rd.get("text"),
        "answer": rd.get("answer", ""),
        "answer_alts": answer_alts,
        "hints": hints,
        "hints_used": 0,
        "solved": False,
    }


def _action_answer_riddle(node: dict, content: dict, answer: str, tier: int) -> dict:
    from app.services.dungeon_service import _answer_matches

    riddle = content.get("riddle")
    if not riddle:
        return {"ok": False, "action": "answer_riddle",
                "narrative": "Brak zagadki w tym pomieszczeniu."}

    riddle_state = node.get("riddle_state") or {}

    if riddle_state.get("solved") or riddle.get("solved"):
        return {"ok": True, "action": "answer_riddle", "solved": True,
                "trap": None, "narrative": "Zagadka już rozwiązana."}

    if riddle_state.get("failed_permanently"):
        return {"ok": True, "action": "answer_riddle", "solved": False,
                "failed_permanently": True, "trap": None,
                "narrative": "Wyczerpałeś wszystkie próby."}

    attempts = int(riddle_state.get("attempts", 0))
    if attempts >= _MAX_RIDDLE_ATTEMPTS:
        riddle_state["failed_permanently"] = True
        node["riddle_state"] = riddle_state
        return {"ok": True, "action": "answer_riddle", "solved": False,
                "failed_permanently": True, "attempt": attempts,
                "max_attempts": _MAX_RIDDLE_ATTEMPTS, "trap": None,
                "narrative": "Wyczerpałeś wszystkie próby odpowiedzi."}

    attempts += 1
    riddle_state["attempts"] = attempts

    r_answer = riddle.get("answer", "")
    r_alts = riddle.get("answer_alts", [])

    if _answer_matches(answer, r_answer, r_alts):
        riddle_state["solved"] = True
        riddle["solved"] = True
        content["riddle"] = riddle
        node["riddle_state"] = riddle_state
        return {
            "ok": True, "action": "answer_riddle", "solved": True,
            "attempt": attempts, "max_attempts": _MAX_RIDDLE_ATTEMPTS,
            "trap": None, "narrative": "Zagadka rozwiązana! Drzwi się otwierają.",
        }

    # Wrong answer → optional hint + 30% trap
    trap = _trigger_trap_chance(content, tier)
    hints = riddle.get("hints", [])
    hints_used = int(riddle_state.get("hints_used", 0))
    hint = None
    if hints_used < len(hints) and hints_used < _MAX_RIDDLE_HINTS:
        hint = hints[hints_used]
        riddle_state["hints_used"] = hints_used + 1

    failed_permanently = attempts >= _MAX_RIDDLE_ATTEMPTS
    if failed_permanently:
        riddle_state["failed_permanently"] = True

    node["riddle_state"] = riddle_state
    narrative = "Błędna odpowiedź."
    if hint:
        narrative += f" Podpowiedź {riddle_state['hints_used']}: {hint}"
    if failed_permanently:
        narrative += " Wyczerpałeś wszystkie próby!"
    else:
        narrative += f" Pozostało prób: {_MAX_RIDDLE_ATTEMPTS - attempts}."

    return {
        "ok": True, "action": "answer_riddle", "solved": False,
        "failed_permanently": failed_permanently,
        "attempt": attempts, "max_attempts": _MAX_RIDDLE_ATTEMPTS,
        "hint": hint, "trap": trap, "narrative": narrative,
    }


def _action_riddle_hint(node: dict, content: dict) -> dict:
    riddle = content.get("riddle")
    if not riddle:
        return {"ok": False, "action": "riddle_hint",
                "narrative": "Brak zagadki w tym pomieszczeniu."}

    riddle_state = node.get("riddle_state") or {}
    hints_used = int(riddle_state.get("hints_used", 0))
    hints = riddle.get("hints", [])

    if hints_used >= _MAX_RIDDLE_HINTS or hints_used >= len(hints):
        node["riddle_state"] = riddle_state
        return {"ok": True, "action": "riddle_hint", "hint": None, "no_more_hints": True,
                "narrative": "Brak kolejnych podpowiedzi."}

    hint = hints[hints_used]
    riddle_state["hints_used"] = hints_used + 1
    node["riddle_state"] = riddle_state
    return {
        "ok": True, "action": "riddle_hint",
        "hint": hint, "hints_used": riddle_state["hints_used"],
        "no_more_hints": False,
        "narrative": f"Podpowiedź {riddle_state['hints_used']}: {hint}",
    }


def _apply_heal_to_character(conn: sqlite3.Connection, character_id: int, pct: int) -> int | None:
    """LB1 (#735): heal `pct`% of max HP (pct>=100 → full). Returns new current_hp."""
    try:
        row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (character_id,)).fetchone()
        if not row:
            return None
        sheet = json.loads(row["sheet_json"] or "{}")
        mx = int(sheet.get("max_hp") or 0)
        cur = int(sheet.get("current_hp", mx) or 0)
        if mx <= 0:
            return cur
        heal = mx if pct >= 100 else max(1, (mx * pct) // 100)
        new_hp = min(mx, cur + heal)
        sheet["current_hp"] = new_hp
        conn.execute("UPDATE characters SET sheet_json = ? WHERE id = ?",
                     (json.dumps(sheet, ensure_ascii=False), character_id))
        conn.commit()
        return new_hp
    except Exception:
        import logging
        logging.getLogger(__name__).exception("rest heal apply failed")
        return None


def _dungeon_rest_policy(conn: sqlite3.Connection, dungeon_key: str) -> tuple[int, int | None]:
    """LB1 (#735): (heal_pct, max_charges) for a dungeon. charges None = unlimited
    (onboarding); default 20% / 2 charges = 'fend for yourself' in deeper dungeons."""
    try:
        r = conn.execute(
            "SELECT rest_heal_pct, rest_charges FROM game_dungeons WHERE key = ?",
            (dungeon_key,),
        ).fetchone()
    except Exception:
        r = None
    if not r:
        return _REST_HEAL_PCT, 2
    pct = int(r["rest_heal_pct"] if r["rest_heal_pct"] is not None else _REST_HEAL_PCT)
    ch = r["rest_charges"]
    charges: int | None = None if ch is None else int(ch)
    if charges is not None and charges <= 0:  # convention: <=0 → unlimited
        charges = None
    return pct, charges


def _action_rest(conn: sqlite3.Connection, node: dict, content: dict,
                 character_id: int, run: dict) -> dict:
    """LB1 (#735): rest on a SAFE (cleared / enemy-free) tile. Heals per dungeon policy;
    onboarding = full heal + unlimited, others = limited % + charges ('radź sobie sam')."""
    enemies = content.get("enemies") or []
    if enemies and not node.get("cleared"):
        return {"ok": False, "action": "rest", "blocked": True, "trap": None,
                "narrative": "Najpierw pokonaj wrogów w tej komnacie, zanim odpoczniesz."}

    heal_pct, max_charges = _dungeon_rest_policy(conn, run.get("dungeon_key", ""))
    used = int(run.get("rest_used", 0))
    if max_charges is not None and used >= max_charges:
        return {"ok": True, "action": "rest", "no_charges": True, "trap": None,
                "narrative": "Brak sił na kolejny odpoczynek w tym lochu — radź sobie tym, co masz."}

    new_hp = _apply_heal_to_character(conn, character_id, heal_pct)
    node["rested"] = True
    run["rest_used"] = used + 1
    full = heal_pct >= 100
    charges_left = None if max_charges is None else max(0, max_charges - (used + 1))
    if full:
        note = "Pełny odpoczynek to udogodnienie tego lochu wprowadzającego — w głębszych lochach musisz radzić sobie sam."
        heal_txt = "pełne HP"
    else:
        note = f"Odpoczynek w tym lochu jest ograniczony ({heal_pct}% HP, pozostało: {charges_left})."
        heal_txt = f"{heal_pct}% maksymalnego HP"
    return {
        "ok": True, "action": "rest", "heal_pct": heal_pct, "hp_after": new_hp,
        "full_rest": full, "charges_left": charges_left, "onboarding_note": full,
        "trap": None,
        "narrative": f"Komnata jest oczyszczona i bezpieczna. Odpoczywasz — leczysz {heal_txt}. {note}",
    }


def resolve_tile_action(
    campaign_id: int,
    character_id: int,
    action: str,
    payload: dict | None = None,
) -> dict:
    """L6: Resolve non-combat tile action (open_chest / answer_riddle / riddle_hint / rest).

    Returns action result dict. U22 fallback: missing node → empty corridor response.
    Raises ValueError for unknown action or no active v2 run.
    """
    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run")
        if not run or run.get("system") != "tiles_v2":
            raise ValueError("Brak aktywnego lochu kafelkowego (v2).")

        tier = int(run.get("dungeon_difficulty", 1))
        graph = run.get("graph") or {}
        nodes = graph.get("nodes") or {}
        node_id = get_current_node_id(run, character_id)

        if not node_id or node_id not in nodes:
            return _empty_corridor_response(action)

        node = nodes[node_id]
        content = node.get("content") or {}

        if action == "open_chest":
            result = _action_open_chest(conn, node, content, character_id, tier, run)
        elif action == "answer_riddle":
            _resolve_riddle_in_content(conn, content)
            answer = (payload or {}).get("answer", "")
            result = _action_answer_riddle(node, content, answer, tier)
        elif action == "riddle_hint":
            _resolve_riddle_in_content(conn, content)
            result = _action_riddle_hint(node, content)
        elif action == "rest":
            result = _action_rest(conn, node, content, character_id, run)
        else:
            raise ValueError(f"Nieznana akcja: {action}")

        nodes[node_id] = node
        run["graph"]["nodes"] = nodes
        flags["dungeon_run"] = run
        _save_flags(conn, campaign_id, flags)
        return result
    finally:
        conn.close()


# ── Graph generation (L2) ─────────────────────────────────────────────────────

def _get_tile_content(tile: dict) -> dict:
    """Parse raw tile dict into content summary for graph storage.

    Enemy stats are NOT scaled here (L5 adds tier-based scaling via absolutna skala D1–D5).
    Riddle is stored as key only; full resolution happens in L3.
    """
    if not tile:
        return {
            "tile_id": None, "label": "???", "image_url": None,
            "room_description": "", "doors": [], "enemies": [],
            "items": [], "active_states": [], "exit_conditions": [],
            "riddle": None, "is_boss_tile": False,
        }
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
    # #722: auto-gate riddle tiles — safety net for seeds without exit_conditions_json set
    if tile.get("riddle_key") and not any(c.get("type") == "riddle_solved" for c in exit_conditions):
        exit_conditions.append({"type": "riddle_solved"})
    return {
        "tile_id": tile.get("id"),
        "label": tile.get("label", ""),
        "image_url": tile.get("image_url"),
        "room_description": tile.get("room_description") or "",
        "doors": _doors(tile),
        "enemies": enemies,
        "items": items,
        "active_states": active_states,
        "exit_conditions": exit_conditions,
        "riddle": tile.get("riddle_key"),
        "is_boss_tile": bool(tile.get("is_boss_tile") or 0),
    }


def _content_hint(content: dict) -> str:
    """Return a door hint string based on what's behind that door."""
    if content.get("is_boss_tile"):
        return _DOOR_HINTS["boss"]
    if content.get("enemies"):
        return _DOOR_HINTS["enemies"]
    if content.get("riddle"):
        return _DOOR_HINTS["riddle"]
    if content.get("items"):
        return _DOOR_HINTS["chest"]
    return _DOOR_HINTS["empty"]


def _is_reward_tile(tile: dict) -> bool:
    """True if tile has riddle or items (preferred for branch endings)."""
    if tile.get("riddle_key"):
        return True
    try:
        return len(json.loads(tile.get("items_json") or "[]")) > 0
    except Exception:
        return False


def _try_build_branch(
    branch_dir: str,
    parent_pos: list[int],
    non_boss_tiles: list[dict],
    used_positions: set[tuple[int, int]],
    tile_id_to_node_ids: dict[int, list[str]],
    all_nodes: dict[str, dict],
) -> list[dict] | None:
    """Try to build a 1–2 tile branch starting from parent_pos going branch_dir.

    Returns list of step dicts [{tile_id, entry_door, exit_door, position}] or None.
    Constraint: no tile can be placed adjacent to another node with the same tile_id.
    """
    entry_needed = OPPOSITE[branch_dir]
    dx, dy = OFFSET[branch_dir]
    first_pos = (parent_pos[0] + dx, parent_pos[1] + dy)
    if first_pos in used_positions:
        return None

    candidates = [t for t in non_boss_tiles if entry_needed in _doors(t)]
    if not candidates:
        return None

    def adjacent_repeat_ok(tile_id: int, pos: tuple[int, int]) -> bool:
        for existing_nid in tile_id_to_node_ids.get(tile_id, []):
            enode = all_nodes.get(existing_nid)
            if not enode:
                continue
            ep = tuple(enode["position"])
            if abs(ep[0] - pos[0]) + abs(ep[1] - pos[1]) <= 1:
                return False
        return True

    branch_length = random.randint(1, MAX_BRANCH_LENGTH)

    random.shuffle(candidates)
    if branch_length == 1:
        candidates = sorted(candidates, key=lambda t: 0 if _is_reward_tile(t) else 1)

    first_tile = None
    for cand in candidates:
        if adjacent_repeat_ok(cand["id"], first_pos):
            first_tile = cand
            break
    if first_tile is None:
        return None

    steps: list[dict] = [{
        "tile_id": first_tile["id"],
        "entry_door": entry_needed,
        "exit_door": None,
        "position": first_pos,
    }]
    if branch_length == 1:
        return steps

    # Attempt second tile
    free_exits = [d for d in _doors(first_tile) if d != entry_needed]
    random.shuffle(free_exits)
    for exit_dir in free_exits:
        dx2, dy2 = OFFSET[exit_dir]
        second_pos = (first_pos[0] + dx2, first_pos[1] + dy2)
        if second_pos in used_positions:
            continue
        second_entry = OPPOSITE[exit_dir]
        second_cands = [t for t in non_boss_tiles if second_entry in _doors(t)]
        random.shuffle(second_cands)
        second_cands = sorted(second_cands, key=lambda t: 0 if _is_reward_tile(t) else 1)
        for cand in second_cands:
            if adjacent_repeat_ok(cand["id"], second_pos):
                steps[0]["exit_door"] = exit_dir
                steps.append({
                    "tile_id": cand["id"],
                    "entry_door": second_entry,
                    "exit_door": None,
                    "position": second_pos,
                })
                return steps

    return steps  # 1-tile branch (no valid second tile found)


# Issue #697 (Decyzja 2b): safety cap on filler nodes. With multi-door pools and no
# 1-door „zaślepki", cap-fill would expand the grid indefinitely (each filler exposes
# new open doors). Caps the cascade; remaining open doors fall to the best-graph fallback.
_FILL_NODE_CAP = 60


def _adjacent_repeat_ok(
    tile_id: int,
    pos: tuple[int, int],
    tile_id_to_node_ids: dict[int, list[str]],
    all_nodes: dict[str, dict],
) -> bool:
    """No node with the same tile_id may sit orthogonally adjacent (Decyzja 9 constraint)."""
    for existing_nid in tile_id_to_node_ids.get(tile_id, []):
        enode = all_nodes.get(existing_nid)
        if not enode:
            continue
        ep = tuple(enode["position"])
        if abs(ep[0] - pos[0]) + abs(ep[1] - pos[1]) <= 1:
            return False
    return True


def _fill_open_doors(
    nodes: dict[str, dict],
    used_positions: set[tuple[int, int]],
    non_boss: list[dict],
    tile_id_to_node_ids: dict[int, list[str]],
    boss_nid: str | None = None,
) -> dict[str, dict]:
    """Issue #697: connect every drawn-but-open door so the d-pad matches the tile art.

    Repeats to a fixpoint:
      - Weld: an open door facing an EXISTING neighbour with the matching opposite open
        door is linked directly (no new tile; also closes path/branch shortcuts).
      - Cap-fill: an open door facing a FREE grid cell gets a 1-door „zaślepka" attached
        (a tile whose only door is the matching opposite). 1-door caps add no new open
        door — closure terminates without cascade (Decyzja 2b: „cap bez kaskady").
        Multi-door tiles are deliberately NOT used here: they would expose fresh open
        doors and expand the grid indefinitely. Respects the adjacent-same-tile rule.

    Issue #759: boss_nid is excluded from weld on BOTH sides — neither the boss's extra
    doors are welded to neighbours, nor neighbours' doors are welded to the boss.  Extra
    boss doors are left for cap-fill (1-door stubs, no shortcut possible).

    Open doors that cannot be closed (cell occupied by a non-matching neighbour, or no
    matching cap in the pool) are left as None for the caller's best-graph fallback.
    `pos_to_nid` and `used_positions` are kept live so two fillers never collide.
    """
    pos_to_nid: dict[tuple[int, int], str] = {
        tuple(n["position"]): nid for nid, n in nodes.items()
    }
    # Index 1-door zaślepki by their single door direction.
    caps_by_dir: dict[str, list[dict]] = {}
    for t in non_boss:
        d = _doors(t)
        if len(d) == 1:
            caps_by_dir.setdefault(d[0], []).append(t)

    fill_counter = 0
    progress = True
    while progress and fill_counter < _FILL_NODE_CAP:
        progress = False
        for nid in list(nodes.keys()):
            node = nodes[nid]
            # Issue #759: never weld boss's extra doors — boss stays a strict dead-end.
            skip_boss_weld = boss_nid is not None and nid == boss_nid
            for direction in list(node["doors_open"].keys()):
                if node["doors_open"][direction] is not None:
                    continue
                dx, dy = OFFSET[direction]
                px, py = node["position"]
                npos = (px + dx, py + dy)
                opp = OPPOSITE[direction]

                # Pass 1 — weld to an existing neighbour with a matching open door
                if npos in used_positions:
                    nbr_nid = pos_to_nid.get(npos)
                    if nbr_nid is not None and not skip_boss_weld and nbr_nid != boss_nid:
                        nbr_doors = nodes[nbr_nid]["doors_open"]
                        if opp in nbr_doors and nbr_doors[opp] is None:
                            node["doors_open"][direction] = nbr_nid
                            nbr_doors[opp] = nid
                            progress = True
                    # cell occupied (welded or mismatched) — cannot place a tile here
                    continue

                # Pass 2 — place a 1-door cap (never cascades). Caps are exempt from the
                # adjacent-same-tile rule: a 1-door stub only ever connects back to its
                # parent (never to a sibling cap), so two adjacent caps create no
                # "same room twice" path. With one cap per direction this exemption is
                # what lets a minimal cap set fully close every door.
                caps = caps_by_dir.get(opp, [])
                if fill_counter >= _FILL_NODE_CAP or not caps:
                    continue
                cap = caps[0]

                fill_nid = f"fill_{fill_counter}"
                fill_counter += 1
                nodes[fill_nid] = {
                    "tile_id": cap["id"],
                    "position": [npos[0], npos[1]],
                    "doors_open": {opp: nid},
                    "door_hints": {},
                    "content": _get_tile_content(cap),
                    "visited": False,
                    "cleared": False,
                    "is_boss": False,
                }
                node["doors_open"][direction] = fill_nid
                used_positions.add(npos)
                pos_to_nid[npos] = fill_nid
                tile_id_to_node_ids.setdefault(cap["id"], []).append(fill_nid)
                progress = True
    return nodes


def _count_open_doors(nodes: dict[str, dict]) -> int:
    return sum(
        1
        for n in nodes.values()
        for t in (n.get("doors_open") or {}).values()
        if t is None
    )


def _try_build_graph(
    non_boss: list[dict],
    boss_pool: list[dict],
    tile_count: int,
    boss_tile_id: int | None,
    enemy_hp: dict[str, int] | None = None,
    tier: int = 1,
    ease_in: bool = False,
) -> dict | None:
    """Try to build a branching graph. Returns graph dict or None on failure."""
    sequence = _try_build_path(
        non_boss, boss_pool, tile_count, boss_tile_id,
        enemy_hp=enemy_hp, tier=tier, ease_in=ease_in,
    )
    if sequence is None:
        return None

    all_tiles_by_id: dict[int, dict] = {t["id"]: t for t in non_boss + boss_pool}
    nodes: dict[str, dict] = {}
    used_positions: set[tuple[int, int]] = set()
    tile_id_to_node_ids: dict[int, list[str]] = {}

    # Build main path nodes
    for i, step in enumerate(sequence):
        nid = f"node_{i}"
        pos = tuple(step["position"])
        used_positions.add(pos)
        tile_id = step["tile_id"]
        tile = all_tiles_by_id.get(tile_id, {})

        doors_open: dict[str, str | None] = {d: None for d in _doors(tile)}
        if i > 0 and step.get("entry_door"):
            doors_open[step["entry_door"]] = f"node_{i - 1}"
        if i < len(sequence) - 1 and step.get("exit_door"):
            doors_open[step["exit_door"]] = f"node_{i + 1}"

        nodes[nid] = {
            "tile_id": tile_id,
            "position": list(pos),
            "doors_open": doors_open,
            "door_hints": {},
            "content": _get_tile_content(tile),
            "visited": False,
            "cleared": False,
            "is_boss": step.get("is_boss", False),
        }
        tile_id_to_node_ids.setdefault(tile_id, []).append(nid)

    # Add branches to non-boss main path nodes
    branch_count = 0
    for i in range(len(sequence) - 1):
        if branch_count >= MAX_BRANCHES:
            break
        parent_nid = f"node_{i}"
        parent = nodes[parent_nid]
        free_dirs = [d for d, t in parent["doors_open"].items() if t is None]
        if not free_dirs:
            continue
        if random.random() >= BRANCH_CHANCE:
            continue

        random.shuffle(free_dirs)
        for branch_dir in free_dirs:
            branch_steps = _try_build_branch(
                branch_dir, parent["position"],
                non_boss, used_positions, tile_id_to_node_ids, nodes,
            )
            if branch_steps is None:
                continue

            prev_nid = parent_nid
            first_branch_nid: str | None = None
            for bi, bstep in enumerate(branch_steps):
                bid = f"branch_{branch_count}_{bi}"
                if bi == 0:
                    first_branch_nid = bid
                bpos = tuple(bstep["position"])
                used_positions.add(bpos)
                btile_id = bstep["tile_id"]
                btile = all_tiles_by_id.get(btile_id, {})
                bdoors_open: dict[str, str | None] = {d: None for d in _doors(btile)}
                bdoors_open[bstep["entry_door"]] = prev_nid
                if bstep.get("exit_door") and bi < len(branch_steps) - 1:
                    bdoors_open[bstep["exit_door"]] = f"branch_{branch_count}_{bi + 1}"

                nodes[bid] = {
                    "tile_id": btile_id,
                    "position": list(bpos),
                    "doors_open": bdoors_open,
                    "door_hints": {},
                    "content": _get_tile_content(btile),
                    "visited": False,
                    "cleared": False,
                    "is_boss": False,
                }
                tile_id_to_node_ids.setdefault(btile_id, []).append(bid)
                if bi < len(branch_steps) - 1:
                    prev_nid = bid

            if first_branch_nid:
                parent["doors_open"][branch_dir] = first_branch_nid
            branch_count += 1
            break  # one branch attempt per parent node

    boss_nid = f"node_{len(sequence) - 1}"

    # Issue #697 (Decyzja 2b): close every drawn-but-open door so the d-pad matches
    # the tile art (weld neighbours + cap-fill free cells with 1-door zaślepki).
    # Issue #759: pass boss_nid so the boss stays a strict dead-end (no shortcut welds).
    _fill_open_doors(nodes, used_positions, non_boss, tile_id_to_node_ids, boss_nid=boss_nid)

    # Issue #759 option C: BFS safety-net — boss must not be reachable via a shortcut.
    # If shortest path entry→boss < len(sequence)-1, a shortcut slipped through;
    # return None so draw_tile_graph retries with a fresh layout.
    entry_nid = "node_0"
    required_depth = len(sequence) - 1
    if required_depth > 0:
        dist: dict[str, int] = {entry_nid: 0}
        queue = [entry_nid]
        while queue:
            cur = queue.pop(0)
            for tgt in nodes[cur]["doors_open"].values():
                if tgt is not None and tgt not in dist:
                    dist[tgt] = dist[cur] + 1
                    queue.append(tgt)
        boss_dist = dist.get(boss_nid)
        if boss_dist is not None and boss_dist < required_depth:
            return None  # shortcut exists — caller retries

    # Generate door hints for all nodes
    for node in nodes.values():
        hints: dict[str, str] = {}
        for direction, target_nid in node["doors_open"].items():
            if target_nid is not None:
                hints[direction] = _content_hint(nodes[target_nid]["content"])
        node["door_hints"] = hints

    return {
        "nodes": nodes,
        "entry_node": "node_0",
        "boss_node": boss_nid,
    }


def draw_tile_graph(
    category_key: str,
    tile_count: int,
    boss_tile_id: int | None = None,
    growth_cycle: int = 1,
    max_retries: int = 25,
    allowed_enemy_keys: set[str] | None = None,
    tier: int = 1,
) -> dict:
    """Generate a branching dungeon graph (dungeon_run v2 format).

    Main path of length `tile_count` (including boss) plus side branches:
    30% chance per non-boss tile with free doors, max 3 branches, 1–2 tiles each.
    Door hints assigned per direction from content type of the target node.

    Numbers Policy starting values (tuning after L19):
      BRANCH_CHANCE=0.30, MAX_BRANCHES=3, MAX_BRANCH_LENGTH=2

    Returns:
        {
          "nodes": {node_id: {tile_id, position, doors_open, door_hints,
                               content, visited, cleared, is_boss}},
          "entry_node": str,
          "boss_node": str,
        }
    Raises:
        ValueError if pool too small or all retries fail.
    """
    conn = _get_db()
    try:
        non_boss = _load_tiles(conn, category_key, include_boss=False)
        boss_pool = _load_tiles(conn, category_key, include_boss=True)
        if not boss_pool:
            boss_pool = non_boss
        available = len(non_boss) + len(boss_pool)
        if available < 2:
            raise ValueError(
                f"Category '{category_key}' has fewer than 2 tiles — cannot build dungeon"
            )
        tile_count = min(tile_count, available)
        # L18 (#733): enemy base-HP map for ease-in budgeting of the first combat rooms.
        enemy_hp = {
            r["key"]: int(r["hp_base"] or 0)
            for r in conn.execute("SELECT key, hp_base FROM game_config_enemies").fetchall()
        }
    finally:
        conn.close()

    # L18 (#733): ease-in only on the entry run (cycle 1) — endless segments keep full
    # difficulty since the hero is already strong by then.
    ease_in = growth_cycle == 1

    # L18 (#729): gate combat tiles to the dungeon's declared roster. Keep the full
    # pool as a fallback when filtering would starve path-building (never block entry).
    if allowed_enemy_keys:
        gated = [t for t in non_boss if _tile_enemies_allowed(t, allowed_enemy_keys)]
        if len(gated) + len(boss_pool) >= max(tile_count, 4):
            non_boss = gated
        else:
            import logging
            logging.getLogger(__name__).warning(
                "draw_tile_graph: '%s' enemy_pool gating left only %d non-boss tiles "
                "(< needed) — falling back to full pool", category_key, len(gated),
            )

    # Issue #697: prefer a graph with ZERO open doors. Keep the best (fewest open
    # doors) across retries; fall back to it (never block dungeon entry) + log.
    best: dict | None = None
    best_open: int | None = None
    for _ in range(max_retries):
        graph = _try_build_graph(
            non_boss, boss_pool, tile_count, boss_tile_id,
            enemy_hp=enemy_hp, tier=tier, ease_in=ease_in,
        )
        if not graph:
            continue
        open_doors = _count_open_doors(graph["nodes"])
        if open_doors == 0:
            return graph
        if best_open is None or open_doors < best_open:
            best, best_open = graph, open_doors

    if best is not None:
        if best_open:
            import logging
            logging.getLogger(__name__).warning(
                "draw_tile_graph: '%s' best graph still has %d open door(s) after %d "
                "retries — falling back (add 1-door zaślepki to the category to close them)",
                category_key, best_open, max_retries,
            )
        return best

    raise ValueError(
        f"Could not build valid dungeon graph in '{category_key}' after {max_retries} retries — "
        f"pool may be too small or door distribution unbalanced"
    )


# ── L7: Boss checkpoint ───────────────────────────────────────────────────────

def save_dungeon_checkpoint(campaign_id: int, character_id: int) -> dict:
    """L7: Save boss checkpoint after boss is defeated.

    Saves a world_state_snapshots row (source='dungeon_boss_checkpoint') and
    appends the checkpoint to run['checkpoints']. Sets run['at_checkpoint']=True.
    Called by L8 boss completion flow.
    """
    from app.services.world_state_service import save_snapshot

    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run") or {}
        char = conn.execute(
            "SELECT sheet_json, gold_gp FROM characters WHERE id = ?", (character_id,)  # #1181: legacy `gold` retired
        ).fetchone()
        if not char:
            return {}
        sheet = json.loads(char["sheet_json"] or "{}")
        inv_rows = conn.execute(
            """SELECT item_key, weapon_key, consumable_key, quantity, equipped
               FROM character_inventory WHERE character_id = ?""",
            (character_id,),
        ).fetchall()
        inventory = [dict(r) for r in inv_rows]
        turn_row = conn.execute(
            "SELECT MAX(turn_number) AS t FROM campaign_turns WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()
        turn_number = (turn_row["t"] or 0) if turn_row else 0

        xp_lifetime = int(sheet.get("xp_lifetime_earned") or 0)
        xp_available = int(sheet.get("xp_available") or 0)

        state_dict = {
            "current_hp": sheet.get("current_hp"),
            "max_hp": sheet.get("max_hp"),
            "current_mana": sheet.get("current_mana"),
            "gold_gp": char["gold_gp"],  # #1181: gold_gp is the sole gold column
            "inventory": inventory,
            "xp_lifetime_earned": xp_lifetime,
            "xp_available": xp_available,
        }

        snapshot_id = save_snapshot(campaign_id, turn_number, state_dict, source="dungeon_boss_checkpoint")

        checkpoint: dict[str, Any] = {
            "cycle": run.get("cycle", 1),
            "source": "dungeon_boss_checkpoint",
            "snapshot_id": snapshot_id,
            "xp_lifetime_earned": xp_lifetime,
            "xp_available": xp_available,
        }

        run.setdefault("checkpoints", []).append(checkpoint)
        run["at_checkpoint"] = True
        flags["dungeon_run"] = run
        _save_flags(conn, campaign_id, flags)

        return checkpoint
    finally:
        conn.close()


# ── L8: Boss cleared hook + endless extension ─────────────────────────────────

def on_boss_tile_cleared(campaign_id: int, character_id: int) -> dict:
    """L8: Called after combat victory clears a boss tile node.

    If current node is_boss_tile and boss_choice_pending not yet set:
    - Grants boss loot (rarity adjusted for endless cycle via get_boss_loot_rarity_for_cycle)
    - Saves boss checkpoint (L7 save_dungeon_checkpoint)
    - Sets run['boss_choice_pending'] = True
    Idempotent: second call returns early.
    Returns {is_boss_tile: bool, loot: list[dict]}
    """
    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run") or {}
        if not run or run.get("system") != "tiles_v2":
            return {"is_boss_tile": False, "loot": []}
        if run.get("boss_choice_pending"):
            return {"is_boss_tile": True, "loot": []}
        node_id = get_current_node_id(run, character_id)
        if not node_id:
            return {"is_boss_tile": False, "loot": []}
        node = (run.get("graph") or {}).get("nodes", {}).get(node_id) or {}
        content = node.get("content") or {}
        if not content.get("is_boss_tile"):
            return {"is_boss_tile": False, "loot": []}
        dungeon_key = run.get("dungeon_key", "")
        cycle = int(run.get("cycle", 1))
        dungeon_tier = int(run.get("dungeon_difficulty", 1))
        # Mark pending early to prevent double-grant on concurrent calls
        run["boss_choice_pending"] = True
        flags["dungeon_run"] = run
        _save_flags(conn, campaign_id, flags)
    finally:
        conn.close()

    from app.services.dungeon_service import (
        roll_boss_loot_for_endless, grant_dungeon_loot,
    )
    loot_items, loot_tier = roll_boss_loot_for_endless(dungeon_key, cycle)
    granted: list[dict] = []
    if loot_items:
        try:
            # Return the GRANTED rows (carry human `label`) — the raw roll only has
            # *_key columns, so the player-facing "co wypadło" reveal would show "?".
            granted = grant_dungeon_loot(character_id, campaign_id, loot_items, loot_tier=loot_tier)
        except Exception:
            granted = []

    # Checkpoint after loot granted (captures loot in inventory)
    try:
        save_dungeon_checkpoint(campaign_id, character_id)
    except Exception:
        pass

    return {"is_boss_tile": True, "loot": granted or loot_items}


def _is_cap_node(node: dict | None) -> bool:
    """True for a 1-door zaślepka (stub that only connects back to its parent)."""
    if not node or node.get("is_boss"):
        return False
    return len((node.get("content") or {}).get("doors") or []) == 1


def _attach_endless_segment(
    old_nodes: dict[str, dict],
    old_boss_nid: str,
    new_graph: dict,
    new_cycle: int,
    non_boss_caps: list[dict],
) -> dict:
    """Issue #698 (L-doors2): weld a freshly drawn segment onto the existing graph.

    After #697 the boss has EVERY door capped (0 free). The old "first free door"
    logic always fell into the `else` branch → orphaned cap + ghost door at the seam.

    This helper:
      - picks the seam from a pair of SPARE doors (unconnected or sealed by a 1-door
        cap) — one on the boss, one on the new entry, opposite-facing and both real
        doors of their tiles. A real-PATH door is never used (regression found by
        /playwright-test-report L13c 2026-06-16: attaching on the boss's path door
        orphaned the whole new segment + broke symmetry);
      - raises ValueError when no compatible spare pair exists, so the caller can
        regenerate the segment instead of forcing a bad weld;
      - removes the spare caps the weld replaces (both would be orphaned otherwise);
      - shifts the new segment so its entry occupies the freed boss-adjacent cell;
      - connects boss↔entry on both sides, then re-runs `_fill_open_doors` over the
        WHOLE merged graph to close any door freed by cap removal.

    Returns {"nodes", "boss_node", "entry_node"} for the merged graph.
    """
    # Work on copies so callers' dicts stay intact.
    merged_old = {
        nid: {**n, "doors_open": dict(n.get("doors_open") or {})}
        for nid, n in old_nodes.items()
    }

    new_nodes = new_graph.get("nodes") or {}
    new_entry_key = new_graph.get("entry_node") or "node_0"
    new_boss_key = new_graph.get("boss_node")
    cycle_prefix = f"c{new_cycle}_"

    # Remap new-segment nodes: cycle-prefixed IDs (positions shifted after seam pick).
    new_boss_nid: str | None = None
    remapped: dict[str, dict] = {}
    for old_nid, node in new_nodes.items():
        new_nid = cycle_prefix + old_nid
        if old_nid == new_boss_key:
            new_boss_nid = new_nid
        new_doors: dict[str, str | None] = {}
        for d, tgt in (node.get("doors_open") or {}).items():
            new_doors[d] = (cycle_prefix + tgt) if tgt else None
        remapped[new_nid] = {
            **node,
            "position": list(node["position"]),
            "doors_open": new_doors,
            "content": dict(node.get("content") or {}),
        }
    new_entry_nid = cycle_prefix + new_entry_key

    boss_node = merged_old.get(old_boss_nid) or {}
    boss_pos = list(boss_node.get("position") or [0, 0])
    boss_doors = dict(boss_node.get("doors_open") or {})
    boss_real = [d for d in DIRECTIONS if d in set((boss_node.get("content") or {}).get("doors") or [])]
    entry_node = remapped.get(new_entry_nid) or {}
    entry_doors = dict(entry_node.get("doors_open") or {})
    entry_real = [d for d in DIRECTIONS if d in set((entry_node.get("content") or {}).get("doors") or [])]

    def _spare(doors: dict, d: str, nodes_map: dict) -> bool:
        """A door is spare if unconnected (None) or sealed by a 1-door cap — it can
        host the seam WITHOUT detaching a real path."""
        tgt = doors.get(d)
        return tgt is None or _is_cap_node(nodes_map.get(tgt))

    # Seam = a spare door on BOTH sides, opposite-facing, real on both tiles.
    pairs: list[tuple[int, str, str]] = []
    for d in boss_real:
        if not _spare(boss_doors, d, merged_old):
            continue
        e = OPPOSITE[d]
        if e not in entry_real or not _spare(entry_doors, e, remapped):
            continue
        # Prefer removing caps on both sides (cleanest closure); deterministic tiebreak.
        cap_score = _is_cap_node(merged_old.get(boss_doors.get(d))) + _is_cap_node(
            remapped.get(entry_doors.get(e))
        )
        pairs.append((-cap_score, d, e))
    if not pairs:
        raise ValueError(
            "Brak zgodnej pary zapasowych drzwi na styku segmentów (#698) — przegeneruj segment."
        )
    pairs.sort(key=lambda x: (x[0], x[1]))
    _, attach_dir, opp_dir = pairs[0]

    # Drop the spare caps the weld replaces (both would be orphaned otherwise).
    boss_cap = boss_doors.get(attach_dir)
    if boss_cap and _is_cap_node(merged_old.get(boss_cap)):
        merged_old.pop(boss_cap, None)
    entry_cap = entry_doors.get(opp_dir)
    if entry_cap and _is_cap_node(remapped.get(entry_cap)):
        remapped.pop(entry_cap, None)

    # Shift the new segment so entry sits at boss_pos + offset(attach_dir).
    dx, dy = OFFSET.get(attach_dir, (0, 1))
    target_entry_pos = [boss_pos[0] + dx, boss_pos[1] + dy]
    entry_old_pos = list(remapped[new_entry_nid]["position"])
    pdx = target_entry_pos[0] - entry_old_pos[0]
    pdy = target_entry_pos[1] - entry_old_pos[1]
    for n in remapped.values():
        n["position"] = [n["position"][0] + pdx, n["position"][1] + pdy]

    # Weld both sides (both spare real doors → no ghost, no detached path).
    boss_doors[attach_dir] = new_entry_nid
    merged_old[old_boss_nid]["doors_open"] = boss_doors
    remapped[new_entry_nid]["doors_open"][opp_dir] = old_boss_nid

    all_nodes = {**merged_old, **remapped}

    # Re-seal the whole graph: close any door freed by cap removal (weld + cap-fill).
    # Issue #759: protect the new boss from shortcut welds.
    used_positions = {tuple(n["position"]) for n in all_nodes.values()}
    tile_id_to_node_ids: dict[int, list[str]] = {}
    for nid, n in all_nodes.items():
        tile_id_to_node_ids.setdefault(n.get("tile_id"), []).append(nid)
    _fill_open_doors(
        all_nodes, used_positions, non_boss_caps, tile_id_to_node_ids,
        boss_nid=new_boss_nid,
    )

    # Refresh door hints across the merged graph.
    for node in all_nodes.values():
        hints: dict[str, str] = {}
        for direction, tgt in node["doors_open"].items():
            if tgt is not None and tgt in all_nodes:
                hints[direction] = _content_hint(all_nodes[tgt]["content"])
        node["door_hints"] = hints

    return {
        "nodes": all_nodes,
        "boss_node": new_boss_nid or (cycle_prefix + "node_0"),
        "entry_node": new_entry_nid,
    }


def extend_dungeon_for_endless(campaign_id: int, character_id: int) -> dict:
    """L8: go_deeper — generate next segment and append to existing graph.

    New segment length = tile_count + endless_growth_n × (new_cycle − 1).
    New nodes use cycle-prefixed IDs to avoid collisions.
    Seam is welded via `_attach_endless_segment` (Issue #698): attach direction is
    chosen from the boss's real doors, orphaned caps removed, whole graph re-sealed.
    Positions (col, row) continue the existing grid.
    """
    from app.services.dungeon_service import get_dungeon

    # Read current run state
    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run") or {}
        if not run or run.get("system") != "tiles_v2":
            raise ValueError("Brak aktywnego lochu kafelkowego (v2).")
        current_cycle = int(run.get("cycle", 1))
        dungeon_key = run.get("dungeon_key", "")
        old_graph = run.get("graph") or {}
        old_nodes = dict(old_graph.get("nodes") or {})
        old_boss_nid = old_graph.get("boss_node") or ""
    finally:
        conn.close()

    new_cycle = current_cycle + 1

    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        raise ValueError("Dungeon not found.")
    category_key = dungeon.get("tile_category_key")
    if not category_key:
        raise ValueError("Brak kategorii kafelków dla trybu endless.")

    base_tile_count = int(dungeon.get("tile_count") or dungeon.get("rooms") or 4)
    endless_growth_n = int(dungeon.get("endless_growth_n") or 0)
    boss_tile_id = dungeon.get("boss_tile_id")

    # L18 (#729): keep endless segments on the dungeon's declared roster too.
    _ep_raw = dungeon.get("enemy_pool") or "[]"
    try:
        _ep = json.loads(_ep_raw) if isinstance(_ep_raw, str) else list(_ep_raw)
    except Exception:
        _ep = []
    allowed_enemy_keys = {k for k in _ep if k} or None

    # Length = tile_count + n × (new_cycle − 1)
    new_tile_count = max(2, base_tile_count + endless_growth_n * (new_cycle - 1))

    # Load the cap pool so _attach_endless_segment can re-seal freed doors.
    conn2 = _get_db()
    try:
        non_boss_caps = _load_tiles(conn2, category_key, include_boss=False)
    finally:
        conn2.close()

    # Issue #698: weld the segment onto a SPARE boss door (cap/free) matched to a spare
    # entry door — never a real-path door. If the freshly drawn segment has no entry
    # door compatible with a spare boss door, regenerate it (draw is randomised, so a
    # retry usually yields a compatible entry) before giving up.
    merged = None
    last_err: Exception | None = None
    for _ in range(12):
        new_graph = draw_tile_graph(
            category_key, new_tile_count, boss_tile_id, growth_cycle=new_cycle,
            allowed_enemy_keys=allowed_enemy_keys,
        )
        try:
            merged = _attach_endless_segment(
                old_nodes, old_boss_nid, new_graph, new_cycle, non_boss_caps
            )
            break
        except ValueError as e:
            last_err = e
            continue
    if merged is None:
        raise ValueError(
            f"Nie udało się doczepić segmentu endless po 12 próbach: {last_err}"
        )
    all_nodes = merged["nodes"]
    new_entry_nid = merged["entry_node"]

    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run") or {}
        run["graph"]["nodes"] = all_nodes
        run["graph"]["boss_node"] = merged["boss_node"]
        run["cycle"] = new_cycle
        run["at_checkpoint"] = False
        run["boss_choice_pending"] = False
        flags["dungeon_run"] = run
        _save_flags(conn, campaign_id, flags)
        return {
            "ok": True,
            "new_cycle": new_cycle,
            "new_segment_tile_count": new_tile_count,
            "new_entry_node": new_entry_nid,
            "new_boss_node": run["graph"]["boss_node"],
        }
    finally:
        conn.close()
