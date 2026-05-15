import json
import logging
import os
import random
import re
import sqlite3

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.character_creation_config import (
    CREATION_SKILL_POOL,
    MAX_SKILL_LVL_AT_CREATION,
    PLAYER_SWAP_SLOTS,
    roll_4d6_drop_lowest,
    roll_creation_skills,
)
from app.services.loot_service import grant_loot_to_character
from app.services.vitality_service import calculate_hp, calculate_mana
from app.services.campaign_plan_service import generate_v2_campaign_plan
from app.services.turn_pipeline import generate_opening_scene as generate_v2_opening_scene
from app.services.gm_plan_generation_service import generate_initial_gm_plan_with_retries
from app.services.llm_service import generate_chat
from app.services.user_llm_settings import get_user_llm_settings_full
from app.system_prompt_loader import SYSTEM_PROMPT_TEXT
from app.services.location_intent_parser import parse as parse_location_intent
from app.services.location_validator import persist_ai_generated_location

DB_PATH = "/data/ai_gm.db"
HIDDEN_POTENTIALS = ["blessed", "cursed", "gifted", "hollow"]
logger = logging.getLogger(__name__)

router = APIRouter()


class CharacterCreateRequest(BaseModel):
    user_id: int
    name: str
    system_id: str
    sheet_json: dict = {}
    location: str | None = None
    is_active: int = 1


class CharacterSheetPatchRequest(BaseModel):
    sheet_json: dict


class NarrativeItemCreateRequest(BaseModel):
    label: str
    description: str | None = None
    source: str = "gm"
    given_at: str | None = None


def _ensure_game_session(conn: sqlite3.Connection, campaign_id: int) -> str:
    """
    Ensure campaign has a game_sessions row so location tracking can persist.
    """
    session_id = str(campaign_id)
    conn.execute(
        """
        INSERT OR IGNORE INTO game_sessions (id, campaign_id, session_flags)
        VALUES (?, ?, '{}')
        """,
        (session_id, campaign_id),
    )
    conn.commit()
    return session_id


def _ensure_opening_location_fallback(
    conn: sqlite3.Connection,
    campaign_id: int,
    session_id: str,
    opening_message: str | None,
    requested_location: str | None,
) -> int | None:
    """
    Create a deterministic start location when opening scene has no location_intent.
    """
    key = f"campaign_{campaign_id}_start"
    row = conn.execute(
        "SELECT id FROM game_locations WHERE key = ? LIMIT 1",
        (key,),
    ).fetchone()
    if row:
        location_id = int(row["id"])
    else:
        label = (requested_location or "").strip()
        if not label or label.lower() in {"here", "start", "unknown", "nieznane miejsce"}:
            label = f"Punkt startowy kampanii {campaign_id}"
        description = (opening_message or "").strip()
        if description:
            description = description[:500]
        conn.execute(
            """
            INSERT INTO game_locations
              (key, label, description, location_type, ai_generated, approved, is_active)
            VALUES (?, ?, ?, 'macro', 1, 1, 1)
            """,
            (key, label, description),
        )
        conn.commit()
        location_id = int(conn.execute("SELECT id FROM game_locations WHERE key = ?", (key,)).fetchone()["id"])

    conn.execute(
        "UPDATE game_sessions SET current_location_id = ? WHERE id = ?",
        (location_id, session_id),
    )
    conn.commit()
    logger.info(
        "[opening_scene] opening_location_fallback_created campaign_id=%s session_id=%s location_id=%s",
        campaign_id,
        session_id,
        location_id,
    )
    return location_id


def _deep_merge_dicts(base: dict, incoming: dict) -> dict:
    merged = dict(base)
    for key, value in incoming.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _stat_modifier(value: int) -> int:
    return (int(value) - 10) // 2


def _default_identity_block() -> dict:
    return {
        "appearance": "",
        "personality": "",
        "flaw": "",
        "bonds": [{"text": "", "strength": "strong", "origin": "creation"}],
        "secret": "",
    }


def _ensure_identity_block(sheet: dict) -> None:
    """Ensure sheet_json contains a full identity block (additive; does not remove keys)."""
    if not isinstance(sheet.get("identity"), dict):
        sheet["identity"] = _default_identity_block()
        return
    ident = sheet["identity"]
    ident.setdefault("appearance", "")
    ident.setdefault("personality", "")
    ident.setdefault("flaw", "")
    ident.setdefault("secret", "")
    bonds = ident.get("bonds")
    if not isinstance(bonds, list) or not bonds:
        ident["bonds"] = [{"text": "", "strength": "strong", "origin": "creation"}]
    else:
        for b in bonds:
            if isinstance(b, dict):
                b.setdefault("text", "")
                b.setdefault("strength", "strong")
                b.setdefault("origin", "creation")


def _ensure_narrative_items_block(sheet: dict) -> None:
    items = sheet.get("narrative_items")
    if not isinstance(items, list):
        sheet["narrative_items"] = []


def _build_character_sheet(
    base_sheet: dict,
    archetype: str | None = None,
    *,
    apply_archetype_skill_minimums: bool = True,
) -> dict:
    sheet = dict(base_sheet or {})
    _preserved_runtime = {}
    for _k in ("death_save_failures",):
        if _k in sheet and sheet.get(_k) is not None:
            try:
                _preserved_runtime[_k] = int(sheet[_k])
            except (TypeError, ValueError):
                _preserved_runtime[_k] = sheet[_k]
    source_stats = dict(sheet.get("stats") or {})
    stats = {}
    for upper_key in ("STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"):
        lower_key = upper_key.lower()
        stats[upper_key] = int(source_stats.get(upper_key, source_stats.get(lower_key, 10)))
    skills = dict(sheet.get("skills") or {})

    normalized_archetype = (archetype or sheet.get("archetype") or "").strip().lower()
    if normalized_archetype not in ("warrior", "scholar"):
        normalized_archetype = "warrior"
    sheet["archetype"] = normalized_archetype

    # Archetype bonuses on top of existing values.
    if normalized_archetype == "warrior":
        stats["STR"] = int(stats.get("STR", 10)) + 2
        stats["CON"] = int(stats.get("CON", 10)) + 1
        if apply_archetype_skill_minimums:
            skills["athletics"] = max(int(skills.get("athletics", 0)), 2)
            skills["melee_attack"] = max(int(skills.get("melee_attack", 0)), 2)
            skills["intimidation"] = max(int(skills.get("intimidation", 0)), 1)
    else:
        stats["INT"] = int(stats.get("INT", 10)) + 2
        stats["WIS"] = int(stats.get("WIS", 10)) + 1
        if apply_archetype_skill_minimums:
            skills["arcana"] = max(int(skills.get("arcana", 0)), 2)
            skills["lore"] = max(int(skills.get("lore", 0)), 2)
            skills["spell_attack"] = max(int(skills.get("spell_attack", 0)), 1)

    # Keep stat values inside the defined 1-20 range.
    for stat_key in ("STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"):
        stats[stat_key] = max(1, min(20, int(stats.get(stat_key, 10))))

    con_mod = _stat_modifier(stats["CON"])
    int_mod = _stat_modifier(stats["INT"])

    level = int(sheet.get("level", 1) or 1)
    hp = calculate_hp(normalized_archetype, stats["CON"], level)
    mana = calculate_mana(normalized_archetype, stats["INT"], level)
    sheet["current_hp"] = hp
    sheet["max_hp"] = hp
    sheet["current_mana"] = mana
    sheet["max_mana"] = mana

    if "hidden_potential" not in sheet:
        sheet["hidden_potential"] = random.choice(HIDDEN_POTENTIALS)

    sheet["stats"] = stats
    sheet["skills"] = skills

    # Modifiers (floor((value - 10) / 2)) for core + luck — used by UI / exports.
    sheet["stat_modifiers"] = {
        k: (int(stats[k]) - 10) // 2 for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK")
    }
    dex_mod = sheet["stat_modifiers"]["DEX"]
    sheet["defense"] = {"base": 10 + dex_mod}

    _ensure_identity_block(sheet)
    _ensure_narrative_items_block(sheet)
    sheet.update(_preserved_runtime)
    return sheet


def _strip_hidden_fields(sheet: dict) -> dict:
    sanitized = dict(sheet or {})
    sanitized.pop("hidden_potential", None)
    sanitized.pop("gm_only", None)  # V2: never expose gm_only (secret_predisposition etc.) to player
    return sanitized


# --- finalize-sheet (Phase 7.6): stat/skill redistribution + identity (player review) ---

SIX_CORE_STATS = ("STR", "DEX", "CON", "INT", "WIS", "CHA")
STAT_ROLL_MIN = 8
STAT_ROLL_MAX = 18
_STAT_OVERRIDE_ALIASES = {
    "str": "STR",
    "strength": "STR",
    "dex": "DEX",
    "dexterity": "DEX",
    "con": "CON",
    "constitution": "CON",
    "int": "INT",
    "intelligence": "INT",
    "wis": "WIS",
    "wisdom": "WIS",
    "cha": "CHA",
    "charisma": "CHA",
    "STR": "STR",
    "DEX": "DEX",
    "CON": "CON",
    "INT": "INT",
    "WIS": "WIS",
    "CHA": "CHA",
}


def _core_bases_from_stored_stats(stats: dict, archetype: str) -> dict[str, int]:
    """Subtract archetype stat bonuses to recover pre-bonus bases (what _build_character_sheet adds)."""
    out: dict[str, int] = {}
    for k in SIX_CORE_STATS:
        lk = k.lower()
        out[k] = int(stats.get(k, stats.get(lk, 10)))
    a = (archetype or "warrior").strip().lower()
    if a not in ("scholar", "warrior"):
        a = "warrior"
    if a == "warrior":
        out["STR"] -= 2
        out["CON"] -= 1
    else:
        out["INT"] -= 2
        out["WIS"] -= 1
    return out


def _normalize_stat_override_key(raw: str) -> str | None:
    k = (raw or "").strip()
    if not k:
        return None
    if k in _STAT_OVERRIDE_ALIASES:
        return _STAT_OVERRIDE_ALIASES[k]
    kl = k.lower()
    return _STAT_OVERRIDE_ALIASES.get(kl)


def _validate_creation_skills_after_swap(
    skills_orig: dict[str, int],
    skills_after: dict[str, int],
    slot_current: dict[str, str] | None,
) -> int:
    """
    Rolled creation slots (skills_orig[k] > 0) may move to another skill key via swap.
    Budget counts only **level changes** per slot: sum_r |after[c_r] - orig[r]| ≤ PLAYER_SWAP_SLOTS.
    Swapping rank r from Survival to Arcana at the same level costs 0.
    """
    rolled = [k for k in sorted(CREATION_SKILL_POOL) if int(skills_orig.get(k, 0) or 0) > 0]
    if not rolled:
        return 0

    sc = slot_current or {}
    seen_targets: set[str] = set()
    mapping: dict[str, str] = {}
    for r in rolled:
        raw = sc.get(r, r)
        ck = str(raw).strip()
        if ck not in CREATION_SKILL_POOL:
            raise HTTPException(
                status_code=400,
                detail=f"skill_slot_current: unknown skill {ck!r} for rolled slot {r!r}.",
            )
        if ck in seen_targets:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"skill_slot_current: two creation slots map to the same skill {ck!r}. "
                    "Each rolled slot must target a distinct skill key."
                ),
            )
        seen_targets.add(ck)
        mapping[r] = ck

    for k in CREATION_SKILL_POOL:
        v = int(skills_after.get(k, 0) or 0)
        if k in seen_targets:
            continue
        if v != 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Skill {k!r} has rank {v} but is not the target of any rolled creation slot. "
                    "After swaps, only slot targets may be non-zero (plus keys with rank 0 everywhere else)."
                ),
            )

    budget = 0
    for r in rolled:
        ck = mapping[r]
        o = int(skills_orig.get(r, 0) or 0)
        f = int(skills_after.get(ck, 0) or 0)
        budget += abs(f - o)

    if budget > PLAYER_SWAP_SLOTS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Too many skill level changes vs the rolled creation set (total {budget} > {PLAYER_SWAP_SLOTS}). "
                "Swapping one skill for another at the same rank does not use this budget; only changing "
                "ranks on your rolled slots does."
            ),
        )
    return budget


def _coerce_creation_skills_payload(
    incoming: dict | None, sheet_skills: dict
) -> dict[str, int]:
    base = {k: int(sheet_skills.get(k, 0) or 0) for k in CREATION_SKILL_POOL}
    if incoming is None:
        return base
    out = dict(base)
    for raw_k, raw_v in incoming.items():
        k = str(raw_k).strip()
        if k not in CREATION_SKILL_POOL:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown skill key {k!r}. Allowed keys are the creation skill pool.",
            )
        try:
            v = int(raw_v)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"Skill rank for {k!r} must be an integer.",
            ) from None
        if v < 0 or v > MAX_SKILL_LVL_AT_CREATION:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Skill {k!r} must be between 0 and {MAX_SKILL_LVL_AT_CREATION} "
                    f"at character creation; got {v}."
                ),
            )
        out[k] = v
    return out


class BondEntry(BaseModel):
    """V2 structured bond."""
    description: str = ""
    type: str = "person"  # person | place | object | ideal


class WeaknessEntry(BaseModel):
    """V2 structured weakness."""
    description: str = ""
    type: str = "flaw"  # fear | flaw | addiction | trauma


class IdentityOverrideIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    appearance: str | None = None
    personality: str | None = None
    # V2 structured fields
    bonds: list[dict] | None = None       # [{description, type}]
    weaknesses: list[dict] | None = None  # [{description, type}]
    # Legacy V1 fields (kept for backward compat)
    flaw: str | None = None
    secret: str | None = None
    bond: str | None = None


class FinalizeSheetRequest(BaseModel):
    stat_overrides: dict[str, int] | None = None
    skills: dict[str, int] | None = None
    skill_slot_current: dict[str, str] | None = None
    identity_overrides: IdentityOverrideIn | None = None


class GeneratedIdentityPreview(BaseModel):
    """LLM preview for identity fields (not yet merged into sheet_json)."""

    appearance: str
    personality: str
    # V2 structured fields
    bonds: list[dict] = []      # [{description, type}] — player-editable
    weaknesses: list[dict] = [] # [{description, type}] — player-editable
    # Legacy V1 fields (kept for backward compat with old frontend)
    flaw: str = ""
    bond: str = ""
    secret: str = ""


def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


_SESSION_LANG_LABELS = {
    "pl": "Polish (polski)",
    "en": "English",
    "de": "German (Deutsch)",
    "es": "Spanish (español)",
    "fr": "French (français)",
    "it": "Italian (italiano)",
}


def _identity_generation_user_prompt(
    name: str, char_class: str, backstory: str, session_language: str,
    stats: dict | None = None, skills: dict | None = None,
) -> str:
    lang = (session_language or "pl").strip().lower() or "pl"
    label = _SESSION_LANG_LABELS.get(lang, f"the campaign session language (ISO {lang})")

    # Build stat context for better identity generation
    stat_lines = ""
    if stats:
        top_stats = sorted(stats.items(), key=lambda x: -int(x[1] or 0))[:3]
        stat_lines = f"Najwyższe statystyki: {', '.join(f'{k}={v}' for k, v in top_stats)}\n"
    skill_lines = ""
    if skills:
        top_skills = [(k, v) for k, v in skills.items() if int(v or 0) >= 2][:3]
        if top_skills:
            skill_lines = f"Główne umiejętności: {', '.join(f'{k}({v})' for k, v in top_skills)}\n"

    return (
        f"Postać: {name}, Archetype: {char_class}\n"
        f"Tło: {backstory or '(brak notatki)'}\n"
        f"{stat_lines}{skill_lines}\n"
        f"Język kampanii (OBOWIĄZKOWY dla wszystkich wartości): {lang} ({label}).\n\n"
        "Wygeneruj tożsamość bohatera jako JSON. ZASADY BEZWZGLĘDNE:\n"
        '1. Każde pole MUSI zawierać niepusty tekst.\n'
        '2. "appearance": opis wyglądu fizycznego (2-3 zdania)\n'
        '3. "personality": dominująca cecha charakteru (2-3 zdania, głos, nawyki, sposób bycia)\n'
        '4. "bonds": lista DOKŁADNIE 2 więzi, każda z polami "description" i "type".\n'
        '   type musi być jednym z: "person", "place", "object", "ideal"\n'
        '   Przykład: [{"description": "Przysiągł zemścić się na lordzie...", "type": "person"},\n'
        '              {"description": "Nie rozstaje się ze starym medalionem ojca", "type": "object"}]\n'
        '5. "weaknesses": lista DOKŁADNIE 2 słabości, każda z polami "description" i "type".\n'
        '   type musi być jednym z: "fear", "flaw", "addiction", "trauma"\n'
        '   Przykład: [{"description": "Obsesyjny strach przed ogniem...", "type": "fear"},\n'
        '              {"description": "Sięga po alkohol gdy sytuacja staje się trudna", "type": "addiction"}]\n'
        '6. "secret_predisposition": 1-2 zdania opisujące UKRYTĄ cechę charakteru której postać NIE jest świadoma.\n'
        '   To tajemnica dla GM — nie dla gracza. Coś co wyjdzie pod presją.\n'
        '   Przykład: "Mimo pozorów hardości, Aldric czuje głęboką potrzebę bycia docenionym."\n'
        "Zwróć WYŁĄCZNIE poprawny JSON, bez komentarzy, bez markdown."
    )


_IDENTITY_RETRY_USER = (
    "Poprzednia odpowiedź była niekompletna lub miała błędny format. "
    "Wygeneruj ponownie TEN SAM JSON. Pamiętaj: bonds i weaknesses to listy DOKŁADNIE 2 elementów "
    "z polami 'description' i 'type'. Żadne pole nie może być puste."
)


def _bond_text_from_identity_dict(data: dict) -> str:
    """Legacy helper — extracts first bond as plain text."""
    bonds = data.get("bonds")
    if isinstance(bonds, list) and bonds:
        b0 = bonds[0]
        if isinstance(b0, dict):
            return str(b0.get("description") or b0.get("text") or "").strip()
    return str(data.get("bond") or "").strip()


def _parse_v2_bonds(data: dict) -> list[dict]:
    """Parse bonds list into V2 format [{description, type}]."""
    raw = data.get("bonds")
    if not isinstance(raw, list):
        # Fallback: wrap legacy bond text
        text = _bond_text_from_identity_dict(data)
        return [{"description": text, "type": "ideal"}] * 2 if text else []
    result = []
    for b in raw[:2]:
        if isinstance(b, dict):
            desc = str(b.get("description") or b.get("text") or "").strip()
            btype = str(b.get("type") or "person").strip().lower()
            if btype not in ("person", "place", "object", "ideal"):
                btype = "person"
            if desc:
                result.append({"description": desc, "type": btype})
    return result


def _parse_v2_weaknesses(data: dict) -> list[dict]:
    """Parse weaknesses list into V2 format [{description, type}]."""
    raw = data.get("weaknesses")
    if not isinstance(raw, list):
        # Fallback: wrap legacy flaw
        flaw = str(data.get("flaw") or "").strip()
        return [{"description": flaw, "type": "flaw"}] * 2 if flaw else []
    result = []
    for w in raw[:2]:
        if isinstance(w, dict):
            desc = str(w.get("description") or w.get("text") or "").strip()
            wtype = str(w.get("type") or "flaw").strip().lower()
            if wtype not in ("fear", "flaw", "addiction", "trauma"):
                wtype = "flaw"
            if desc:
                result.append({"description": desc, "type": wtype})
    return result


def _identity_dict_fields_non_empty(data: dict) -> bool:
    appearance = str(data.get("appearance") or "").strip()
    personality = str(data.get("personality") or "").strip()
    bonds = _parse_v2_bonds(data)
    weaknesses = _parse_v2_weaknesses(data)
    return bool(appearance and personality and bonds and weaknesses)


def _parse_identity_llm_to_dict(raw: str) -> dict:
    cleaned = _strip_code_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from LLM: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("LLM JSON must be an object")
    return data


def _dict_to_identity_preview(data: dict) -> GeneratedIdentityPreview:
    bonds = _parse_v2_bonds(data)
    weaknesses = _parse_v2_weaknesses(data)
    # Pad to 2 if LLM returned fewer
    while len(bonds) < 2:
        bonds.append({"description": "...", "type": "ideal"})
    while len(weaknesses) < 2:
        weaknesses.append({"description": "...", "type": "flaw"})
    return GeneratedIdentityPreview(
        appearance=str(data.get("appearance") or "").strip(),
        personality=str(data.get("personality") or "").strip(),
        bonds=bonds,
        weaknesses=weaknesses,
        # Legacy fields for backward compat
        flaw=weaknesses[0]["description"] if weaknesses else "",
        bond=bonds[0]["description"] if bonds else "",
        secret=str(data.get("secret_predisposition") or data.get("secret") or "").strip(),
    )


# Opening scene uses the same unified prompt as narrative turns and /api/gm/chat (fantasy).
OPENING_SYSTEM_PROMPT = SYSTEM_PROMPT_TEXT


# ── Task 42: Character-first flow endpoints ───────────────────────────────────

@router.get("/characters")
def list_user_characters(user_id: int):
    """List all characters (heroes) belonging to a user, across all campaigns."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT c.id, c.campaign_id, c.user_id, c.name, c.system_id,
                   c.sheet_json, c.location, c.is_active, c.created_at, c.status,
                   cam.title AS campaign_title, cam.status AS campaign_status
            FROM characters c
            LEFT JOIN campaigns cam ON cam.id = c.campaign_id
            WHERE c.user_id = ? AND c.is_active = 1
            ORDER BY c.created_at DESC
            """,
            (user_id,),
        ).fetchall()
        heroes = []
        for row in rows:
            item = dict(row)
            try:
                sheet = json.loads(item.get("sheet_json") or "{}")
            except Exception:
                sheet = {}
            item["sheet_json"] = _strip_hidden_fields(sheet)
            heroes.append(item)
        return {"heroes": heroes}
    finally:
        conn.close()


@router.post("/characters")
def create_standalone_character(req: dict = Body(...)):
    """Create a character without a campaign (hero-first flow). campaign_id stays NULL.
    Rolls stats and skills identically to the campaign-scoped endpoint so the wizard
    steps 2 and 3 work correctly.
    """
    user_id = req.get("user_id")
    name = (req.get("name") or "").strip()
    system_id = req.get("system_id", "fantasy")
    base_sheet = dict(req.get("sheet_json") or {})

    if not user_id or not name:
        raise HTTPException(status_code=400, detail="user_id and name are required")

    archetype = str(base_sheet.get("archetype") or "warrior").strip().lower()
    if archetype not in ("warrior", "scholar"):
        archetype = "warrior"

    # Roll stats and skills exactly as the campaign-scoped endpoint does
    base_sheet["archetype"] = archetype
    base_sheet["stats"] = {
        k: max(STAT_ROLL_MIN, min(STAT_ROLL_MAX, roll_4d6_drop_lowest()))
        for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK")
    }
    skills_rolled = roll_creation_skills(archetype)
    base_sheet["skills"] = skills_rolled
    base_sheet["skills_at_creation"] = dict(skills_rolled)

    created_sheet = _build_character_sheet(base_sheet, archetype, apply_archetype_skill_minimums=False)
    created_sheet["skills_at_creation"] = dict(skills_rolled)
    created_sheet.setdefault("narrative_items", [])

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        cur = conn.execute(
            """
            INSERT INTO characters
                (campaign_id, user_id, name, system_id, sheet_json, is_active, status, created_at)
            VALUES (NULL, ?, ?, ?, ?, 1, 'idle', datetime('now'))
            """,
            (int(user_id), name, system_id, json.dumps(created_sheet, ensure_ascii=False)),
        )
        conn.commit()
        char_id = cur.lastrowid
        row = conn.execute("SELECT * FROM characters WHERE id = ?", (char_id,)).fetchone()
        item = dict(row)
        try:
            item["sheet_json"] = json.loads(item["sheet_json"])
        except Exception:
            item["sheet_json"] = {}
        return item
    finally:
        conn.close()


@router.patch("/characters/{character_id}/status")
def update_character_status(character_id: int, req: dict = Body(...)):
    """Update hero status: idle | in_campaign | in_dungeon."""
    status = req.get("status", "idle")
    campaign_id = req.get("campaign_id")  # set when entering campaign
    if status not in ("idle", "in_campaign", "in_dungeon"):
        raise HTTPException(status_code=422, detail="status must be idle | in_campaign | in_dungeon")
    conn = sqlite3.connect(DB_PATH)
    try:
        if campaign_id is not None:
            conn.execute(
                "UPDATE characters SET status = ?, campaign_id = ? WHERE id = ?",
                (status, int(campaign_id), character_id),
            )
        else:
            conn.execute(
                "UPDATE characters SET status = ? WHERE id = ?",
                (status, character_id),
            )
        conn.commit()
        return {"ok": True, "status": status}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/characters")
def list_characters(campaign_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    campaign = conn.execute(
        "SELECT id FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()

    if not campaign:
        conn.close()
        raise HTTPException(status_code=404, detail="Campaign not found")

    rows = conn.execute(
        """
        SELECT id, campaign_id, user_id, name, system_id, sheet_json, location, is_active, created_at
        FROM characters
        WHERE campaign_id = ?
        ORDER BY id ASC
        """,
        (campaign_id,),
    ).fetchall()

    conn.close()

    characters = []
    for row in rows:
        item = dict(row)
        try:
            item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
        except Exception:
            item["sheet_json"] = {}
        item["sheet_json"] = _strip_hidden_fields(item["sheet_json"])
        characters.append(item)

    return {"characters": characters}


@router.get("/characters/{character_id}")
def get_character(character_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT id, campaign_id, user_id, name, system_id, sheet_json, location, is_active, created_at
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Character not found")

    item = dict(row)
    try:
        item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
    except Exception:
        item["sheet_json"] = {}
    item["sheet_json"] = _strip_hidden_fields(item["sheet_json"])

    return item


@router.get("/characters/{character_id}/sheet")
def get_character_sheet(character_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT sheet_json
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        sheet_json = json.loads(row["sheet_json"]) if row["sheet_json"] else {}
    except Exception:
        sheet_json = {}
    return {"sheet_json": _strip_hidden_fields(sheet_json)}


class SpendSkillXpRequest(BaseModel):
    """Buy +1 rank in a skill; cost from `game_config_meta.xp_skill_rank_costs` ([S10])."""

    model_config = ConfigDict(extra="ignore")
    skill_key: str


class SpendStatXpRequest(BaseModel):
    """Raise a core stat by 1; cost from `game_config_meta.xp_stat_point_costs` (**T21**)."""

    model_config = ConfigDict(extra="ignore")
    stat_key: str


class GrantMgXpRequest(BaseModel):
    """Manual XP from campaign owner (MG); audited (**[S10d]**)."""

    model_config = ConfigDict(extra="ignore")
    amount: int | None = Field(default=None, ge=1, le=50_000)
    reward_key: str | None = Field(
        default=None,
        max_length=80,
        description="Opcjonalnie: klucz z game_config_xp_rewards (T12) — kwota z DB, nie z LLM.",
    )
    reason: str = Field(..., min_length=1, max_length=2000)

    @model_validator(mode="after")
    def amount_or_reward_key(self):
        rk = (self.reward_key or "").strip()
        if rk:
            self.reward_key = rk
            return self
        if self.amount is not None and self.amount >= 1:
            return self
        raise ValueError("Provide amount (1..50000) or reward_key from game_config_xp_rewards")


@router.get("/characters/{character_id}/xp")
def get_character_xp(character_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        from app.services import xp_service

        try:
            snap = xp_service.get_xp_snapshot(conn, character_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Character not found") from None
        return snap
    finally:
        conn.close()


@router.post("/characters/{character_id}/xp/spend-skill")
def spend_character_skill_xp(character_id: int, req: SpendSkillXpRequest):
    from app.services import xp_service

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        try:
            result = xp_service.spend_skill_rank_up(conn, character_id, req.skill_key)
            conn.commit()
            return {"ok": True, **result}
        except ValueError as e:
            conn.rollback()
            code = str(e)
            if code == "character not found":
                raise HTTPException(status_code=404, detail="Character not found") from None
            if code == "skill_key_required":
                raise HTTPException(status_code=400, detail="skill_key is required") from None
            if code == "unknown_skill":
                raise HTTPException(
                    status_code=400,
                    detail="Unknown skill — must exist in game_config_skills catalog.",
                ) from None
            if code == "skill_at_ceiling":
                raise HTTPException(status_code=400, detail="Skill rank already at ceiling") from None
            if code == "insufficient_xp":
                raise HTTPException(status_code=400, detail="Not enough XP") from None
            raise HTTPException(status_code=400, detail=code) from None
    finally:
        conn.close()


@router.post("/characters/{character_id}/xp/spend-stat")
def spend_character_stat_xp(character_id: int, req: SpendStatXpRequest):
    """Spend XP to increase one stat from `game_config_stats` by 1 (**T21**)."""
    from app.services import xp_service

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        try:
            result = xp_service.spend_stat_point_up(conn, character_id, req.stat_key)
            conn.commit()
            return {"ok": True, **result}
        except ValueError as e:
            conn.rollback()
            code = str(e)
            if code == "character not found":
                raise HTTPException(status_code=404, detail="Character not found") from None
            if code == "stat_key_required":
                raise HTTPException(status_code=400, detail="stat_key is required") from None
            if code == "unknown_stat":
                raise HTTPException(
                    status_code=400,
                    detail="Unknown stat — must exist in game_config_stats catalog.",
                ) from None
            if code == "stat_at_ceiling":
                raise HTTPException(status_code=400, detail="Stat already at configured ceiling") from None
            if code == "insufficient_xp":
                raise HTTPException(status_code=400, detail="Not enough XP") from None
            if code == "stat_cost_not_configured":
                raise HTTPException(
                    status_code=400,
                    detail="No XP cost configured for that stat value — check game_config_meta.",
                ) from None
            raise HTTPException(status_code=400, detail=code) from None
    finally:
        conn.close()


@router.post("/characters/{character_id}/xp/grant-mg")
def grant_character_xp_mg(character_id: int, req: GrantMgXpRequest, user_id: int = Query(...)):
    """
    Owner kampanii postaci przyznaje XP z puli MG (**[S10b]**); wpis w `character_xp_grants` (**[S10d]**).
    """
    from app.services import xp_service

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        info = xp_service.fetch_character_campaign_owner(conn, character_id)
        if not info:
            raise HTTPException(status_code=404, detail="Character not found") from None
        if int(info["owner_user_id"]) != int(user_id):
            raise HTTPException(
                status_code=403,
                detail="user_id must match campaign owner to grant XP",
            ) from None
        try:
            meta_grant: dict = {
                "granted_by": "mg_api",
                "campaign_id": int(info["campaign_id"]),
            }
            if req.reward_key:
                grant_amount = xp_service.require_xp_reward_amount(conn, req.reward_key)
                meta_grant["xp_reward_key"] = req.reward_key
            else:
                grant_amount = int(req.amount or 0)
            result = xp_service.grant_character_xp(
                conn,
                character_id,
                grant_amount,
                reason=req.reason.strip(),
                meta=meta_grant,
            )
            gid = xp_service.insert_mg_xp_grant_audit(
                conn,
                character_id=character_id,
                campaign_id=int(info["campaign_id"]),
                amount=grant_amount,
                reason=req.reason.strip(),
                granted_by_user_id=int(user_id),
                meta=meta_grant,
            )
            conn.commit()
            return {"ok": True, **result, "grant_id": gid}
        except ValueError as e:
            conn.rollback()
            if str(e) == "character not found":
                raise HTTPException(status_code=404, detail="Character not found") from None
            if str(e) == "unknown_or_inactive_xp_reward_key":
                raise HTTPException(
                    status_code=400,
                    detail="Unknown or inactive reward_key — use GET …/xp/reward-catalog",
                ) from None
            raise HTTPException(status_code=400, detail=str(e)) from None
        except sqlite3.OperationalError as e:
            conn.rollback()
            if "no such table" in str(e).lower():
                raise HTTPException(
                    status_code=503,
                    detail="character_xp_grants / migration missing — apply migrations and restart API",
                ) from None
            raise HTTPException(status_code=500, detail=str(e)) from None
    finally:
        conn.close()


@router.get("/characters/{character_id}/xp/reward-catalog")
def get_character_xp_reward_catalog(
    character_id: int,
    user_id: int = Query(...),
    categories: str = Query(
        "mg_grant,quest",
        description="Po przecinku: mg_grant, quest, enemy_tier (T12 / S10e).",
    ),
):
    """
    Katalog `game_config_xp_rewards` dla właściciela kampanii (np. wybór `reward_key` przy grancie MG).
    """
    from app.services import xp_service

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        info = xp_service.fetch_character_campaign_owner(conn, character_id)
        if not info:
            raise HTTPException(status_code=404, detail="Character not found") from None
        if int(info["owner_user_id"]) != int(user_id):
            raise HTTPException(
                status_code=403,
                detail="user_id must match campaign owner",
            ) from None
        cats = [c.strip() for c in (categories or "").split(",") if c.strip()]
        if not cats:
            cats = ["mg_grant", "quest"]
        try:
            items = xp_service.list_xp_rewards_for_categories(conn, cats)
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                raise HTTPException(
                    status_code=503,
                    detail="game_config_xp_rewards missing — apply migrations and restart API",
                ) from None
            raise HTTPException(status_code=500, detail=str(e)) from None
        return {"character_id": character_id, "categories": cats, "items": items}
    finally:
        conn.close()


@router.get("/characters/{character_id}/xp/grant-log")
def list_character_xp_grants(
    character_id: int, user_id: int = Query(...), limit: int = Query(50, ge=1, le=200)
):
    """Ostatnie granty XP (audit); tylko owner kampanii."""
    from app.services import xp_service

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        info = xp_service.fetch_character_campaign_owner(conn, character_id)
        if not info:
            raise HTTPException(status_code=404, detail="Character not found") from None
        if int(info["owner_user_id"]) != int(user_id):
            raise HTTPException(status_code=403, detail="user_id must match campaign owner") from None
        try:
            rows = xp_service.list_xp_grants_for_character(conn, character_id, limit=limit)
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                raise HTTPException(
                    status_code=503,
                    detail="character_xp_grants missing — apply migrations and restart API",
                ) from None
            raise HTTPException(status_code=500, detail=str(e)) from None
        return {"character_id": character_id, "grants": rows}
    finally:
        conn.close()


@router.post("/characters/{character_id}/generate-identity", response_model=GeneratedIdentityPreview)
def generate_character_identity(character_id: int):
    """
    Preview-only: generates appearance/personality/flaw/bond/secret via LLM.
    Does not persist to sheet_json (player reviews first).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT c.id, c.user_id, c.name, c.sheet_json,
               COALESCE(cam.model_id, 'default') AS model_id,
               COALESCE(cam.language, 'pl')      AS language
        FROM characters c
        LEFT JOIN campaigns cam ON cam.id = c.campaign_id
        WHERE c.id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        sheet = json.loads(row["sheet_json"]) if row["sheet_json"] else {}
    except Exception:
        sheet = {}

    name = str(sheet.get("name") or row["name"] or "").strip() or "Hero"
    char_class = str(sheet.get("class") or sheet.get("archetype") or "").strip() or "adventurer"
    backstory = str(
        sheet.get("background_note") or sheet.get("backstory") or sheet.get("background") or ""
    ).strip()
    if not backstory:
        backstory = "(No backstory provided yet — infer a fitting tone from name and class.)"

    stats = sheet.get("stats") or {}
    skills = sheet.get("skills") or {}

    session_language = str(row["language"] or "pl").strip() or "pl"
    lang = session_language.strip().lower()
    label = _SESSION_LANG_LABELS.get(lang, f"session language ({lang})")
    user_prompt = _identity_generation_user_prompt(
        name, char_class, backstory, session_language, stats=stats, skills=skills
    )
    base_messages = [
        {
            "role": "system",
            "content": (
                "Jesteś generatorem tożsamości postaci RPG. "
                "Odpowiadasz WYŁĄCZNIE poprawnym obiektem JSON — bez komentarzy, bez markdown, bez dodatkowego tekstu. "
                f"Wszystkie wartości napisowe MUSZĄ być w języku {label} (kod: {lang}). "
                'Żadne pole nie może być pustym stringiem "".'
            ),
        },
        {"role": "user", "content": user_prompt},
    ]

    llm_config = get_user_llm_settings_full(int(row["user_id"]))
    model = (llm_config.get("model") or "").strip() or (str(row["model_id"] or "").strip() or None)

    try:
        raw = (generate_chat(messages=base_messages, model=model, llm_config=llm_config) or "").strip()
        data = _parse_identity_llm_to_dict(raw)
    except ValueError as e:
        logger.warning("[generate_identity] parse failed: %s", str(e))
        raise HTTPException(status_code=502, detail=str(e)) from None
    except Exception as e:
        logger.warning("[generate_identity] LLM failed: %s", str(e))
        raise HTTPException(status_code=502, detail=str(e)) from None

    if not _identity_dict_fields_non_empty(data):
        retry_messages = [*base_messages, {"role": "user", "content": _IDENTITY_RETRY_USER}]
        try:
            raw2 = (generate_chat(messages=retry_messages, model=model, llm_config=llm_config) or "").strip()
            data = _parse_identity_llm_to_dict(raw2)
        except ValueError as e:
            logger.warning("[generate_identity] parse failed on retry: %s", str(e))
            raise HTTPException(status_code=502, detail=str(e)) from None
        except Exception as e:
            logger.warning("[generate_identity] LLM failed on retry: %s", str(e))
            raise HTTPException(status_code=502, detail=str(e)) from None
        if not _identity_dict_fields_non_empty(data):
            logger.warning("[generate_identity] incomplete fields after retry")
            raise HTTPException(
                status_code=500,
                detail="Identity generation incomplete — please try again",
            )

    # Store secret_predisposition in gm_only (never returned to player via _strip_hidden_fields)
    secret_pred = str(data.get("secret_predisposition") or data.get("secret") or "").strip()
    if secret_pred:
        conn2 = sqlite3.connect(DB_PATH)
        try:
            row2 = conn2.execute("SELECT sheet_json FROM characters WHERE id = ?", (character_id,)).fetchone()
            if row2:
                s2 = json.loads(row2[0] or "{}") if row2[0] else {}
                if "gm_only" not in s2:
                    s2["gm_only"] = {}
                s2["gm_only"]["secret_predisposition"] = secret_pred
                conn2.execute("UPDATE characters SET sheet_json = ? WHERE id = ?",
                              (json.dumps(s2), character_id))
                conn2.commit()
        finally:
            conn2.close()

    return _dict_to_identity_preview(data)


@router.post("/characters/{character_id}/finalize-sheet")
def finalize_character_sheet(character_id: int, req: FinalizeSheetRequest):
    """
    One-shot end of character creation: optional stat redistribution, skill budget edits, identity text.
    Persists validated sheet_json.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT id, sheet_json
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        sheet = json.loads(row["sheet_json"]) if row["sheet_json"] else {}
    except Exception:
        sheet = {}

    archetype = str(sheet.get("archetype") or "warrior").strip().lower()
    if archetype not in ("warrior", "scholar"):
        archetype = "warrior"
    sheet["archetype"] = archetype

    raw_stats = dict(sheet.get("stats") or {})
    bases = _core_bases_from_stored_stats(raw_stats, archetype)
    sum_target = sum(bases[k] for k in SIX_CORE_STATS)

    merged = dict(bases)
    if req.stat_overrides:
        for key, val in req.stat_overrides.items():
            sk = _normalize_stat_override_key(str(key))
            if sk is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown stat key in stat_overrides: {key!r}. "
                    f"Use strength/dexterity/… or STR/DEX/… for the six core stats.",
                )
            if sk not in SIX_CORE_STATS:
                raise HTTPException(
                    status_code=400,
                    detail=f"stat_overrides supports only the six core stats (STR–CHA), not {sk!r}.",
                )
            try:
                merged[sk] = int(val)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400,
                    detail=f"stat value for {sk!r} must be an integer.",
                ) from None

    merged_sum = sum(merged[k] for k in SIX_CORE_STATS)
    if merged_sum != sum_target:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Stat redistribution must keep the same total as current rolled bases ({sum_target}); "
                f"got {merged_sum}."
            ),
        )
    for k in SIX_CORE_STATS:
        v = merged[k]
        if v < STAT_ROLL_MIN or v > STAT_ROLL_MAX:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{k} must be between {STAT_ROLL_MIN} and {STAT_ROLL_MAX} (before class bonuses); "
                    f"got {v}."
                ),
            )

    skills_sheet = {k: int(v) for k, v in (sheet.get("skills") or {}).items()}
    orig_snapshot = sheet.get("skills_at_creation")
    if isinstance(orig_snapshot, dict) and orig_snapshot:
        skills_orig = {k: int(orig_snapshot.get(k, 0) or 0) for k in CREATION_SKILL_POOL}
    else:
        skills_orig = {k: int(skills_sheet.get(k, 0) or 0) for k in CREATION_SKILL_POOL}

    skills_after = _coerce_creation_skills_payload(req.skills, skills_sheet)

    _validate_creation_skills_after_swap(skills_orig, skills_after, req.skill_slot_current)

    lck = int(raw_stats.get("LCK", raw_stats.get("lck", 10)))
    new_stats_input = {k: merged[k] for k in SIX_CORE_STATS}
    new_stats_input["LCK"] = lck

    sheet["stats"] = new_stats_input
    sheet["skills"] = skills_after

    rebuilt = _build_character_sheet(
        sheet,
        archetype,
        apply_archetype_skill_minimums=False,
    )

    if req.identity_overrides is not None:
        _ensure_identity_block(rebuilt)
        io = req.identity_overrides
        if io.appearance is not None:
            rebuilt["identity"]["appearance"] = io.appearance
        if io.personality is not None:
            rebuilt["identity"]["personality"] = io.personality
        # V2: structured bonds and weaknesses
        if io.bonds is not None:
            rebuilt["identity"]["bonds"] = io.bonds
        if io.weaknesses is not None:
            rebuilt["identity"]["weaknesses"] = io.weaknesses
        # Legacy V1 fields (backward compat)
        if io.flaw is not None:
            rebuilt["identity"]["flaw"] = io.flaw
        if io.secret is not None:
            rebuilt["identity"]["secret"] = io.secret
        if io.bond is not None and io.bonds is None:
            rebuilt["identity"]["bonds"] = [
                {"description": io.bond, "type": "ideal"}
            ]

    conn.execute(
        """
        UPDATE characters
        SET sheet_json = ?
        WHERE id = ?
        """,
        (json.dumps(rebuilt, ensure_ascii=False), character_id),
    )
    conn.commit()

    # ── Generate GM plan + opening scene if not already done ─────────────────
    # finalize-sheet is the final step of character creation; trigger plan
    # generation here so the player gets the opening GM message immediately.
    opening_message = None
    try:
        char_row = conn.execute(
            "SELECT campaign_id, user_id, name, location FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        campaign_id = int(char_row["campaign_id"]) if char_row else None
        user_id = int(char_row["user_id"]) if char_row else None

        if campaign_id:
            campaign = conn.execute(
                "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()

            if campaign:
                from app.services.gm_plan_schema import gm_plan_is_ready
                plan_already_ready = gm_plan_is_ready(campaign["gm_plan_json"] if campaign else None)

                # Check if opening turn already exists
                existing_turn = conn.execute(
                    "SELECT 1 FROM campaign_turns WHERE campaign_id = ? LIMIT 1",
                    (campaign_id,),
                ).fetchone()

                if not plan_already_ready and not existing_turn:
                    llm_config = get_user_llm_settings_full(user_id or 0)
                    model = llm_config.get("model") or "gemma3:1b"

                    identity_block = rebuilt.get("identity") or {}
                    has_v2_identity = bool(identity_block.get("bonds") or identity_block.get("weaknesses"))

                    archetype = str(rebuilt.get("archetype", "warrior")).strip().lower()
                    name = str(char_row["name"] or "Bohater")
                    stats = rebuilt.get("stats") or {}
                    skills = rebuilt.get("skills") or {}
                    hp = rebuilt.get("max_hp", "?")
                    mana = rebuilt.get("max_mana", 0)
                    location = str(char_row["location"] or "nieznane miejsce")
                    background = str(rebuilt.get("background") or "").strip()
                    archetype_label = "Uczony" if archetype == "scholar" else "Wojownik"
                    stat_lines = ", ".join(f"{k}:{v}" for k, v in stats.items()) if stats else ""
                    skill_lines = ", ".join(
                        f"{k}:{v}" for k, v in skills.items()
                        if isinstance(v, (int, float)) and v > 0
                    ) if skills else ""
                    char_summary = (
                        f"Postać: {name}, Archetyp: {archetype_label}, HP: {hp}"
                        + (f", Mana: {mana}" if mana else "")
                        + (f", Statystyki: {stat_lines}" if stat_lines else "")
                        + (f", Umiejętności: {skill_lines}" if skill_lines else "")
                        + (f", Tło: {background}" if background else "")
                        + f", Lokalizacja startowa: {location}."
                    )

                    if has_v2_identity:
                        char_data = {
                            "name": name,
                            "archetype": archetype,
                            "background_note": background,
                            "identity": identity_block,
                            "gm_only": rebuilt.get("gm_only") or {},
                        }
                        gm_plan_ready, _ = generate_v2_campaign_plan(
                            conn,
                            campaign_id=campaign_id,
                            character_data=char_data,
                            model=model,
                            llm_config=llm_config,
                            max_attempts=2,
                        )
                    else:
                        gm_plan_ready, _ = generate_initial_gm_plan_with_retries(
                            conn,
                            campaign_id=campaign_id,
                            campaign_title=str(campaign["title"] or f"Kampania {campaign_id}"),
                            campaign_language=str(campaign["language"] or "pl"),
                            system_id=str(campaign["system_id"] or ""),
                            char_summary=char_summary,
                            user_id=user_id or 0,
                            model=model,
                            llm_config=llm_config,
                            max_attempts=3,
                        )

                    if gm_plan_ready:
                        opening_prompt = (
                            f"{char_summary}\n\n"
                            "To jest pierwsza chwila przygody. Zacznij sesję od klimatycznego opisu miejsca, "
                            "w którym bohater się znajduje. Nie pytaj gracza o plany - po prostu opisz scenę "
                            "i zostaw otwarte zakończenie zachęcające do działania."
                        )
                        messages = [
                            {"role": "system", "content": OPENING_SYSTEM_PROMPT},
                            {"role": "user", "content": opening_prompt},
                        ]
                        opening_message = (
                            generate_chat(messages=messages, model=model, llm_config=llm_config) or ""
                        ).strip() or None

                        if opening_message:
                            session_id = conn.execute(
                                "SELECT id FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                                (campaign_id,),
                            ).fetchone()
                            if not session_id:
                                conn.execute(
                                    "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (?, ?)",
                                    (campaign_id, "{}"),
                                )
                                conn.commit()

                            next_turn = int((conn.execute(
                                "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id=?",
                                (campaign_id,),
                            ).fetchone()[0]) or 1)
                            conn.execute(
                                """INSERT INTO campaign_turns
                                   (campaign_id, character_id, user_text, route, assistant_text, turn_number)
                                   VALUES (?, ?, ?, ?, ?, ?)""",
                                (campaign_id, character_id, "", "narrative", opening_message, next_turn),
                            )
                            conn.commit()
    except Exception as e:
        logger.warning("[finalize_sheet] gm_plan/opening_scene failed (non-fatal): %s", str(e))

    # ── Place player on starting hex (match global hex or create nearby) ─────
    try:
        from app.services.hex_travel_service import resolve_starting_hex
        # Get starting location from the character's sheet
        _start_loc = str(rebuilt.get("location") or "")
        gs_check = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        _flags_check = json.loads((gs_check["session_flags"] if gs_check else None) or "{}")
        if not _flags_check.get("current_hex"):
            resolve_starting_hex(campaign_id, character_id, _start_loc or None, conn)
            logger.info("[finalize_sheet] starting hex resolved for campaign %d", campaign_id)
    except Exception as e:
        logger.warning("[finalize_sheet] starting hex placement failed (non-fatal): %s", str(e))

    conn.close()

    result = {"sheet_json": _strip_hidden_fields(rebuilt)}
    if opening_message:
        result["opening_message"] = opening_message
    return result


@router.patch("/characters/{character_id}/sheet")
def patch_character_sheet(character_id: int, req: CharacterSheetPatchRequest):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT id, campaign_id, sheet_json
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        existing_sheet_json = json.loads(row["sheet_json"]) if row["sheet_json"] else {}
    except Exception:
        existing_sheet_json = {}

    merged_sheet_json = _deep_merge_dicts(existing_sheet_json, req.sheet_json)
    _ensure_narrative_items_block(merged_sheet_json)

    conn.execute(
        """
        UPDATE characters
        SET sheet_json = ?
        WHERE id = ?
        """,
        (json.dumps(merged_sheet_json, ensure_ascii=False), character_id),
    )
    conn.commit()
    campaign_id_for_new_act = int(row["campaign_id"] or 0)

    updated_row = conn.execute(
        """
        SELECT id, campaign_id, user_id, name, system_id, sheet_json, location, is_active, created_at
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not updated_row:
        raise HTTPException(status_code=500, detail="Character updated but could not be loaded")

    from app.services.new_act_service import maybe_trigger_new_act_after_main_quest

    maybe_trigger_new_act_after_main_quest(
        campaign_id=campaign_id_for_new_act,
        character_id=character_id,
        old_sheet=existing_sheet_json,
        new_sheet=merged_sheet_json,
    )

    item = dict(updated_row)
    try:
        item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
    except Exception:
        item["sheet_json"] = {}
    item["sheet_json"] = _strip_hidden_fields(item["sheet_json"])

    return item


@router.post("/characters/{character_id}/narrative-item")
def add_character_narrative_item(character_id: int, req: NarrativeItemCreateRequest):
    label = str(req.label or "").strip()
    if not label:
        raise HTTPException(status_code=422, detail="label is required")

    source = str(req.source or "gm").strip() or "gm"
    given_at = str(req.given_at or "").strip() or None
    description = str(req.description or "").strip() or None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, sheet_json FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Character not found")
        try:
            sheet = json.loads(row["sheet_json"] or "{}") if row["sheet_json"] else {}
        except Exception:
            sheet = {}
        if not isinstance(sheet, dict):
            sheet = {}

        _ensure_narrative_items_block(sheet)
        new_item = {"label": label, "source": source}
        if description:
            new_item["description"] = description
        if given_at:
            new_item["given_at"] = given_at
        sheet["narrative_items"].append(new_item)

        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), character_id),
        )
        conn.commit()
        return {"ok": True, "item": new_item, "narrative_items": sheet["narrative_items"]}
    finally:
        conn.close()


@router.post("/campaigns/{campaign_id}/characters")
def create_character(campaign_id: int, req: CharacterCreateRequest):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    conn.execute("BEGIN IMMEDIATE")

    campaign = conn.execute(
        """
        SELECT id, system_id, model_id, language, title, owner_user_id, gm_plan_json
        FROM campaigns
        WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()

    if not campaign:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=404, detail="Campaign not found")

    existing = conn.execute(
        "SELECT COUNT(*) AS n FROM characters WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    if existing and int(existing["n"] or 0) >= 1:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=409, detail="Campaign already has a character.")

    if req.system_id != campaign["system_id"]:
        conn.rollback()
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"system_id mismatch: campaign uses '{campaign['system_id']}'"
        )

    base_sheet = dict(req.sheet_json or {})
    requested_archetype = str(base_sheet.get("archetype") or "warrior").strip().lower()
    # Starter pack + gold come only from DB rows for warrior/scholar; unknown types
    # still create a valid sheet (defaults to warrior stats) but get no starter loot.
    starter_archetype_key = requested_archetype if requested_archetype in ("warrior", "scholar") else None
    archetype = starter_archetype_key or "warrior"
    base_sheet["archetype"] = archetype
    # Roll 4d6 drop-lowest, then clamp each base to [STAT_ROLL_MIN, STAT_ROLL_MAX].
    # The wizard requires every pre-bonus stat to be in that range; clamping ensures
    # the player never opens step 2 with a stat that can't satisfy the confirm check.
    base_sheet["stats"] = {
        k: max(STAT_ROLL_MIN, min(STAT_ROLL_MAX, roll_4d6_drop_lowest()))
        for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK")
    }
    skills_rolled = roll_creation_skills(archetype)
    base_sheet["skills"] = skills_rolled
    base_sheet["skills_at_creation"] = dict(skills_rolled)

    created_sheet = _build_character_sheet(
        base_sheet,
        archetype,
        apply_archetype_skill_minimums=False,
    )
    created_sheet["skills_at_creation"] = dict(skills_rolled)
    created_sheet.setdefault("narrative_items", [])

    cur.execute(
        """
        INSERT INTO characters (campaign_id, user_id, name, system_id, sheet_json, location, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            campaign_id,
            req.user_id,
            req.name,
            req.system_id,
            json.dumps(created_sheet, ensure_ascii=False),
            req.location,
            req.is_active,
        ),
    )
    conn.commit()

    character_id = cur.lastrowid
    session_id = _ensure_game_session(conn, campaign_id)

    try:
        arch_row = (
            conn.execute(
                """
                SELECT starter_items_json, starter_gold_gp
                FROM game_config_archetypes
                WHERE key = ? AND (is_active = 1 OR is_active IS NULL)
                """,
                (starter_archetype_key,),
            ).fetchone()
            if starter_archetype_key
            else None
        )
        if arch_row:
            raw_json = arch_row["starter_items_json"] or "[]"
            try:
                starter_items = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
            except json.JSONDecodeError:
                starter_items = []
            if isinstance(starter_items, list) and starter_items:
                grant_loot_to_character(character_id, starter_items, source="start")
            ggp = int(arch_row["starter_gold_gp"] or 0)
            if ggp > 0:
                conn.execute(
                    "UPDATE characters SET gold_gp = COALESCE(gold_gp, 0) + ? WHERE id = ?",
                    (ggp, character_id),
                )
                conn.commit()
    except Exception as e:
        logger.warning("[create_character] starter items / gold failed (non-fatal): %s", str(e))

    # Grant starting spells for Scholar
    if archetype == "scholar":
        try:
            from app.services.spell_service import grant_starting_spells
            created_sheet["arcane_points"] = 1
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(created_sheet, ensure_ascii=False), character_id),
            )
            conn.commit()
            grant_starting_spells(character_id, conn)
            conn.commit()
        except Exception as e:
            logger.warning("[create_character] scholar starting spells failed (non-fatal): %s", str(e))

    sheet = created_sheet or {}
    archetype = str(sheet.get("archetype", "warrior")).strip().lower()
    name = (req.name or "").strip() or "Bohater"
    stats = sheet.get("stats", {}) or {}
    skills = sheet.get("skills", {}) or {}
    hp = sheet.get("max_hp", "?")
    mana = sheet.get("max_mana", 0)
    location = req.location or "nieznane miejsce"
    background = str(sheet.get("background") or "").strip()

    stat_lines = ", ".join(f"{k}:{v}" for k, v in stats.items()) if stats else ""
    skill_lines = ", ".join(
        f"{k}:{v}" for k, v in skills.items() if isinstance(v, (int, float)) and v > 0
    ) if skills else ""
    archetype_label = "Uczony" if archetype == "scholar" else "Wojownik"

    char_summary = (
        f"Postać: {name}, Archetyp: {archetype_label}, "
        f"HP: {hp}"
        + (f", Mana: {mana}" if mana else "")
        + (f", Statystyki: {stat_lines}" if stat_lines else "")
        + (f", Umiejętności: {skill_lines}" if skill_lines else "")
        + (f", Tło: {background}" if background else "")
        + f", Lokalizacja startowa: {location}."
    )

    model = str(campaign["model_id"] or "").strip() or "gemma3:1b"
    settings_conn = sqlite3.connect(DB_PATH)
    settings_conn.row_factory = sqlite3.Row
    try:
        model_row = settings_conn.execute(
            "SELECT value FROM settings WHERE key = 'model' LIMIT 1"
        ).fetchone()
        if model_row and model_row["value"]:
            model = str(model_row["value"]).strip()
        elif os.getenv("LLM_MODEL"):
            model = os.getenv("LLM_MODEL", "gemma3:1b").strip() or "gemma3:1b"
    except Exception:
        pass
    finally:
        settings_conn.close()

    llm_config = get_user_llm_settings_full(req.user_id)
    model = llm_config.get("model") or model

    gm_plan_ready = False
    gm_plan_error: str | None = None
    try:
        # V2: use structured plan generator if character has bonds/weaknesses
        rebuilt_sheet = json.loads(conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
        ).fetchone()["sheet_json"] or "{}")
        identity_block = rebuilt_sheet.get("identity") or {}
        has_v2_identity = bool(identity_block.get("bonds") or identity_block.get("weaknesses"))

        if has_v2_identity:
            char_data = {
                "name": name,
                "archetype": archetype,
                "background_note": background,
                "identity": identity_block,
                "gm_only": rebuilt_sheet.get("gm_only") or {},
            }
            gm_plan_ready, gm_plan_error = generate_v2_campaign_plan(
                conn,
                campaign_id=campaign_id,
                character_data=char_data,
                model=model,
                llm_config=llm_config,
                max_attempts=2,
            )
        else:
            gm_plan_ready, gm_plan_error = generate_initial_gm_plan_with_retries(
                conn,
                campaign_id=campaign_id,
                campaign_title=str(campaign["title"] or f"Kampania {campaign_id}"),
                campaign_language=str(campaign["language"] or "pl"),
                system_id=str(campaign["system_id"] or ""),
                char_summary=char_summary,
                user_id=int(req.user_id),
                model=model,
                llm_config=llm_config,
                max_attempts=3,
            )
    except Exception as e:
        logger.warning("[create_character] gm plan generation failed (non-fatal): %s", str(e))
        gm_plan_error = str(e)

    opening_message = None
    if gm_plan_ready:
        try:
            opening_prompt = (
                f"{char_summary}\n\n"
                "To jest pierwsza chwila przygody. Zacznij sesję od klimatycznego opisu miejsca, "
                "w którym bohater się znajduje. Nie pytaj gracza o plany - po prostu opisz scenę "
                "i zostaw otwarte zakończenie zachęcające do działania."
            )

            messages = [
                {"role": "system", "content": OPENING_SYSTEM_PROMPT},
                {"role": "user", "content": opening_prompt},
            ]

            opening_message = (
                generate_chat(messages=messages, model=model, llm_config=llm_config) or ""
            ).strip() or None

            if opening_message:
                try:
                    location_intent = parse_location_intent(opening_message, None)
                except Exception as exc:
                    logger.warning(
                        "[opening_scene] location_intent_parse_failed campaign_id=%s error=%s",
                        campaign_id,
                        str(exc),
                    )
                    location_intent = None

                if location_intent and location_intent.action == "create":
                    created = persist_ai_generated_location(
                        location_intent,
                        campaign_id=campaign_id,
                        conn=conn,
                    )
                    if created:
                        conn.execute(
                            "UPDATE game_sessions SET current_location_id = ? WHERE id = ?",
                            (created["id"], session_id),
                        )
                        conn.commit()
                    else:
                        _ensure_opening_location_fallback(
                            conn=conn,
                            campaign_id=campaign_id,
                            session_id=session_id,
                            opening_message=opening_message,
                            requested_location=req.location,
                        )
                else:
                    _ensure_opening_location_fallback(
                        conn=conn,
                        campaign_id=campaign_id,
                        session_id=session_id,
                        opening_message=opening_message,
                        requested_location=req.location,
                    )
                next_turn_row = conn.execute(
                    """
                    SELECT COALESCE(MAX(turn_number), 0) + 1 AS next_turn
                    FROM campaign_turns
                    WHERE campaign_id = ?
                    """,
                    (campaign_id,),
                ).fetchone()
                next_turn_number = int(next_turn_row["next_turn"] or 1)
                conn.execute(
                    """
                    INSERT INTO campaign_turns (
                        campaign_id, character_id, user_text, route, assistant_text, turn_number
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (campaign_id, character_id, "", "narrative", opening_message, next_turn_number),
                )
                conn.commit()
        except Exception as e:
            logger.warning("[create_character] opening message failed (non-fatal): %s", str(e))
            opening_message = None

    # ── Place player on starting hex (match global or create nearby) ─────────
    try:
        from app.services.hex_travel_service import resolve_starting_hex
        gs_check2 = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        _f2 = json.loads((gs_check2["session_flags"] if gs_check2 else None) or "{}")
        if not _f2.get("current_hex"):
            _start_loc2 = str(req.location or "").strip() or None
            resolve_starting_hex(campaign_id, character_id, _start_loc2, conn)
            logger.info("[create_character] starting hex resolved for campaign %d", campaign_id)
    except Exception as e:
        logger.warning("[create_character] starting hex placement failed (non-fatal): %s", str(e))

    row = conn.execute(
        """
        SELECT id, campaign_id, user_id, name, system_id, sheet_json, location, is_active, created_at, gold_gp
        FROM characters
        WHERE id = ?
        """,
        (character_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=500, detail="Character created but could not be loaded")

    item = dict(row)
    try:
        item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
    except Exception:
        item["sheet_json"] = {}
    item["sheet_json"] = _strip_hidden_fields(item["sheet_json"])
    item["opening_message"] = opening_message
    item["gm_plan_ready"] = bool(gm_plan_ready)
    item["gm_plan_error"] = gm_plan_error

    return item


def _default_playtest_sheet(name: str, archetype: str, old_sheet: dict) -> dict:
    """Minimal combat-ready sheet aligned with solo character wizard defaults."""
    arc = str(archetype or "").lower()
    if arc not in ("warrior", "scholar"):
        arc = "warrior"
    if arc == "warrior":
        stats = {"STR": 12, "DEX": 12, "CON": 12, "INT": 10, "WIS": 11, "CHA": 10, "LCK": 10}
        skills = {
            "athletics": 2,
            "stealth": 1,
            "sleight_of_hand": 0,
            "endurance": 1,
            "arcana": 0,
            "investigation": 0,
            "lore": 0,
            "awareness": 1,
            "survival": 1,
            "medicine": 0,
            "persuasion": 1,
            "intimidation": 1,
        }
    else:
        stats = {"STR": 10, "DEX": 11, "CON": 10, "INT": 12, "WIS": 11, "CHA": 10, "LCK": 10}
        skills = {
            "athletics": 1,
            "stealth": 1,
            "sleight_of_hand": 0,
            "endurance": 1,
            "arcana": 2,
            "investigation": 0,
            "lore": 1,
            "awareness": 1,
            "survival": 1,
            "medicine": 0,
            "persuasion": 1,
            "intimidation": 0,
        }
    dex_mod = _stat_modifier(int(stats.get("DEX", 10) or 10))
    defense_base = 10 + dex_mod
    bg = old_sheet.get("background") if isinstance(old_sheet.get("background"), str) else ""
    return {
        "archetype": arc,
        "background": bg,
        "level": 1,
        "current_hp": calculate_hp(arc, int(stats.get("CON", 10))),
        "max_hp":     calculate_hp(arc, int(stats.get("CON", 10))),
        "current_mana": calculate_mana(arc, int(stats.get("INT", 10))),
        "max_mana":     calculate_mana(arc, int(stats.get("INT", 10))),
        "stats": stats,
        "skills": skills,
        "inventory": [],
        "narrative_items": [],
        "defense": {"base": defense_base},
        "equipped_weapon": "sword",
        "name": name,
    }


@router.post("/characters/{character_id}/reset-progress")
def reset_character_progress(character_id: int):
    """
    Dev / playtest: clear inventory and restore sheet to wizard-style defaults
    (keeps name, archetype, background text, hidden identity secret).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, campaign_id, name, sheet_json FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Character not found")
        try:
            old = json.loads(row["sheet_json"] or "{}") if row["sheet_json"] else {}
        except Exception:
            old = {}
        if not isinstance(old, dict):
            old = {}
        archetype = str(old.get("archetype") or "warrior").lower()
        name = str(row["name"] or "Hero").strip() or "Hero"
        new_sheet = _default_playtest_sheet(name, archetype, old)
        _ensure_identity_block(new_sheet)
        if isinstance(old.get("identity"), dict) and old["identity"].get("secret"):
            new_sheet.setdefault("identity", _default_identity_block())
            new_sheet["identity"]["secret"] = str(old["identity"]["secret"])

        try:
            conn.execute("DELETE FROM character_inventory WHERE character_id = ?", (character_id,))
        except sqlite3.OperationalError:
            pass

        conn.execute(
            "UPDATE characters SET sheet_json = ?, location = ? WHERE id = ?",
            (json.dumps(new_sheet, ensure_ascii=False), "Start", character_id),
        )
        conn.commit()
        logger.info(
            "character_progress_reset",
            character_id=character_id,
            campaign_id=int(row["campaign_id"]),
        )
        return {
            "ok": True,
            "character_id": character_id,
            "campaign_id": int(row["campaign_id"]),
            "sheet_json": _strip_hidden_fields(new_sheet),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Character reset failed: {e}") from None
    finally:
        conn.close()