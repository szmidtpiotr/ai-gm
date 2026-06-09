"""Dungeon run service — Task 41 V2 (room types, riddles, loot tiers, death handling)."""
from __future__ import annotations
import json
import random
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

DB_PATH = "/data/ai_gm.db"

# Room type weights default (boss always last, not in weights)
DEFAULT_ROOM_WEIGHTS = {"combat": 50, "chest": 15, "trap": 15, "riddle": 10, "rest": 10}


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


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
        cooldown_until_str = str(row["cooldown_until"] or "")
        run_count = int(row["run_count"] or 0)
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
    cooldown_hours = int(dungeon.get("cooldown_hours") or 72)
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


# ── Enemy scaling ─────────────────────────────────────────────────────────────

_SCALE_TABLE = [(2, 0.75), (4, 1.0), (6, 1.25), (8, 1.5), (99, 2.0)]
_DIE_PROGRESSION = ["d4", "d6", "d8", "d10", "d12"]


def _level_multiplier(hero_level: int) -> float:
    for max_level, mult in _SCALE_TABLE:
        if hero_level <= max_level:
            return mult
    return 2.0


def _scale_die_up(die_expr: str) -> str:
    m = re.match(r"^(\d*)d(\d+)$", (die_expr or "1d6").strip().lower())
    if not m:
        return die_expr
    n = m.group(1) or "1"
    sides = int(m.group(2))
    try:
        idx = _DIE_PROGRESSION.index(f"d{sides}")
        return f"{n}{_DIE_PROGRESSION[min(idx + 1, len(_DIE_PROGRESSION) - 1)]}"
    except ValueError:
        return die_expr


def scale_enemy_stats(base: dict, hero_level: int, is_boss: bool = False) -> dict:
    mult = _level_multiplier(hero_level)
    if is_boss:
        tiers = [t[1] for t in _SCALE_TABLE]
        idx = tiers.index(mult) if mult in tiers else 0
        mult = tiers[min(idx + 1, len(tiers) - 1)]
    scaled = dict(base)
    scaled["hp_base"] = max(1, round(int(base.get("hp_base", 5)) * mult))
    scaled["ac_base"] = max(5, round(int(base.get("ac_base", 8)) * (1 + (mult - 1) * 0.3)))
    if mult >= 1.5:
        scaled["damage_die"] = _scale_die_up(str(base.get("damage_die", "1d6")))
    return scaled


# ── Room type generation ──────────────────────────────────────────────────────

def _pick_room_type(weights: dict[str, int]) -> str:
    """Weighted random pick among non-boss room types."""
    pool = [t for t in weights if t != "boss"]
    w = [max(1, weights.get(t, 1)) for t in pool]
    return random.choices(pool, weights=w, k=1)[0]


def _get_riddle_for_theme(conn: sqlite3.Connection, theme: str | None = None, difficulty: int | None = None) -> dict | None:
    """Pick a random active riddle from the bank, optionally filtered."""
    clauses, params = ["is_active = 1"], []
    if theme:
        clauses.append("theme = ?"); params.append(theme)
    if difficulty:
        clauses.append("difficulty <= ?"); params.append(difficulty)
    rows = conn.execute(
        f"SELECT * FROM game_config_riddles WHERE {' AND '.join(clauses)} ORDER BY RANDOM() LIMIT 1",
        params
    ).fetchall()
    if not rows:
        rows = conn.execute("SELECT * FROM game_config_riddles WHERE is_active = 1 ORDER BY RANDOM() LIMIT 1").fetchall()
    return dict(rows[0]) if rows else None


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


# ── Dungeon instance generation ───────────────────────────────────────────────

def _build_dungeon_instance(dungeon: dict, hero_level: int) -> dict:
    """Build a dungeon run instance dict from a dungeon config dict."""
    dungeon_key = dungeon.get("key", "")
    dungeon_difficulty = int(dungeon.get("dungeon_difficulty") or 1)
    pool = json.loads(dungeon.get("enemy_pool") or "[]")
    num_rooms = int(dungeon.get("rooms") or 5)
    boss_key = dungeon.get("boss_enemy") or (pool[-1] if pool else None)
    atmosphere = dungeon.get("atmosphere") or ""
    cooldown_hours = int(dungeon.get("cooldown_hours") or 72)
    room_loot_chance = float(dungeon.get("room_loot_chance") or 0.15)
    riddle_source = str(dungeon.get("riddle_source") or "database")
    riddle_max_hints = int(dungeon.get("riddle_max_hints") or 2)

    try:
        weights = json.loads(dungeon.get("room_types_json") or "{}")
    except Exception:
        weights = {}
    weights = {**DEFAULT_ROOM_WEIGHTS, **weights}

    conn = _get_db()
    try:
        # Cache enemy stats
        enemy_cache: dict[str, dict] = {}
        for ek in set(pool + ([boss_key] if boss_key else [])):
            row = conn.execute(
                "SELECT key, label, hp_base, ac_base, attack_bonus, damage_die, damage_bonus, dex_modifier, tier FROM game_config_enemies WHERE key = ?",
                (ek,)
            ).fetchone()
            if row:
                enemy_cache[ek] = dict(row)

        # Ensure first and last rooms are always combat/boss
        rooms = []
        for room_num in range(1, num_rooms + 1):
            is_boss = (room_num == num_rooms)
            if room_num == 1:
                room_type = "combat"
            elif is_boss:
                room_type = "boss"
            else:
                room_type = _pick_room_type(weights)

            room: dict[str, Any] = {
                "room_id": room_num,
                "room_type": room_type,
                "is_boss": is_boss,
                "cleared": False,
                "room_loot_chance": room_loot_chance,
            }

            if room_type in ("combat", "boss"):
                enemy_key = boss_key if is_boss else (random.choice(pool) if pool else None)
                enemy_count = 1 if is_boss else min(4, max(1, 1 + hero_level // 3))
                base_stats = enemy_cache.get(enemy_key, {}) if enemy_key else {}
                scaled = scale_enemy_stats(base_stats, hero_level, is_boss) if base_stats else base_stats
                room["enemy_key"] = enemy_key
                room["enemy_count"] = enemy_count
                room["enemy_stats"] = scaled
                room["enemy_label"] = base_stats.get("label", enemy_key or "")
                room["rarity"] = get_loot_rarity_for_difficulty(dungeon_difficulty, is_boss=is_boss)
            elif room_type == "riddle":
                riddle = _get_riddle_for_theme(conn)
                if riddle:
                    room["riddle_key"] = riddle["key"]
                    room["riddle_text"] = riddle["text"]
                    room["riddle_answer"] = riddle["answer"]
                    room["riddle_answer_alts"] = json.loads(riddle.get("answer_alts") or "[]")
                    hints = json.loads(riddle.get("hints") or "[]")
                    room["riddle_hints"] = hints[:riddle_max_hints]
                    room["riddle_max_hints"] = riddle_max_hints
                    room["riddle_hints_used"] = 0
                    room["riddle_source"] = riddle_source
                else:
                    # No riddles in DB — fall back to combat
                    room["room_type"] = "combat"
                    enemy_key = random.choice(pool) if pool else None
                    base_stats = enemy_cache.get(enemy_key, {}) if enemy_key else {}
                    room["enemy_key"] = enemy_key
                    room["enemy_count"] = 1
                    room["enemy_stats"] = scale_enemy_stats(base_stats, hero_level) if base_stats else base_stats
                    room["enemy_label"] = base_stats.get("label", enemy_key or "")
            elif room_type == "trap":
                traps = [
                    {"name": "Pająki", "save_stat": "DEX", "dc": 12, "damage": "1d6",
                     "description": "Z sufitu sypią się jadowite pająki!"},
                    {"name": "Ognista Pułapka", "save_stat": "DEX", "dc": 14, "damage": "2d4",
                     "description": "Na podłodze widać dziwne symbole — za późno!"},
                    {"name": "Trujące Opary", "save_stat": "CON", "dc": 13, "damage": "1d4",
                     "description": "Powietrze gęstnieje od zielonkawej mgiełki."},
                    {"name": "Zawalający się Sufit", "save_stat": "DEX", "dc": 11, "damage": "1d8",
                     "description": "Słyszysz pęknięcia powyżej!"},
                    {"name": "Błysk Runicznej Kuli", "save_stat": "WIS", "dc": 12, "damage": "1d6",
                     "description": "Runy na ścianie zaczynają świecić złowrogim blaskiem."},
                ]
                room["trap"] = random.choice(traps)
            elif room_type == "chest":
                room["chest_loot_table"] = dungeon.get("chest_loot_table_key") or ""
                room["rarity"] = get_loot_rarity_for_difficulty(dungeon_difficulty, is_boss=False)
            elif room_type == "rest":
                heal_pct = random.choice([15, 20, 25, 30])
                rest_descriptions = [
                    "Między walkami natykasz się na małą jaskinię z podziemnym źródełkiem.",
                    "W bocznej komnacie stoi porzucona mieszanka ziół — dawny obóz awanturników.",
                    "Znalazłeś spokojną grotę, dobre miejsce na chwilę wytchnienia.",
                    "Słabe promienie z podziemnego kryształu kojąco wpływają na twoje rany.",
                ]
                room["rest_heal_pct"] = heal_pct
                room["rest_description"] = random.choice(rest_descriptions)

            # Map coordinates — linear for now, supports branching later
            room["map_col"] = room_num - 1
            room["map_row"] = 0

            rooms.append(room)

    finally:
        conn.close()

    return {
        "dungeon_key": dungeon_key,
        "dungeon_label": dungeon.get("label", dungeon_key),
        "dungeon_difficulty": dungeon_difficulty,
        "atmosphere": atmosphere,
        "rooms": rooms,
        "total_rooms": num_rooms,
        "current_room": 1,
        "completed": False,
        "failed": False,
        "hero_level_at_entry": hero_level,
        "cooldown_hours": cooldown_hours,
        "chest_loot_table_key": dungeon.get("chest_loot_table_key") or "",
        "boss_loot_table_key": dungeon.get("boss_loot_table_key") or "",
        "loot_collected": [],
    }


def generate_dungeon_instance(dungeon_key: str, hero_level: int) -> dict:
    dungeon = get_dungeon(dungeon_key)
    if not dungeon:
        raise ValueError(f"Dungeon not found: {dungeon_key}")
    return _build_dungeon_instance(dungeon, hero_level)


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


def enter_dungeon(campaign_id: int, character_id: int, dungeon_key: str,
                  hero_level: int, previous_campaign_id: int | None = None) -> dict:
    cd = check_cooldown(character_id, dungeon_key)
    if cd.get("on_cooldown"):
        raise PermissionError(f"dungeon_on_cooldown:{cd.get('cooldown_until')}:{cd.get('hours_remaining')}")

    instance = generate_dungeon_instance(dungeon_key, hero_level)

    conn, flags = _load_flags(campaign_id)
    try:
        flags["dungeon_run"] = instance
        if previous_campaign_id:
            flags["dungeon_previous_campaign_id"] = previous_campaign_id
        _save_flags(conn, campaign_id, flags)
    finally:
        conn.close()

    return instance


def advance_room(campaign_id: int) -> dict:
    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run")
        if not run:
            raise ValueError("No active dungeon run")
        current = int(run.get("current_room", 1))
        total = int(run.get("total_rooms", 1))
        for r in run["rooms"]:
            if r["room_id"] == current:
                r["cleared"] = True
                break
        if current >= total:
            run["completed"] = True
        else:
            run["current_room"] = current + 1
        flags["dungeon_run"] = run
        _save_flags(conn, campaign_id, flags)
        return run
    finally:
        conn.close()


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


# ── Non-combat room resolution ────────────────────────────────────────────────

def resolve_room(campaign_id: int, character_id: int, player_input: str | None = None) -> dict:
    """
    Resolve the current non-combat room (riddle/trap/chest/rest).
    Returns {success, narrative, loot, heal_pct, advance_available}.
    """
    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run")
        if not run:
            raise ValueError("No active dungeon run")

        current = int(run.get("current_room", 1))
        room = next((r for r in run["rooms"] if r["room_id"] == current), None)
        if not room:
            raise ValueError("Room not found")

        room_type = room.get("room_type", "combat")
        result: dict[str, Any] = {"success": True, "loot": [], "heal_pct": 0, "advance_available": True}

        if room_type == "riddle":
            if not player_input:
                # Return hint if available
                hints_used = int(room.get("riddle_hints_used", 0))
                hints = room.get("riddle_hints", [])
                if hints_used < len(hints):
                    hint = hints[hints_used]
                    room["riddle_hints_used"] = hints_used + 1
                    result["success"] = False
                    result["advance_available"] = False
                    result["hint"] = hint
                    result["hints_used"] = hints_used + 1
                    result["hints_remaining"] = len(hints) - (hints_used + 1)
                    result["narrative"] = f"Podpowiedź: {hint}"
                else:
                    # Out of hints — fail
                    result["success"] = False
                    result["advance_available"] = True
                    result["narrative"] = "Wyczerpałeś wskazówki. Kamienna płyta uderza cię za karę!"
                    result["fail_damage"] = "1d4"
            else:
                answer = room.get("riddle_answer", "")
                alts = room.get("riddle_answer_alts", [])
                if _answer_matches(player_input, answer, alts):
                    result["success"] = True
                    result["narrative"] = "Zagadka rozwiązana! Drzwi otwierają się ze skrzypnięciem."
                    # Small bonus loot for solving
                    room["cleared"] = True
                else:
                    hints_used = int(room.get("riddle_hints_used", 0))
                    hints = room.get("riddle_hints", [])
                    max_hints = int(room.get("riddle_max_hints", 2))
                    if hints_used < len(hints) and hints_used < max_hints:
                        hint = hints[hints_used]
                        room["riddle_hints_used"] = hints_used + 1
                        result["success"] = False
                        result["advance_available"] = False
                        result["hint"] = hint
                        result["narrative"] = f"Błędna odpowiedź. Podpowiedź: {hint}"
                    else:
                        result["success"] = False
                        result["advance_available"] = True
                        result["narrative"] = "Odpowiedź błędna. Mechanizm pułapkowy cię karze!"
                        result["fail_damage"] = "1d4"

        elif room_type == "trap":
            trap = room.get("trap", {})
            # Roll a DEX/CON/WIS save — simplified: ~50% success for now, frontend can animate
            success = random.random() < 0.5
            if success:
                result["narrative"] = f"{trap.get('description', '')} Udaje ci się uniknąć!"
            else:
                result["success"] = False
                result["fail_damage"] = trap.get("damage", "1d4")
                result["save_stat"] = trap.get("save_stat", "DEX")
                result["narrative"] = f"{trap.get('description', '')} Nie zdążyłeś!"
            room["cleared"] = True

        elif room_type == "chest":
            loot_table = room.get("chest_loot_table") or run.get("chest_loot_table_key") or ""
            loot = _roll_loot_table(conn, loot_table) if loot_table else []
            result["loot"] = loot
            result["narrative"] = "Otwierasz skrzynię. " + (
                f"W środku znajdujesz {len(loot)} przedmiot(y)!" if loot else "Skrzynia jest pusta.")
            room["cleared"] = True

        elif room_type == "rest":
            heal_pct = int(room.get("rest_heal_pct", 20))
            desc = room.get("rest_description", "Odpoczywasz przez chwilę.")
            result["heal_pct"] = heal_pct
            result["narrative"] = f"{desc} Leczysz {heal_pct}% maksymalnego HP."
            room["cleared"] = True

        flags["dungeon_run"] = run
        _save_flags(conn, campaign_id, flags)
        return result
    finally:
        conn.close()


def grant_dungeon_loot(character_id: int, campaign_id: int, loot_items: list[dict]) -> list[dict]:
    """Grant loot items to character inventory."""
    if not loot_items:
        return []
    try:
        from app.services.loot_service import grant_loot_to_character
        return grant_loot_to_character(character_id, loot_items, source="dungeon")
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


def restore_dungeon_entry_snapshot(campaign_id: int, character_id: int) -> bool:
    """Restore character HP/gold/inventory from the dungeon_enter snapshot."""
    conn = _get_db()
    try:
        row = conn.execute(
            """SELECT snapshot_json FROM world_state_snapshots
               WHERE campaign_id = ? AND snapshot_source = 'dungeon_enter'
               ORDER BY id DESC LIMIT 1""",
            (campaign_id,)
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

        conn.execute(
            "UPDATE characters SET sheet_json = ?, gold = ?, gold_gp = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), snap.get("gold", 0), snap.get("gold_gp", 0), character_id)
        )

        inventory = snap.get("inventory") or []
        conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (character_id,))
        for item in inventory:
            conn.execute(
                """INSERT INTO character_inventory
                       (character_id, item_key, weapon_key, consumable_key, quantity, equipped)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (character_id, item.get("item_key"), item.get("weapon_key"),
                 item.get("consumable_key"), item.get("quantity", 1), item.get("equipped", 0))
            )
        conn.commit()
        return True
    finally:
        conn.close()


def _reset_dungeon_run(run: dict) -> dict:
    """Reset an in-progress run back to room 1 with all rooms un-cleared."""
    run["current_room"] = 1
    run["completed"] = False
    run["failed"] = False
    for room in run.get("rooms", []):
        room["cleared"] = False
    return run


def handle_dungeon_death(campaign_id: int, character_id: int) -> dict:
    """Hero died in dungeon. Restore entry snapshot and restart run from room 1."""
    conn, flags = _load_flags(campaign_id)
    try:
        run = flags.get("dungeon_run")
        if not run:
            return {"ok": True, "restored": False, "restarted": False}
        death_mode = _get_meta(conn, "dungeon_death_hp_mode", "campaign_state")
        dungeon_key = run.get("dungeon_key", "")
        _reset_dungeon_run(run)
        flags["dungeon_run"] = run
        _save_flags(conn, campaign_id, flags)
    finally:
        conn.close()

    restored = restore_dungeon_entry_snapshot(campaign_id, character_id)

    return {
        "ok": True,
        "death_mode": death_mode,
        "dungeon_key": dungeon_key,
        "restored": restored,
        "restarted": True,
    }
