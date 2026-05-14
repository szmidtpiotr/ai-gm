"""
Smart Entry Agent Router — Phase 08 Task 33

Admin endpoints for an AI-assisted record creation/editing agent.
The agent asks structured questions and builds DB records interactively.
"""

import json
import re
import sqlite3
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services.admin_auth import verify_admin_token
from app.services.llm_service import generate_chat

DB_PATH = "/data/ai_gm.db"

router = APIRouter(prefix="/api/admin/smart-entry", tags=["admin-smart-entry"])

# ── Session store ─────────────────────────────────────────────────────────────

_sessions: dict[str, dict] = {}
SESSION_TTL_SECONDS = 1800  # 30 minutes


def _purge_expired() -> None:
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["last_active"] > SESSION_TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]


def _get_or_create_session(session_id: str) -> dict:
    _purge_expired()
    if session_id not in _sessions:
        _sessions[session_id] = {
            "table": None,
            "history": [],
            "draft": {},
            "target_key": None,
            "answers": {},
            "proposed_changes": None,
            "last_active": time.time(),
        }
    else:
        _sessions[session_id]["last_active"] = time.time()
    return _sessions[session_id]


# ── Auth ──────────────────────────────────────────────────────────────────────

def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


# ── Table permissions ─────────────────────────────────────────────────────────

WRITABLE_TABLES = {
    "game_config_weapons",
    "game_config_items",
    "game_config_consumables",
    "game_config_enemies",
}

READ_ONLY_TABLES = {
    "game_config_skills",
    "game_config_archetypes",
    "characters",
    "campaigns",
    "users",
}


def _assert_writable(table: str) -> None:
    if table in READ_ONLY_TABLES or table not in WRITABLE_TABLES:
        raise HTTPException(
            status_code=403,
            detail=f"Table '{table}' is read-only or not supported for Smart Entry.",
        )


# ── Schema descriptors ────────────────────────────────────────────────────────

SCHEMA_DESCRIPTORS: dict[str, dict] = {
    "game_config_weapons": {
        "required": ["key", "label", "damage_die", "weapon_type", "linked_stat"],
        "optional": ["two_handed", "value_gp", "allowed_classes"],
        "fields": {
            "key": {
                "type": "text",
                "question": "Podaj unikalny klucz (slug) dla tej broni, np. 'cursed_sword'.",
            },
            "label": {
                "type": "text",
                "question": "Jak ma się nazywać ta broń (wyświetlana nazwa)?",
            },
            "damage_die": {
                "type": "single_choice",
                "question": "Jak duże obrażenia zadaje?",
                "options": [
                    {"label": "d4", "description": "Lekka broń", "preview": "Avg: 2.5 + STR"},
                    {"label": "d6", "description": "Standardowa broń", "preview": "Avg: 3.5 + STR"},
                    {"label": "d8", "description": "Solidna broń", "preview": "Avg: 4.5 + STR"},
                    {"label": "d10", "description": "Ciężka broń", "preview": "Avg: 5.5 + STR"},
                    {"label": "d12", "description": "Broń dwuręczna lub potężna", "preview": "Avg: 6.5 + STR"},
                ],
            },
            "weapon_type": {
                "type": "single_choice",
                "question": "Jaki to rodzaj broni?",
                "options": [
                    {"label": "melee", "description": "Broń do walki wręcz"},
                    {"label": "ranged", "description": "Broń miotana lub strzelecka"},
                    {"label": "spell", "description": "Broń magiczna / zaklęcie"},
                ],
            },
            "linked_stat": {
                "type": "single_choice",
                "question": "Na jaki atrybut postaci wpływa ta broń?",
                "options": [
                    {"label": "STR", "description": "Siła — dla broni do walki wręcz"},
                    {"label": "DEX", "description": "Zręczność — dla broni zwinnych i ranged"},
                    {"label": "INT", "description": "Inteligencja — dla broni magicznych"},
                ],
            },
            "two_handed": {
                "type": "boolean",
                "question": "Czy broń wymaga obu rąk?",
            },
            "value_gp": {
                "type": "number",
                "question": "Ile kosztuje ta broń (w złotych monetach, 1-500)?",
                "min": 1,
                "max": 500,
            },
            "allowed_classes": {
                "type": "multi_choice",
                "question": "Które klasy mogą używać tej broni?",
                "options": [
                    {"label": "warrior", "description": "Wojownik"},
                    {"label": "scholar", "description": "Uczony"},
                ],
            },
        },
    },
    "game_config_items": {
        "required": ["key", "label", "item_type", "value_gp"],
        "optional": ["ac_bonus", "effect_json"],
        "fields": {
            "key": {
                "type": "text",
                "question": "Podaj unikalny klucz (slug) dla tego przedmiotu, np. 'iron_shield'.",
            },
            "label": {
                "type": "text",
                "question": "Jak ma się nazywać ten przedmiot (wyświetlana nazwa)?",
            },
            "item_type": {
                "type": "single_choice",
                "question": "Jaki to rodzaj przedmiotu?",
                "options": [
                    {"label": "armor", "description": "Zbroja / ochrona"},
                    {"label": "accessory", "description": "Akcesoria (pierścień, amulet)"},
                    {"label": "misc", "description": "Różne przedmioty"},
                    {"label": "key_item", "description": "Przedmiot fabularny / klucz"},
                ],
            },
            "value_gp": {
                "type": "number",
                "question": "Ile kosztuje ten przedmiot (w złotych monetach)?",
                "min": 0,
            },
            "ac_bonus": {
                "type": "number",
                "question": "O ile punktów zwiększa Klasę Pancerza (AC)? (0-8)",
                "min": 0,
                "max": 8,
            },
            "effect_json": {
                "type": "text",
                "question": "Opisz efekt przedmiotu w formacie JSON (opcjonalnie), np. {\"type\": \"heal\", \"amount\": 5}.",
            },
        },
    },
    "game_config_consumables": {
        "required": ["key", "label", "effect_type", "base_price"],
        "optional": ["effect_dice", "effect_bonus"],
        "fields": {
            "key": {
                "type": "text",
                "question": "Podaj unikalny klucz (slug) dla tego konsumabla, np. 'healing_potion'.",
            },
            "label": {
                "type": "text",
                "question": "Jak ma się nazywać ten konsumable (wyświetlana nazwa)?",
            },
            "effect_type": {
                "type": "single_choice",
                "question": "Jaki efekt ma ten konsumable?",
                "options": [
                    {"label": "heal_hp", "description": "Leczy punkty życia"},
                    {"label": "restore_mana", "description": "Przywraca manę"},
                    {"label": "cure_condition", "description": "Usuwa negatywny stan"},
                    {"label": "buff", "description": "Daje tymczasowe wzmocnienie"},
                ],
            },
            "base_price": {
                "type": "number",
                "question": "Ile kosztuje ten konsumable (w złotych monetach)?",
                "min": 1,
            },
            "effect_dice": {
                "type": "text",
                "question": "Ile kości efektu? Podaj notację np. '1d8', '2d6' (opcjonalnie).",
            },
            "effect_bonus": {
                "type": "number",
                "question": "Stały bonus do efektu (np. +2 do leczenia, opcjonalnie).",
            },
        },
    },
    "game_config_enemies": {
        "required": ["key", "label", "tier", "hp_base", "ac_base", "attack_bonus", "damage_dice"],
        "optional": ["drop_chance", "loot_table_key"],
        "fields": {
            "key": {
                "type": "text",
                "question": "Podaj unikalny klucz (slug) dla tego przeciwnika, np. 'goblin_raider'.",
            },
            "label": {
                "type": "text",
                "question": "Jak ma się nazywać ten przeciwnik (wyświetlana nazwa)?",
            },
            "tier": {
                "type": "single_choice",
                "question": "Jaka jest siła tego przeciwnika?",
                "options": [
                    {"label": "weak", "description": "Słaby — łatwy do pokonania"},
                    {"label": "standard", "description": "Standardowy — normalny wróg"},
                    {"label": "elite", "description": "Elitarny — silniejszy niż przeciętny"},
                    {"label": "boss", "description": "Boss — bardzo potężny"},
                ],
            },
            "hp_base": {
                "type": "number",
                "question": "Ile podstawowych punktów życia ma ten przeciwnik?",
                "min": 1,
            },
            "ac_base": {
                "type": "number",
                "question": "Jaka jest podstawowa Klasa Pancerza (AC) tego przeciwnika? (zwykle 8-18)",
                "min": 1,
            },
            "attack_bonus": {
                "type": "number",
                "question": "Jaki bonus do ataku ma ten przeciwnik?",
            },
            "damage_dice": {
                "type": "text",
                "question": "Ile obrażeń zadaje w jednym ataku? Podaj notację np. '1d6', '2d8+2'.",
            },
            "drop_chance": {
                "type": "number",
                "question": "Szansa na upuszczenie łupu (0.0-1.0, opcjonalnie)?",
                "min": 0,
                "max": 1,
            },
            "loot_table_key": {
                "type": "text",
                "question": "Klucz tabeli łupów (opcjonalnie, np. 'goblin_loot').",
            },
        },
    },
}

# ── Table inference ───────────────────────────────────────────────────────────

TABLE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("game_config_weapons", ["weapon", "broń", "bron", "sword", "miecz", "axe", "siekier", "bow", "łuk", "spear", "włóczni", "dagger", "sztylet", "hammer", "młot"]),
    ("game_config_enemies", [
        "enemy", "enemies", "wróg", "wroga", "wrogi", "wrogiem", "wrogów",
        "monster", "potwór", "potwora", "potwory", "creature", "stworzenie",
        "boss", "goblin", "orc", "ork", "dragon", "smok", "undead", "nieumarły",
    ]),
    ("game_config_consumables", ["consumable", "konsumable", "potion", "mikstura", "elixir", "eliksir", "scroll", "zwój", "food", "jedzenie"]),
    ("game_config_items", ["item", "przedmiot", "armor", "zbroja", "shield", "tarcza", "accessory", "akcesoria", "ring", "pierścień", "amulet", "helm", "hełm"]),
]


def _infer_table(message: str) -> Optional[str]:
    msg_lower = message.lower()
    for table, keywords in TABLE_KEYWORDS:
        for kw in keywords:
            if kw in msg_lower:
                return table
    return None


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _db_search(table: str, filters: dict, limit: int = 5) -> list[dict]:
    """Simple SELECT with LIKE filters."""
    if table not in WRITABLE_TABLES and table not in READ_ONLY_TABLES:
        return []
    conn = _get_db()
    try:
        if filters:
            conditions = []
            params = []
            for col, val in filters.items():
                conditions.append(f"{col} LIKE ?")
                params.append(f"%{val}%")
            where = " AND ".join(conditions)
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE {where} LIMIT ?",
                params + [limit],
            ).fetchall()
        else:
            rows = conn.execute(f"SELECT * FROM {table} LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _db_get(table: str, key: str) -> Optional[dict]:
    """SELECT WHERE key = ?"""
    conn = _get_db()
    try:
        row = conn.execute(f"SELECT * FROM {table} WHERE key = ?", (key,)).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def _db_insert(table: str, record: dict) -> str:
    """INSERT into table, returns key."""
    conn = _get_db()
    try:
        cols = ", ".join(record.keys())
        placeholders = ", ".join(["?" for _ in record])
        conn.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
            list(record.values()),
        )
        conn.commit()
        return record["key"]
    finally:
        conn.close()


def _db_update_field(table: str, key: str, field: str, value: Any) -> None:
    """UPDATE single field WHERE key = ?"""
    conn = _get_db()
    try:
        conn.execute(
            f"UPDATE {table} SET {field} = ? WHERE key = ?",
            (value, key),
        )
        conn.commit()
    finally:
        conn.close()


# ── Agent system prompt ───────────────────────────────────────────────────────

SMART_ENTRY_SYSTEM_PROMPT = """Jesteś asystentem tworzenia treści gry RPG. Pomagasz administratorowi tworzyć i edytować rekordy w bazie danych.
Zadajesz jedno konkretne pytanie na raz. Jesteś precyzyjny i skupiony na mechanice.
Nie zadawaj więcej niż 6 pytań zanim zaproponujesz gotowy rekord.
Gdy draft jest kompletny powiedz adminowi i zaproponuj zapis.
Świat gry: mroczna fantasy, WFRP-inspired."""


# ── Question builder ──────────────────────────────────────────────────────────

def _build_questions_for_table(table: str, answered: dict) -> list[dict]:
    """Return the next unanswered question as a visual card list (max 1)."""
    schema = SCHEMA_DESCRIPTORS.get(table)
    if not schema:
        return []

    questions = []
    # Ask required fields first, then optional
    for field_key in schema["required"] + schema["optional"]:
        if field_key in answered:
            continue
        field_def = schema["fields"].get(field_key)
        if not field_def:
            continue

        q: dict[str, Any] = {
            "id": field_key,
            "type": field_def["type"],
            "question": field_def["question"],
        }
        if "options" in field_def:
            q["options"] = field_def["options"]
        if "min" in field_def:
            q["min"] = field_def["min"]
        if "max" in field_def:
            q["max"] = field_def["max"]

        questions.append(q)
        break  # one question at a time

    return questions if questions else []


def _all_required_filled(table: str, answered: dict) -> bool:
    schema = SCHEMA_DESCRIPTORS.get(table)
    if not schema:
        return False
    return all(f in answered for f in schema["required"])


# ── Agent logic ───────────────────────────────────────────────────────────────

def _build_llm_context(session: dict, user_message: str, db_context: Optional[dict]) -> str:
    """Build a context string injected into the LLM alongside the system prompt."""
    parts = []

    if session.get("table"):
        parts.append(f"Aktywna tabela: {session['table']}")

    if session.get("answers"):
        parts.append(f"Zebrane odpowiedzi: {json.dumps(session['answers'], ensure_ascii=False)}")

    if db_context:
        parts.append(f"Znalezione w DB: {json.dumps(db_context, ensure_ascii=False)}")

    if session.get("draft"):
        parts.append(f"Bieżący draft: {json.dumps(session['draft'], ensure_ascii=False)}")

    if session.get("target_key"):
        parts.append(f"Edytowany rekord: {session['target_key']}")

    return "\n".join(parts)


# ── Request/response models ───────────────────────────────────────────────────

class SmartEntryMessageReq(BaseModel):
    session_id: str
    table: Optional[str] = None
    message: str = ""
    answer: Optional[dict] = None  # {"question_id": str, "value": Any}


class SmartEntrySaveReq(BaseModel):
    session_id: str


class SmartEntryApplyChangeReq(BaseModel):
    session_id: str
    change_index: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/message")
def smart_entry_message(
    req: SmartEntryMessageReq,
    _: None = Depends(_require_admin),
):
    session = _get_or_create_session(req.session_id)

    # ── Apply incoming structured answer ──────────────────────────────────────
    if req.answer and isinstance(req.answer, dict):
        qid = req.answer.get("question_id")
        val = req.answer.get("value")
        if qid is not None and val is not None:
            session["answers"][qid] = val
            session["draft"][qid] = val

    # ── Resolve table ─────────────────────────────────────────────────────────
    if req.table:
        if req.table in READ_ONLY_TABLES:
            raise HTTPException(
                status_code=403,
                detail=f"Table '{req.table}' is read-only and cannot be used with Smart Entry.",
            )
        if req.table not in WRITABLE_TABLES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown table '{req.table}'. Supported: {sorted(WRITABLE_TABLES)}",
            )
        session["table"] = req.table
    elif not session["table"]:
        inferred = _infer_table(req.message)
        if inferred:
            session["table"] = inferred

    table = session["table"]

    # ── DB context: look up existing records matching the message ─────────────
    db_context: Optional[dict] = None
    if table:
        # Try exact key match first
        words = re.findall(r"[a-z_]+", req.message.lower())
        for word in words:
            if len(word) >= 3:
                found = _db_get(table, word)
                if found:
                    session["target_key"] = word
                    db_context = {"found": found, "mode": "update"}
                    break

        # Fall back to label LIKE search
        if not db_context:
            similar = _db_search(table, {"label": req.message[:40]}, limit=3)
            if similar:
                db_context = {"similar": similar}

    # ── Build questions ───────────────────────────────────────────────────────
    questions: Optional[list] = None
    ready_to_save = False
    save_key: Optional[str] = None

    if table:
        if session.get("target_key"):
            # UPDATE flow — detect proposed changes from LLM later
            pass
        else:
            # CREATE flow
            all_required_done = _all_required_filled(table, session["answers"])
            if all_required_done:
                # Required fields are complete — ready to save, optionals are bonus
                ready_to_save = True
                save_key = None  # new record
                # Still offer optional questions if they haven't been asked yet
                questions = _build_questions_for_table(table, session["answers"])
                if not questions:
                    questions = None
            else:
                # Keep asking until required fields are done
                questions = _build_questions_for_table(table, session["answers"])
                if not questions:
                    questions = None

        if session.get("target_key") and _all_required_filled(table, session["answers"]):
            ready_to_save = True
            save_key = session["target_key"]

    # ── Build LLM messages ────────────────────────────────────────────────────
    context_str = _build_llm_context(session, req.message, db_context)

    user_content = req.message
    if context_str:
        user_content = f"{context_str}\n\nWiadomość admina: {req.message}"

    session["history"].append({"role": "user", "content": user_content})
    messages = [{"role": "system", "content": SMART_ENTRY_SYSTEM_PROMPT}] + session["history"]

    try:
        reply = generate_chat(messages=messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    session["history"].append({"role": "assistant", "content": reply})

    # ── Detect proposed_changes in UPDATE flow ────────────────────────────────
    proposed_changes: Optional[list] = None
    if session.get("target_key"):
        changes_match = re.search(r"```json\s*\n(\[.*?\])\n```", reply, re.DOTALL)
        if changes_match:
            try:
                changes = json.loads(changes_match.group(1))
                if isinstance(changes, list):
                    session["proposed_changes"] = changes
                    proposed_changes = changes
            except json.JSONDecodeError:
                pass
        else:
            proposed_changes = session.get("proposed_changes")

    return {
        "session_id": req.session_id,
        "reply": reply,
        "questions": questions if questions else None,
        "db_context": db_context,
        "draft": session["draft"] if session["draft"] else None,
        "proposed_changes": proposed_changes,
        "ready_to_save": ready_to_save,
        "save_table": table,
        "save_key": save_key,
    }


@router.post("/save")
def smart_entry_save(
    req: SmartEntrySaveReq,
    _: None = Depends(_require_admin),
):
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    table = session.get("table")
    if not table:
        raise HTTPException(status_code=400, detail="No table set in session.")

    _assert_writable(table)

    draft = session.get("draft", {})
    if not draft:
        raise HTTPException(status_code=400, detail="No draft data to save.")

    schema = SCHEMA_DESCRIPTORS.get(table, {})
    required = schema.get("required", [])
    missing = [f for f in required if f not in draft]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Draft is missing required fields: {missing}",
        )

    # Coerce boolean/number fields
    record = dict(draft)
    fields_def = schema.get("fields", {})
    for k, v in record.items():
        field_type = fields_def.get(k, {}).get("type")
        if field_type == "boolean":
            record[k] = 1 if v else 0
        elif field_type == "number":
            try:
                record[k] = float(v) if "." in str(v) else int(v)
            except (ValueError, TypeError):
                pass

    try:
        saved_key = _db_insert(table, record)
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"Record already exists or constraint failed: {e}")

    return {"ok": True, "key": saved_key, "table": table}


@router.post("/apply-change")
def smart_entry_apply_change(
    req: SmartEntryApplyChangeReq,
    _: None = Depends(_require_admin),
):
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    proposed = session.get("proposed_changes") or []
    if req.change_index < 0 or req.change_index >= len(proposed):
        raise HTTPException(status_code=400, detail=f"change_index {req.change_index} is out of range.")

    table = session.get("table")
    target_key = session.get("target_key")
    if not table or not target_key:
        raise HTTPException(status_code=400, detail="No table/target_key set in session.")

    _assert_writable(table)

    change = proposed[req.change_index]
    field = change.get("field")
    new_value = change.get("new_value") if "new_value" in change else change.get("value")

    if not field:
        raise HTTPException(status_code=400, detail="Change is missing 'field'.")

    try:
        _db_update_field(table, target_key, field, new_value)
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=500, detail=f"DB update failed: {e}")

    return {"ok": True}
