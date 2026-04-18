import json
import logging
import os
import random
import re
import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from app.services.llm_service import generate_chat
from app.services.user_llm_settings import get_user_llm_settings_full
from app.system_prompt_loader import SYSTEM_PROMPT_TEXT

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
    if normalized_archetype not in ("warrior", "mage"):
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

    if normalized_archetype == "warrior":
        hp = 12 + con_mod
        sheet["current_hp"] = hp
        sheet["max_hp"] = hp
        sheet["current_mana"] = 0
        sheet["max_mana"] = 0
    else:
        hp = 6 + con_mod
        mana = 8 + int_mod
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
    sheet.update(_preserved_runtime)
    return sheet


def _strip_hidden_fields(sheet: dict) -> dict:
    sanitized = dict(sheet or {})
    sanitized.pop("hidden_potential", None)
    return sanitized


# --- finalize-sheet (Phase 7.6): stat/skill redistribution + identity (player review) ---

SIX_CORE_STATS = ("STR", "DEX", "CON", "INT", "WIS", "CHA")
STAT_ROLL_MIN = 8
STAT_ROLL_MAX = 18
# Spec: floor(12 × 0.4) is 4 in pure math; task caps at 5 swaps — use 5.
MAX_SKILL_SWAPS = 5

LOCKED_SKILL_NAMES = frozenset(
    (
        "athletics",
        "stealth",
        "sleight_of_hand",
        "endurance",
        "arcana",
        "investigation",
        "lore",
        "awareness",
        "survival",
        "medicine",
        "persuasion",
        "intimidation",
    )
)

# Skills that may receive ranks via replacement (locked twelve + combat/spell tests not in that list).
REPLACEMENT_TARGET_SKILL_NAMES = frozenset(
    LOCKED_SKILL_NAMES
    | {
        "melee_attack",
        "ranged_attack",
        "spell_attack",
        "alchemy",
    }
)

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
    if a not in ("mage", "warrior"):
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


def _skill_rank_total(skills: dict) -> int:
    total = 0
    for _k, v in (skills or {}).items():
        try:
            total += int(v)
        except (TypeError, ValueError):
            continue
    return total


def _apply_skill_replacements(skills: dict, swaps: list[dict]) -> dict:
    """
    Move rank from from_skill onto to_skill (to_skill must be empty before each step).
    This matches the Phase 7.6 UI: replace one trained skill slot with another unused skill key.
    """
    out = {k: int(v) for k, v in (skills or {}).items()}
    for sw in swaps:
        a = (sw.get("from_skill") or "").strip()
        b = (sw.get("to_skill") or "").strip()
        r = int(out.get(a, 0))
        if r <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"from_skill {a!r} has no rank to move for this replacement.",
            )
        prev_b = int(out.get(b, 0))
        if prev_b != 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Skill replacement target {b!r} must be inactive (rank 0) before replacing into it."
                ),
            )
        out[a] = 0
        out[b] = r
    return out


class SkillSwapItem(BaseModel):
    from_skill: str
    to_skill: str


class IdentityOverrideIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    appearance: str | None = None
    personality: str | None = None


class FinalizeSheetRequest(BaseModel):
    stat_overrides: dict[str, int] | None = None
    skill_swaps: list[SkillSwapItem] | None = None
    identity_overrides: IdentityOverrideIn | None = None


class GeneratedIdentityPreview(BaseModel):
    """LLM preview for identity fields (not yet merged into sheet_json)."""

    appearance: str
    personality: str
    flaw: str
    bond: str
    secret: str


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
    name: str, char_class: str, backstory: str, session_language: str
) -> str:
    lang = (session_language or "pl").strip().lower() or "pl"
    label = _SESSION_LANG_LABELS.get(lang, f"the campaign session language (ISO {lang})")
    return (
        "You are generating a character identity for a dark fantasy RPG.\n"
        f"Character name: {name}\n"
        f"Class: {char_class}\n"
        f"Backstory (may be any language — translate ideas, do not copy language if it conflicts): {backstory}\n\n"
        f"CAMPAIGN SESSION LANGUAGE (mandatory for all output text): {lang} — write entirely in {label}. "
        "Do not use Spanish, English, or any other language for the JSON values unless it matches this session language.\n\n"
        "Generate in JSON format (respond ONLY with valid JSON, no markdown).\n"
        "Use exactly these keys as a JSON object: "
        '"appearance", "personality", "flaw", "bond", "secret".\n\n'
        "appearance: 2-3 sentence physical description, gritty and specific\n"
        "personality: 2-3 sentences, defining character traits and worldview\n"
        "flaw: 1 sentence, a genuine weakness or vice that creates story tension\n"
        "bond: 1 sentence, a personal loyalty, debt, or unfinished business\n"
        "secret: 1 sentence, something the character hides — shameful, dangerous, or tragic\n\n"
        f"Every string value MUST be in {label} ({lang})."
    )


def _parse_identity_llm_response(raw: str) -> GeneratedIdentityPreview:
    cleaned = _strip_code_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from LLM: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("LLM JSON must be an object")
    return GeneratedIdentityPreview(
        appearance=str(data.get("appearance") or "").strip(),
        personality=str(data.get("personality") or "").strip(),
        flaw=str(data.get("flaw") or "").strip(),
        bond=str(data.get("bond") or "").strip(),
        secret=str(data.get("secret") or "").strip(),
    )


# Opening scene uses the same unified prompt as narrative turns and /api/gm/chat (fantasy).
OPENING_SYSTEM_PROMPT = SYSTEM_PROMPT_TEXT


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
        SELECT c.id, c.user_id, c.name, c.sheet_json, cam.model_id, cam.language
        FROM characters c
        JOIN campaigns cam ON cam.id = c.campaign_id
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
    backstory = str(sheet.get("backstory") or sheet.get("background") or "").strip()
    if not backstory:
        backstory = "(No backstory provided yet — infer a fitting tone from name and class.)"

    session_language = str(row["language"] or "pl").strip() or "pl"
    lang = session_language.strip().lower()
    label = _SESSION_LANG_LABELS.get(lang, f"session language ({lang})")
    user_prompt = _identity_generation_user_prompt(name, char_class, backstory, session_language)
    messages = [
        {
            "role": "system",
            "content": (
                "You output only valid JSON objects. No markdown fences, no commentary. "
                f"All natural-language strings in the JSON MUST be written in {label} (language code {lang})."
            ),
        },
        {"role": "user", "content": user_prompt},
    ]

    llm_config = get_user_llm_settings_full(int(row["user_id"]))
    model = (llm_config.get("model") or "").strip() or (str(row["model_id"] or "").strip() or None)

    try:
        raw = (generate_chat(messages=messages, model=model, llm_config=llm_config) or "").strip()
        preview = _parse_identity_llm_response(raw)
    except ValueError as e:
        logger.warning("[generate_identity] parse failed: %s", str(e))
        raise HTTPException(status_code=502, detail=str(e)) from None
    except Exception as e:
        logger.warning("[generate_identity] LLM failed: %s", str(e))
        raise HTTPException(status_code=502, detail=str(e)) from None

    return preview


@router.post("/characters/{character_id}/finalize-sheet")
def finalize_character_sheet(character_id: int, req: FinalizeSheetRequest):
    """
    One-shot end of character creation: optional stat redistribution, skill swaps, identity text.
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
    if archetype not in ("warrior", "mage"):
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

    swaps_list = [s.model_dump() for s in (req.skill_swaps or [])]
    if len(swaps_list) > MAX_SKILL_SWAPS:
        raise HTTPException(
            status_code=400,
            detail=f"At most {MAX_SKILL_SWAPS} skill swaps allowed; got {len(swaps_list)}.",
        )

    skills_before = {k: int(v) for k, v in (sheet.get("skills") or {}).items()}
    sum_sk_before = _skill_rank_total(skills_before)

    for sw in swaps_list:
        fs = (sw.get("from_skill") or "").strip()
        ts = (sw.get("to_skill") or "").strip()
        if fs == ts:
            raise HTTPException(
                status_code=400,
                detail="Each skill replacement must use two different skills (from_skill != to_skill).",
            )
        if fs not in LOCKED_SKILL_NAMES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"from_skill must be one of the twelve character skills; got {fs!r}. "
                    f"Allowed: {', '.join(sorted(LOCKED_SKILL_NAMES))}."
                ),
            )
        if ts not in REPLACEMENT_TARGET_SKILL_NAMES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Replacement skill {ts!r} is not allowed. "
                    f"Allowed targets: {', '.join(sorted(REPLACEMENT_TARGET_SKILL_NAMES))}."
                ),
            )

    skills_after = _apply_skill_replacements(skills_before, swaps_list) if swaps_list else dict(skills_before)
    sum_sk_after = _skill_rank_total(skills_after)
    if sum_sk_after != sum_sk_before:
        raise HTTPException(
            status_code=400,
            detail="Total skill ranks must stay the same after swaps (internal validation failed).",
        )

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

    conn.execute(
        """
        UPDATE characters
        SET sheet_json = ?
        WHERE id = ?
        """,
        (json.dumps(rebuilt, ensure_ascii=False), character_id),
    )
    conn.commit()
    conn.close()

    return {"sheet_json": _strip_hidden_fields(rebuilt)}


@router.patch("/characters/{character_id}/sheet")
def patch_character_sheet(character_id: int, req: CharacterSheetPatchRequest):
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
        existing_sheet_json = json.loads(row["sheet_json"]) if row["sheet_json"] else {}
    except Exception:
        existing_sheet_json = {}

    merged_sheet_json = _deep_merge_dicts(existing_sheet_json, req.sheet_json)

    conn.execute(
        """
        UPDATE characters
        SET sheet_json = ?
        WHERE id = ?
        """,
        (json.dumps(merged_sheet_json, ensure_ascii=False), character_id),
    )
    conn.commit()

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

    item = dict(updated_row)
    try:
        item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
    except Exception:
        item["sheet_json"] = {}
    item["sheet_json"] = _strip_hidden_fields(item["sheet_json"])

    return item


@router.post("/campaigns/{campaign_id}/characters")
def create_character(campaign_id: int, req: CharacterCreateRequest):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    campaign = conn.execute(
        """
        SELECT id, system_id, model_id, language
        FROM campaigns
        WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()

    if not campaign:
        conn.close()
        raise HTTPException(status_code=404, detail="Campaign not found")

    existing = conn.execute(
        "SELECT COUNT(*) AS n FROM characters WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    if existing and int(existing["n"] or 0) >= 1:
        conn.close()
        raise HTTPException(status_code=409, detail="Campaign already has a character.")

    if req.system_id != campaign["system_id"]:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"system_id mismatch: campaign uses '{campaign['system_id']}'"
        )

    # Insert first, then auto-build sheet values as part of creation flow.
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
            json.dumps(req.sheet_json, ensure_ascii=False),
            req.location,
            req.is_active,
        ),
    )
    conn.commit()

    character_id = cur.lastrowid

    created_sheet = _build_character_sheet(req.sheet_json, req.sheet_json.get("archetype"))
    conn.execute(
        """
        UPDATE characters
        SET sheet_json = ?
        WHERE id = ?
        """,
        (json.dumps(created_sheet, ensure_ascii=False), character_id),
    )
    conn.commit()

    opening_message = None
    try:
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
        archetype_label = "Mag" if archetype == "mage" else "Wojownik"

        char_summary = (
            f"Postać: {name}, Archetyp: {archetype_label}, "
            f"HP: {hp}"
            + (f", Mana: {mana}" if mana else "")
            + (f", Statystyki: {stat_lines}" if stat_lines else "")
            + (f", Umiejętności: {skill_lines}" if skill_lines else "")
            + (f", Tło: {background}" if background else "")
            + f", Lokalizacja startowa: {location}."
        )

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
            # settings table may not exist; keep fallback model
            pass
        finally:
            settings_conn.close()

        llm_config = get_user_llm_settings_full(req.user_id)
        # Prefer per-user model selection when generating the opening message.
        model = llm_config.get("model") or model
        opening_message = (generate_chat(messages=messages, model=model, llm_config=llm_config) or "").strip() or None

        if opening_message:
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
        raise HTTPException(status_code=500, detail="Character created but could not be loaded")

    item = dict(row)
    try:
        item["sheet_json"] = json.loads(item["sheet_json"]) if item["sheet_json"] else {}
    except Exception:
        item["sheet_json"] = {}
    item["sheet_json"] = _strip_hidden_fields(item["sheet_json"])
    item["opening_message"] = opening_message

    return item