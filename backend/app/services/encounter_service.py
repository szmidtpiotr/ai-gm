"""Encounter injection service — automated GM encounter triggering."""
import json
import random
import re
import sqlite3
import unicodedata

import structlog

from app.services.encounter_config_service import get_encounter_config

logger = structlog.get_logger()

# D7 (#382) — base chance the generic template fallback fires when it matches
# (so it isn't guaranteed every eligible turn). Scaled by the dwell multiplier.
TEMPLATE_FALLBACK_BASE_PROB = 0.5


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text).lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:48] or "enemy"


def _parse_stat(notes: str, pattern: str, default: int) -> int:
    m = re.search(pattern, notes, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, IndexError):
            pass
    return default


def ensure_encounter_enemies_in_db(conn: sqlite3.Connection, encounter: dict) -> dict:
    """
    For each enemy in encounter.enemies[], ensure a game_config_enemies row exists.
    Parses HP/AC/attack/damage from notes text if present.
    Creates a loot table stub if the enemy has none.
    Adds/updates enemy_key field in the enemy dict.
    Returns the (possibly mutated) encounter dict.
    """
    enemies = encounter.get("enemies") or []
    for enemy in enemies:
        name = str(enemy.get("name") or "").strip()
        if not name:
            continue
        notes = str(enemy.get("notes") or "")

        # Derive key
        existing_key = str(enemy.get("enemy_key") or "").strip()
        key = existing_key or _slugify(name)
        if not key:
            continue

        # Check if already in DB
        existing = conn.execute(
            "SELECT key FROM game_config_enemies WHERE key = ?", (key,)
        ).fetchone()

        if not existing:
            # Parse stats from notes (fallback to safe defaults)
            hp = _parse_stat(notes, r"HP\s*bazowe?\s*(\d+)", 15)
            ac = _parse_stat(notes, r"AC\s*bazowe?\s*(\d+)", 12)
            atk = _parse_stat(notes, r"atak\s*\+(\d+)", 2)
            dmg_m = re.search(r"obrażenia\s+(\d+d\d+)", notes, re.IGNORECASE)
            dmg_die = dmg_m.group(1) if dmg_m else "1d6"
            dmg_type_m = re.search(r"(\d+d\d+)\s+(fizyczne|ogień|lód|błyskawica|kwas|nekro|psycho|święte)", notes, re.IGNORECASE)
            dmg_type = dmg_type_m.group(2).lower() if dmg_type_m else "physical"
            # Map Polish damage type names
            _dmg_type_map = {
                "fizyczne": "physical", "ogień": "fire", "lód": "ice",
                "błyskawica": "lightning", "kwas": "acid",
                "nekro": "necrotic", "psycho": "psychic", "święte": "holy",
            }
            dmg_type = _dmg_type_map.get(dmg_type, dmg_type)

            count = int(enemy.get("count") or 1)
            tier = "standard"
            if hp >= 50 or count == 1:
                tier = "elite"

            loot_key = f"loot_{key}"
            conn.execute(
                """
                INSERT INTO game_config_enemies
                  (key, label, hp_base, ac_base, attack_bonus, damage_die,
                   damage_type, tier, xp_award, loot_table_key, drop_chance,
                   description, review_status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    key, name, hp, ac, atk, dmg_die, dmg_type, tier,
                    max(10, hp * 2),
                    loot_key, 1.0,
                    notes[:300] if notes else "",
                    "pending_review",
                ),
            )
            # Create a minimal loot table stub so combat engine finds it
            conn.execute(
                "INSERT OR IGNORE INTO game_config_loot_tables (key, label, gold_min, gold_max) VALUES (?,?,?,?)",
                (loot_key, f"Łupy: {name}", 1, 5),
            )

        enemy["enemy_key"] = key

    encounter["enemies"] = enemies
    return encounter


def maybe_inject_encounter(
    conn: sqlite3.Connection,
    campaign_id: int,
    trigger: str,
    q: int = None,
    r: int = None,
) -> bool:
    """
    Check if an encounter should fire for the given trigger event.
    Returns True if encounter was injected into session_flags.active_encounter.

    trigger values: 'hex_enter', 'n_turns', 'combat_end'
    q, r: hex coordinates of current hex (for biome/pool filtering)
    """
    try:
        # 1. Skip if active_encounter already set or in COMBAT/SKILL_TEST_PENDING state
        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not gs:
            return False
        sf = json.loads(gs["session_flags"] or "{}")
        if sf.get("active_encounter"):
            return False
        if sf.get("state") in ("COMBAT", "SKILL_TEST_PENDING"):
            return False

        # 1b. D7 (#382) — safety gate: no random encounters in safe locations
        #     (tavern/settlement marked safe_for_rest). Same hex, different
        #     narrative location — sitting in a room ≠ ambush.
        if is_encounter_blocked_by_location(conn, sf):
            return False

        # 1c. Dwell decay: the longer the hero has settled in one location doing
        #     things, the lower the encounter chance (occupied, not exploring).
        try:
            _settle = int(get_encounter_config(conn=conn).get("dwell_settle_turns", 3))
        except Exception:
            _settle = 3
        dwell = dwell_chance_multiplier(sf.get("turns_at_location", 0), settle_turns=_settle)

        # 2. Get hex context for biome/pool filtering
        hex_type = None
        hex_pool = []
        if q is not None and r is not None:
            hex_row = conn.execute(
                "SELECT hex_type, forge_encounter_pool FROM world_hexes WHERE q=? AND r=? AND is_active=1 LIMIT 1",
                (q, r),
            ).fetchone()
            if hex_row:
                hex_type = hex_row["hex_type"]
                try:
                    hex_pool = json.loads(hex_row["forge_encounter_pool"] or "[]")
                except Exception:
                    hex_pool = []

        # 3. Load candidate encounter hooks (restricted to hex pool if set, else all approved)
        if hex_pool:
            placeholders = ",".join("?" * len(hex_pool))
            rows = conn.execute(
                f"SELECT id, draft_data FROM adventure_hooks WHERE id IN ({placeholders}) AND status IN ('approved','promoted')",
                hex_pool,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, draft_data FROM adventure_hooks WHERE draft_data LIKE '%\"encounter\"%' AND status IN ('approved','promoted') ORDER BY id",
            ).fetchall()

        # 4. Filter by trigger type, biome and player level (E13/E14 #428/#429)
        hero_level = _hero_level_for_campaign(conn, campaign_id)
        candidates = []
        for row in rows:
            try:
                dd = json.loads(row["draft_data"] or "{}")
                enc = dd.get("encounter")
                if not enc:
                    continue
                if not encounter_matches(enc, trigger=trigger, hex_type=hex_type, hero_level=hero_level):
                    continue
                prob = float(enc.get("trigger_probability") or 0.25)
                candidates.append((prob, enc, row["id"]))
            except Exception:
                continue

        # 5. Shuffle, roll each candidate (chance scaled by dwell decay), first
        #    that fires wins. No early return — fall through to the generic
        #    template fallback (step 6) when no hook candidate fires.
        random.shuffle(candidates)
        for prob, enc, hook_id in candidates:
            if random.random() <= prob * dwell:
                enc = ensure_encounter_enemies_in_db(conn, enc)
                sf["active_encounter"] = enc
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                    (json.dumps(sf, ensure_ascii=False), campaign_id),
                )
                conn.commit()
                logger.info(
                    "encounter_auto_injected",
                    trigger=trigger,
                    hook_id=hook_id,
                    campaign_id=campaign_id,
                    hex_type=hex_type,
                )
                return True

        return False

        # 6. D7 (#382) — fallback: no adventure_hook fired → try a GENERIC template
        #    from gameconfig_encounter_templates matched by hero level + terrain tag.
        level = _hero_level_for_campaign(conn, campaign_id)
        tmpl = select_encounter_template(conn, level=level, location_tag=hex_type)
        if tmpl:
            enc = {
                "label": tmpl.get("label"),
                "source": "template",
                "template_key": tmpl.get("key"),
                "difficulty": tmpl.get("difficulty"),
                "trigger": trigger,
                "enemies": [
                    {"enemy_key": e.get("key"), "name": e.get("key"),
                     "count": int(e.get("count") or 1)}
                    for e in tmpl.get("enemies", []) if e.get("key")
                ],
            }
            if enc["enemies"] and random.random() <= TEMPLATE_FALLBACK_BASE_PROB * dwell:
                sf["active_encounter"] = enc
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                    (json.dumps(sf, ensure_ascii=False), campaign_id),
                )
                conn.commit()
                logger.info(
                    "encounter_template_injected", trigger=trigger,
                    template_key=tmpl.get("key"), campaign_id=campaign_id,
                    level=level, hex_type=hex_type,
                )
                return True

        return False

    except Exception as exc:
        logger.warning("maybe_inject_encounter_error", error=str(exc), campaign_id=campaign_id)
        return False


def encounter_matches(enc: dict, *, trigger: str, hex_type: str | None, hero_level: int) -> bool:
    """E13/E14 (#428/#429) — does an encounter qualify for the current context?

    Gates: trigger type, biome (vs hex_type) and player level band
    (level_min/level_max). An encounter with no level bounds fits any level;
    one with no biomes fits any biome.
    """
    if not isinstance(enc, dict):
        return False
    triggers = enc.get("trigger_types") or ["hex_enter"]
    if trigger not in triggers:
        return False
    biomes = enc.get("biomes") or []
    if biomes and hex_type and hex_type not in biomes:
        return False
    # E14 — level scaling: skip too-hard (below min) and too-easy (above max).
    lvl = int(hero_level or 1)
    lmin = enc.get("level_min")
    if lmin is not None and lvl < int(lmin):
        return False
    lmax = enc.get("level_max")
    if lmax is not None and int(lmax) > 0 and lvl > int(lmax):
        return False
    return True


def is_encounter_blocked_by_location(conn: sqlite3.Connection, session_flags: dict) -> bool:
    """D7 (#382) — żadnych losowych encounterów w bezpiecznej lokacji (karczma,
    osada itp.). Gate po `safe_for_rest` bieżącej lokacji narracyjnej."""
    key = (session_flags or {}).get("current_location_key")
    if not key:
        return False
    try:
        row = conn.execute(
            "SELECT safe_for_rest FROM game_locations WHERE key = ? AND is_active = 1 LIMIT 1",
            (key,),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return bool(row and int(row["safe_for_rest"] or 0))


def dwell_chance_multiplier(turns_at_location, settle_turns: int = 3) -> float:
    """D7 (#382) — im dłużej bohater osiadł w tej samej lokacji robiąc rzeczy,
    tym niższa szansa losowego encountera (osiadł = zajęty, nie eksploruje).
    1.0 dopóki < settle_turns, potem maleje do podłogi 0.1."""
    t = int(turns_at_location or 0)
    if t < settle_turns:
        return 1.0
    extra = t - settle_turns
    return max(0.1, 1.0 - 0.18 * (extra + 1))


def _parse_tags(raw) -> list[str]:
    """location_tags może być JSON array albo CSV. Zwraca lowercase listę."""
    if not raw:
        return []
    try:
        v = json.loads(raw)
        if isinstance(v, list):
            return [str(x).strip().lower() for x in v if str(x).strip()]
    except Exception:
        pass
    return [t.strip().lower() for t in str(raw).split(",") if t.strip()]


def _hero_level_for_campaign(conn: sqlite3.Connection, campaign_id: int) -> int:
    """Poziom aktywnego bohatera kampanii (sheet_json.level), domyślnie 1."""
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE campaign_id = ? AND is_active = 1 "
            "ORDER BY id DESC LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not row:
            return 1
        sheet = json.loads(row["sheet_json"] or "{}")
        return max(1, int(sheet.get("level") or 1))
    except Exception:
        return 1


def match_encounter_templates(
    conn: sqlite3.Connection, *, level: int, location_tag: str | None = None
) -> list[dict]:
    """D7 (#382) — ALL generic templates matching hero level + terrain (deterministic).

    From gameconfig_encounter_templates (is_active=1) where min_level <= level <=
    max_level. Tagged templates require a matching `location_tag`; tagless templates
    are generic (eligible anywhere). Sorted by threat_total. Each result carries a
    parsed `enemies` list.
    """
    try:
        rows = conn.execute(
            "SELECT * FROM gameconfig_encounter_templates "
            "WHERE is_active = 1 AND min_level <= ? AND max_level >= ? "
            "ORDER BY COALESCE(threat_total, 0), key",
            (int(level), int(level)),
        ).fetchall()
    except sqlite3.OperationalError:
        return []

    lt = (location_tag or "").strip().lower()
    out: list[dict] = []
    for r in rows:
        tags = _parse_tags(r["location_tags"] if "location_tags" in r.keys() else None)
        if tags and (not lt or lt not in tags):
            continue  # tagged template needs a matching location
        d = dict(r)
        try:
            d["enemies"] = json.loads(r["enemies_json"] or "[]")
        except Exception:
            d["enemies"] = []
        out.append(d)
    return out


def select_encounter_template(
    conn: sqlite3.Connection, *, level: int, location_tag: str | None = None
) -> dict | None:
    """D7 (#382) — pick ONE matching template at random (for actual injection)."""
    candidates = match_encounter_templates(conn, level=level, location_tag=location_tag)
    return random.choice(candidates) if candidates else None
