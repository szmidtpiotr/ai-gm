"""
Skill test service — Task 12.

Handles:
  1. [SKILL_TEST:skill_key:DC:14] and [SKILL_TEST:skill_key:OPPOSED:perception] tag interception
  2. [TRAP:skill_key:dc:damage_dice:condition] tag interception
  3. resolve_pending_skill_test() — called when player sends their d20 roll
"""

import json
import re
import random
import sqlite3
import uuid
from typing import Optional

from app.core.mechanics import proficiency_bonus
from app.services.vitality_service import stat_modifier
from app.services.dice import roll_d20

DB_PATH = "/data/ai_gm.db"

# Fallback skill → governing stat (used when DB lookup unavailable)
_SKILL_STAT_FALLBACK: dict[str, str] = {
    "stealth": "DEX", "lockpick": "DEX", "acrobatics": "DEX", "dodge": "DEX",
    "perception": "WIS", "insight": "WIS", "survival": "WIS",
    "persuasion": "CHA", "deception": "CHA", "intimidation": "CHA",
    "athletics": "STR", "arcana": "INT", "medicine": "INT", "lore": "INT",
}

# Fallback labels
_SKILL_LABEL_FALLBACK: dict[str, str] = {
    "stealth": "Skradanie", "lockpick": "Otwieranie zamków", "acrobatics": "Akrobatyka",
    "perception": "Percepcja", "insight": "Wnikliwość", "survival": "Przetrwanie",
    "persuasion": "Perswazja", "deception": "Oszustwo", "intimidation": "Zastraszenie",
    "athletics": "Atletyka", "arcana": "Arkana", "medicine": "Medycyna", "lore": "Wiedza",
}

def _query_skill_from_db(skill_key: str) -> tuple[str, str] | None:
    """Query game_config_skills for a single skill. Returns (linked_stat, label) or None."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT linked_stat, label FROM game_config_skills WHERE key = ? LIMIT 1",
            (skill_key,),
        ).fetchone()
        conn.close()
        if row:
            return str(row["linked_stat"] or "INT").upper(), str(row["label"] or skill_key.title())
    except Exception:
        pass
    return None


def _skill_stat(skill_key: str) -> str:
    """Return governing stat for a skill. Always reads from DB, falls back to hardcoded map."""
    result = _query_skill_from_db(skill_key)
    if result:
        return result[0]
    return _SKILL_STAT_FALLBACK.get(skill_key, "INT")


def _skill_label(skill_key: str) -> str:
    """Return display label for a skill. Always reads from DB, falls back to hardcoded map."""
    result = _query_skill_from_db(skill_key)
    if result:
        return result[1]
    return _SKILL_LABEL_FALLBACK.get(skill_key, skill_key.title())


# Keep SKILL_LABELS for backward compat (tag intercept code)
SKILL_LABELS = _SKILL_LABEL_FALLBACK

# The 7 locked ability stats (CLAUDE.md → Locked Game Mechanics).
_STAT_NAMES = {"STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"}


def _counter_governing_stat(counter_key: str | None) -> str:
    """S4: OPPOSED counter_key may be a STAT name (e.g. ``WIS``) or a SKILL name
    (e.g. ``insight``). Return the ability stat the opponent rolls with — for a skill
    that means its governing/linked stat. Default WIS (mental defence)."""
    ck = (counter_key or "WIS").strip()
    if ck.upper() in _STAT_NAMES:
        return ck.upper()
    return _skill_stat(ck.lower())


def _opponent_modifier(opponent: dict, stat: str) -> int:
    """S4: opponent's defence modifier for ``stat`` from its REAL stats, with every
    active condition folded in. Reuses ``combat_service._combatant_stat_modifier`` so the
    stat_mods folding logic lives in exactly one place (Zasada projektowa FAZY S #1).

    ``opponent`` is an actor-agnostic sheet-like dict ``{stats, conditions?}`` — the same
    shape a player / NPC / enemy / second player exposes (MP groundwork, CZĘŚĆ AC)."""
    try:
        from app.services.combat_service import _combatant_stat_modifier
        return _combatant_stat_modifier(opponent, sheet=None, stat=stat)
    except Exception:
        # Defensive: never let opposed resolution crash a turn — degrade to bare stat mod.
        stats = opponent.get("stats") if isinstance(opponent.get("stats"), dict) else {}
        try:
            return (int(stats.get(stat, 10) or 10) - 10) // 2
        except (TypeError, ValueError):
            return 0


# ── Modifier calculation ──────────────────────────────────────────────────────

def calc_skill_modifier_info(sheet: dict, skill_key: str, conn=None, character_id=None) -> dict:
    """Return full modifier breakdown for the Roll Popup.

    #1302 — when ``conn`` + ``character_id`` are supplied, passive bonuses from
    equipped relics are folded in: stat POINTS raise the governing stat (then the
    modifier is recomputed) and skill points raise the rank. Proficiency stays
    keyed to the BASE rank (locked rule: +2 at rank≥3, relics don't grant it).
    Without conn/character_id the function is pure — identical to the old behaviour.
    """
    stats = sheet.get("stats") or {}
    skills = sheet.get("skills") or {}
    governing_stat = _skill_stat(skill_key)
    base_stat_val = int(stats.get(governing_stat, 10))
    base_skill_rank = int(skills.get(skill_key, 0))
    proficiency = proficiency_bonus(base_skill_rank)

    equip_stat_pts = 0
    equip_skill_pts = 0
    if conn is not None and character_id is not None:
        try:
            from app.services.equipment_effects_service import get_equipment_bonuses
            eb = get_equipment_bonuses(int(character_id), conn)
            equip_stat_pts = int(eb["stats"].get(governing_stat, 0))
            equip_skill_pts = int(eb["skills"].get(str(skill_key).lower(), 0))
        except Exception:
            equip_stat_pts = 0
            equip_skill_pts = 0

    stat_mod = stat_modifier(base_stat_val + equip_stat_pts)
    skill_rank = base_skill_rank + equip_skill_pts
    equipment_bonus = (stat_mod - stat_modifier(base_stat_val)) + equip_skill_pts
    # PT-D1 (#1124): zmęczenie (exhausted) obniża sumę KAŻDEGO testu o poziom stacka.
    # Data-driven (prymityw test_penalty); krasnolud ignoruje 1. stack.
    try:
        from app.services.fatigue_service import compute_test_penalty
        fatigue_penalty = compute_test_penalty(sheet.get("conditions") or [], race=sheet.get("race"))
    except Exception:
        fatigue_penalty = 0
    # #1193: choroba (zaraza) — kara flat_test_penalty, niezależna od zmęczenia
    # (długi odpoczynek jej nie zdejmuje). Osobny prymityw → osobny sumator.
    try:
        from app.services.disease_service import compute_disease_penalty
        disease_penalty = compute_disease_penalty(sheet.get("conditions") or [])
    except Exception:
        disease_penalty = 0
    # G1 #1458: kara za rany (wariant A łagodny) obniża KAŻDY test umiejętności,
    # obok zmęczenia i choroby. Osobny prymityw (wound_utils = jedno źródło), start
    # od ≤25% HP. Symetria z atakiem (weapon_rules) i torem wroga (combat_service).
    try:
        from app.services.wound_utils import wound_penalty as _wound_pen
        wound_penalty = _wound_pen(
            int(sheet.get("current_hp", 0) or 0),
            int(sheet.get("max_hp", 0) or 0),
        )
    except Exception:
        wound_penalty = 0
    total = skill_rank + stat_mod + proficiency + fatigue_penalty + disease_penalty + wound_penalty
    return {
        "governing_stat": governing_stat,
        "skill_rank": skill_rank,
        "stat_mod": stat_mod,
        "proficiency": proficiency,
        "fatigue_penalty": fatigue_penalty,
        "disease_penalty": disease_penalty,
        "wound_penalty": wound_penalty,
        "equipment_bonus": equipment_bonus,
        "total": total,
    }


# ── Counter lookup ────────────────────────────────────────────────────────────

def _get_counter(conn: sqlite3.Connection, skill_key: str) -> dict:
    try:
        row = conn.execute(
            "SELECT counter_type, counter_key, default_dc FROM skill_counters WHERE player_skill_key = ? LIMIT 1",
            (skill_key,),
        ).fetchone()
        if row:
            return {"counter_type": row[0], "counter_key": row[1], "dc": row[2] or 12}
    except sqlite3.OperationalError:
        pass
    return {"counter_type": "dc", "counter_key": None, "dc": 12}


def _resolve_opponent(conn: sqlite3.Connection, counter: dict, campaign_id: int) -> tuple[int, int | None]:
    """Roll the opponent side of an opposed check. Returns (opponent_total, opponent_roll).

    S4 (#584): when the test target was resolved to a real actor (``counter["opponent"]``
    = ``{stats, conditions?}``, populated at intercept time from scene enemies/NPCs), the
    opponent rolls ``d20 + real stat modifier`` for the governing stat — its conditions
    fold into the defence. With no resolvable actor we fall back to a flat DC from
    ``skill_counters`` (no opposed roll), so behaviour is preserved for unknown targets."""
    if counter.get("counter_type") != "opposed":
        return int(counter.get("dc", 12)), None

    opponent = counter.get("opponent")
    if isinstance(opponent, dict) and isinstance(opponent.get("stats"), dict):
        stat = _counter_governing_stat(counter.get("counter_key"))
        opp_roll = random.randint(1, 20)
        return opp_roll + _opponent_modifier(opponent, stat), opp_roll

    # No nameable actor / no stats → flat DC fallback (behaviour unchanged for unknowns).
    return int(counter.get("dc", 12)), None


# ── Opponent actor resolution (scene → actor-agnostic sheet) ──────────────────

def _norm(s: object) -> str:
    return str(s or "").strip().lower()


def resolve_opponent_actor(
    conn: sqlite3.Connection, campaign_id: int, target_name: str | None
) -> dict | None:
    """S4: resolve the test target to an actor-agnostic ``{stats, conditions}`` dict.

    Sources (richest first): a live combatant (stats + conditions) → a scene enemy
    (``game_config_enemies.stats_json``) → a scene NPC (``ensure_npc_stats``, S3, lazy +
    per-campaign). With an explicit ``target_name`` we match it against actor names/keys;
    without one we use the single-actor-in-scene heuristic (one obvious opponent → use it).
    No nameable actor → ``None`` and the caller falls back to a flat DC."""
    try:
        from app.services.actor_stats import parse_stats_json
    except Exception:
        return None

    candidates: list[dict] = []

    # 1. Live combat — combatants carry real stats AND active conditions.
    try:
        from app.services.combat_service import get_active_combat
        snap = get_active_combat(campaign_id)
        if snap:
            for c in (snap.get("combatants") or []):
                if not isinstance(c, dict) or c.get("is_player"):
                    continue
                if isinstance(c.get("stats"), dict):
                    candidates.append({
                        "name": c.get("name") or c.get("key"),
                        "key": c.get("key"),
                        "stats": c.get("stats"),
                        "conditions": c.get("conditions") or [],
                    })
    except Exception:
        pass

    # 2/3. Out-of-combat scene actors from world state.
    try:
        from app.services.world_state_service import get_world_state
        ws = get_world_state(campaign_id)
    except Exception:
        ws = {}

    have_keys = {_norm(c.get("key")) for c in candidates}

    for enemy in (ws.get("scene_enemies") or []):
        if not isinstance(enemy, dict) or _norm(enemy.get("key")) in have_keys:
            continue
        stats = None
        try:
            row = conn.execute(
                "SELECT stats_json FROM game_config_enemies WHERE key = ? LIMIT 1",
                (enemy.get("key"),),
            ).fetchone()
            if row:
                stats = parse_stats_json(row[0])
        except Exception:
            stats = None
        candidates.append({
            "name": enemy.get("name") or enemy.get("key"),
            "key": enemy.get("key"),
            "stats": stats or {},
            "conditions": [],
        })

    for npc in (ws.get("scene_npcs") or []):
        if not isinstance(npc, dict):
            continue
        name = npc.get("name") or npc.get("key")
        stats = None
        try:
            from app.services.npc_memory_service import ensure_npc_stats
            stats = ensure_npc_stats(conn, campaign_id, name)
        except Exception:
            stats = None
        if stats:
            candidates.append({
                "name": name, "key": npc.get("key"),
                "stats": stats, "conditions": [],
            })

    candidates = [c for c in candidates if isinstance(c.get("stats"), dict) and c["stats"]]
    if not candidates:
        return None

    chosen: dict | None = None
    tgt = _norm(target_name)
    if tgt:
        for c in candidates:
            if tgt in _norm(c.get("name")) or tgt in _norm(c.get("key")) \
               or _norm(c.get("name")) in tgt:
                chosen = c
                break
    elif len(candidates) == 1:
        chosen = candidates[0]

    if not chosen:
        return None
    return {"stats": chosen["stats"], "conditions": chosen.get("conditions") or []}


# ── [SKILL_TEST:...] tag interception ────────────────────────────────────────

SKILL_TEST_RE = re.compile(
    r"\[SKILL_TEST:([a-z_]+):(DC|OPPOSED):([^\]]+)\]",
    re.IGNORECASE,
)

TRAP_RE = re.compile(
    r"\[TRAP:([a-z_]+):(\d+):([^:]+):([^\]]*)\]",
    re.IGNORECASE,
)

# S7 (#601): [GAMBLE:<stake>:DC:<n>] lub [GAMBLE:<stake>:OPPOSED:CHA:<npc>].
# Hazard to test umiejętności ``gamble`` z prawdziwą stawką złota — stawkę podaje
# gracz, ale waliduje ją mechanika (≥1 gp, ≤ aktualne złoto) + limit gier na scenę.
GAMBLE_RE = re.compile(
    r"\[GAMBLE:(\d+):(DC|OPPOSED):([^\]]+)\]",
    re.IGNORECASE,
)

# #616: deterministyczne wykrycie intencji hazardu ze stawką w tekście gracza.
# Pre-LLM most intent→tag — bez tego bramka U7 / skaner skilli zżerają turę
# generycznym testem i mechanika stawki (S7) nigdy nie rusza złotem. Czysta funkcja
# (bez DB/silnika): rozpoznaje sens hazardowy + kwotę; resztę (walidacja, limit,
# wypłata) robi istniejący tor [GAMBLE] (prymityw raz).
_GAMBLE_INTENT_RE = re.compile(
    r"\b(ko[śs]ci(?:[ąa]mi|e|)|ko[śs][ćc]mi|hazard\w*|zak[łl]ad\w*|obstaw\w*|ruletk\w*|karty\b|w\s+karty)\b",
    re.IGNORECASE,
)
# Kwota: liczba przy słowie „złoto/sztuk/monet/gp" LUB tuż po czasowniku stawki.
_GAMBLE_STAKE_GOLD_RE = re.compile(
    r"(\d+)\s*(?:szt\w*\s*)?(?:z[łl]ot\w*|gp|monet\w*|sztuk\w*)",
    re.IGNORECASE,
)
_GAMBLE_STAKE_VERB_RE = re.compile(
    r"(?:stawia\w*|stawk\w*|obstaw\w*|zak[łl]ad\w*|gra\w*\s+o|gram\s+o)\D{0,12}(\d+)",
    re.IGNORECASE,
)


def detect_gamble_intent(text: Optional[str]) -> Optional[int]:
    """Zwróć zadeklarowaną stawkę (int gp), jeśli tekst gracza to hazard z kwotą.

    Wymaga JEDNOCZEŚNIE sensu hazardowego (kości/hazard/zakład/obstaw/karty/ruletka)
    ORAZ liczbowej stawki przy złocie lub po czasowniku stawki. Brak któregokolwiek
    → ``None`` (mechanika nie zgaduje stawki — wtedy LLM po prostu narruje). Czysta,
    deterministyczna; faktyczną walidację/limit/wypłatę robi tor [GAMBLE] (S7)."""
    if not text:
        return None
    if not _GAMBLE_INTENT_RE.search(text):
        return None
    m = _GAMBLE_STAKE_GOLD_RE.search(text) or _GAMBLE_STAKE_VERB_RE.search(text)
    if not m:
        return None
    try:
        stake = int(m.group(1))
    except (TypeError, ValueError):
        return None
    return stake if stake >= 1 else None


def _match_curable_condition(
    conn: sqlite3.Connection,
    character_id: int,
    skill_key: str,
) -> tuple[Optional[str], Optional[int]]:
    """S10 (#605): czy ten skill leczy którąś aktywną kondycję gracza?

    Deklaratywne — czyta blok ``cure: {skill, dc}`` z effect_json kondycji w katalogu.
    Zwraca ``(condition_key, dc)`` pierwszej dopasowanej kondycji albo ``(None, None)``.
    DC pochodzi z KATALOGU (mechanika decyduje), nie z taga LLM. Żadnego ``if key==...``.
    """
    skill_lo = str(skill_key or "").strip().lower()
    if not skill_lo or not character_id:
        return (None, None)
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (int(character_id),)
        ).fetchone()
        if not row:
            return (None, None)
        sheet = json.loads((row[0] if not hasattr(row, "keys") else row["sheet_json"]) or "{}")
        active_keys = [
            str(c.get("key") or "").strip().lower()
            for c in (sheet.get("conditions") or [])
            if isinstance(c, dict) and c.get("key")
        ]
        if not active_keys:
            return (None, None)
        for ck in active_keys:
            crow = conn.execute(
                "SELECT effect_json FROM game_config_conditions WHERE key = ? AND is_active = 1 LIMIT 1",
                (ck,),
            ).fetchone()
            if not crow:
                continue
            try:
                ejson = json.loads((crow[0] if not hasattr(crow, "keys") else crow["effect_json"]) or "{}")
            except (TypeError, ValueError):
                continue
            cure = ejson.get("cure") if isinstance(ejson, dict) else None
            if not isinstance(cure, dict):
                continue
            if str(cure.get("skill") or "").strip().lower() == skill_lo:
                try:
                    dc = int(cure.get("dc")) if cure.get("dc") is not None else None
                except (TypeError, ValueError):
                    dc = None
                return (ck, dc)
    except Exception:
        return (None, None)
    return (None, None)


def _match_grantable_condition(
    conn: sqlite3.Connection,
    skill_key: str,
) -> tuple[Optional[str], Optional[int]]:
    """S19 (#614): czy udany SKILL_TEST tym skillem NAKŁADA którąś kondycję z katalogu?

    ODWROTNOŚĆ ``_match_curable_condition`` (S10): czyta blok ``granted_by: {skill, dc}``
    z effect_json kondycji. Zwraca ``(condition_key, dc)`` pierwszej dopasowanej kondycji
    albo ``(None, None)``. DC z KATALOGU (mechanika decyduje), nie z taga LLM. Żaden ``if key==...``.
    """
    skill_lo = str(skill_key or "").strip().lower()
    if not skill_lo:
        return (None, None)
    try:
        rows = conn.execute(
            "SELECT key, effect_json FROM game_config_conditions WHERE is_active = 1"
        ).fetchall()
        for r in rows:
            ck = r[0] if not hasattr(r, "keys") else r["key"]
            ej_raw = r[1] if not hasattr(r, "keys") else r["effect_json"]
            try:
                ejson = json.loads(ej_raw or "{}")
            except (TypeError, ValueError):
                continue
            gb = ejson.get("granted_by") if isinstance(ejson, dict) else None
            if not isinstance(gb, dict):
                continue
            if str(gb.get("skill") or "").strip().lower() == skill_lo:
                try:
                    dc = int(gb.get("dc")) if gb.get("dc") is not None else None
                except (TypeError, ValueError):
                    dc = None
                return (str(ck or "").strip().lower(), dc)
    except Exception:
        return (None, None)
    return (None, None)


def intercept_skill_test_tag(
    prose: str,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    user_text: str | None = None,
) -> tuple[str, dict | None]:
    """
    Strip first [SKILL_TEST:...] tag from prose and return pending context.
    Returns (cleaned_prose, pending_dict | None).
    """
    m = SKILL_TEST_RE.search(prose)
    if not m:
        # S7 (#601): no SKILL_TEST tag → try [GAMBLE:...] (gamble rides the same
        # pending-skill-test rails, with a validated gold stake attached).
        return _intercept_gamble_tag(prose, conn, campaign_id, character_id)

    skill_key = m.group(1).lower()
    res_type = m.group(2).upper()
    value = m.group(3).strip()

    # S6 (#586): kupiec obrażony (krytyczna porażka targowania) → blokada ponownego
    # targowania w tej scenie. Tag jest zdejmowany (gracz nie dostaje karty rzutu),
    # ale narracja pozostaje. Blokada gaśnie przy zmianie sceny/lokacji.
    if skill_key == "haggling":
        try:
            from app.services.haggle_service import is_haggle_blocked, is_haggle_capped
            gs = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            flags = json.loads((gs[0] if gs else None) or "{}")
            # AUDIT #1439: block a re-roll when the merchant is offended (crit-fail)
            # OR the per-scene attempt cap is exhausted — the tag is stripped so the
            # player gets no dice card, but the narration survives.
            if is_haggle_blocked(flags) or is_haggle_capped(flags):
                cleaned = (prose[:m.start()].rstrip() + prose[m.end():]).strip()
                return cleaned, None
        except Exception:
            pass

    # Build counter
    if res_type == "DC":
        counter = {"counter_type": "dc", "counter_key": None, "dc": int(value) if value.isdigit() else 12}
    else:
        # S4: OPPOSED value is "<stat_or_skill>" or "<stat_or_skill>:<target_name>".
        parts = [p.strip() for p in value.split(":") if p.strip()]
        counter_key = parts[0].lower() if parts else "wis"
        target_name = parts[1] if len(parts) > 1 else None
        base = _get_counter(conn, skill_key)  # default_dc for the no-actor fallback
        counter = {"counter_type": "opposed", "counter_key": counter_key, "dc": base.get("dc", 12)}
        opponent = resolve_opponent_actor(conn, campaign_id, target_name)
        if opponent:
            counter["opponent"] = opponent

    # Load character sheet for modifier
    sheet = {}
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (character_id,)
        ).fetchone()
        if row:
            sheet = json.loads(row[0] or "{}")
    except Exception:
        pass

    mod_info = calc_skill_modifier_info(sheet, skill_key)
    skill_test_id = f"st-{uuid.uuid4().hex[:8]}"

    pending = {
        "skill_test_id": skill_test_id,
        "skill_key": skill_key,
        "skill_label": _skill_label(skill_key),
        "counter": counter,
        "modifier_breakdown": mod_info,
    }

    # S10 (#605): jeśli ten skill leczy aktywną kondycję gracza, dołącz cures_condition
    # i narzuć DC z katalogu (mechanika decyduje, nie LLM). Generyczne — S19 i przyszłe kondycje.
    _cure_key, _cure_dc = _match_curable_condition(conn, character_id, skill_key)
    if _cure_key:
        pending["cures_condition"] = _cure_key
        if _cure_dc is not None and counter.get("counter_type") == "dc":
            counter["dc"] = int(_cure_dc)

    # S19 (#614): jeśli ten skill NAKŁADA kondycję (granted_by, np. stealth→hidden), dołącz
    # grants_condition_self i narzuć DC z katalogu (mechanika decyduje, nie LLM). Generyczne.
    _grant_key, _grant_dc = _match_grantable_condition(conn, skill_key)
    if _grant_key:
        pending["grants_condition_self"] = _grant_key
        if _grant_dc is not None and counter.get("counter_type") == "dc":
            counter["dc"] = int(_grant_dc)

    cleaned = prose[:m.start()].rstrip() + prose[m.end():]
    cleaned = cleaned.strip()
    return cleaned, pending


def _load_session_flags(conn: sqlite3.Connection, campaign_id: int) -> dict:
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        return json.loads((row[0] if row else None) or "{}")
    except Exception:
        return {}


def _character_gold(conn: sqlite3.Connection, character_id: int) -> int:
    try:
        row = conn.execute(
            "SELECT gold_gp FROM characters WHERE id = ? LIMIT 1", (character_id,)
        ).fetchone()
        return int((row[0] if row else 0) or 0)
    except Exception:
        return 0


def _current_location_key(conn: sqlite3.Connection, campaign_id: int) -> str:
    """Best-effort key of the current location (scopes the per-scene gamble limit)."""
    try:
        row = conn.execute(
            "SELECT gl.key FROM game_sessions gs "
            "JOIN game_locations gl ON gl.id = gs.current_location_id "
            "WHERE gs.campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if row and row[0]:
            return str(row[0])
    except Exception:
        pass
    return ""


def _intercept_gamble_tag(
    prose: str,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
) -> tuple[str, dict | None]:
    """S7 (#601): strip first [GAMBLE:...] tag → pending skill test with a stake.

    Validates the player-declared stake mechanically (≥1 gp, ≤ current gold) and
    enforces the per-scene gamble limit BEFORE creating the test. An invalid stake
    or an exhausted limit drops the tag (no dice card) — narration stays. The
    resulting pending mirrors a normal skill test (skill_key=``gamble``) plus a
    ``gamble`` sub-dict carrying the validated stake; the resolve hook then moves
    the gold via change_gold (U26)."""
    m = GAMBLE_RE.search(prose)
    if not m:
        return prose, None

    stake_raw = m.group(1)
    res_type = m.group(2).upper()
    value = m.group(3).strip()

    cleaned = (prose[:m.start()].rstrip() + prose[m.end():]).strip()

    from app.services import gamble_service as _gs
    flags = _load_session_flags(conn, campaign_id)
    location_key = _current_location_key(conn, campaign_id)

    # Anti-abuse: max gier na scenę/lokację — przekroczony limit → brak karty rzutu.
    if not _gs.can_gamble(flags, location_key):
        return cleaned, None

    # Walidacja stawki (C12/F4: kwoty z mechaniki) — niepoprawna → brak karty rzutu.
    stake, err = _gs.validate_stake(stake_raw, _character_gold(conn, character_id))
    if err:
        return cleaned, None

    # Counter: opposed CHA przeciwnika (staty z S3/S4) lub flat DC.
    if res_type == "DC":
        counter = {"counter_type": "dc", "counter_key": None,
                   "dc": int(value) if value.isdigit() else 12}
    else:
        parts = [p.strip() for p in value.split(":") if p.strip()]
        counter_key = parts[0].lower() if parts else "cha"
        target_name = parts[1] if len(parts) > 1 else None
        base = _get_counter(conn, "gamble")
        counter = {"counter_type": "opposed", "counter_key": counter_key,
                   "dc": base.get("dc", 12)}
        opponent = resolve_opponent_actor(conn, campaign_id, target_name)
        if opponent:
            counter["opponent"] = opponent

    sheet = {}
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (character_id,)
        ).fetchone()
        if row:
            sheet = json.loads(row[0] or "{}")
    except Exception:
        pass

    mod_info = calc_skill_modifier_info(sheet, "gamble")
    pending = {
        "skill_test_id": f"st-{uuid.uuid4().hex[:8]}",
        "skill_key": "gamble",
        "skill_label": _skill_label("gamble"),
        "counter": counter,
        "modifier_breakdown": mod_info,
        "gamble": {"stake": stake},
    }
    return cleaned, pending


def intercept_trap_tag(
    prose: str,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    sheet: dict,
) -> tuple[str, dict | None]:
    """
    Strip first [TRAP:...] tag; return pending trap context.
    Traps also go through the Roll Popup but carry damage/condition on fail.
    """
    m = TRAP_RE.search(prose)
    if not m:
        return prose, None

    skill_key = m.group(1).lower()
    dc = int(m.group(2))
    damage_dice = m.group(3).strip()
    condition_key = m.group(4).strip() or None

    mod_info = calc_skill_modifier_info(sheet, skill_key)
    skill_test_id = f"tr-{uuid.uuid4().hex[:8]}"

    pending = {
        "skill_test_id": skill_test_id,
        "skill_key": skill_key,
        "skill_label": _skill_label(skill_key),
        "counter": {"counter_type": "dc", "dc": dc},
        "modifier_breakdown": mod_info,
        "trap": {
            "damage_dice": damage_dice,
            "condition_key": condition_key,
        },
    }

    cleaned = prose[:m.start()].rstrip() + prose[m.end():]
    cleaned = cleaned.strip()
    return cleaned, pending


# ── Skill test resolution ─────────────────────────────────────────────────────

def _derive_outcome(d20_roll: int, mod_total: int, opponent_total: int) -> dict:
    """S1 (#581) — wyprowadź stopień testu z surowego d20 i progu przeciwnika.
    Wydzielone, bo S11 (#606) przelicza wynik drugi raz przy wymuszonym przerzucie."""
    player_total = d20_roll + int(mod_total)
    nat20 = d20_roll == 20
    nat1 = d20_roll == 1
    margin = player_total - opponent_total
    success = nat20 or (not nat1 and player_total >= opponent_total)
    # Nat 20 / nat 1 mają ABSOLUTNE pierwszeństwo nad marginesem.
    if nat20:
        outcome = "CRITICAL_SUCCESS"
    elif nat1:
        outcome = "CRITICAL_FAILURE"
    elif margin >= 5:
        outcome = "CRITICAL_SUCCESS"
    elif margin <= -5:
        outcome = "CRITICAL_FAILURE"
    elif margin >= 0:
        outcome = "SUCCESS"
    else:
        outcome = "FAILURE"
    return {
        "d20_roll": d20_roll,
        "player_total": player_total,
        "margin": margin,
        "outcome": outcome,
        "nat20": nat20,
        "nat1": nat1,
        "success": success,
    }


def resolve_skill_test(
    d20_roll: int,
    pending: dict,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    session_flags: dict | None = None,
) -> dict:
    """
    Resolve a pending skill test given the player's d20 roll.
    Returns resolution result dict for narrator context injection.

    S11 (#606): when ``session_flags`` is provided, an active ``cursed`` ("zły omen")
    condition may force-reroll a FAVOURABLE result to the worse roll (budget 1×/scene,
    mutated into ``session_flags``). A failed result with an active ``inspired`` condition
    advertises ``reroll_available`` so the UI can offer a keep-best reroll. Both ride the
    generic ``reroll`` primitive — zero ``if condition_key == ...`` (Zasada 1 FAZY S).
    """
    skill_key = pending.get("skill_key", "perception")
    mod_info = pending.get("modifier_breakdown", {})
    counter = pending.get("counter", {"counter_type": "dc", "dc": 12})
    mod_total = int(mod_info.get("total", 0))

    # #1461: Wzrok górnika — w aktywnej sesji lochu (session_flags.dungeon_run) krasnolud
    # dostaje +3 do percepcji/obserwacji/pułapek, człowiek −4 (kara za brak darkvision).
    # Data-driven z dungeon_service.get_darkvision_bonus; obejmuje wykrywanie pułapek
    # (te same rzuty percepcji z tagu [TRAP:...]). Bonus wchodzi do rzutu (mod_total).
    _PERCEPTION_SKILLS = {"perception", "awareness", "investigation", "spot", "search"}
    darkvision_delta = 0
    try:
        _in_dungeon = bool((session_flags or {}).get("dungeon_run"))
        if _in_dungeon and str(skill_key).strip().lower() in _PERCEPTION_SKILLS:
            from app.services.dungeon_service import get_darkvision_bonus
            _dv = get_darkvision_bonus(character_id, is_dungeon=True)
            darkvision_delta = int(_dv.get("perception_bonus", 0)) + int(_dv.get("darkness_penalty", 0))
            if darkvision_delta:
                mod_total += darkvision_delta
    except Exception:
        darkvision_delta = 0

    # Opponent side (rolled once — a forced reroll keeps the same threshold).
    opponent_total, opponent_roll = _resolve_opponent(conn, counter, campaign_id)

    derived = _derive_outcome(d20_roll, mod_total, opponent_total)

    result = {
        "skill_key": skill_key,
        "skill_label": pending.get("skill_label", skill_key),
        "d20_roll": derived["d20_roll"],
        "modifier": mod_total,
        "player_total": derived["player_total"],
        "opponent_total": opponent_total,
        "opponent_roll": opponent_roll,
        "margin": derived["margin"],
        "outcome": derived["outcome"],
        "nat20": derived["nat20"],
        "nat1": derived["nat1"],
        "success": derived["success"],
        "darkvision_bonus": darkvision_delta,  # #1461: +3 dwarf / −4 human w lochu (0 poza)
    }

    # S11 (#606) — wymuszony przerzut ("zły omen"): klątwa psuje UDANY (korzystny) test.
    # Nat 20/nat 1 nietknięte (rozstrzygnięte absolutnie). Budżet 1×/scenę z session_flags.
    if session_flags is not None and result["success"] and not result["nat20"] and not result.get("trap"):
        try:
            from app.services import reroll_service as _rr
            forced = _rr.extract_reroll_effects(
                _rr.load_active_conditions(conn, character_id), mode="forced_keep_worst"
            )
            loc_key = _current_location_key(conn, campaign_id)
            if forced and _rr.omen_available(session_flags, loc_key):
                second = random.randint(1, 20)
                kept_d20 = _rr.keep_worse(d20_roll, second)
                _rr.consume_omen(session_flags, loc_key)
                result["omen_applied"] = True
                result["omen_original"] = {
                    "d20_roll": d20_roll,
                    "player_total": derived["player_total"],
                    "outcome": derived["outcome"],
                }
                rederived = _derive_outcome(kept_d20, mod_total, opponent_total)
                result.update({
                    "d20_roll": rederived["d20_roll"],
                    "player_total": rederived["player_total"],
                    "margin": rederived["margin"],
                    "outcome": rederived["outcome"],
                    "nat20": rederived["nat20"],
                    "nat1": rederived["nat1"],
                    "success": rederived["success"],
                })
        except Exception:
            pass

    # Handle trap damage/condition on failure (po ewentualnym przerzucie omenu).
    trap = pending.get("trap")
    if trap and not result["success"]:
        damage_dice = trap.get("damage_dice", "1d4")
        dmg = _roll_dice(damage_dice)
        result["trap_damage"] = dmg
        result["trap_damage_dice"] = damage_dice
        result["trap_condition_key"] = trap.get("condition_key")
        # Apply HP damage
        _hp_before_trap = None
        try:
            _r = conn.execute("SELECT sheet_json FROM characters WHERE id=?", (character_id,)).fetchone()
            if _r:
                _hp_before_trap = int(json.loads(_r[0] or "{}").get("current_hp", 0))
        except Exception:
            _hp_before_trap = None
        _apply_trap_damage(character_id, dmg, conn)
        # #761: rejestr obrażeń z pułapki
        if _hp_before_trap is not None:
            try:
                from app.services.state_log_service import record_state_change
                record_state_change(
                    campaign_id=campaign_id, resource="hp", character_id=character_id,
                    before_val=_hp_before_trap, after_val=max(0, _hp_before_trap - dmg),
                    cause="trap", meta={"damage_dice": damage_dice, "skill_key": result.get("skill_key")},
                )
            except Exception:
                pass

    # S11 (#606) — przerzut gracza (inspired): nieudany test → oferta keep-best na karcie.
    if not result["success"]:
        try:
            from app.services import reroll_service as _rr
            offer = _rr.player_reroll_offer(conn, character_id)
            if offer:
                result["reroll_available"] = offer
        except Exception:
            pass

    # #754: strukturalny rejestr — test skilla (jeden punkt dla WSZYSTKICH ścieżek skill-test).
    try:
        from app.services.dice_log_service import record_dice_roll as _rec_roll
        _tn = None
        try:
            _tn = conn.execute(
                "SELECT COALESCE(MAX(turn_number),0) FROM campaign_turns WHERE campaign_id=?",
                (campaign_id,),
            ).fetchone()[0]
        except Exception:
            _tn = None
        _rec_roll(
            campaign_id=campaign_id,
            roll_type="skill_test",
            character_id=character_id,
            turn_number=_tn,
            actor="player",
            notation="1d20",
            raw_rolls=[int(result["d20_roll"])],
            modifiers={
                "total": mod_total,
                "stat_mod": mod_info.get("stat_mod"),
                "skill_rank": mod_info.get("skill_rank"),
                "proficiency": mod_info.get("proficiency"),
                # #1054: bez tego log wygląda jak rzut bez bonusu przewagi (gate +2/+4)
                "advantage_bonus": mod_info.get("advantage_bonus"),
            },
            total=int(result["player_total"]),
            dc=int(opponent_total),
            outcome=str(result["outcome"]).lower(),
            meta={"skill_key": result["skill_key"], "skill_label": result["skill_label"],
                  "omen_applied": result.get("omen_applied", False)},
        )
    except Exception:
        pass

    return result


def _roll_dice(expr: str) -> int:
    m = re.match(r"^(\d*)d(\d+)([+-]\d+)?$", expr.lower().strip())
    if not m:
        return 1
    n = int(m.group(1) or 1)
    sides = int(m.group(2))
    bonus = int(m.group(3) or 0)
    return max(0, sum(random.randint(1, sides) for _ in range(max(1, n))) + bonus)


def _apply_trap_damage(character_id: int, damage: int, conn: sqlite3.Connection) -> None:
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        if not row:
            return
        sheet = json.loads(row[0] or "{}")
        cur_hp = int(sheet.get("current_hp", 0))
        new_hp = max(0, cur_hp - damage)
        sheet["current_hp"] = new_hp
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), character_id),
        )
        conn.commit()
    except Exception:
        pass


# ── Narrator context for resolution ──────────────────────────────────────────

def build_skill_result_context(result: dict) -> str:
    """Build context string to inject into the second narrator call."""
    outcome_label = {
        "CRITICAL_SUCCESS": "Krytyczny sukces!",
        "SUCCESS": "Sukces",
        "FAILURE": "Niepowodzenie",
        "CRITICAL_FAILURE": "Krytyczne niepowodzenie!",
    }.get(result["outcome"], result["outcome"])

    margin = int(result.get("margin", result.get("player_total", 0) - result.get("opponent_total", 0)))
    margin_str = f"+{margin}" if margin >= 0 else str(margin)
    # Słowny opis stopnia — narrator ma 4 stany zamiast 2 (S1 #581).
    if margin >= 5:
        margin_word = "z dużą nawiązką"
    elif margin >= 0:
        margin_word = "z zapasem" if margin >= 2 else "na styk"
    elif margin >= -4:
        margin_word = "o włos"
    else:
        margin_word = "wyraźnie poniżej progu"

    lines = [
        f"[WYNIK TESTU UMIEJĘTNOŚCI]",
        f"Umiejętność: {result['skill_label']}",
        f"Rzut gracza: {result['d20_roll']} + {result['modifier']} = {result['player_total']}",
        f"Próg: {result['opponent_total']}" + (f" (przeciwnik rzucił {result['opponent_roll']})" if result.get('opponent_roll') else ""),
        f"Margines: {margin_str} ({margin_word})",
        f"Wynik: {outcome_label}",
    ]
    if result.get("nat20"):
        lines.append("Naturalny 20 — wyjątkowy sukces.")
    if result.get("nat1"):
        lines.append("Naturalny 1 — komplikacja w narracji.")
    if result.get("trap_damage"):
        lines.append(f"Pułapka zadała {result['trap_damage']} obrażeń.")
    return "\n".join(lines)
