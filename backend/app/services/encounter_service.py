"""Encounter injection service — automated GM encounter triggering."""
import json
import random
import re
import sqlite3
import unicodedata

import structlog

logger = structlog.get_logger()


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

        # 4. Filter by trigger type and biome
        candidates = []
        for row in rows:
            try:
                dd = json.loads(row["draft_data"] or "{}")
                enc = dd.get("encounter")
                if not enc:
                    continue
                enc_triggers = enc.get("trigger_types") or ["hex_enter"]
                if trigger not in enc_triggers:
                    continue
                enc_biomes = enc.get("biomes") or []
                if enc_biomes and hex_type and hex_type not in enc_biomes:
                    continue
                prob = float(enc.get("trigger_probability") or 0.25)
                candidates.append((prob, enc, row["id"]))
            except Exception:
                continue

        if not candidates:
            return False

        # 5. Shuffle, roll each candidate, use first that fires
        random.shuffle(candidates)
        for prob, enc, hook_id in candidates:
            if random.random() <= prob:
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

    except Exception as exc:
        logger.warning("maybe_inject_encounter_error", error=str(exc), campaign_id=campaign_id)
        return False
