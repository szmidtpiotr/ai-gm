"""
Spell Service — Task 26 Scholar Spells.
Handles spell resolution, mana deduction, miscast, and Nat20 secondary effects.
"""
import json
import random
import re
import sqlite3
from typing import Any

DB_PATH = "/data/ai_gm.db"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Spell lookup ──────────────────────────────────────────────────────────────

def get_spell(spell_key: str) -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT * FROM game_config_spells WHERE key = ? AND is_active = 1",
            (spell_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_character_spells(character_id: int) -> list[dict]:
    """Return all spells known by a character with their rank."""
    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT cs.spell_key, cs.rank, gs.label, gs.tier, gs.mana_cost,
                      gs.spell_type, gs.damage_die, gs.heal_die, gs.effect_stat,
                      gs.effect_type, gs.effect_duration, gs.target_zone, gs.aoe,
                      gs.description, gs.rank2_json, gs.rank3_json
               FROM character_spells cs
               JOIN game_config_spells gs ON gs.key = cs.spell_key
               WHERE cs.character_id = ?
               ORDER BY gs.tier, gs.key""",
            (character_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_character_spell(character_id: int, spell_key: str) -> dict | None:
    spells = get_character_spells(character_id)
    return next((s for s in spells if s["spell_key"] == spell_key), None)


def get_spell_stats_at_rank(spell: dict, rank: int) -> dict:
    """Merge base spell with rank upgrade overrides."""
    base = dict(spell)
    if rank >= 2 and spell.get("rank2_json"):
        try:
            base.update(json.loads(spell["rank2_json"]))
        except Exception:
            pass
    if rank >= 3 and spell.get("rank3_json"):
        try:
            base.update(json.loads(spell["rank3_json"]))
        except Exception:
            pass
    base["rank"] = rank
    return base


# ── Mana management ───────────────────────────────────────────────────────────

def check_and_deduct_mana(sheet: dict, mana_cost: int) -> tuple[bool, int]:
    """Check mana available and deduct. Returns (ok, new_current_mana)."""
    current = int(sheet.get("current_mana") or 0)
    if current < mana_cost:
        return False, current
    new_mana = current - mana_cost
    sheet["current_mana"] = new_mana
    return True, new_mana


# ── Miscast (Nat 1 on spell attack) ──────────────────────────────────────────

def resolve_miscast(sheet: dict, enemy: dict, conn: sqlite3.Connection) -> dict:
    """
    Apply miscast effects based on Scholar's level.
    Returns miscast result dict with self_damage, stun, narrative.
    """
    level = int(sheet.get("level", 1) or 1)
    cur_hp = int(sheet.get("current_hp", 0) or 0)

    result: dict[str, Any] = {"miscast": True, "self_damage": 0, "stun": True, "narrative": ""}

    if level <= 2:
        result["self_damage"] = 0
        result["narrative"] = "Czar wymknął się spod kontroli — czujesz oszołomienie."
    elif level <= 4:
        dmg = random.randint(1, 4)
        result["self_damage"] = dmg
        result["narrative"] = f"Czar eksploduje w twoich dłoniach! Tracisz {dmg} HP."
    elif level <= 7:
        dmg = random.randint(1, 6)
        result["self_damage"] = dmg
        result["narrative"] = f"Niekontrolowana magia rani cię za {dmg} HP i ogłusza."
    else:
        dmg = random.randint(1, 8)
        result["self_damage"] = dmg
        secondary = random.randint(1, 4)
        secondary_text = {
            1: "Wróg odzyskuje 1k4 HP.",
            2: "Sojusznik w pobliżu odnosi 1k4 obrażeń.",
            3: "Czar uderza w ciebie.",
            4: "Tylko podstawowa kara.",
        }[secondary]
        result["secondary"] = secondary
        result["narrative"] = f"Katastrofalna pomyłka! {dmg} HP strat. {secondary_text}"

    # Apply self-damage
    if result["self_damage"] > 0:
        new_hp = max(0, cur_hp - result["self_damage"])
        sheet["current_hp"] = new_hp
        result["hp_after"] = new_hp
    else:
        result["hp_after"] = cur_hp

    return result


# ── Nat 20 secondary effects for spells ──────────────────────────────────────

def resolve_spell_nat20_secondary(enemy: dict, dmg: int) -> dict:
    """Roll d6 for Nat 20 secondary spell effect. Returns extra info."""
    roll = random.randint(1, 6)
    result: dict[str, Any] = {
        "nat20_secondary_roll": roll,
        "extra_damage": 0,
        "condition": None,
        "zone_change": False,
    }

    if roll <= 2:
        # Double damage only — already handled by caller doubling dmg
        result["narrative"] = "Krytyczne trafienie! Podwójne obrażenia."
    elif roll <= 4:
        # Double damage + stun
        result["condition"] = "stunned"
        result["narrative"] = "Krytyczne trafienie! Podwójne obrażenia + wróg ogłuszony."
    elif roll == 5:
        # Double damage + zone change
        result["zone_change"] = True
        result["narrative"] = "Krytyczne trafienie! Podwójne obrażenia + wróg odrzucony."
    else:
        # Double damage + burning
        result["condition"] = "burning"
        result["narrative"] = "Krytyczne trafienie! Podwójne obrażenia + wróg płonie."

    return result


# ── Spell-specific resolution ─────────────────────────────────────────────────

def roll_damage_dice(expr: str, mod: int = 0) -> int:
    m = re.match(r"^(\d*)d(\d+)$", (expr or "1d4").strip().lower())
    if not m:
        return max(0, mod)
    n = int(m.group(1) or 1)
    sides = int(m.group(2))
    return max(0, sum(random.randint(1, sides) for _ in range(max(1, n))) + mod)


def resolve_mend_wounds(sheet: dict, spell_stats: dict) -> dict:
    """Heal self: roll heal_die + INT mod."""
    from app.services.vitality_service import stat_modifier
    int_mod = stat_modifier(int((sheet.get("stats") or {}).get("INT", 10)))
    heal_die = spell_stats.get("heal_die") or "2d6"
    healed = roll_damage_dice(heal_die, int_mod)
    cur_hp = int(sheet.get("current_hp") or 0)
    max_hp = int(sheet.get("max_hp") or cur_hp)
    new_hp = min(max_hp, cur_hp + healed)
    sheet["current_hp"] = new_hp
    return {"healed": healed, "hp_after": new_hp, "outcome": "heal"}


# ── Arcane Points ─────────────────────────────────────────────────────────────

# ── Spell rank progression via use_count ──────────────────────────────────────

def _rank_up_threshold(tier: int, target_rank: int) -> int:
    """Successful casts needed to reach target_rank. R1→R2: always 5. R2→R3: 5 + tier*2."""
    if target_rank == 2:
        return 5
    if target_rank == 3:
        return 5 + int(tier) * 2
    return 9999


def record_spell_use(character_id: int, spell_key: str, conn=None) -> dict:
    """Increment use_count for a known spell; auto rank-up when threshold reached."""
    managed = conn is None
    if managed:
        conn = _get_db()
    try:
        row = conn.execute(
            "SELECT cs.rank, cs.use_count, gs.tier "
            "FROM character_spells cs "
            "JOIN game_config_spells gs ON gs.key = cs.spell_key "
            "WHERE cs.character_id = ? AND cs.spell_key = ?",
            (character_id, spell_key),
        ).fetchone()
        if not row:
            return {"recorded": False}

        current_rank = int(row["rank"])
        use_count = int(row["use_count"]) + 1
        tier = int(row["tier"])

        ranked_up = False
        new_rank = current_rank
        if current_rank < 3:
            threshold = _rank_up_threshold(tier, current_rank + 1)
            if use_count >= threshold:
                new_rank = current_rank + 1
                use_count = 0
                ranked_up = True
                conn.execute(
                    "UPDATE character_spells SET rank = ?, use_count = 0 WHERE character_id = ? AND spell_key = ?",
                    (new_rank, character_id, spell_key),
                )
            else:
                conn.execute(
                    "UPDATE character_spells SET use_count = ? WHERE character_id = ? AND spell_key = ?",
                    (use_count, character_id, spell_key),
                )
        else:
            conn.execute(
                "UPDATE character_spells SET use_count = ? WHERE character_id = ? AND spell_key = ?",
                (use_count, character_id, spell_key),
            )

        if managed:
            conn.commit()
        return {
            "recorded": True,
            "spell_key": spell_key,
            "use_count": use_count,
            "rank": new_rank,
            "ranked_up": ranked_up,
        }
    finally:
        if managed:
            conn.close()


def learn_spell(character_id: int, spell_key: str) -> dict:
    """Add a spell at rank 1 to character_spells."""
    conn = _get_db()
    try:
        # Verify spell exists
        spell = conn.execute(
            "SELECT key, label FROM game_config_spells WHERE key = ?",
            (spell_key,),
        ).fetchone()
        if not spell:
            raise ValueError(f"Spell '{spell_key}' not found")
        # Check not already known
        existing = conn.execute(
            "SELECT rank FROM character_spells WHERE character_id = ? AND spell_key = ?",
            (character_id, spell_key),
        ).fetchone()
        if existing:
            raise ValueError(f"Already knows '{spell_key}' at rank {existing['rank']}")
        # Stamp the level so Stage 11 resurrection xp_revert can roll back
        # spells purchased above the new level. Level lives in sheet_json.
        sj_row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        import json as _j
        char_level = 1
        if sj_row:
            try:
                char_level = int(_j.loads(sj_row["sheet_json"] or "{}").get("level") or 1)
            except Exception:
                char_level = 1
        conn.execute(
            "INSERT INTO character_spells (character_id, spell_key, rank, learned_at_level) VALUES (?, ?, 1, ?)",
            (character_id, spell_key, char_level),
        )
        conn.commit()
        return {"spell_key": spell_key, "label": spell["label"], "rank": 1}
    finally:
        conn.close()


def upgrade_spell(character_id: int, spell_key: str) -> dict:
    """Upgrade a known spell to the next rank (max 3)."""
    conn = _get_db()
    try:
        existing = conn.execute(
            "SELECT rank FROM character_spells WHERE character_id = ? AND spell_key = ?",
            (character_id, spell_key),
        ).fetchone()
        if not existing:
            raise ValueError(f"Character doesn't know spell '{spell_key}'")
        current_rank = int(existing["rank"])
        if current_rank >= 3:
            raise ValueError(f"'{spell_key}' is already at max rank 3")
        new_rank = current_rank + 1
        conn.execute(
            "UPDATE character_spells SET rank = ? WHERE character_id = ? AND spell_key = ?",
            (new_rank, character_id, spell_key),
        )
        conn.commit()
        return {"spell_key": spell_key, "rank": new_rank}
    finally:
        conn.close()


def grant_starting_spells(
    character_id: int, conn: sqlite3.Connection | None = None
) -> None:
    """Grant Scholar's starting spells: magic_bolt R1 and mend_wounds R1."""
    managed = conn is None
    if managed:
        conn = _get_db()
    try:
        for spell_key in ("magic_bolt", "mend_wounds"):
            conn.execute(
                "INSERT OR IGNORE INTO character_spells (character_id, spell_key, rank) VALUES (?, ?, 1)",
                (character_id, spell_key),
            )
        if managed:
            conn.commit()
    finally:
        if managed:
            conn.close()
