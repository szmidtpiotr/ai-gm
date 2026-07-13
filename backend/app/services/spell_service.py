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


# ── #975 R6: Rdzeń-magia krasnoludów — stałe (STARTING values, tunable) ──────

DWARF_MISCAST_THRESHOLD = 2  # Nat 1 i Nat 2 = miscast dla krasnoludów

# Efekty uboczne per czar krasnoludowy (losowy index d4/d6 → opis)
_DWARF_SIDE_EFFECTS: dict[str, list[str]] = {
    "vein_tremor": [
        "Odrzut żyły — tracisz 1 HP.",
        "Żyła spokojna — brak efektu ubocznego.",
        "Teren niestabilny — +1 DC do następnego ruchu wszystkich.",
        "Odłamki kamieni — każdy w zasięgu traci 1 HP.",
    ],
    "rdzen_pulse": [
        "Rdzeń odpycha — również ogłuszon przez 1 turę.",
        "Puls kontrolowany — brak efektu.",
        "Puls kontrolowany — brak efektu.",
        "Dmg ×1.5, ale tracisz 2 HP (żyła odpycha).",
        "Puls skupiony — nic złego.",
        "Żyła wzmacnia — dmg ×1.5, ale tracisz 2 HP.",
    ],
    "vein_bleed": [
        "Krwawisz razem z wrogiem — bleeding 2 tury (−1 HP/tura).",
        "Rana czysta — brak efektu.",
        "Wróg goi się wolniej — healing −50% przez 2 tury.",
        "Tracisz 2 max HP na resztę walki (żyła nadweręża).",
        "Dmg ×2, ale ryzyko dodatkowego miscast.",
        "Wróg nestabilny — eksploduje na śmierci (1d4 area dmg).",
    ],
    "rdzen_shield": [
        "Tarcza pęka — 1d4 HP zwracane castorowi.",
        "Tarcza działa normalnie.",
        "Absorb + 1 dmg reflect do atakującego.",
        "Absorb + bonus +2 ATK następna tura.",
    ],
    "deep_quake": [
        "Też upadasz (prone).",
        "Gwarantowany koszt — nic poza tym.",
        "Gwarantowany koszt — nic poza tym.",
        "Gwarantowany koszt — nic poza tym.",
        "Dmg ×1.5, ale tracisz 3 HP zamiast 1d4.",
        "Dmg ×1.5, ale tracisz 3 HP zamiast 1d4.",
    ],
    "black_vein": [
        "Dodatkowy rzut na miscast — żyła niespokojma.",
        "Gwarantowany koszt — nic poza tym.",
        "Gwarantowany koszt — nic poza tym.",
        "Gwarantowany koszt — nic poza tym.",
        "Lekko zatruty (−1 HP/tura, 1 tura).",
        "Power surge — następny czar bez kosztu many.",
    ],
}

# Czary startowe krasnoluda-Uczonego (zamiast ludzkiego zestawu)
DWARF_SCHOLAR_STARTING_SPELLS = ("vein_tremor", "rdzen_shield")
HUMAN_SCHOLAR_STARTING_SPELLS = ("fire_bolt", "minor_heal", "ward_of_iron", "detect_magic", "spark_burst")


def is_miscast(raw_d20: int, race: str = "human") -> bool:
    """Return True if the roll triggers a miscast for this race.

    Humans: Nat 1 only. Dwarves: Nat 1 or Nat 2 (higher Rdzen risk).
    """
    threshold = DWARF_MISCAST_THRESHOLD if str(race or "human").strip().lower() == "dwarf" else 1
    return int(raw_d20) <= threshold


def resolve_dwarf_spell_side_effect(spell_key: str, rng=random) -> str:
    """Roll d4/d6 side effect for a dwarf spell on SUCCESS.

    Returns a human-readable Polish description of the side effect.
    Returns '' if spell_key has no side-effect table.
    """
    table = _DWARF_SIDE_EFFECTS.get(str(spell_key or ""), [])
    if not table:
        return ""
    idx = rng.randint(0, len(table) - 1)
    return table[idx]


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


def get_spell_catalog() -> list[dict]:
    """#1170 — Public catalog of all active spells (for the Scholar level-up modal).

    Returns every learnable spell ordered by tier; each row carries at least
    ``key``, ``label`` and ``description`` (the fields the level-up UI needs).
    """
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM game_config_spells WHERE is_active = 1 ORDER BY tier, key"
        ).fetchall()
        return [dict(r) for r in rows]
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


# ── Defense / absorption (B10 #657) ───────────────────────────────────────────

# Fallback puli absorpcji wg tieru, gdy spell.effect_json nie podaje `absorb`.
# Wartości startowe (Numbers Policy #657) — tuning po playteście B13.
_ABSORB_FALLBACK_BY_TIER = {1: 4, 2: 8, 3: 12, 4: 16, 5: 20}


def defense_absorb_amount(spell_row) -> int:
    """Ile temp-HP (pula absorpcji) daje czar obronny (B10).

    Czyta `effect_json.absorb` (źródło prawdy, edytowalne z panelu admina B12);
    brak/niepoprawny → fallback wg tieru (≥4, nigdy 0). Płaska wartość — bez INT_mod
    (przewidywalna tarcza; kandydat na skalowanie po B13)."""
    raw = None
    if isinstance(spell_row, dict):
        raw = spell_row.get("effect_json")
        tier = int(spell_row.get("tier") or 1)
    else:  # sqlite3.Row
        raw = spell_row["effect_json"] if "effect_json" in spell_row.keys() else None
        tier = int((spell_row["tier"] if "tier" in spell_row.keys() else 1) or 1)
    if raw:
        try:
            absorb = int(json.loads(raw).get("absorb"))
            if absorb > 0:
                return absorb
        except (ValueError, TypeError, AttributeError):
            pass
    return _ABSORB_FALLBACK_BY_TIER.get(tier, max(4, tier * 4))


# ── Mana management ───────────────────────────────────────────────────────────

def check_and_deduct_mana(
    sheet: dict,
    mana_cost: int,
    *,
    campaign_id: int | None = None,
    character_id: int | None = None,
    combat_id: int | None = None,
    cause: str = "spell_cast",
) -> tuple[bool, int]:
    """Check mana available and deduct. Returns (ok, new_current_mana).

    #761: gdy podasz campaign_id, udane potrącenie many jest zapisane do state_changes
    (before→after+delta). Best-effort — nigdy nie wywraca rzucania czaru.
    """
    current = int(sheet.get("current_mana") or 0)
    if current < mana_cost:
        return False, current
    new_mana = current - mana_cost
    sheet["current_mana"] = new_mana
    if campaign_id is not None:
        try:
            from app.services.state_log_service import record_state_change
            record_state_change(
                campaign_id=campaign_id, resource="mana", character_id=character_id,
                combat_id=combat_id, before_val=current, after_val=new_mana,
                cause=cause, meta={"mana_cost": int(mana_cost)},
            )
        except Exception:
            pass
    return True, new_mana


# ── Miscast (Nat 1 on spell attack) ──────────────────────────────────────────

def resolve_miscast(sheet: dict, enemy: dict, conn: sqlite3.Connection, race: str = "human") -> dict:
    """
    Apply miscast effects based on Scholar's level.
    Returns miscast result dict with self_damage, stun, narrative.
    #975 R6: Krasnolud miscast ma inny flavor (rdzen_miscast=True).
    """
    level = int(sheet.get("level", 1) or 1)
    cur_hp = int(sheet.get("current_hp", 0) or 0)
    is_dwarf = str(race or "human").strip().lower() == "dwarf"

    result: dict[str, Any] = {"miscast": True, "self_damage": 0, "stun": True, "narrative": "", "rdzen_miscast": is_dwarf}

    if is_dwarf:
        # Rdzeń-magia: żyła wibruje — inny flavor
        if level <= 2:
            result["self_damage"] = 0
            result["narrative"] = "Żyła wibruje — krew z uszu, kamień pęka pod stopami. Ogłuszenie."
        elif level <= 4:
            dmg = random.randint(1, 4)
            result["self_damage"] = dmg
            result["narrative"] = f"Rdzeń odwraca się przeciw tobie! Żyła eksploduje — {dmg} HP strat."
        elif level <= 7:
            dmg = random.randint(1, 6)
            result["self_damage"] = dmg
            result["narrative"] = f"Surowa moc Rdzenia rani cię za {dmg} HP. Kamień pod stopami pęka i ogłusza."
        else:
            dmg = random.randint(1, 8)
            result["self_damage"] = dmg
            secondary = random.randint(1, 4)
            secondary_text = {
                1: "Skażenie Rdzenia rozprzestrzenia się — wróg też traci 1k4 HP.",
                2: "Fala Rdzenia uderza w sojusznika — 1k4 obrażeń.",
                3: "Żyła obraca czar — uderza w ciebie podwójnie.",
                4: "Tylko podstawowa kara Rdzenia.",
            }[secondary]
            result["secondary"] = secondary
            result["narrative"] = f"Katastrofalne Rdzeń-pęknięcie! {dmg} HP strat. {secondary_text}"
    else:
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

def roll_dice_detailed(expr: str) -> dict:
    """#661: roll NdM, return per-die rolls + notation for dice visualization."""
    m = re.match(r"^(\d*)d(\d+)$", (expr or "1d4").strip().lower())
    if not m:
        return {"die": (expr or "1d4"), "rolls": [], "sides": 0, "n": 0}
    n = max(1, int(m.group(1) or 1))
    sides = int(m.group(2))
    rolls = [random.randint(1, sides) for _ in range(n)]
    return {"die": f"{n}d{sides}", "rolls": rolls, "sides": sides, "n": n}


def roll_damage_dice(expr: str, mod: int = 0) -> int:
    d = roll_dice_detailed(expr)
    if not d["rolls"]:
        return max(0, mod)
    return max(0, sum(d["rolls"]) + mod)


def resolve_mend_wounds(sheet: dict, spell_stats: dict) -> dict:
    """Heal self: roll heal_die + INT mod."""
    from app.services.vitality_service import stat_modifier
    int_mod = stat_modifier(int((sheet.get("stats") or {}).get("INT", 10)))
    heal_die = spell_stats.get("heal_die") or "2d6"
    detail = roll_dice_detailed(heal_die)
    healed = max(0, sum(detail["rolls"]) + int_mod) if detail["rolls"] else max(0, int_mod)
    cur_hp = int(sheet.get("current_hp") or 0)
    max_hp = int(sheet.get("max_hp") or cur_hp)
    new_hp = min(max_hp, cur_hp + healed)
    sheet["current_hp"] = new_hp
    return {
        "healed": healed, "hp_after": new_hp, "outcome": "heal",
        "heal_die": detail["die"] or heal_die, "heal_rolls": detail["rolls"],
        "heal_modifier": int_mod,
    }


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


# ── B7 (#652): tier-gating nauki + model trafienia czaru (D-spell) ───────────

def max_spell_tier_for_level(level: int) -> int:
    """Bramka tieru: max_tier = ceil(level/2). Tier T wymaga poziomu 2T-1.

    L1-2→T1, L3-4→T2, L5-6→T3, … Wartości startowe (Numbers Policy, tuning po B13).
    """
    lvl = max(1, int(level or 1))
    return (lvl + 1) // 2


# Kondycja czaru → stat OBRONY celu (D-spell, CZĘŚĆ AK.6): WIS=umysł, CON=ciało.
# Klucze = istniejące kondycje FAZY S (reużycie, zero duplikatu).
_SPELL_SAVE_STAT = {
    "confused": "WIS", "cursed": "WIS", "blinded": "WIS", "charmed": "WIS", "feared": "WIS",
    "slowed": "CON", "frozen": "CON", "stunned": "CON", "poisoned": "CON",
}


def spell_save_stat(condition_key: str) -> str:
    """Stat, którym cel broni się przed czarem nie-atakującym. Fallback = CON (ciało)."""
    return _SPELL_SAVE_STAT.get(str(condition_key or "").strip().lower(), "CON")


def resolve_spell_opposed_save(
    caster_sheet: dict, target_stats: dict, condition_key: str, rng=random
) -> dict:
    """Pojedynek trafienia czaru nie-atakującego (D-spell):
    `d20 + INT_mod` (mag) vs `d20 + stat_obrony_mod` (cel). Remis → mag wygrywa.

    Czary ATAKUJĄCE nie używają tej ścieżki (d20+INT vs unik wroga — #475 nietknięte).
    Stat obrony zależy od efektu (WIS umysł / CON ciało). Czyste — bez DB, rng wstrzykiwalny.
    """
    from app.services.vitality_service import stat_modifier

    int_mod = stat_modifier(int((caster_sheet.get("stats") or {}).get("INT", 10) or 10))
    save_stat = spell_save_stat(condition_key)
    tgt_val = int((target_stats or {}).get(save_stat, 10) or 10)
    target_mod = (tgt_val - 10) // 2
    caster_roll = rng.randint(1, 20)
    target_roll = rng.randint(1, 20)
    caster_total = caster_roll + int_mod
    target_total = target_roll + target_mod
    return {
        "landed": caster_total >= target_total,  # remis → mag
        "save_stat": save_stat,
        "caster_roll": caster_roll, "int_mod": int_mod, "caster_total": caster_total,
        "target_roll": target_roll, "target_mod": target_mod, "target_total": target_total,
    }


def mana_refund_on_resist(mana_cost: int) -> int:
    """Zwrot ½ many (floor) gdy cel się oparł — kara = tylko tura, jak pudło wojownika.

    Pełna mana gdy czar łapie / przy miscast (rozliczane przez wywołującego).
    """
    return max(0, int(mana_cost or 0)) // 2


def resolve_combat_effect_spell(
    caster_sheet: dict, target_stats: dict, condition_key: str,
    mana_cost: int, raw_d20: int | None = None, rng=random,
) -> dict:
    """B9 (#656): rozstrzygnięcie czaru NIE-atakującego (kondycja) w walce.

    Model trafienia D-spell (CZĘŚĆ AK.6): pojedynek przeciwny `d20+INT_mod (mag)` vs
    `d20+stat_obrony_mod (cel)` — NIE rzut na unik. Stat obrony wg kondycji
    (`spell_save_stat`: WIS umysł / CON ciało). Mana wydawana z góry przez wywołującego;
    przy oporze ½ many wraca (`mana_refund_on_resist`). Nat 1 = miscast (pełna mana).

    Czysta funkcja — apply-condition i persist robi `combat_service` (jedno źródło
    persistu walki). Zwraca {outcome, condition_applied, save_stat, mana_refund, save}.
    """
    save_stat = spell_save_stat(condition_key)
    if raw_d20 == 1:
        return {"outcome": "miscast", "condition_applied": False,
                "save_stat": save_stat, "mana_refund": 0, "save": None}
    save = resolve_spell_opposed_save(caster_sheet, target_stats, condition_key, rng=rng)
    if save.get("landed"):
        return {"outcome": "landed", "condition_applied": True,
                "save_stat": save_stat, "mana_refund": 0, "save": save}
    return {"outcome": "resisted", "condition_applied": False,
            "save_stat": save_stat, "mana_refund": mana_refund_on_resist(mana_cost), "save": save}


def learn_spell(character_id: int, spell_key: str) -> dict:
    """Add a spell at rank 1 to character_spells. B7 (#652): bramkuje tier wg poziomu.
    #975 R6: bramkuje race_lock — krasnolud nie może nauczyć się ludzkiego czaru i vice versa.
    """
    conn = _get_db()
    try:
        # Verify spell exists
        spell = conn.execute(
            "SELECT key, label, tier, race_lock FROM game_config_spells WHERE key = ?",
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
            "SELECT sheet_json, race FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        import json as _j
        char_level = 1
        char_race = "human"
        if sj_row:
            try:
                char_level = int(_j.loads(sj_row["sheet_json"] or "{}").get("level") or 1)
                char_race = str(sj_row["race"] or "human").strip().lower()
            except Exception:
                char_level = 1
        # #975 R6 / #1373: race_lock = lista ras (CSV) dopuszczonych do nauki.
        # Pusty/NULL = legacy "pula ludzka" → tylko human (krasnolud wykluczony).
        spell_race_lock = None
        try:
            spell_race_lock = spell["race_lock"]
        except Exception:
            pass
        raw_lock = str(spell_race_lock or "").strip().lower()
        allowed_races = [r.strip() for r in raw_lock.split(",") if r.strip()] or ["human"]
        if char_race not in allowed_races:
            if raw_lock:
                pretty = " / ".join(allowed_races)
                raise ValueError(
                    f"Czar '{spell_key}' jest dostępny dla ras: {pretty} "
                    f"(twoja rasa: '{char_race}')."
                )
            raise ValueError(
                f"Czar '{spell_key}' jest dostępny tylko dla ludzi. "
                f"Krasnolud może uczyć się wyłącznie czarów Rdzeń-magii (race_lock=dwarf)."
            )
        # B7 (#652): bramka tieru — nie wolno nauczyć się czaru ponad max_tier dla poziomu.
        spell_tier = int(spell["tier"] or 1) if "tier" in spell.keys() else 1
        max_tier = max_spell_tier_for_level(char_level)
        if spell_tier > max_tier:
            raise ValueError(
                f"Za niski poziom: '{spell['label']}' to tier {spell_tier}, "
                f"wymaga poziomu {spell_tier * 2 - 1}+ (masz {char_level})."
            )
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


def cast_spell_out_of_combat(character_id: int, spell_key: str) -> dict:
    """Cast a heal/defense/narrative spell outside active combat.

    Deducts mana (if any), applies effect, records use for rank progression.
    Raises ValueError on invalid state (wrong archetype, unknown spell, insufficient mana,
    offensive spell type).
    """
    conn = _get_db()
    try:
        # BEGIN IMMEDIATE acquires a reserved lock before the read so no concurrent
        # writer can slip in between our SELECT and UPDATE (lost-update prevention).
        conn.execute("BEGIN IMMEDIATE")
        char_row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        if not char_row:
            raise ValueError("Postać nie istnieje")
        sheet = json.loads(char_row["sheet_json"] or "{}")
        if str(sheet.get("archetype") or "").strip().lower() != "scholar":
            raise ValueError("Tylko Uczony może rzucać zaklęcia")
        known = get_character_spell(character_id, spell_key)
        if not known:
            raise ValueError(f"Nie znasz zaklęcia: {spell_key}")
        spell = get_spell(spell_key)
        if not spell:
            raise ValueError(f"Zaklęcie '{spell_key}' nie istnieje")
        if spell["spell_type"] in ("attack", "attack_aoe", "effect"):
            raise ValueError("Zaklęcia ofensywne i efektowe można rzucić tylko w walce — wymagają celu")
        spell_stats = get_spell_stats_at_rank(spell, known["rank"])
        mana_cost = int(spell_stats.get("mana_cost") or 0)
        if mana_cost > 0:
            ok, _ = check_and_deduct_mana(sheet, mana_cost)
            if not ok:
                raise ValueError(
                    f"Za mało many: masz {int(sheet.get('current_mana', 0))}, potrzebujesz {mana_cost}"
                )
        result: dict[str, Any] = {
            "spell_key": spell_key,
            "label": spell.get("label", spell_key),
            "spell_type": spell["spell_type"],
            "mana_cost": mana_cost,
            "current_mana": int(sheet.get("current_mana", 0)),
        }
        if spell["spell_type"] == "heal":
            heal_result = resolve_mend_wounds(sheet, spell_stats)
            result.update(heal_result)
            result["message"] = (
                f"Rzucasz {spell.get('label', spell_key)} — leczysz się za "
                f"{heal_result['healed']} HP. Masz teraz "
                f"{heal_result['hp_after']}/{int(sheet.get('max_hp', 0))} HP."
            )
        elif spell["spell_type"] == "defense":
            conditions = list(sheet.get("conditions") or [])
            if spell_key not in conditions:
                conditions.append(spell_key)
            sheet["conditions"] = conditions
            result["outcome"] = "defense"
            result["conditions"] = conditions
            result["message"] = (
                f"Rzucasz {spell.get('label', spell_key)}. Magiczna ochrona otacza cię."
            )
        elif spell["spell_type"] == "narrative":
            result["outcome"] = "narrative"
            desc = (spell.get("description") or "").rstrip(".")
            result["message"] = f"Rzucasz {spell.get('label', spell_key)}. {desc}." if desc else f"Rzucasz {spell.get('label', spell_key)}."
        else:
            result["outcome"] = "ok"
            result["message"] = f"Rzucasz {spell.get('label', spell_key)}."
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), character_id),
        )
        record_spell_use(character_id, spell_key, conn)
        conn.commit()
        return result
    finally:
        conn.close()


def grant_starting_spells(
    character_id: int, conn: sqlite3.Connection | None = None
) -> None:
    """Grant Scholar's L1 starting kit.

    Człowiek: fire_bolt, minor_heal, ward_of_iron, detect_magic, spark_burst (B8 #655 + B11b #983)
    Krasnolud (#975 R6): vein_tremor + rdzen_shield (Rdzeń-magia pula, rozłączna z ludzką)
    """
    managed = conn is None
    if managed:
        conn = _get_db()
    try:
        # Check character race for dwarf spell set
        race = "human"
        try:
            row = conn.execute(
                "SELECT race FROM characters WHERE id = ? LIMIT 1",
                (int(character_id),),
            ).fetchone()
            if row:
                race = str(row["race"] or "human").strip().lower()
        except Exception:
            pass

        spells = DWARF_SCHOLAR_STARTING_SPELLS if race == "dwarf" else HUMAN_SCHOLAR_STARTING_SPELLS
        for spell_key in spells:
            conn.execute(
                "INSERT OR IGNORE INTO character_spells (character_id, spell_key, rank) VALUES (?, ?, 1)",
                (character_id, spell_key),
            )
        if managed:
            conn.commit()
    finally:
        if managed:
            conn.close()
