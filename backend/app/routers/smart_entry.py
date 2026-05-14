"""
Smart Entry Agent Router — Phase 08 Task 33 (v2)

Admin endpoints for an AI-assisted record creation/editing agent.
v2: Form-first flow — LLM fills JSON draft in one shot instead of Q&A.
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
        "optional": ["two_handed", "value_gp", "allowed_classes", "description", "note", "targeting", "weight_kg"],
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
                    {"label": "d4", "description": "Lekka broń"},
                    {"label": "d6", "description": "Standardowa broń"},
                    {"label": "d8", "description": "Solidna broń"},
                    {"label": "d10", "description": "Ciężka broń"},
                    {"label": "d12", "description": "Broń dwuręczna lub potężna"},
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
                "min": 0,
                "max": 500,
            },
            "allowed_classes": {
                "type": "multi_choice",
                "question": "Które klasy mogą używać tej broni?",
                "options": [
                    {"label": "warrior", "description": "Wojownik"},
                    {"label": "scholar", "description": "Uczony"},
                    {"label": "ranger", "description": "Łucznik/Strzelec"},
                ],
            },
            "description": {
                "type": "textarea",
                "question": "Opis broni dla GM (wygląd, materiał, historia, klimat).",
            },
            "note": {
                "type": "textarea",
                "question": "Specjalne zdolności / reguły (np. 'Zadaje 1k4 trucizny przy trafieniu, DC 12 odporność').",
            },
            "targeting": {
                "type": "single_choice",
                "question": "Rodzaj celowania?",
                "options": [
                    {"label": "single", "description": "Jeden cel"},
                    {"label": "aoe", "description": "Obszar (AOE)"},
                    {"label": "line", "description": "Linia"},
                ],
            },
            "weight_kg": {
                "type": "number",
                "question": "Waga w kilogramach (np. 0.5, 2.0)?",
                "min": 0,
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


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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


# ── LLM prompt (v2 — JSON output) ─────────────────────────────────────────────

SMART_ENTRY_SYSTEM_PROMPT_V2 = """Jesteś asystentem tworzenia rekordów gry RPG (mroczna fantasy, WFRP-inspired).
Admin opisuje rekord który chce stworzyć lub zmienić. Ty wypełniasz pola formularza.

ZAWSZE odpowiadaj WYŁĄCZNIE prawidłowym JSON-em w formacie:
{"reply": "krótki komentarz co zrobiłeś (po polsku, max 2 zdania)", "draft": {"pole": wartość, ...}}

ZASADY:
- Pola i dozwolone wartości są podane w kontekście (SCHEMAT). NIE wymyślaj innych.
- Dla single_choice: użyj DOKŁADNIE jednej z podanych wartości (np. "d6", "melee", "STR")
- Dla multi_choice: zwróć listę wartości oddzieloną przecinkami np. "warrior,scholar"
- Dla boolean: zwróć 1 lub 0
- Dla number: zwróć liczbę (nie string)
- Klucz 'key': generuj automatycznie ze slug z 'label': małe litery, pl→ascii, spacje→_
- Wypełnij tyle pól ile możesz. Pomiń pola których nie znasz.
- Jeśli admin prosi o zmianę konkretnego pola, zmień tylko to pole (zachowaj resztę z current_draft)
"""


def _build_schema_constraint_text(table: str) -> str:
    """Build a human-readable schema description for the LLM."""
    schema = SCHEMA_DESCRIPTORS.get(table, {})
    if not schema:
        return ""
    lines = [f"SCHEMAT {table}:", "Wymagane:"]
    for fk in schema.get("required", []):
        fd = schema["fields"].get(fk, {})
        line = f"  {fk} (typ={fd.get('type', 'text')})"
        if fd.get("options"):
            opts = [str(o.get("label", o) if isinstance(o, dict) else o) for o in fd["options"]]
            line += f" → dozwolone: [{', '.join(opts)}]"
        if "min" in fd:
            line += f" min={fd['min']}"
        if "max" in fd:
            line += f" max={fd['max']}"
        lines.append(line)
    if schema.get("optional"):
        lines.append("Opcjonalne:")
        for fk in schema.get("optional", []):
            fd = schema["fields"].get(fk, {})
            line = f"  {fk} (typ={fd.get('type', 'text')})"
            if fd.get("options"):
                opts = [str(o.get("label", o) if isinstance(o, dict) else o) for o in fd["options"]]
                line += f" → dozwolone: [{', '.join(opts)}]"
            lines.append(line)
    return "\n".join(lines)


def _parse_llm_draft_response(reply: str) -> tuple[str, dict]:
    """Parse LLM reply that should contain JSON {reply, draft}. Returns (text, draft)."""
    text = reply.strip()
    # Remove markdown code fences
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = text.replace('```', '').strip()
    # Try whole thing as JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return str(data.get("reply", "")), dict(data.get("draft", {}))
    except json.JSONDecodeError:
        pass
    # Find first { ... } block
    start = text.find('{')
    if start >= 0:
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start:i + 1])
                        if isinstance(data, dict):
                            return str(data.get("reply", reply)), dict(data.get("draft", {}))
                    except json.JSONDecodeError:
                        break
    return reply, {}


# ── Request/response models ───────────────────────────────────────────────────

class SmartEntryMessageReq(BaseModel):
    session_id: str
    table: Optional[str] = None
    message: str = ""
    current_draft: Optional[dict] = None  # full form state from frontend
    target_key: Optional[str] = None      # if editing an existing record


class SmartEntrySaveReq(BaseModel):
    session_id: str
    draft: dict = {}        # form values from frontend
    table: Optional[str] = None
    target_key: Optional[str] = None  # if editing existing


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/schema")
def smart_entry_schema(table: str, _: None = Depends(_require_admin)):
    """Return field schema for frontend form rendering."""
    schema = SCHEMA_DESCRIPTORS.get(table)
    if not schema:
        raise HTTPException(status_code=404, detail=f"No schema for table '{table}'")

    FIELD_LABELS = {
        "key": "Klucz (slug)", "label": "Nazwa", "damage_die": "Kość obrażeń",
        "weapon_type": "Typ broni", "linked_stat": "Stat. powiązana", "two_handed": "Dwuręczna",
        "value_gp": "Cena (gp)", "allowed_classes": "Klasy", "item_type": "Typ przedmiotu",
        "ac_bonus": "Bonus AC", "effect_json": "Efekt (JSON)", "effect_type": "Typ efektu",
        "base_price": "Cena bazowa", "effect_dice": "Kości efektu", "effect_bonus": "Bonus efektu",
        "tier": "Poziom", "hp_base": "HP bazowe", "ac_base": "AC bazowe",
        "attack_bonus": "Bonus do ataku", "damage_dice": "Kości obrażeń",
        "drop_chance": "Szansa łupu", "loot_table_key": "Tabela łupów",
        "description": "Opis (dla GM)", "note": "Zdolności specjalne",
        "targeting": "Rodzaj celowania", "weight_kg": "Waga (kg)",
    }

    fields = []
    for field_key in schema["required"] + schema.get("optional", []):
        field_def = schema["fields"].get(field_key, {})
        f: dict[str, Any] = {
            "key": field_key,
            "label": FIELD_LABELS.get(field_key, field_key.replace("_", " ").title()),
            "type": field_def.get("type", "text"),
            "required": field_key in schema["required"],
        }
        if field_def.get("options"):
            f["options"] = field_def["options"]
        if "min" in field_def:
            f["min"] = field_def["min"]
        if "max" in field_def:
            f["max"] = field_def["max"]
        if field_def.get("question"):
            f["placeholder"] = field_def["question"]
        fields.append(f)

    return {"table": table, "fields": fields}


@router.get("/list")
def smart_entry_list(table: str, _: None = Depends(_require_admin)):
    """Return list of existing records for the dropdown."""
    if table not in WRITABLE_TABLES:
        raise HTTPException(status_code=400, detail=f"Unknown table '{table}'")
    conn = _get_db()
    try:
        rows = conn.execute(f"SELECT key, label FROM {table} ORDER BY label LIMIT 300").fetchall()
        return {"items": [{"key": r["key"], "label": r["label"]} for r in rows]}
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/record")
def smart_entry_record(table: str, key: str, _: None = Depends(_require_admin)):
    """Return a single record by key for editing."""
    _assert_writable(table)
    record = _db_get(table, key)
    if not record:
        raise HTTPException(status_code=404, detail=f"Record '{key}' not found in {table}")
    return record


@router.post("/message")
def smart_entry_message(
    req: SmartEntryMessageReq,
    _: None = Depends(_require_admin),
):
    session = _get_or_create_session(req.session_id)

    # Sync table
    if req.table:
        _assert_writable(req.table)
        session["table"] = req.table
    if req.target_key is not None:
        session["target_key"] = req.target_key or None

    # Merge frontend draft into session draft
    if req.current_draft:
        session["draft"].update({k: v for k, v in req.current_draft.items() if v not in (None, "")})

    table = session.get("table")

    # Build system prompt with schema constraints
    schema_text = _build_schema_constraint_text(table) if table else "Tabela nieznana — zapytaj o typ rekordu."

    # Build user message context
    context_parts = []
    if table:
        context_parts.append(schema_text)
    if session["draft"]:
        context_parts.append(f"Bieżący draft: {json.dumps(session['draft'], ensure_ascii=False)}")
    if session.get("target_key"):
        context_parts.append(f"TRYB EDYCJI rekordu: {session['target_key']}")

    user_content = req.message
    if context_parts:
        user_content = "\n".join(context_parts) + f"\n\nAdmin: {req.message}"

    session["history"].append({"role": "user", "content": user_content})
    messages = [{"role": "system", "content": SMART_ENTRY_SYSTEM_PROMPT_V2}] + session["history"][-10:]

    try:
        raw_reply = generate_chat(messages=messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    session["history"].append({"role": "assistant", "content": raw_reply})

    # Parse JSON response
    reply_text, new_draft = _parse_llm_draft_response(raw_reply)

    # Validate and merge new_draft into session draft
    if new_draft and table:
        schema = SCHEMA_DESCRIPTORS.get(table, {})
        valid_fields = set(schema.get("required", [])) | set(schema.get("optional", []))
        for k, v in new_draft.items():
            if k in valid_fields:
                session["draft"][k] = v

    return {
        "session_id": req.session_id,
        "reply": reply_text or "Wypełniłem co mogłem.",
        "draft": session["draft"],
    }


@router.post("/save")
def smart_entry_save(
    req: SmartEntrySaveReq,
    _: None = Depends(_require_admin),
):
    # Use request values, fall back to session
    session = _sessions.get(req.session_id, {})
    table = req.table or session.get("table")
    draft = req.draft or session.get("draft", {})
    target_key = req.target_key or session.get("target_key")

    if not table:
        raise HTTPException(status_code=400, detail="No table specified.")
    _assert_writable(table)
    if not draft:
        raise HTTPException(status_code=400, detail="No draft data to save.")

    schema = SCHEMA_DESCRIPTORS.get(table, {})
    required = schema.get("required", [])
    missing = [f for f in required if not draft.get(f)]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required fields: {missing}")

    # Coerce types
    record = dict(draft)
    fields_def = schema.get("fields", {})
    for k, v in list(record.items()):
        field_type = fields_def.get(k, {}).get("type")
        if field_type == "boolean":
            record[k] = 1 if v else 0
        elif field_type == "number":
            try:
                record[k] = float(v) if "." in str(v) else int(v)
            except (ValueError, TypeError):
                pass

    if target_key:
        # UPDATE existing record
        for field, value in record.items():
            if field != "key":
                _db_update_field(table, target_key, field, value)
        return {"ok": True, "key": target_key, "table": table, "mode": "update"}
    else:
        # INSERT new record
        try:
            key = _db_insert(table, record)
            return {"ok": True, "key": key, "table": table, "mode": "create"}
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=409, detail=f"Record already exists: {e}")
