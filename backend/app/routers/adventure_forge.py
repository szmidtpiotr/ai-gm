"""
Adventure Forge Router — Kuźnia Kampanii
AI-assisted adventure idea creation → hooks → real DB records → campaign templates
"""

import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from app.core.logging import get_logger
from app.services.admin_auth import verify_admin_token
from app.services.campaign_plan_service import normalize_plan_beats
from app.services.llm_service import generate_chat
from app.core.db_runtime import resolve_db_path

logger = get_logger(__name__)


def _safe_int(val, default):
    try:
        return int(val) if val is not None and val != "" else default
    except (ValueError, TypeError):
        return default


_LOC_TYPE_MAP = {"sub": "sub"}  # everything else → macro

DB_PATH = resolve_db_path()

router = APIRouter(prefix="/api/admin/forge", tags=["admin-adventure-forge"])

# ── Session store ─────────────────────────────────────────────────────────────

_sessions: dict[str, dict] = {}
SESSION_TTL_SECONDS = 7200


def _purge_expired() -> None:
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["last_active"] > SESSION_TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]


def _get_or_create_session(session_id: str) -> dict:
    _purge_expired()
    if session_id not in _sessions:
        _sessions[session_id] = {"history": [], "draft": None, "last_active": time.time()}
    else:
        _sessions[session_id]["last_active"] = time.time()
    return _sessions[session_id]


# ── Auth ──────────────────────────────────────────────────────────────────────

def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


# ── DB helper ─────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── AI system prompts ─────────────────────────────────────────────────────────

FORGE_SYSTEM_PROMPT = """Jesteś kreatywnym projektantem przygód do mrocznego fantasy RPG (WFRP-inspired). Pomagasz administratorowi zbudować ustrukturyzowany pomysł na przygodę, który trafi do bazy danych gry.

TWOJE ZADANIE:
1. Zadaj 4-6 pytań doprecyzowujących (ton, klimat, typ protagonisty, główny konflikt, skala, styl narracji)
2. Po zebraniu wystarczających informacji — zaproponuj pełny szkic przygody w formacie JSON
3. Dostosuj szkic na podstawie feedbacku
4. Gdy admin powie "zapisz", "zatwierdź" lub "save" — zwróć JSON z kluczem "READY_TO_SAVE": true i pełnym szkicem

ZASADA ABSOLUTNA — JSON:
- Gdy zwracasz lub aktualizujesz szkic, ZAWSZE zwróć KOMPLETNY zaktualizowany szkic w bloku ```json
- NIGDY nie zwracaj częściowego patcha, diff-a ani tylko zmienionych pól
- Jeśli admin zaakceptuje propozycję zmian — natychmiast wygeneruj pełny zaktualizowany JSON
- JSON MUSI być w bloku ```json ... ``` — nigdy jako surowy tekst
- Tekst odpowiedzi (poza blokiem JSON) może być krótki — 1-2 zdania komentarza

FORMAT JSON gdy proponujesz lub aktualizujesz szkic:
```json
{
  "title": "Tytuł przygody",
  "premise": "2-3 zdania opisu przygody",
  "tone": ["dark", "mystery"],
  "themes": ["betrayal", "ancient evil"],
  "difficulty": "easy|medium|hard",
  "arcs": [
    {
      "title": "Tytuł aktu",
      "description": "Opis aktu",
      "scene_goals": ["Cel sceny 1", "Cel sceny 2"],
      "private_twist": "Sekret tylko dla GM"
    }
  ],
  "hooks": [
    {
      "type": "weapon|armor|item|consumable|enemy|npc|location|event|theme",
      "title": "Nazwa hooka",
      "description": "Opis hooka",
      "significance": "minor|major|central",
      "draft_data": {}
    }
  ],
  "player_hook": "Co wciąga gracza w przygodę",
  "gm_private": "Sekretny twist tylko dla GM"
}
```

ŚWIAT: Mroczna fantasy (WFRP-inspired) — grim, niebezpieczny, moralnie niejednoznaczny.
TON: Kreatywny, entuzjastyczny. Traktuj admina jak współautora.
JĘZYK: Odpowiadaj po polsku.

Gdy gotowy do zapisu: {"READY_TO_SAVE": true, "draft": {...}}"""

EXTRACT_HOOKS_SYSTEM_PROMPT = """Jesteś ekspertem od ekstrakcji elementów gry RPG z opisu przygody.

Zadanie: przeanalizuj JSON przygody i wyodrębnij WSZYSTKIE hooki gotowe do wstawienia do bazy danych.

Dla każdego hooka wypełnij draft_data zgodnie ze schematem docelowej tabeli:

WEAPON lub ARMOR (hook_type: weapon / armor):
{"key": "slug", "label": "Nazwa", "damage_die": "1d6", "linked_stat": "STR", "allowed_classes": "warrior,rogue", "description": "...", "weapon_type": "melee|ranged|armor", "rarity": 1, "note": "Zdolności specjalne dla MG (opcjonalne)", "effect_json": null}

ITEM (hook_type: item):
{"key": "slug", "label": "Nazwa", "item_type": "misc|tool|key|quest", "description": "...", "value_gp": 0, "rarity": 1, "effect_json": null}

CONSUMABLE (hook_type: consumable):
{"key": "slug", "label": "Nazwa", "description": "...", "effect_type": "heal|buff|misc", "base_price": 0, "rarity": 1, "effect_dice": "1d4", "effect_bonus": 0, "effect_target": "self"}

ENEMY (hook_type: enemy):
{"key": "slug", "label": "Nazwa", "hp_base": 20, "ac_base": 12, "attack_bonus": 3, "damage_die": "1d6", "description": "...", "tier": "standard|weak|elite|boss", "damage_type": "physical|fire|poison"}

NPC (hook_type: npc):
{"key": "slug", "label": "Nazwa", "npc_type": "neutral|merchant|quest_giver|ally", "description": "...", "personality_prompt": "opis osobowości"}

LOCATION (hook_type: location):
{"key": "slug", "label": "Nazwa", "description": "...", "location_type": "macro|micro|dungeon", "biome": "forest|city|dungeon|ruin|plains"}

Klucze (slug) generuj z tytułu: małe litery, spacje → podkreślniki, bez polskich znaków.

Zwróć TYLKO tablicę JSON:
```json
[
  {"hook_type": "weapon", "title": "...", "description": "...", "significance": "minor|major|central", "draft_data": {...}},
  ...
]
```"""


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _extract_json_object(text: str) -> dict | None:
    candidates = []
    cb = re.search(r"```json\s*\n?(.*?)```", text, re.DOTALL)
    if cb:
        candidates.append(cb.group(1).strip())
    stripped = text.strip()
    if stripped.startswith("{"):
        candidates.append(stripped)
    span = re.search(r"\{.*\}", text, re.DOTALL)
    if span:
        candidates.append(span.group(0))
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return None


def _extract_json_array(text: str) -> list | None:
    candidates = []
    cb = re.search(r"```json\s*\n?(.*?)```", text, re.DOTALL)
    if cb:
        candidates.append(cb.group(1).strip())
    stripped = text.strip()
    if stripped.startswith("["):
        candidates.append(stripped)
    span = re.search(r"\[.*\]", text, re.DOTALL)
    if span:
        candidates.append(span.group(0))
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, list):
                return obj
        except json.JSONDecodeError:
            pass
    return None


def _extract_draft(text: str) -> tuple[dict | None, bool]:
    obj = _extract_json_object(text)
    if obj is None:
        return None, False
    ready = bool(obj.get("READY_TO_SAVE") or obj.get("ready_to_save"))
    draft = obj.get("draft")
    if isinstance(draft, dict) and draft:
        return draft, ready
    if "title" in obj or "arcs" in obj or "hooks" in obj:
        return obj, ready
    return None, False


# ── Row converters ────────────────────────────────────────────────────────────

def _idea_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "premise": row["premise"],
        "tone": json.loads(row["tone"] or "[]"),
        "themes": json.loads(row["themes"] or "[]"),
        "difficulty": row["difficulty"],
        "structured_data": json.loads(row["structured_data"] or "{}"),
        "status": row["status"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


def _hook_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "adventure_idea_id": row["adventure_idea_id"],
        "hook_type": row["hook_type"],
        "title": row["title"],
        "description": row["description"],
        "significance": row["significance"],
        "draft_data": json.loads(row["draft_data"] or "{}"),
        "status": row["status"],
        "promoted_record_id": row["promoted_record_id"],
        "promoted_table": row["promoted_table"],
        "quality_rating": row["quality_rating"],
        "times_used": row["times_used"],
        "created_at": row["created_at"],
    }


def _template_to_dict(row: sqlite3.Row) -> dict:
    keys = row.keys()
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "difficulty_rating": row["difficulty_rating"],
        "atmosphere": row["atmosphere"],
        "gm_plan_json": json.loads(row["gm_plan_json"] or "{}"),
        "hook_ids": json.loads(row["hook_ids"] or "[]"),
        "status": row["status"],
        "play_count": row["play_count"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "start_hex_q": row["start_hex_q"] if "start_hex_q" in keys else None,
        "start_hex_r": row["start_hex_r"] if "start_hex_r" in keys else None,
        # E7 (#422) — required NPCs/beats + player visibility.
        "required_npc_keys": json.loads(row["required_npc_keys"] or "[]") if "required_npc_keys" in keys else [],
        "required_beats": json.loads(row["required_beats"] or "[]") if "required_beats" in keys else [],
        "player_visible": row["player_visible"] if "player_visible" in keys else 1,
    }


# ── Promotion helpers ─────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[ąćęłńóśźż]", lambda m: {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
        "ó": "o", "ś": "s", "ź": "z", "ż": "z"
    }.get(m.group(), m.group()), s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")[:50]


def _ensure_unique_key(conn: sqlite3.Connection, table: str, base_key: str) -> str:
    key = base_key
    i = 2
    while True:
        row = conn.execute(f"SELECT 1 FROM {table} WHERE key = ?", (key,)).fetchone()
        if not row:
            return key
        key = f"{base_key}_{i}"
        i += 1


def _u11c_sync(conn: sqlite3.Connection, table: str, key: str) -> None:
    """U11c dual-write: re-read legacy row → upsert game_items. Non-fatal."""
    try:
        from app.services.game_items_service import sync_from_legacy
        sync_from_legacy(conn, table, key)
    except Exception:
        pass


def _existing_rowid(conn: sqlite3.Connection, table: str, key: str) -> int:
    return conn.execute(f"SELECT rowid FROM {table} WHERE key = ?", (key,)).fetchone()[0]


def _promote_hook_to_db(conn: sqlite3.Connection, hook: dict) -> tuple[str, int]:
    """Insert hook draft_data into the appropriate game config table.
    Returns (table_name, new_record_id).

    #1400: identyczna nazwa (po normalizacji) w katalogu → podpinamy istniejący
    rekord zamiast tworzyć duplikat; podobna nazwa → tworzymy, ale flagujemy
    dla detektora duplikatów (#1399)."""
    from app.services.duplicate_service import log_flagged_creation, resolve_new_label
    raw_d = hook.get("draft_data")
    if isinstance(raw_d, dict):
        d = raw_d
    elif isinstance(raw_d, str) and raw_d.strip():
        try:
            d = json.loads(raw_d)
        except Exception:
            d = {}
    else:
        d = {}
    htype = hook["hook_type"]
    now = datetime.utcnow().isoformat()

    if htype in ("weapon", "armor"):
        table = "game_config_weapons"
        label = d.get("label") or hook["title"]
        dup = resolve_new_label(conn, "weapons", label, source="forge_hook")
        if dup["action"] == "reuse":
            return table, _existing_rowid(conn, table, dup["key"])
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        cur = conn.execute(
            """INSERT INTO game_config_weapons
               (key, label, damage_die, linked_stat, allowed_classes, description,
                weapon_type, rarity, note, effect_json,
                ai_generated, approved, review_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 'permanent', ?, ?)""",
            (key, label,
             d.get("damage_die", "1d6"), d.get("linked_stat", "STR"),
             d.get("allowed_classes", "warrior"),
             d.get("description", hook.get("description", "")),
             d.get("weapon_type", "armor" if htype == "armor" else "melee"),
             _safe_int(d.get("rarity"), 1),
             d.get("note") or d.get("gm_note", ""),
             json.dumps(d["effect_json"], ensure_ascii=False) if d.get("effect_json") and isinstance(d.get("effect_json"), dict) else (d.get("effect_json") if isinstance(d.get("effect_json"), str) else None),
             now, now),
        )
        if dup["action"] == "create_flagged":
            log_flagged_creation(conn, "weapons", key, label, dup["similar_to"], source="forge_hook")
        _u11c_sync(conn, table, key)
        return table, cur.lastrowid

    elif htype == "item":
        table = "game_config_items"
        label = d.get("label") or hook["title"]
        dup = resolve_new_label(conn, "items", label, source="forge_hook")
        if dup["action"] == "reuse":
            return table, _existing_rowid(conn, table, dup["key"])
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        cur = conn.execute(
            """INSERT INTO game_config_items
               (key, label, item_type, description, value_gp, rarity, effect_json,
                ai_generated, approved, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)""",
            (key, label,
             d.get("item_type", "misc"),
             d.get("description", hook.get("description", "")),
             _safe_int(d.get("value_gp"), 0), _safe_int(d.get("rarity"), 1),
             json.dumps(d["effect_json"], ensure_ascii=False) if d.get("effect_json") and isinstance(d.get("effect_json"), dict) else (d.get("effect_json") if isinstance(d.get("effect_json"), str) else None),
             now, now),
        )
        if dup["action"] == "create_flagged":
            log_flagged_creation(conn, "items", key, label, dup["similar_to"], source="forge_hook")
        _u11c_sync(conn, table, key)
        return table, cur.lastrowid

    elif htype == "consumable":
        table = "game_config_consumables"
        label = d.get("label") or hook["title"]
        dup = resolve_new_label(conn, "consumables", label, source="forge_hook")
        if dup["action"] == "reuse":
            return table, _existing_rowid(conn, table, dup["key"])
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        cur = conn.execute(
            """INSERT INTO game_config_consumables
               (key, label, description, effect_type, base_price, rarity,
                effect_dice, effect_bonus, effect_target, ai_generated, approved, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)""",
            (key, label,
             d.get("description", hook.get("description", "")),
             d.get("effect_type", "misc"),
             _safe_int(d.get("base_price"), 0), _safe_int(d.get("rarity"), 1),
             d.get("effect_dice") or None,
             _safe_int(d.get("effect_bonus"), 0),
             d.get("effect_target", "self"),
             now, now),
        )
        if dup["action"] == "create_flagged":
            log_flagged_creation(conn, "consumables", key, label, dup["similar_to"], source="forge_hook")
        _u11c_sync(conn, table, key)
        return table, cur.lastrowid

    elif htype == "enemy":
        table = "game_config_enemies"
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        label = d.get("label") or hook["title"]
        cur = conn.execute(
            """INSERT INTO game_config_enemies
               (key, label, hp_base, ac_base, attack_bonus, damage_die, description,
                tier, damage_type, review_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'permanent', ?, ?)""",
            (key, label,
             _safe_int(d.get("hp_base"), 20), _safe_int(d.get("ac_base"), 12),
             _safe_int(d.get("attack_bonus"), 3), d.get("damage_die", "1d6"),
             d.get("description", hook.get("description", "")),
             d.get("tier", "standard"), d.get("damage_type", "physical"),
             now, now),
        )
        try:
            from app.services.world_service import _auto_populate_enemy_loot
            _auto_populate_enemy_loot(conn, key, d.get("tier", "standard"), label)
        except Exception:
            pass
        return table, cur.lastrowid

    elif htype == "npc":
        table = "npcs"
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        label = d.get("label") or hook["title"]
        existing_npc = conn.execute(
            "SELECT id FROM npcs WHERE label = ?", (label,)
        ).fetchone()
        if existing_npc:
            return "npcs", existing_npc["id"]
        description = d.get("description", hook.get("description", ""))
        personality_json = json.dumps({"description": description}, ensure_ascii=False)
        cur = conn.execute(
            """INSERT INTO npcs
               (key, label, npc_type, description, personality_json, personality_prompt,
                review_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'permanent', ?, ?)""",
            (key, label,
             d.get("npc_type", "neutral"),
             description, personality_json,
             d.get("personality_prompt", ""),
             now, now),
        )
        return table, cur.lastrowid

    elif htype == "location":
        table = "game_locations"
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        label = d.get("label") or hook["title"]
        cur = conn.execute(
            """INSERT INTO game_locations
               (key, label, description, location_type, biome,
                ai_generated, approved, review_status, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 1, 1, 'permanent', 'admin_kreator', ?, ?)""",
            (key, label,
             d.get("description", hook.get("description", "")),
             _LOC_TYPE_MAP.get(d.get("location_type", ""), "macro"),
             d.get("biome", ""),
             now, now),
        )
        return table, cur.lastrowid

    else:
        raise ValueError(f"Cannot promote hook_type='{htype}' — no target table mapping")


# ── Request models ────────────────────────────────────────────────────────────

class ForgeMessageReq(BaseModel):
    session_id: str
    message: str
    draft_override: Optional[dict] = None  # admin-edited draft to inject as context


class SaveIdeaReq(BaseModel):
    session_id: Optional[str] = None
    idea_data: Optional[dict] = None


class PatchIdeaReq(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    structured_data: Optional[dict] = None


class PatchHookReq(BaseModel):
    status: Optional[str] = None
    draft_data: Optional[dict] = None
    title: Optional[str] = None
    description: Optional[str] = None


class CreateTemplateReq(BaseModel):
    title: str
    description: str = ""
    difficulty_rating: int = 2
    atmosphere: str = ""
    gm_plan_json: dict = {}
    hook_ids: list[int] = []
    adventure_idea_id: Optional[int] = None
    # E7 (#422)
    required_npc_keys: list[str] = []
    required_beats: list[str] = []
    player_visible: bool = True


class PatchTemplateReq(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    difficulty_rating: Optional[int] = None
    atmosphere: Optional[str] = None
    gm_plan_json: Optional[dict] = None
    hook_ids: Optional[list[int]] = None
    status: Optional[str] = None
    adventure_idea_id: Optional[int] = None
    # E7 (#422)
    required_npc_keys: Optional[list[str]] = None
    required_beats: Optional[list[str]] = None
    player_visible: Optional[bool] = None


# ── Chat endpoints ────────────────────────────────────────────────────────────

@router.post("/chat/message")
def forge_chat_message(req: ForgeMessageReq, _: None = Depends(_require_admin)):
    session = _get_or_create_session(req.session_id)
    if req.draft_override:
        session["draft"] = req.draft_override
        user_content = (
            f"[Kontekst: Admin ręcznie zaktualizował szkic. Aktualny stan:\n"
            f"{json.dumps(req.draft_override, ensure_ascii=False, indent=2)}]\n\n"
            f"{req.message}"
        )
    else:
        user_content = req.message
    session["history"].append({"role": "user", "content": user_content})

    messages = [{"role": "system", "content": FORGE_SYSTEM_PROMPT}] + session["history"]
    try:
        reply = generate_chat(messages=messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    session["history"].append({"role": "assistant", "content": reply})
    draft, ready_to_save = _extract_draft(reply)
    if draft:
        session["draft"] = draft

    # Strip JSON blocks from displayed reply so chat stays readable
    display_reply = re.sub(r"```json.*?```", "", reply, flags=re.DOTALL).strip()
    # Also strip bare JSON objects that look like a draft (large objects with title/arcs/hooks)
    if draft and not display_reply:
        display_reply = "✓ Szkic zaktualizowany."
    elif draft and re.search(r"\{[^{}]{200,}\}", display_reply, re.DOTALL):
        display_reply = re.sub(r"\{[^{}]{200,}\}", "", display_reply, flags=re.DOTALL).strip()
    if not display_reply:
        display_reply = "✓ Szkic zaktualizowany." if draft else reply

    return {
        "session_id": req.session_id,
        "reply": display_reply,
        "draft": session.get("draft"),
        "ready_to_save": ready_to_save,
    }


@router.post("/chat/save")
def forge_chat_save(req: SaveIdeaReq, _: None = Depends(_require_admin)):
    idea_data = req.idea_data
    if not idea_data and req.session_id:
        session = _sessions.get(req.session_id, {})
        idea_data = session.get("draft")
    if not idea_data:
        raise HTTPException(status_code=400, detail="No idea data to save")

    conn = _get_db()
    try:
        cur = conn.execute(
            """INSERT INTO adventure_ideas
               (title, premise, tone, themes, difficulty, structured_data, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, 'draft', 'admin')""",
            (
                idea_data.get("title", "Nowy pomysł"),
                idea_data.get("premise", ""),
                json.dumps(idea_data.get("tone", []), ensure_ascii=False),
                json.dumps(idea_data.get("themes", []), ensure_ascii=False),
                idea_data.get("difficulty", "medium"),
                json.dumps(idea_data, ensure_ascii=False),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM adventure_ideas WHERE id = ?", (cur.lastrowid,)).fetchone()
        return {"ok": True, "idea": _idea_to_dict(row)}
    finally:
        conn.close()


# ── Idea endpoints ────────────────────────────────────────────────────────────

@router.get("/ideas")
def forge_list_ideas(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    _: None = Depends(_require_admin),
):
    conn = _get_db()
    try:
        q = "SELECT * FROM adventure_ideas WHERE 1=1"
        params: list = []
        if status:
            q += " AND status = ?"
            params.append(status)
        if search:
            q += " AND (title LIKE ? OR premise LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        q += " ORDER BY created_at DESC"
        rows = conn.execute(q, params).fetchall()
        return {"items": [_idea_to_dict(r) for r in rows]}
    finally:
        conn.close()


@router.get("/ideas/{idea_id}")
def forge_get_idea(idea_id: int, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM adventure_ideas WHERE id = ?", (idea_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Idea not found")
        hooks = conn.execute(
            "SELECT * FROM adventure_hooks WHERE adventure_idea_id = ? ORDER BY created_at",
            (idea_id,),
        ).fetchall()
        idea = _idea_to_dict(row)
        idea["hooks"] = [_hook_to_dict(h) for h in hooks]
        return idea
    finally:
        conn.close()


@router.patch("/ideas/{idea_id}")
def forge_patch_idea(idea_id: int, req: PatchIdeaReq, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM adventure_ideas WHERE id = ?", (idea_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Idea not found")
        updates: list[str] = []
        params: list = []
        if req.title is not None:
            updates.append("title = ?"); params.append(req.title)
        if req.status is not None:
            updates.append("status = ?"); params.append(req.status)
        if req.structured_data is not None:
            updates.append("structured_data = ?")
            params.append(json.dumps(req.structured_data, ensure_ascii=False))
        if not updates:
            return _idea_to_dict(row)
        params.append(idea_id)
        conn.execute(f"UPDATE adventure_ideas SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        updated = conn.execute("SELECT * FROM adventure_ideas WHERE id = ?", (idea_id,)).fetchone()
        return _idea_to_dict(updated)
    finally:
        conn.close()


@router.delete("/ideas/{idea_id}")
def forge_delete_idea(idea_id: int, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        conn.execute("DELETE FROM adventure_ideas WHERE id = ?", (idea_id,))
        conn.commit()
        return {"ok": True, "id": idea_id}
    finally:
        conn.close()


@router.post("/ideas/{idea_id}/extract-hooks")
def forge_extract_hooks(idea_id: int, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM adventure_ideas WHERE id = ?", (idea_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Idea not found")

        structured = json.loads(row["structured_data"] or "{}")
        prompt = (
            f"Przygoda: {json.dumps(structured, ensure_ascii=False)}\n\n"
            "Wyodrębnij wszystkie hooki z tej przygody."
        )
        messages = [
            {"role": "system", "content": EXTRACT_HOOKS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        try:
            raw = generate_chat(messages=messages)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM error: {e}")

        hooks_raw = _extract_json_array(raw)
        if not hooks_raw:
            raise HTTPException(status_code=422, detail="LLM did not return a valid hook array")

        created = []
        for h in hooks_raw:
            if not isinstance(h, dict) or not h.get("hook_type"):
                continue
            existing = conn.execute(
                "SELECT id FROM adventure_hooks WHERE adventure_idea_id=? AND title=? AND hook_type=?",
                (idea_id, h.get("title", "Hook"), h.get("hook_type", "event"))
            ).fetchone()
            if existing:
                created.append(existing["id"])
                continue
            cur = conn.execute(
                """INSERT INTO adventure_hooks
                   (adventure_idea_id, hook_type, title, description, significance, draft_data, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
                (
                    idea_id,
                    h.get("hook_type", "event"),
                    h.get("title", "Hook"),
                    h.get("description", ""),
                    h.get("significance", "minor"),
                    json.dumps(h.get("draft_data", {}), ensure_ascii=False),
                ),
            )
            created.append(cur.lastrowid)
        conn.commit()

        rows = conn.execute(
            f"SELECT * FROM adventure_hooks WHERE id IN ({','.join('?' * len(created))})",
            created,
        ).fetchall() if created else []
        return {"ok": True, "hooks_created": len(created), "hooks": [_hook_to_dict(r) for r in rows]}
    finally:
        conn.close()


# ── Hook endpoints ────────────────────────────────────────────────────────────

@router.get("/hooks")
def forge_list_hooks(
    status: Optional[str] = Query(None),
    hook_type: Optional[str] = Query(None),
    _: None = Depends(_require_admin),
):
    conn = _get_db()
    try:
        q = "SELECT * FROM adventure_hooks WHERE 1=1"
        params: list = []
        if status:
            q += " AND status = ?"
            params.append(status)
        if hook_type:
            q += " AND hook_type = ?"
            params.append(hook_type)
        q += " ORDER BY created_at DESC"
        rows = conn.execute(q, params).fetchall()
        return {"items": [_hook_to_dict(r) for r in rows]}
    finally:
        conn.close()


@router.get("/hooks/pool")
def forge_hooks_pool(_: None = Depends(_require_admin)):
    """Return approved+promoted hooks available for campaign creation."""
    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM adventure_hooks WHERE status IN ('approved', 'promoted')
               ORDER BY quality_rating DESC, times_used ASC""",
        ).fetchall()
        return {"items": [_hook_to_dict(r) for r in rows]}
    finally:
        conn.close()


@router.patch("/hooks/{hook_id}")
def forge_patch_hook(hook_id: int, req: PatchHookReq, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM adventure_hooks WHERE id = ?", (hook_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Hook not found")
        updates: list[str] = []
        params: list = []
        if req.status is not None:
            updates.append("status = ?"); params.append(req.status)
        if req.title is not None:
            updates.append("title = ?"); params.append(req.title)
        if req.description is not None:
            updates.append("description = ?"); params.append(req.description)
        if req.draft_data is not None:
            updates.append("draft_data = ?")
            params.append(json.dumps(req.draft_data, ensure_ascii=False))
        if not updates:
            return _hook_to_dict(row)
        params.append(hook_id)
        conn.execute(f"UPDATE adventure_hooks SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        updated = conn.execute("SELECT * FROM adventure_hooks WHERE id = ?", (hook_id,)).fetchone()
        return _hook_to_dict(updated)
    finally:
        conn.close()


@router.delete("/hooks/{hook_id}")
def forge_delete_hook(hook_id: int, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        row = conn.execute("SELECT id FROM adventure_hooks WHERE id = ?", (hook_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Hook not found")
        conn.execute("DELETE FROM adventure_hooks WHERE id = ?", (hook_id,))
        conn.commit()
        return {"ok": True, "deleted_id": hook_id}
    finally:
        conn.close()


@router.post("/hooks/{hook_id}/promote")
def forge_promote_hook(hook_id: int, _: None = Depends(_require_admin)):
    """Promote an approved hook to a real game DB record."""
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM adventure_hooks WHERE id = ?", (hook_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Hook not found")
        hook = _hook_to_dict(row)
        if hook["status"] not in ("approved", "pending"):
            raise HTTPException(
                status_code=400,
                detail=f"Hook must be approved before promotion (current: {hook['status']})"
            )
        if hook["hook_type"] in ("event", "theme"):
            raise HTTPException(status_code=400, detail="Event/theme hooks cannot be promoted to DB records")

        try:
            table_name, record_id = _promote_hook_to_db(conn, hook)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=409, detail=f"DB conflict: {e}")

        conn.execute(
            "UPDATE adventure_hooks SET status = 'promoted', promoted_record_id = ?, promoted_table = ? WHERE id = ?",
            (record_id, table_name, hook_id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM adventure_hooks WHERE id = ?", (hook_id,)).fetchone()
        return {
            "ok": True,
            "hook": _hook_to_dict(updated),
            "promoted_table": table_name,
            "promoted_record_id": record_id,
        }
    finally:
        conn.close()


# ── Template endpoints ────────────────────────────────────────────────────────

@router.get("/templates")
def forge_list_templates(
    status: Optional[str] = Query(None),
    _: None = Depends(_require_admin),
):
    conn = _get_db()
    try:
        q = "SELECT * FROM campaign_templates WHERE 1=1"
        params: list = []
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY created_at DESC"
        rows = conn.execute(q, params).fetchall()
        return {"items": [_template_to_dict(r) for r in rows]}
    finally:
        conn.close()


@router.get("/templates/{template_id}")
def forge_get_template(template_id: int, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT * FROM campaign_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Template not found")
        return _template_to_dict(row)
    finally:
        conn.close()


@router.post("/templates")
def forge_create_template(req: CreateTemplateReq, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        gm_plan = req.gm_plan_json
        hook_ids = req.hook_ids

        # Auto-fill from adventure_idea if provided
        if req.adventure_idea_id and not gm_plan:
            row = conn.execute(
                "SELECT * FROM adventure_ideas WHERE id = ?", (req.adventure_idea_id,)
            ).fetchone()
            if row:
                structured = json.loads(row["structured_data"] or "{}")
                arcs = {}
                for i, arc in enumerate(structured.get("arcs", []), 1):
                    arc_id = f"arc_{i}"
                    arcs[arc_id] = {
                        "id": arc_id,
                        "title": arc.get("title", f"Akt {i}"),
                        "status": "draft" if i > 1 else "active",
                        "roadmap": arc.get("description", ""),
                        "scene_goals": arc.get("scene_goals", []),
                        "hooks": {"npcs": [], "locations": []},
                        "current_scene_ordinal": 1,
                        "scene_log": [],
                        "private_notes": arc.get("private_twist", ""),
                    }
                gm_plan = {
                    "schema_version": 2,
                    "arcs": arcs,
                    "active_arc_id": "arc_1" if arcs else None,
                    "engine_private": {
                        "secret_predisposition_hint": structured.get("gm_private", ""),
                        "hidden_twist": "",
                        "contingency": "",
                    },
                }
                if not hook_ids:
                    hooks = conn.execute(
                        "SELECT id FROM adventure_hooks WHERE adventure_idea_id = ? AND status IN ('approved','promoted')",
                        (req.adventure_idea_id,),
                    ).fetchall()
                    hook_ids = [h["id"] for h in hooks]

        # #1014 — derive beat_key + preserve `optional` for UI-authored beats.
        gm_plan = normalize_plan_beats(gm_plan)

        cur = conn.execute(
            """INSERT INTO campaign_templates
               (title, description, difficulty_rating, atmosphere, gm_plan_json, hook_ids, status, created_by, adventure_idea_id,
                required_npc_keys, required_beats, player_visible)
               VALUES (?, ?, ?, ?, ?, ?, 'draft', 'admin', ?, ?, ?, ?)""",
            (
                req.title, req.description, req.difficulty_rating, req.atmosphere,
                json.dumps(gm_plan, ensure_ascii=False),
                json.dumps(hook_ids, ensure_ascii=False),
                req.adventure_idea_id,
                json.dumps(req.required_npc_keys, ensure_ascii=False),
                json.dumps(req.required_beats, ensure_ascii=False),
                1 if req.player_visible else 0,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM campaign_templates WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _template_to_dict(row)
    finally:
        conn.close()


def _plan_beat_keys(plan: dict) -> set[str]:
    """Collect every beat_key present in a gm_plan (arcs[].key_beats[] or acts[].key_beats[])."""
    keys: set[str] = set()
    containers = []
    arcs = plan.get("arcs")
    if isinstance(arcs, dict):
        containers.extend(arcs.values())
    elif isinstance(arcs, list):
        containers.extend(arcs)
    if isinstance(plan.get("acts"), list):
        containers.extend(plan["acts"])
    for c in containers:
        if not isinstance(c, dict):
            continue
        for b in (c.get("key_beats") or []):
            if isinstance(b, dict) and b.get("beat_key"):
                keys.add(str(b["beat_key"]))
            elif isinstance(b, str):
                keys.add(b)
    return keys


def validate_template_publish(template_id: int, conn: sqlite3.Connection) -> dict:
    """E10 (#425) — Verify a template is publishable.

    Checks that every required NPC key exists in the npcs table and every
    required beat exists in the template's gm_plan. Returns
    {ok, missing_npcs, missing_beats}.
    """
    row = conn.execute(
        "SELECT required_npc_keys, required_beats, gm_plan_json FROM campaign_templates WHERE id = ?",
        (template_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")

    def _load(v):
        try:
            return json.loads(v or "[]")
        except Exception:
            return []

    required_npcs = _load(row["required_npc_keys"])
    required_beats = _load(row["required_beats"])
    try:
        plan = json.loads(row["gm_plan_json"] or "{}")
    except Exception:
        plan = {}

    missing_npcs = []
    for key in required_npcs:
        hit = conn.execute(
            "SELECT 1 FROM npcs WHERE key = ? AND is_active = 1", (key,)
        ).fetchone()
        if not hit:
            missing_npcs.append(key)

    plan_beats = _plan_beat_keys(plan)
    missing_beats = [b for b in required_beats if b not in plan_beats]

    # #1212 — settlement structure sanity: subs must reference a declared hub.
    # Only enforced when the plan uses scale at all (legacy flat plans skip).
    structure_errors: list[str] = []
    locs = [l for l in (plan.get("key_locations") or []) if isinstance(l, dict)]
    if any(l.get("scale") for l in locs):
        hub_keys = {str(l.get("key")) for l in locs if l.get("scale") == "hub" and l.get("key")}
        subs = [l for l in locs if l.get("scale") == "sub"]
        if subs and not hub_keys:
            structure_errors.append("sublokacje bez zadeklarowanego huba (scale:'hub')")
        if len(hub_keys) > 1:
            structure_errors.append("więcej niż jeden hub w key_locations")
        for s in subs:
            p = s.get("parent")
            if p and str(p) not in hub_keys:
                structure_errors.append(
                    f"sub '{s.get('key')}' wskazuje parent '{p}' spoza hubów"
                )

    return {
        "ok": not missing_npcs and not missing_beats and not structure_errors,
        "missing_npcs": missing_npcs,
        "missing_beats": missing_beats,
        "structure_errors": structure_errors,
    }


class ValidatePlanReq(BaseModel):
    gm_plan_json: dict = {}


@router.post("/validate-plan")
def forge_validate_plan(req: ValidatePlanReq, _: None = Depends(_require_admin)):
    """#1060 — Standalone plan validator. Returns structured issues for Forge UI pre-publish feedback."""
    from app.services.campaign_plan_runtime import validate_gm_plan
    return validate_gm_plan(req.gm_plan_json)


@router.get("/templates/{template_id}/validate-publish")
def forge_validate_publish(template_id: int, _: None = Depends(_require_admin)):
    """#1153 — full publish-gate preflight for the Forge validation panel.

    Mirrors every check the PATCH status=published gate enforces (required NPCs/beats
    + winnable plan), so the panel can never claim "gotowy do publikacji" while the
    Opublikuj button would still 422 (validate-plan alone checks only plan structure).
    """
    conn = _get_db()
    try:
        vres = validate_template_publish(template_id, conn)
        row = conn.execute(
            "SELECT gm_plan_json FROM campaign_templates WHERE id = ?", (template_id,)
        ).fetchone()
        try:
            plan = json.loads((row["gm_plan_json"] if row else None) or "{}")
        except Exception:
            plan = {}
        from app.services.campaign_plan_runtime import validate_winnable_plan
        wres = validate_winnable_plan(plan)
        return {
            "ok": bool(vres["ok"] and wres["ok"]),
            "missing_npcs": vres["missing_npcs"],
            "missing_beats": vres["missing_beats"],
            "structure_errors": vres.get("structure_errors", []),
            "plan_beat_keys": sorted(_plan_beat_keys(plan)),
            "winnable": wres,
        }
    finally:
        conn.close()


@router.patch("/templates/{template_id}")
def forge_patch_template(template_id: int, req: PatchTemplateReq, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM campaign_templates WHERE id = ?", (template_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Template not found")
        # E12 (#427) — workflow guard: only draft → review → published (+ revert) allowed.
        if req.status is not None and req.status not in ("draft", "review", "published"):
            raise HTTPException(status_code=422, detail={
                "error": "invalid_status",
                "message": f"Nieprawidłowy status '{req.status}'. Dozwolone: draft, review, published.",
                "allowed": ["draft", "review", "published"],
            })
        # E10 (#425) — block publishing when required NPCs/beats are missing.
        if req.status == "published":
            # Apply any required_*/plan changes coming in the same request first, so
            # validation runs against the about-to-be-saved values.
            if req.required_npc_keys is not None or req.required_beats is not None or req.gm_plan_json is not None:
                if req.required_npc_keys is not None:
                    conn.execute("UPDATE campaign_templates SET required_npc_keys = ? WHERE id = ?",
                                 (json.dumps(req.required_npc_keys, ensure_ascii=False), template_id))
                if req.required_beats is not None:
                    conn.execute("UPDATE campaign_templates SET required_beats = ? WHERE id = ?",
                                 (json.dumps(req.required_beats, ensure_ascii=False), template_id))
                if req.gm_plan_json is not None:
                    conn.execute("UPDATE campaign_templates SET gm_plan_json = ? WHERE id = ?",
                                 (json.dumps(normalize_plan_beats(req.gm_plan_json), ensure_ascii=False), template_id))
                conn.commit()
            vres = validate_template_publish(template_id, conn)
            if not vres["ok"]:
                raise HTTPException(status_code=422, detail={
                    "error": "template_incomplete",
                    "message": "Nie można opublikować — brakuje wymaganych elementów.",
                    "missing_npcs": vres["missing_npcs"],
                    "missing_beats": vres["missing_beats"],
                    "structure_errors": vres.get("structure_errors", []),
                })
            # #1020 — hard "winnable premade" gate: endings(primary) + no critical
            # orphan + ≥1 closable critical beat/act, so every published premade is
            # playable to victory (#1009) without manual edits.
            from app.services.campaign_plan_runtime import validate_winnable_plan
            prow = conn.execute(
                "SELECT gm_plan_json FROM campaign_templates WHERE id = ?", (template_id,)
            ).fetchone()
            try:
                _plan = json.loads((prow["gm_plan_json"] if prow else None) or "{}")
            except Exception:
                _plan = {}
            wres = validate_winnable_plan(_plan)
            if not wres["ok"]:
                raise HTTPException(status_code=422, detail={
                    "error": "template_not_winnable",
                    "message": "Nie można opublikować — szablon nie jest grywalny do końca (winnable). "
                               + " ".join(wres["errors"]),
                    "errors": wres["errors"],
                    "orphan_beats": wres["orphan_beats"],
                    "acts_without_closable_beat": wres["acts_without_closable_beat"],
                })
            # #1094 — auto-allocate start hex if not set, so launch never falls back to a random/occupied hex.
            cur_hex = conn.execute(
                "SELECT start_hex_q FROM campaign_templates WHERE id = ?", (template_id,)
            ).fetchone()
            if cur_hex and cur_hex["start_hex_q"] is None:
                best_hex = _allocate_hex_for_template(conn, template_id)
                if best_hex is None:
                    raise HTTPException(status_code=422, detail={
                        "error": "no_free_hex",
                        "message": "Nie można opublikować — brak wolnych hexów na mapie świata. "
                                   "Wszystkie dostępne hexy są zajęte przez lokacje lub oznaczone jako POI. "
                                   "Zwolnij hex lub ręcznie przydziel teren przed publikacją.",
                    })
                conn.execute(
                    "UPDATE campaign_templates SET start_hex_q = ?, start_hex_r = ? WHERE id = ?",
                    (best_hex["q"], best_hex["r"], template_id),
                )
                conn.commit()
            # #1206 — materialize the plan's start location ON the start hex, so
            # resolve_starting_hex anchors the session there (no forest-drift).
            try:
                from app.services.template_start_anchor import ensure_template_locations
                ensure_template_locations(conn, template_id)
            except Exception as _tsl_err:
                logger.warning("template_start_location_error", error=str(_tsl_err))
        updates: list[str] = []
        params: list = []
        for field, val in [
            ("title", req.title), ("description", req.description),
            ("difficulty_rating", req.difficulty_rating), ("atmosphere", req.atmosphere),
            ("status", req.status),
        ]:
            if val is not None:
                updates.append(f"{field} = ?"); params.append(val)
        if req.gm_plan_json is not None:
            updates.append("gm_plan_json = ?")
            # #1014 — derive beat_key + preserve `optional` for UI-authored beats.
            params.append(json.dumps(normalize_plan_beats(req.gm_plan_json), ensure_ascii=False))
        if req.hook_ids is not None:
            updates.append("hook_ids = ?")
            params.append(json.dumps(req.hook_ids, ensure_ascii=False))
        if req.adventure_idea_id is not None:
            updates.append("adventure_idea_id = ?")
            params.append(req.adventure_idea_id)
        # E7 (#422)
        if req.required_npc_keys is not None:
            updates.append("required_npc_keys = ?")
            params.append(json.dumps(req.required_npc_keys, ensure_ascii=False))
        if req.required_beats is not None:
            updates.append("required_beats = ?")
            params.append(json.dumps(req.required_beats, ensure_ascii=False))
        if req.player_visible is not None:
            updates.append("player_visible = ?")
            params.append(1 if req.player_visible else 0)
        if not updates:
            return _template_to_dict(row)
        params.append(template_id)
        conn.execute(f"UPDATE campaign_templates SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        updated = conn.execute("SELECT * FROM campaign_templates WHERE id = ?", (template_id,)).fetchone()
        return _template_to_dict(updated)
    finally:
        conn.close()


@router.delete("/templates/{template_id}")
def forge_delete_template(template_id: int, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        conn.execute("DELETE FROM campaign_templates WHERE id = ?", (template_id,))
        conn.commit()
        return {"ok": True, "id": template_id}
    finally:
        conn.close()


# ── Auto-create forge enemies for a template (#1085) ──────────────────────────

# HP and AC ranges per tier — derived from DB analysis of permanent enemies.
# difficulty factor: 0.6 at diff=1, stepping +0.1 each level, 1.0 at diff=5.
_TIER_HP_RANGE: dict[str, tuple[int, int]] = {
    "weak":     (6,  15),
    "standard": (8,  28),
    "elite":    (30, 60),
    "boss":     (50, 100),
}
_TIER_AC_RANGE: dict[str, tuple[int, int]] = {
    "weak":     (8,  11),
    "standard": (10, 14),
    "elite":    (12, 16),
    "boss":     (14, 18),
}


def _auto_fill_plan_fields(
    conn: "sqlite3.Connection",
    tpl_id: int,
    tpl: dict,
    idea: "dict | None",
    plan_public: dict,
) -> dict:
    """Auto-fill required_npc_keys, required_beats, and atmosphere on template after plan gen.

    Only fills when the field is currently empty (preserves manual edits).
    Returns dict with auto_filled_npc_keys, auto_filled_beat_keys, auto_filled_atmosphere.
    """
    # sqlite3.Row doesn't support .get() — normalize to plain dicts (#1081)
    if hasattr(tpl, "keys"):
        tpl = dict(tpl)
    if idea is not None and hasattr(idea, "keys"):
        idea = dict(idea)
    try:
        existing_npc = json.loads(tpl["required_npc_keys"] or "[]") if tpl["required_npc_keys"] else []
        existing_beats = json.loads(tpl["required_beats"] or "[]") if tpl["required_beats"] else []
    except Exception:
        existing_npc, existing_beats = [], []

    auto_npc_keys: list[str] = []
    auto_beat_keys: list[str] = []
    auto_filled_atmosphere: str = ""

    if not existing_npc:
        auto_npc_keys = [npc["key"] for npc in plan_public.get("key_npcs", []) if npc.get("key")]
        if auto_npc_keys:
            conn.execute(
                "UPDATE campaign_templates SET required_npc_keys = ? WHERE id = ?",
                (json.dumps(auto_npc_keys, ensure_ascii=False), tpl_id),
            )

    if not existing_beats:
        auto_beat_keys = [
            beat["beat_key"]
            for act in plan_public.get("acts", [])
            for beat in act.get("key_beats", [])
            if beat.get("beat_key") and not beat.get("optional", False)
        ]
        if auto_beat_keys:
            conn.execute(
                "UPDATE campaign_templates SET required_beats = ? WHERE id = ?",
                (json.dumps(auto_beat_keys, ensure_ascii=False), tpl_id),
            )

    # Auto-fill atmosphere from idea tone if template has none
    if idea and not (tpl.get("atmosphere") or "").strip():
        try:
            idea_tone = json.loads(idea.get("tone") or "[]")
        except Exception:
            idea_tone = []
        if idea_tone:
            auto_filled_atmosphere = ", ".join(idea_tone)
            conn.execute(
                "UPDATE campaign_templates SET atmosphere = ? WHERE id = ?",
                (auto_filled_atmosphere, tpl_id),
            )

    return {
        "auto_filled_npc_keys": auto_npc_keys,
        "auto_filled_beat_keys": auto_beat_keys,
        "auto_filled_atmosphere": auto_filled_atmosphere,
    }


def _clamp_enemy_stats(hp: int, ac: int, tier: str, difficulty: int) -> tuple[int, int]:
    """Clamp LLM-generated HP/AC to tier + difficulty-appropriate ranges.

    Prevents LLM hallucinations (e.g. HP=100 for a standard enemy in a diff=1 campaign).
    difficulty 1 → 60% of tier max; difficulty 5 → 100%.
    """
    factor = 0.6 + max(0, min(4, difficulty - 1)) * 0.1

    hp_min, hp_max = _TIER_HP_RANGE.get(tier, (8, 28))
    scaled_hp_max = max(hp_min, int(hp_max * factor))
    clamped_hp = max(hp_min, min(hp, scaled_hp_max))

    ac_min, ac_max = _TIER_AC_RANGE.get(tier, (10, 14))
    scaled_ac_max = max(ac_min, int(ac_max * factor))
    clamped_ac = max(ac_min, min(ac, scaled_ac_max))

    return clamped_hp, clamped_ac


def _auto_create_forge_enemies(
    conn: sqlite3.Connection,
    template_id: int,
    enemies: list[dict],
    difficulty: int = 3,
) -> list[dict]:
    """Create game_config_enemies rows from plan key_enemies with review_status='pending'.

    HP/AC are clamped to tier+difficulty ranges to prevent LLM hallucinations.
    Returns list of {key, name} for each created enemy.
    """
    now = datetime.now(timezone.utc).isoformat()
    created: list[dict] = []
    for e in enemies:
        base_key = e.get("key") or _slugify(e.get("name") or "enemy")
        key = _ensure_unique_key(conn, "game_config_enemies", base_key)
        tier = e.get("tier") or "standard"
        raw_hp = int(e.get("hp_base") or 20)
        raw_ac = int(e.get("ac_base") or 12)
        hp, ac = _clamp_enemy_stats(raw_hp, raw_ac, tier, difficulty)
        try:
            conn.execute(
                """INSERT INTO game_config_enemies
                   (key, label, hp_base, ac_base, attack_bonus, damage_die,
                    description, note, tier, damage_type,
                    review_status, created_by, template_id,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, 'physical',
                           'pending', 'forge', ?, ?, ?)""",
                (
                    key,
                    e.get("name") or key,
                    hp,
                    ac,
                    e.get("damage_die") or "1d6",
                    e.get("description") or "",
                    e.get("note") or "",
                    tier,
                    template_id,
                    now,
                    now,
                ),
            )
            try:
                from app.services.world_service import _auto_populate_enemy_loot
                _auto_populate_enemy_loot(conn, key, tier, e.get("name") or key)
            except Exception:
                pass
            created.append({"key": key, "name": e.get("name") or key})
        except Exception:
            pass
    return created


# ── Auto-create NPC stubs for a template (#1087) ──────────────────────────────

def _auto_create_forge_npcs(
    conn: sqlite3.Connection,
    template_id: int,
    npcs: list[dict],
) -> list[dict]:
    """Create npcs rows from plan key_npcs with review_status='pending'.

    Idempotent: skips any key that already exists in npcs.
    Returns list of {key, name} for each created NPC.
    """
    now = datetime.now(timezone.utc).isoformat()
    created: list[dict] = []
    for n in npcs:
        key = n.get("key") or _slugify(n.get("name") or "npc")
        name = n.get("name") or key
        description = n.get("role") or n.get("description") or ""
        try:
            conn.execute(
                """INSERT OR IGNORE INTO npcs
                   (key, label, npc_type, description, personality_json,
                    keyword_triggers, review_status, is_active,
                    created_at, updated_at)
                   VALUES (?, ?, 'neutral', ?, '{}', '[]', 'pending', 1, ?, ?)""",
                (key, name, description, now, now),
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                created.append({"key": key, "name": name})
        except Exception:
            pass
    return created


# ── Auto-create location stubs for a template (#1092) ─────────────────────────

def _auto_create_forge_locations(
    conn: sqlite3.Connection,
    template_id: int,
    locations: list[dict],
) -> list[dict]:
    """Create game_locations rows from plan key_locations with review_status='pending_review'.

    Idempotent: skips any key that already exists in game_locations.
    Returns list of {key, name} for each created location.
    """
    now = datetime.now(timezone.utc).isoformat()
    created: list[dict] = []
    hub_key = next(
        (str(l.get("key")) for l in locations
         if isinstance(l, dict) and l.get("scale") == "hub" and l.get("key")),
        None,
    )
    for loc in locations:
        key = loc.get("key") or _slugify(loc.get("name") or "location")
        name = loc.get("name") or key
        description = loc.get("description") or loc.get("role") or ""
        # #1212 — settlement structure: sub-locations join the FAZA ML local map
        is_sub = loc.get("scale") == "sub" and (loc.get("parent") or hub_key)
        loc_type = "sub" if is_sub else "macro"
        parent_key = (loc.get("parent") or hub_key) if is_sub else None
        try:
            conn.execute(
                """INSERT OR IGNORE INTO game_locations
                   (key, label, description, location_type, parent_key,
                    review_status, is_active, ai_generated,
                    created_by, source_campaign_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'pending_review', 1, 1, 'forge', ?, ?, ?)""",
                (key, name, description, loc_type, parent_key, template_id, now, now),
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                created.append({"key": key, "name": name})
        except Exception:
            pass
    return created


# ── Auto-assign reward items for a template ────────────────────────────────────

def _auto_assign_reward_items(
    conn: sqlite3.Connection,
    template_id: int,
    difficulty_rating: int,
) -> list[dict]:
    """#1084 — pull 1 weapon + 1 item + 1 consumable from global pool matching
    difficulty tier and insert as hidden template-scoped reward items.
    Returns [{category, key, name}] for each assigned item."""
    if difficulty_rating <= 2:
        rarity_min, rarity_max = 1, 2
    elif difficulty_rating <= 4:
        rarity_min, rarity_max = 3, 3
    else:
        rarity_min, rarity_max = 4, 99

    now = datetime.utcnow().isoformat()
    assigned: list[dict] = []

    def _unique_key(table: str, base: str) -> str:
        key, i = base, 2
        while conn.execute(f"SELECT 1 FROM {table} WHERE key = ?", (key,)).fetchone():
            key = f"{base}_{i}"; i += 1
        return key

    weapon = conn.execute(
        "SELECT key, label, damage_die, weapon_type, linked_stat, allowed_classes, rarity, description, note "
        "FROM game_config_weapons WHERE template_id IS NULL AND rarity BETWEEN ? AND ? "
        "AND is_active=1 AND approved=1 ORDER BY RANDOM() LIMIT 1",
        (rarity_min, rarity_max),
    ).fetchone()
    if weapon:
        new_key = _unique_key("game_config_weapons", f"tpl{template_id}_{weapon['key']}")
        conn.execute(
            "INSERT INTO game_config_weapons "
            "(key, label, damage_die, weapon_type, linked_stat, allowed_classes, rarity, description, note, "
            "template_id, hidden, ai_generated, approved, review_status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 1, 'permanent', ?, ?)",
            (
                new_key, weapon["label"], weapon["damage_die"], weapon["weapon_type"],
                weapon["linked_stat"], weapon["allowed_classes"], weapon["rarity"],
                weapon["description"], weapon["note"],
                template_id, now, now,
            ),
        )
        assigned.append({"category": "weapon", "key": new_key, "name": weapon["label"]})

    item = conn.execute(
        "SELECT key, label, item_type, value_gp, rarity, description "
        "FROM game_config_items WHERE template_id IS NULL AND rarity BETWEEN ? AND ? "
        "AND is_active=1 AND approved=1 AND item_type != 'armor' ORDER BY RANDOM() LIMIT 1",
        (rarity_min, rarity_max),
    ).fetchone()
    if item:
        new_key = _unique_key("game_config_items", f"tpl{template_id}_{item['key']}")
        conn.execute(
            "INSERT INTO game_config_items "
            "(key, label, item_type, value_gp, rarity, description, "
            "template_id, hidden, ai_generated, approved, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, 1, ?, ?)",
            (
                new_key, item["label"], item["item_type"], item["value_gp"] or 0,
                item["rarity"], item["description"],
                template_id, now, now,
            ),
        )
        assigned.append({"category": "item", "key": new_key, "name": item["label"]})

    consumable = conn.execute(
        "SELECT key, label, effect_type, effect_dice, effect_bonus, effect_target, base_price, rarity, description "
        "FROM game_config_consumables WHERE template_id IS NULL AND rarity BETWEEN ? AND ? "
        "AND is_active=1 AND approved=1 ORDER BY RANDOM() LIMIT 1",
        (rarity_min, rarity_max),
    ).fetchone()
    if consumable:
        new_key = _unique_key("game_config_consumables", f"tpl{template_id}_{consumable['key']}")
        conn.execute(
            "INSERT INTO game_config_consumables "
            "(key, label, effect_type, effect_dice, effect_bonus, effect_target, base_price, rarity, description, "
            "template_id, hidden, ai_generated, approved, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 1, ?, ?)",
            (
                new_key, consumable["label"], consumable["effect_type"] or "misc",
                consumable["effect_dice"], consumable["effect_bonus"] or 0,
                consumable["effect_target"] or "self", consumable["base_price"] or 0,
                consumable["rarity"], consumable["description"],
                template_id, now, now,
            ),
        )
        assigned.append({"category": "consumable", "key": new_key, "name": consumable["label"]})

    return assigned


# ── #1301 Reward spine: budget → bespoke signatures + pool notable/minor ───────

def _compute_reward_budget(act_count: int, difficulty_rating: int) -> dict:
    """Reward budget scaled to campaign scope. All STARTING values (Numbers Policy):
    a long/hard campaign earns more and higher-rarity loot than a short one-shot.
    Engine floor — the LLM designs within it, the engine tops up if it undershoots."""
    ac = max(1, int(act_count or 1))
    diff = max(1, min(5, int(difficulty_rating or 3)))
    if ac <= 2:
        rarity_ceiling = 3
    elif ac <= 4:
        rarity_ceiling = 4
    else:
        rarity_ceiling = 5
    if diff >= 4:
        rarity_ceiling = min(5, rarity_ceiling + 1)
    return {
        "signature": 1,
        "notable": max(1, ac - 1),
        "minor": ac // 2,
        "rarity_ceiling": rarity_ceiling,
    }


# Constrained vocabulary → safe weapon effect_json. LLM writes prose in
# `mechanical_effect`; we never trust it to emit raw effect_json (balance + validity).
_STAT_KEYWORDS = [
    ("STR", ("sił", "krzep", "str")),
    ("DEX", ("zręcz", "zwinn", "dex")),
    ("CON", ("kondycj", "wytrzym", "con")),
    ("INT", ("intelig", "wied", "int")),
    ("WIS", ("mądro", "spost", "wis")),
    ("CHA", ("charyzm", "urok", "cha")),
    ("LCK", ("szczęś", "fart", "luck")),
]

# #1302: prose keyword → skill key (game_config_skills.key). Item relics can GRANT
# a skill from nothing (magic lockpick → lockpick), even if the hero never bought
# it. First match wins. Keys must match real game_config_skills.key values.
_SKILL_KEYWORDS = [
    ("lockpick", ("wytrych", "zamk", "kłódk", "otwiera zam", "złodziejsk")),
    ("stealth", ("skrad", "ukryci", "cień", "niewidzial", "cichociem", "bezszelest")),
    ("persuasion", ("perswa", "przekon", "namow", "dyplomac", "krasomów")),
    ("deception", ("oszust", "blef", "kłamstw", "podstęp", "iluzj")),
    ("intimidation", ("zastrasz", "groźb", "onieśmiel", "postrach", "trwog")),
    ("awareness", ("spostrzeg", "czujn", "uważn", "wyczul")),
    ("investigation", ("śledztw", "dochodzeni", "badani", "poszlak")),
    ("medicine", ("lecz", "medyc", "uzdraw", "opatr", "zielarstw")),
    ("survival", ("przetrwani", "obóz", "puszcz", "dzicz")),
    ("tracking", ("tropi", "trop", "ślad", "pościg")),
    ("pickpocket", ("kieszonk", "zwędz")),
    ("athletics", ("atletyk", "siłow wysił", "krzepa")),
    ("acrobatics", ("akrobac", "salto", "balans")),
    ("lore", ("erudycj", "księg wiedz", "uczonoś")),
    ("arcana", ("arkan", "magiczn wiedz")),
]


def _match_skill_effect(txt: str, rarity: int) -> "dict | None":
    """First skill keyword hit → static_skill_modifier effect (or None)."""
    for skill, keys in _SKILL_KEYWORDS:
        if any(k in txt for k in keys):
            return {"type": "static_skill_modifier", "skill": skill, "value": 1 if rarity < 5 else 2}
    return None


def _build_signature_effect_json(mechanical_effect: str, rarity: int, category: str) -> "str | None":
    """Map a signature's prose effect to a valid effect_json.

    #1302: item relics now carry a real PASSIVE hook too (static_stat_modifier /
    ac_bonus), consumed by equipment_effects_service when the relic is equipped —
    stats/AC work in combat AND out of combat. Weapons keep their full combat
    vocabulary (damage_bonus/heal_on_hit/ac_bonus/static_stat_modifier). Consumables
    stay effect-less here (returns None). The stat keyword mapper is shared."""
    txt = (mechanical_effect or "").lower()
    r = max(4, min(5, int(rarity or 4)))
    effects: list[dict] = []

    if category == "item":
        # Passive relic: stats + AC + skills (not a weapon → no damage/heal hooks).
        for stat, keys in _STAT_KEYWORDS:
            if any(k in txt for k in keys):
                effects.append({"type": "static_stat_modifier", "stat": stat, "value": 1 if r < 5 else 2})
                break
        _sk = _match_skill_effect(txt, r)  # #1302: relikt może NADAĆ umiejętność
        if _sk:
            effects.append(_sk)
        if any(k in txt for k in ("pancerz", "obron", "tarcz", "armor", " ac", "ochron")):
            effects.append({"type": "ac_bonus", "value": 1 if r < 5 else 2})
        if not effects:
            # Guarantee a signature relic is mechanically special even if prose was vague.
            effects.append({"type": "ac_bonus", "value": 1 if r < 5 else 2})
        return json.dumps({"schema_version": 1, "effects": effects}, ensure_ascii=False)

    if category != "weapon":
        return None

    if any(k in txt for k in ("obraże", "dmg", "damage", "ostrz", "cios", "rani")):
        effects.append({"type": "damage_bonus", "value": r - 2})  # r4→+2, r5→+3
    if any(k in txt for k in ("wysysa", "życia", "lifesteal", "wampir", "leczy", "krew")):
        effects.append({"type": "heal_on_hit", "value": 1 if r < 5 else 2})
    if any(k in txt for k in ("pancerz", "obron", "tarcz", "armor", " ac")):
        effects.append({"type": "ac_bonus", "value": 1 if r < 5 else 2})
    for stat, keys in _STAT_KEYWORDS:
        if any(k in txt for k in keys):
            effects.append({"type": "static_stat_modifier", "stat": stat, "value": 1})
            break
    _sk = _match_skill_effect(txt, r)  # #1302: broń-relikt może też nadać umiejętność
    if _sk:
        effects.append(_sk)
    if not effects:
        # Guarantee a signature weapon is mechanically special even if the prose was vague.
        effects.append({"type": "damage_bonus", "value": r - 2})
    return json.dumps({"schema_version": 1, "effects": effects}, ensure_ascii=False)


def _materialize_plan_rewards(
    conn: sqlite3.Connection,
    template_id: int,
    plan_public: dict,
    difficulty_rating: int,
    act_count: int,
) -> dict:
    """#1301 — turn plan.rewards[] into real template-scoped game rows and mutate
    plan_public in place so each reward carries `granted_key` (→ runtime grant) and
    each linked beat can resolve its reward. Signatures → bespoke PENDING uniques
    (rarity ≥4, real effect_json). Notable/minor → pool clones by tier. Falls back to
    pool draws when the LLM under-delivers vs the budget floor."""
    budget = _compute_reward_budget(act_count, difficulty_rating)
    now = datetime.utcnow().isoformat()
    rewards = plan_public.get("rewards") or []
    if not isinstance(rewards, list):
        rewards = []
        plan_public["rewards"] = rewards

    def _uniq(table: str, base: str) -> str:
        key, i = base, 2
        while conn.execute(f"SELECT 1 FROM {table} WHERE key = ?", (key,)).fetchone():
            key = f"{base}_{i}"; i += 1
        return key

    def _pool_clone(category: str, rmin: int, rmax: int, label_hint: str | None) -> "tuple[str,str] | None":
        """Clone one random pool row of `category` in [rmin,rmax] as a hidden approved
        template item. Returns (granted_key, label) or None when the pool is empty."""
        if category == "weapon":
            row = conn.execute(
                "SELECT key,label,damage_die,weapon_type,linked_stat,allowed_classes,rarity,description,note "
                "FROM game_config_weapons WHERE template_id IS NULL AND rarity BETWEEN ? AND ? "
                "AND is_active=1 AND approved=1 ORDER BY RANDOM() LIMIT 1", (rmin, rmax)).fetchone()
            if not row:
                return None
            nk = _uniq("game_config_weapons", f"tpl{template_id}_{row['key']}")
            conn.execute(
                "INSERT INTO game_config_weapons (key,label,damage_die,weapon_type,linked_stat,allowed_classes,"
                "rarity,description,note,template_id,hidden,ai_generated,approved,review_status,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,1,0,1,'permanent',?,?)",
                (nk, row["label"], row["damage_die"], row["weapon_type"], row["linked_stat"],
                 row["allowed_classes"], row["rarity"], row["description"], row["note"], template_id, now, now))
            return nk, row["label"]
        if category == "consumable":
            row = conn.execute(
                "SELECT key,label,effect_type,effect_dice,effect_bonus,effect_target,base_price,rarity,description "
                "FROM game_config_consumables WHERE template_id IS NULL AND rarity BETWEEN ? AND ? "
                "AND is_active=1 AND approved=1 ORDER BY RANDOM() LIMIT 1", (rmin, rmax)).fetchone()
            if not row:
                return None
            nk = _uniq("game_config_consumables", f"tpl{template_id}_{row['key']}")
            conn.execute(
                "INSERT INTO game_config_consumables (key,label,effect_type,effect_dice,effect_bonus,effect_target,"
                "base_price,rarity,description,template_id,hidden,ai_generated,approved,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,1,0,1,?,?)",
                (nk, row["label"], row["effect_type"] or "misc", row["effect_dice"], row["effect_bonus"] or 0,
                 row["effect_target"] or "self", row["base_price"] or 0, row["rarity"], row["description"],
                 template_id, now, now))
            return nk, row["label"]
        # item
        row = conn.execute(
            "SELECT key,label,item_type,value_gp,rarity,description "
            "FROM game_config_items WHERE template_id IS NULL AND rarity BETWEEN ? AND ? "
            "AND is_active=1 AND approved=1 AND item_type != 'armor' ORDER BY RANDOM() LIMIT 1", (rmin, rmax)).fetchone()
        if not row:
            return None
        nk = _uniq("game_config_items", f"tpl{template_id}_{row['key']}")
        conn.execute(
            "INSERT INTO game_config_items (key,label,item_type,value_gp,rarity,description,"
            "template_id,hidden,ai_generated,approved,created_at,updated_at) VALUES (?,?,?,?,?,?,?,1,0,1,?,?)",
            (nk, row["label"], row["item_type"], row["value_gp"] or 0, row["rarity"], row["description"],
             template_id, now, now))
        return nk, row["label"]

    def _create_signature(rw: dict) -> "str | None":
        """Create a bespoke PENDING unique from the plan reward. rarity clamped ≥4."""
        category = (rw.get("category") or "weapon").lower()
        if category not in ("weapon", "item", "consumable"):
            category = "weapon"
        label = (rw.get("label") or "Relikt").strip()
        rarity = max(4, min(5, int(budget["rarity_ceiling"])))
        desc = (rw.get("story_hook") or rw.get("mechanical_effect") or "").strip()
        note = (rw.get("mechanical_effect") or "").strip()
        base = _slugify(rw.get("key") or label)
        if category == "weapon":
            nk = _uniq("game_config_weapons", f"tpl{template_id}_{base}")
            efx = _build_signature_effect_json(note, rarity, "weapon")
            conn.execute(
                "INSERT INTO game_config_weapons (key,label,damage_die,weapon_type,linked_stat,allowed_classes,"
                "rarity,description,note,effect_json,template_id,hidden,ai_generated,approved,review_status,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,0,1,0,'pending',?,?)",
                (nk, label, "1d8" if rarity < 5 else "1d10", "melee", "STR", "warrior,rogue,scholar",
                 rarity, desc, note, efx, template_id, now, now))
            return nk
        if category == "consumable":
            # Consumables have no review_status column → no pending queue; ship functional.
            nk = _uniq("game_config_consumables", f"tpl{template_id}_{base}")
            conn.execute(
                "INSERT INTO game_config_consumables (key,label,effect_type,effect_dice,effect_bonus,effect_target,"
                "base_price,rarity,description,template_id,hidden,ai_generated,approved,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,1,1,1,?,?)",
                (nk, label, "heal_hp", "2d6" if rarity < 5 else "3d6", 0, "self", 0, rarity, desc,
                 template_id, now, now))
            return nk
        # #1302: item signature carries a passive effect_json (static_stat_modifier/ac_bonus)
        # so an equipped relic is mechanically alive, not just flavour.
        nk = _uniq("game_config_items", f"tpl{template_id}_{base}")
        efx = _build_signature_effect_json(note, rarity, "item")
        conn.execute(
            "INSERT INTO game_config_items (key,label,item_type,value_gp,rarity,description,note,effect_json,"
            "template_id,hidden,ai_generated,approved,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,0,1,0,'pending',?,?)",
            (nk, label, "relic", 100 * rarity, rarity, desc, note, efx, template_id, now, now))
        return nk

    def _create_map_item(rw: dict) -> "str | None":
        """#1308 — materialize a map reward as a functional item whose effect_json
        reveals the depicted plan locations (mode=location, drift-proof). Ships
        approved (no review queue) so the reveal works the moment it is granted."""
        reveals = [str(k) for k in (rw.get("reveals") or []) if k]
        if not reveals:
            return None
        label = (rw.get("label") or "Mapa").strip()
        desc = (rw.get("story_hook") or rw.get("mechanical_effect") or "").strip()
        efx = json.dumps(
            {"effects": [{"type": "map_reveal", "mode": "location", "list": reveals}]},
            ensure_ascii=False,
        )
        nk = _uniq("game_config_items", f"tpl{template_id}_{_slugify(rw.get('key') or label)}")
        conn.execute(
            "INSERT INTO game_config_items (key,label,item_type,value_gp,rarity,description,note,effect_json,"
            "template_id,hidden,ai_generated,approved,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,1,1,1,'permanent',?,?)",
            (nk, label, "map", 25, 2, desc, "Odsłania fragment mapy świata.", efx,
             template_id, now, now))
        return nk

    summary = {"signature": 0, "notable": 0, "minor": 0, "fallback_added": 0,
               "pending_keys": [], "maps": 0}
    tier_rarity = {"minor": (1, 2), "notable": (3, 3)}

    # #1308 — map rewards first: any reward flagged is_map / carrying `reveals` becomes
    # a functional map item (skipped by the tier pool logic below via `granted_key`).
    for rw in rewards:
        if isinstance(rw, dict) and not rw.get("granted_key") and (rw.get("is_map") or rw.get("reveals")):
            gk = _create_map_item(rw)
            if gk:
                rw["granted_key"] = gk
                rw["is_map"] = True
                rw["category"] = "item"
                summary["maps"] += 1

    by_tier: dict[str, list] = {"signature": [], "notable": [], "minor": []}
    for rw in rewards:
        if isinstance(rw, dict) and rw.get("granted_key"):
            continue  # already materialized (e.g. map) — don't pool-clone over it
        if isinstance(rw, dict) and rw.get("tier") in by_tier:
            by_tier[rw["tier"]].append(rw)

    # Signatures (cap to budget; force ≥budget count).
    sig_list = by_tier["signature"][: budget["signature"]]
    if not sig_list and budget["signature"]:
        # LLM gave none — promote the best notable, else synthesize a generic one.
        promoted = by_tier["notable"][0] if by_tier["notable"] else {
            "key": "signature_relict", "label": "Relikt Przygody", "category": "weapon",
            "act": act_count, "mechanical_effect": "+2 do obrażeń", "tier": "signature"}
        promoted = dict(promoted); promoted["tier"] = "signature"
        promoted.setdefault("category", "weapon")
        rewards.append(promoted)
        sig_list = [promoted]
        summary["fallback_added"] += 1
    for rw in sig_list:
        gk = _create_signature(rw)
        if gk:
            rw["granted_key"] = gk
            rw["tier"] = "signature"
            summary["signature"] += 1
            summary["pending_keys"].append(gk)

    # Notable + minor from pool by tier.
    for tier in ("notable", "minor"):
        want = budget[tier]
        have = by_tier[tier][:want]
        for rw in have:
            cat = (rw.get("category") or "item").lower()
            rmin, rmax = tier_rarity[tier]
            res = _pool_clone(cat if cat in ("weapon", "item", "consumable") else "item", rmin, rmax, rw.get("label"))
            if res:
                rw["granted_key"] = res[0]
                summary[tier] += 1
        # Fallback top-up: LLM under-delivered this tier → synth from pool (no source_beat).
        deficit = want - len(have)
        for _ in range(max(0, deficit)):
            rmin, rmax = tier_rarity[tier]
            res = _pool_clone("weapon" if tier == "notable" else "item", rmin, rmax, None)
            if res:
                rewards.append({
                    "key": _uniq_reward_key(rewards, res[0]), "label": res[1], "tier": tier,
                    "category": "weapon" if tier == "notable" else "item",
                    "act": act_count, "granted_key": res[0], "acquisition": "loot",
                    "story_hook": "", "mechanical_effect": "", "source_beat": None})
                summary[tier] += 1
                summary["fallback_added"] += 1

    return summary


def _uniq_reward_key(rewards: list, base: str) -> str:
    existing = {r.get("key") for r in rewards if isinstance(r, dict)}
    key, i = base, 2
    while key in existing:
        key = f"{base}_{i}"; i += 1
    return key


# ── Generate full CampaignPlan for a template ─────────────────────────────────

def _build_generate_plan_system_prompt(act_count: int, budget: dict | None = None) -> str:
    """Build the generate-plan system prompt with exactly act_count act entries in the schema.
    Showing the correct number in the example is the only reliable way to get LLMs to honour it.
    `budget` (#1301) tells the LLM how many rewards of each tier to design so the loot spine
    scales with campaign size; the engine still validates + tops up afterwards."""
    b = budget or {}
    sig_n = b.get("signature", 1)
    not_n = b.get("notable", max(1, act_count - 1))
    min_n = b.get("minor", act_count // 2)
    rarity_ceiling = b.get("rarity_ceiling", 4)
    acts_entries = ",\n    ".join(
        f'{{"number": {i}, "title": "string", "summary": "string", '
        '"key_beats": [{"beat_key": "slug_beatu", "summary": "string — co się dzieje", '
        '"objective_type": "kill_enemy", "objective_value": "slug_celu", "optional": false, '
        '"reward_key": "slug_nagrody lub null"}], '
        '"completed": false}'
        for i in range(1, act_count + 1)
    )
    return f"""\
Jesteś doświadczonym Mistrzem Gry mrocznego fantasy (styl WFRP).
Twoim zadaniem jest stworzenie planu kampanii na podstawie szkicu przygody.
Zwróć WYŁĄCZNIE poprawny obiekt JSON — bez markdown, bez komentarzy, bez tekstu poza JSON.
Wszystkie wartości tekstowe pisz w języku polskim.

SCHEMAT JSON — WYMAGANA LICZBA AKTÓW: {act_count} (dokładnie tyle wpisów w tablicy "acts"):
{{
  "title": "string",
  "premise": "string",
  "start_hour": 9,
  "acts": [
    {acts_entries}
  ],
  "endings": [
    {{"id": "ending_primary", "title": "string", "type": "primary", "description": "string", "requirements": ["string","string"]}},
    {{"id": "ending_alternate", "title": "string", "type": "alternate", "description": "string", "requirements": ["string"]}}
  ],
  "key_npcs": [
    {{"key": "slug", "name": "string", "role": "string", "importance": "critical", "deviation_consequence": "branch", "alive": true, "personality_prompt": "string", "description": "string", "keyword_triggers": ["string"]}}
  ],
  "key_locations": [
    {{"key": "slug", "name": "string", "role": "string", "description": "string — 2-3 zdania opisu dla MG (klimat, wygląd, przeznaczenie)", "scale": "hub|sub|standalone", "parent": "klucz_huba (tylko dla sub)", "visited": false}}
  ],
  "key_enemies": [
    {{"key": "slug", "name": "string", "tier": "standard", "hp_base": 20, "ac_base": 12, "damage_die": "1d6", "description": "string — wygląd i charakter wroga", "note": "string — specjalne zdolności i taktyki dla MG"}}
  ],
  "rewards": [
    {{"key": "slug_nagrody", "label": "Nazwa nagrody", "tier": "signature|notable|minor", "category": "weapon|item|consumable", "act": 1, "source_beat": "beat_key który ją wydaje", "acquisition": "loot|quest_reward|npc_gift|discovery", "story_hook": "czemu ta nagroda pasuje do fabuły", "mechanical_effect": "KONKRETNY efekt — broń: +2 obrażenia / wysysa 1 HP na trafienie; relikt-item: +1 do CHA / +2 pancerz / pozwala otwierać zamki bez wprawy / wyostrza skradanie"}},
    {{"key": "mapa_slug", "label": "Nazwa mapy", "tier": "minor", "category": "item", "act": 1, "source_beat": "beat_key który ją wydaje", "acquisition": "npc_gift|discovery", "story_hook": "skąd mapa i co przedstawia", "mechanical_effect": "odsłania mapę świata", "is_map": true, "reveals": ["klucz_lokacji_którą_mapa_odsłania", "..."]}}
  ],
  "active_act": 1,
  "scene_log": [],
  "deviations": [],
  "branches": [],
  "engine_private": {{
    "secret_predisposition_hint": "string",
    "hidden_twist": "string",
    "contingency": "string"
  }}
}}

ZASADY:
1. LICZBA AKTÓW: schemat powyżej zawiera dokładnie {act_count} wpisów w tablicy "acts" — wygeneruj DOKŁADNIE tyle, nie mniej, nie więcej.
2. Dokładnie 2 zakończenia: primary + alternate (oba moralnie niejednoznaczne).
3. 3-6 kluczowych NPC, co najmniej jeden critical.
4. 2-5 lokacji. Pierwsza to punkt startowy.
5. Klucze NPC i lokacji: lowercase_slug, np. "innkeeper_boris".
6. Każdy NPC musi zawierać pola: personality_prompt, description, keyword_triggers.
7. 1-3 kluczowych wrogów (key_enemies) typowych dla fabuły.
8. Każdy wróg MUSI mieć description (wygląd/charakter) i note (zdolności specjalne, taktyka).
9. Każda lokacja MUSI mieć description (min. 2 zdania dla MG — klimat, wygląd, przeznaczenie).
10. BEATY (key_beats) to OBIEKTY, nigdy gołe stringi. Każdy beat: "beat_key" (lowercase_slug, unikalny w obrębie planu), "summary" (co się dzieje). Gdzie sensowne dodaj "objective_type" (jedno z: kill_enemy, visit_location, talk_to_npc, find_item) + "objective_value" (slug celu, np. klucz wroga/lokacji/NPC). Ustaw "optional": true dla scen pobocznych. Co najmniej jeden beat krytyczny (optional: false) na akt.
11. DOMYKALNOŚĆ (KRYTYCZNE): każdy beat krytyczny (optional: false) MUSI dać się domknąć — albo ma "objective_type"+"objective_value" (auto-domknięcie), albo "narrative_close": true (domknięcie sygnałem MG). Beat krytyczny bez żadnego z tych pól zablokuje kampanię. Dla scen czysto fabularnych (walka bez konkretnego wroga w bazie, rozmowa, decyzja) ustaw "narrative_close": true.
12. PORA STARTOWA: "start_hour" (liczba 0-23) to godzina, o której dzieje się scena otwarcia — wybierz ją ŚWIADOMIE pod klimat pierwszej sceny (gwarna wieczorna karczma → 19-20, świt na trakcie → 6, nocna ucieczka → 23), nie ustawiaj odruchowo poranka. Zegar gry startuje dokładnie o tej godzinie.
13. STRUKTURA OSADY: jeśli przygoda toczy się w osadzie (wieś/miasteczko) z co najmniej 2 miejscami-budynkami (karczma, kuźnia, młyn, świątynia, sklep...), dodaj do key_locations OSADĘ ze "scale": "hub" (nazwij ją zgodnie z konwencją świata — mieszanka słowiańsko-germańska, np. Czarnstein, Wilczburg), a każdemu budynkowi daj "scale": "sub" + "parent": <klucz huba>. Miejsca POZA osadą (jaskinia, ruiny, leśny obóz, samotna wieża) → "scale": "standalone". Punkt startowy przygody to zwykle sub wewnątrz huba. Beaty visit_location celują w suby/standalone, nie w hub.
14. NAGRODY (rewards) — KRĘGOSŁUP ŁUPÓW: zaprojektuj DOKŁADNIE {sig_n} nagrodę tieru "signature", {not_n} tieru "notable" i {min_n} tieru "minor". Signature = kluczowy artefakt/relikt fabuły (zwykle powiązany z głównym MacGuffinem przygody), wchodzi w OSTATNIM akcie. Notable = solidny łup na koniec kolejnych aktów. Minor = drobne znaleziska poboczne. Każda nagroda MUSI mieć: unikalny "key" (lowercase_slug), tematyczną "label", "tier", "category", "act" (w którym akcie wchodzi do gry), "story_hook" i "mechanical_effect" (KONKRETNY efekt). Rarity nie ustawiaj — nada je silnik (sufit rarity: {rarity_ceiling}).
14b. TYPY NAGRÓD — nie każ każdej nagrodzie być bronią. Używaj też category "item" dla RELIKTÓW z PASYWNYM efektem działającym w walce I poza nią (zakładane przez gracza). Relikt-item ("category": "item") może dać:
   - bonus statystyki (dowolna z 7: STR/DEX/CON/INT/WIS/CHA/LCK) — mechanical_effect np. "+1 do CHA", "+2 do INT";
   - pancerz — np. "+2 pancerz", "chroni jak lekka zbroja";
   - UMIEJĘTNOŚĆ działającą OD ZERA (nawet gdy bohater jej nie wykupił) — opisz CZASOWNIKIEM/rzeczownikiem umiejętności, np. "pozwala otwierać zamki bez wprawy" (wytrych), "wyostrza skradanie", "dodaje charyzmy/perswazji w rozmowach", "pomaga tropić", "wspomaga leczenie ran". Silnik przełoży opis na twardy efekt (klucz statystyki/umiejętności) — dlatego pisz konkretnie, słowami wskazującymi statystykę lub umiejętność.
   Przynajmniej signature powinien mieć wyrazisty, tematyczny efekt pasywny (jeśli to nie broń — zrób go reliktem-itemem ze statystyką lub umiejętnością pasującą do fabuły).
15. WIĄZANIE NAGRÓD Z BEATAMI: rozłóż nagrody po całej kampanii, NIE tylko na finał. Każdą nagrodę przypnij do konkretnego beatu przez "source_beat" (klucz beatu) ORAZ ustaw temu beatowi pole "reward_key" = "key" tej nagrody. Signature przypnij do beatu krytycznego w ostatnim akcie. Gracz dostaje łup w momencie domknięcia tego beatu — dlatego każdy akt (poza być może pierwszym) powinien wydać co najmniej jedną nagrodę.
16. MAPY (odsłanianie mgły): jeśli fabuła daje graczowi MAPĘ (np. mapa do lochu/ruin, plan okolicy od NPC), zrób z niej nagrodę z "category": "item", "is_map": true oraz "reveals": [lista kluczy key_locations, które ta mapa POKAZUJE na mapie świata]. Zdobycie takiej mapy odsłania te lokacje we mgle wojny (gracz zobaczy je na mapie). Przypnij ją "source_beat"+"reward_key" jak każdą nagrodę (mapa "do X" wchodzi w akcie, w którym gracz ma ruszyć do X). NIE licz mapy do limitów signature/notable/minor — to osobny, dodatkowy przedmiot narzędziowy.
"""


class GeneratePlanReq(BaseModel):
    adventure_idea_id: Optional[int] = None
    difficulty: Optional[str] = None          # 'easy'|'medium'|'hard'|'epic'
    suggested_act_count: Optional[int] = None  # hint for number of acts


@router.post("/templates/{template_id}/generate-plan")
def forge_generate_template_plan(
    template_id: int,
    req: GeneratePlanReq,
    _: None = Depends(_require_admin),
):
    """Generate a full CampaignPlan V2 JSON for a template from its linked adventure idea."""
    conn = _get_db()
    try:
        tpl = conn.execute(
            "SELECT * FROM campaign_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")

        idea_id = req.adventure_idea_id or tpl["adventure_idea_id"]
        idea = None
        if idea_id:
            idea = conn.execute(
                "SELECT * FROM adventure_ideas WHERE id = ?", (idea_id,)
            ).fetchone()

        # Resolve difficulty and act count from request params (override idea/template defaults)
        difficulty_map = {
            "easy": "Łatwa", "medium": "Średnia", "hard": "Trudna", "epic": "Epik"
        }
        req_difficulty = difficulty_map.get(req.difficulty or "", "") if req.difficulty else ""
        req_act_count = req.suggested_act_count  # may be None

        # Build prompt from idea structured_data or template metadata
        if idea:
            sd = json.loads(idea["structured_data"] or "{}")
            arcs_text = ""
            for arc in (sd.get("arcs") or []):
                goals = "\n".join(f"    - {g}" for g in (arc.get("scene_goals") or []))
                arcs_text += f"  Akt: {arc.get('title','')}\n  Opis: {arc.get('description','')}\n  Cele scen:\n{goals}\n  Twist GM: {arc.get('private_twist','')}\n\n"
            hooks_text = "\n".join(
                f"  - ({h.get('type','')}) {h.get('title','')}: {h.get('description','')}"
                for h in (sd.get("hooks") or [])
            )
            arc_count = len(sd.get("arcs") or [])
            if req_act_count and req_act_count > 0:
                arc_instruction = f"WAŻNE: Stwórz DOKŁADNIE {req_act_count} aktów (nie mniej, nie więcej). Każdy akt z osobnym tytułem, podsumowaniem i key_beats.\n\n"
            elif arc_count > 0:
                arc_instruction = f"WAŻNE: Stwórz DOKŁADNIE {arc_count} aktów (nie mniej, nie więcej). Każdy akt z osobnym tytułem, podsumowaniem i key_beats.\n\n"
            else:
                arc_instruction = "Stwórz 3-5 aktów.\n\n"
            effective_difficulty = req_difficulty or idea["difficulty"] or "Średnia"
            user_prompt = arc_instruction + (
                f"SZKIC PRZYGODY:\n"
                f"Tytuł: {idea['title']}\n"
                f"Przesłanka: {idea['premise']}\n"
                f"Ton: {', '.join(json.loads(idea['tone'] or '[]'))}\n"
                f"Motywy: {', '.join(json.loads(idea['themes'] or '[]'))}\n"
                f"Trudność: {effective_difficulty}\n"
                f"Wciągacz gracza: {sd.get('player_hook','')}\n"
                f"Sekret GM: {sd.get('gm_private','')}\n"
                f"\nAKTY:\n{arcs_text}"
                f"\nHOOKI:\n{hooks_text}\n"
                "Stwórz pełny plan kampanii na podstawie tego szkicu. "
                "Fabuła i NPC muszą bezpośrednio wynikać ze szkicu."
            )
        else:
            # Fallback: generate from template metadata
            if req_act_count and req_act_count > 0:
                arc_instruction = f"WAŻNE: Stwórz DOKŁADNIE {req_act_count} aktów (nie mniej, nie więcej). Każdy akt z osobnym tytułem, podsumowaniem i key_beats.\n\n"
            else:
                arc_instruction = "Stwórz 3-5 aktów.\n\n"
            effective_difficulty = req_difficulty or f"{tpl['difficulty_rating']}/5"
            user_prompt = arc_instruction + (
                f"SZABLON KAMPANII:\n"
                f"Tytuł: {tpl['title']}\n"
                f"Opis: {tpl['description']}\n"
                f"Klimat: {tpl['atmosphere']}\n"
                f"Trudność: {effective_difficulty}\n"
                "Stwórz pełny plan kampanii na podstawie powyższych danych."
            )

        # Determine final act count to build the schema — must match what user_prompt says
        if req_act_count and req_act_count > 0:
            final_act_count = max(3, min(req_act_count, 12))
        elif idea:
            sd2 = json.loads(idea["structured_data"] or "{}")
            idea_arc_count = len(sd2.get("arcs") or [])
            final_act_count = max(3, idea_arc_count) if idea_arc_count else 5
        else:
            final_act_count = 5

        # #1301 — reward budget scaled to campaign scope; feeds the prompt so the LLM
        # designs the right number of tiers, and the engine validates/tops up afterwards.
        reward_budget = _compute_reward_budget(final_act_count, tpl["difficulty_rating"])

        messages = [
            {"role": "system", "content": _build_generate_plan_system_prompt(final_act_count, reward_budget)},
            {"role": "user", "content": user_prompt},
        ]

        from app.services.llm_service import get_effective_config
        llm_cfg = get_effective_config()
        model = llm_cfg.get("model", "")
        if not model:
            provider = llm_cfg.get("provider", "?")
            raise HTTPException(
                status_code=400,
                detail=f"Brak modelu w aktywnym presecie LLM (provider: {provider}). "
                       "Przejdź Admin → System → Konta i uzupełnij pole 'Model' w aktywnym presecie.",
            )
        last_err = None
        for attempt in range(1, 3):
            try:
                raw = (generate_chat(messages=messages, llm_config=llm_cfg) or "").strip()
                from app.services.campaign_plan_service import _extract_json, CampaignPlan
                from pydantic import ValidationError
                plan_dict = _extract_json(raw)
                if not plan_dict:
                    last_err = "LLM returned no valid JSON"
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content": "Zwróć TYLKO poprawny JSON."})
                    continue
                plan = CampaignPlan.model_validate(plan_dict)
                plan_public = plan.model_dump()
                # #1109 — never emit a plan with critical orphan beats: any non-optional
                # beat lacking objective_type/narrative_close gets a GM narrative close.
                from app.services.campaign_plan_runtime import ensure_beats_closable
                ensure_beats_closable(plan_public)
                # #1301 — materialize the reward spine BEFORE storing the plan so every
                # reward's `granted_key` (and any fallback top-ups) persist into gm_plan_json;
                # the runtime beat→grant path (FAZA 4) reads these back from the DB.
                reward_summary = {"signature": 0, "notable": 0, "minor": 0, "fallback_added": 0, "pending_keys": []}
                try:
                    reward_summary = _materialize_plan_rewards(
                        conn, template_id, plan_public,
                        difficulty_rating=int(tpl["difficulty_rating"] or 3),
                        act_count=final_act_count,
                    )
                except Exception:
                    logger.exception("reward_spine_materialize_failed", template_id=template_id)
                plan_json = json.dumps(plan_public, ensure_ascii=False)
                conn.execute(
                    "UPDATE campaign_templates SET gm_plan_json = ? WHERE id = ?",
                    (plan_json, template_id),
                )
                if idea_id:
                    conn.execute(
                        "UPDATE campaign_templates SET adventure_idea_id = ? WHERE id = ?",
                        (idea_id, template_id),
                    )

                # #1303 — reconcile required_beats / required_npc_keys against the freshly
                # regenerated plan. Each regeneration emits brand-new LLM-invented beat_keys
                # (and often different key_npcs), so a required_* list curated for a PRIOR plan
                # goes stale: validate_template_publish then reports every orphaned key as a
                # "missing beat/npc" error (e.g. 23 phantom errors after a regenerate) even
                # though the new plan is itself valid & winnable. Prune to keys that still exist
                # in the new plan; keep the surviving subset so an admin's curation isn't lost.
                try:
                    new_beat_keys = {
                        b.get("beat_key")
                        for a in (plan_public.get("acts") or [])
                        for b in (a.get("key_beats") or [])
                        if isinstance(b, dict) and b.get("beat_key")
                    }
                    new_npc_keys = {
                        n.get("key")
                        for n in (plan_public.get("key_npcs") or [])
                        if isinstance(n, dict) and n.get("key")
                    }
                    prev_beats = json.loads(tpl["required_beats"] or "[]") if "required_beats" in tpl.keys() else []
                    prev_npcs = json.loads(tpl["required_npc_keys"] or "[]") if "required_npc_keys" in tpl.keys() else []
                    kept_beats = [b for b in prev_beats if b in new_beat_keys]
                    kept_npcs = [n for n in prev_npcs if n in new_npc_keys]
                    if kept_beats != prev_beats:
                        conn.execute(
                            "UPDATE campaign_templates SET required_beats = ? WHERE id = ?",
                            (json.dumps(kept_beats, ensure_ascii=False), template_id),
                        )
                    if kept_npcs != prev_npcs:
                        conn.execute(
                            "UPDATE campaign_templates SET required_npc_keys = ? WHERE id = ?",
                            (json.dumps(kept_npcs, ensure_ascii=False), template_id),
                        )
                except Exception:
                    logger.exception("required_keys_reconcile_failed", template_id=template_id)

                # Auto-fill npc keys, beat keys, atmosphere (#1085)
                # Convert sqlite3.Row → dict so _auto_fill_plan_fields can call .get() (#1081)
                _fill = _auto_fill_plan_fields(
                    conn, tpl_id=template_id, tpl=dict(tpl),
                    idea=dict(idea) if idea else None, plan_public=plan_public
                )
                auto_npc_keys = _fill["auto_filled_npc_keys"]
                auto_beat_keys = _fill["auto_filled_beat_keys"]
                auto_filled_atmosphere = _fill["auto_filled_atmosphere"]

                conn.commit()

                # #1301 — reward spine already materialized above (before plan store).
                # Kept `auto_assigned_items` in the response for the forge UI, now sourced
                # from the plan's rewards[] with their granted_key.
                auto_items = [
                    {"category": rw.get("category"), "key": rw.get("granted_key"),
                     "name": rw.get("label"), "tier": rw.get("tier")}
                    for rw in (plan_public.get("rewards") or [])
                    if isinstance(rw, dict) and rw.get("granted_key")
                ]

                # #1085 — auto-create pending enemies from key_enemies (HP/AC clamped by difficulty)
                auto_enemies: list[dict] = []
                try:
                    raw_enemies = plan_public.get("key_enemies") or []
                    if raw_enemies:
                        auto_enemies = _auto_create_forge_enemies(
                            conn, template_id, raw_enemies,
                            difficulty=int(tpl["difficulty_rating"] or 3),
                        )
                        conn.commit()
                except Exception:
                    pass  # enemy creation is non-fatal

                # #1087 — auto-create pending NPC stubs from key_npcs
                auto_npcs: list[dict] = []
                try:
                    raw_npcs = plan_public.get("key_npcs") or []
                    if raw_npcs:
                        auto_npcs = _auto_create_forge_npcs(conn, template_id, raw_npcs)
                        conn.commit()
                except Exception:
                    pass  # NPC creation is non-fatal

                # #1092 — auto-create pending location stubs from key_locations
                auto_locations: list[dict] = []
                try:
                    raw_locations = plan_public.get("key_locations") or []
                    if raw_locations:
                        auto_locations = _auto_create_forge_locations(
                            conn, template_id, raw_locations
                        )
                        conn.commit()
                except Exception:
                    pass  # location creation is non-fatal

                # Auto-allocate a start hex at plan-generation time (not just at
                # publish) so the template — and every location placed relative to
                # it below — is grounded on the world map from the first draft.
                start_hex_info: dict | None = None
                try:
                    cur_hex = conn.execute(
                        "SELECT start_hex_q, start_hex_r FROM campaign_templates WHERE id = ?",
                        (template_id,),
                    ).fetchone()
                    if cur_hex and cur_hex["start_hex_q"] is None:
                        best_hex = _allocate_hex_for_template(conn, template_id)
                        if best_hex is not None:
                            conn.execute(
                                "UPDATE campaign_templates SET start_hex_q = ?, start_hex_r = ? WHERE id = ?",
                                (best_hex["q"], best_hex["r"], template_id),
                            )
                            conn.commit()
                            start_hex_info = {
                                "q": best_hex["q"], "r": best_hex["r"],
                                "hex_type": best_hex.get("hex_type"),
                                "is_fallback": bool(best_hex.get("is_fallback")),
                            }
                    elif cur_hex:
                        start_hex_info = {"q": int(cur_hex["start_hex_q"]),
                                          "r": int(cur_hex["start_hex_r"])}
                except Exception:
                    pass  # start-hex allocation is non-fatal (publish gate is the backstop)

                # Materialize the plan's start location on the start hex AND place
                # every other macro location on its own free overworld hex, so the
                # travel engine can route to them. Idempotent, non-fatal.
                plan_location_hexes: dict | None = None
                try:
                    from app.services.template_start_anchor import ensure_template_locations
                    _tsl = ensure_template_locations(conn, template_id)
                    if isinstance(_tsl, dict):
                        plan_location_hexes = _tsl.get("plan_location_hexes")
                except Exception as _tsl_err:
                    logger.warning("generate_plan_location_hex_error", error=str(_tsl_err))

                return {
                    "ok": True,
                    "template_id": template_id,
                    "gm_plan_json": plan_public,
                    "auto_filled_npc_keys": auto_npc_keys,
                    "auto_filled_beat_keys": auto_beat_keys,
                    "auto_filled_atmosphere": auto_filled_atmosphere,
                    "auto_assigned_items": auto_items,
                    "auto_created_enemies": auto_enemies,
                    "auto_created_npcs": auto_npcs,
                    "auto_created_locations": auto_locations,
                    "start_hex": start_hex_info,
                    "plan_location_hexes": plan_location_hexes,
                    "reward_summary": reward_summary,  # #1301
                    "rewards": plan_public.get("rewards") or [],  # #1301
                }
            except Exception as e:
                last_err = str(e)

        raise HTTPException(status_code=500, detail=f"Plan generation failed: {last_err}")
    finally:
        conn.close()


# ── Public template endpoint (player-facing) ─────────────────────────────────

public_router = APIRouter(prefix="/campaign-templates", tags=["campaign-templates"])


@public_router.get("")
def list_published_templates():
    """Return published campaign templates for player campaign creation."""
    conn = _get_db()
    try:
        # E8 (#423) — only player-visible templates appear in the player picker.
        # COALESCE keeps pre-migration rows (NULL) visible by default.
        rows = conn.execute(
            "SELECT * FROM campaign_templates WHERE status = 'published' "
            "AND COALESCE(player_visible, 1) = 1 ORDER BY play_count DESC, created_at DESC"
        ).fetchall()
        items = []
        for r in rows:
            d = _template_to_dict(r)
            # Attach campaign-scoped items summary (key, label, entry_type, rarity, damage_die, effect_type, description)
            tid = r["id"]
            try:
                weapons = conn.execute(
                    "SELECT key, label, 'weapon' AS entry_type, rarity, damage_die, NULL AS effect_type, description FROM game_config_weapons WHERE template_id = ? AND COALESCE(hidden, 0) = 0", (tid,)
                ).fetchall()
                cons = conn.execute(
                    "SELECT key, label, 'consumable' AS entry_type, rarity, NULL AS damage_die, effect_type, description FROM game_config_consumables WHERE template_id = ? AND COALESCE(hidden, 0) = 0", (tid,)
                ).fetchall()
                its = conn.execute(
                    "SELECT key, label, 'item' AS entry_type, rarity, NULL AS damage_die, effect_type, description FROM game_config_items WHERE template_id = ? AND COALESCE(hidden, 0) = 0", (tid,)
                ).fetchall()
            except Exception:
                weapons = cons = its = []
            db_items = [dict(x) for x in [*weapons, *cons, *its]]
            # Also include plan items from gm_plan_json.key_items not already in DB
            existing_keys = {it["key"] for it in db_items}
            plan = json.loads(r["gm_plan_json"] or "{}") if r["gm_plan_json"] else {}
            for pit in (plan.get("key_items") or []):
                if not pit.get("key") or pit.get("hidden") or pit["key"] in existing_keys:
                    continue
                ov = pit.get("overrides") or {}
                etype = pit.get("entity_type") or ov.get("entity_type") or "item"
                db_items.append({
                    "key": pit["key"],
                    "label": pit.get("label") or ov.get("label", pit["key"]),
                    "entry_type": etype,
                    "rarity": ov.get("rarity") or 1,
                    "damage_die": ov.get("damage_die"),
                    "effect_type": ov.get("effect_type"),
                    "description": ov.get("description", ""),
                })
                existing_keys.add(pit["key"])
            d["campaign_items"] = db_items
            items.append(d)
        return {"items": items}
    finally:
        conn.close()


@public_router.get("/hooks/pool")
def list_approved_hooks_public():
    """Return approved hooks available for player hook selection during campaign creation."""
    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT id, hook_type, title, description, significance, quality_rating, times_used
               FROM adventure_hooks
               WHERE status IN ('approved', 'promoted')
               ORDER BY quality_rating DESC, times_used ASC"""
        ).fetchall()
        return {"items": [dict(r) for r in rows]}
    finally:
        conn.close()


class GenerateSublocationsReq(BaseModel):
    location_key: str
    location_name: str
    location_description: str = ""


@router.post("/templates/{template_id}/generate-sublocations")
def forge_generate_sublocations(
    template_id: int,
    req: GenerateSublocationsReq,
    _: None = Depends(_require_admin),
):
    conn = _get_db()
    try:
        tpl = conn.execute(
            "SELECT * FROM campaign_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
    finally:
        conn.close()

    system_prompt = (
        "Jesteś asystentem projektanta gier RPG. Zwracasz TYLKO JSON — żadnego tekstu poza JSON. "
        'Format odpowiedzi: {"sub_locations": [{"key": "slug", "name": "Nazwa", "description": "Krótki opis"}]}'
    )
    user_prompt = (
        f"Kampania: {tpl['title']}\n"
        f"Lokacja nadrzędna: {req.location_name} (klucz: {req.location_key})\n"
        f"Opis: {req.location_description or 'brak'}\n\n"
        f"Zaproponuj 4-6 podlokacji (pomieszczenia, obszary, strefy) tej lokacji. "
        f"Klucze: lowercase_slug zaczynający się od '{req.location_key}_'. "
        f"KAŻDA podlokacja MUSI mieć pole description (min. 1 zdanie opisujące lokację). "
        f"Opisy max 1 zdanie."
    )

    from app.services.campaign_plan_service import _extract_json as _cps_extract_json
    try:
        raw = (generate_chat(messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]) or "").strip()
        result = _cps_extract_json(raw)
        if result is None:
            try:
                result = json.loads(raw)
            except Exception:
                raise HTTPException(status_code=500, detail="LLM returned no valid JSON")
        return {"sub_locations": result.get("sub_locations", [])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")


@router.post("/hooks/{hook_id}/generate-encounter")
def forge_generate_encounter(
    hook_id: int,
    _: None = Depends(_require_admin),
):
    """Expand an approved hook into a standalone mini-encounter JSON."""
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM adventure_hooks WHERE id = ?", (hook_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Hook not found")
        hook = _hook_to_dict(row)
    finally:
        conn.close()

    dd = hook.get("draft_data") or {}
    if isinstance(dd, str):
        try:
            dd = json.loads(dd)
        except Exception:
            dd = {}

    system_prompt = (
        "Jesteś mistrzem gry RPG tworzącym spotkania. Zwracasz TYLKO JSON — żadnego tekstu poza JSON. "
        'Format: {"title":"...","scene_setup":"...","trigger_condition":"...","enemies":[{"name":"...","count":1,"notes":"..."}],"objectives":["..."],"rewards":{"xp_estimate":50,"loot_notes":"..."},"gm_notes":"..."}'
    )
    user_prompt = (
        f"Typ haka: {hook['hook_type']}\n"
        f"Tytuł: {hook['title']}\n"
        f"Opis: {hook['description']}\n"
        f"Dane draftu: {json.dumps(dd, ensure_ascii=False)}\n\n"
        "Stwórz standalone spotkanie (mini-przygodę) bazując na tym haku. "
        "Spotkanie powinno być samowystarczalne — GM może je wstawić w dowolnym momencie kampanii. "
        "Opis sceny max 3 zdania. Maksymalnie 3 wrogów. Cele: 1-3 punkty."
    )

    from app.services.campaign_plan_service import _extract_json as _cps_extract_json
    try:
        raw = (generate_chat(messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]) or "").strip()
        encounter = _cps_extract_json(raw)
        if encounter is None:
            try:
                encounter = json.loads(raw)
            except Exception:
                raise HTTPException(status_code=500, detail="LLM returned no valid JSON for encounter")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    # Save encounter into draft_data.encounter
    conn = _get_db()
    try:
        current_dd = conn.execute(
            "SELECT draft_data FROM adventure_hooks WHERE id = ?", (hook_id,)
        ).fetchone()
        existing_dd: dict = {}
        if current_dd and current_dd["draft_data"]:
            try:
                existing_dd = json.loads(current_dd["draft_data"])
            except Exception:
                existing_dd = {}
        existing_dd["encounter"] = encounter
        conn.execute(
            "UPDATE adventure_hooks SET draft_data = ? WHERE id = ?",
            (json.dumps(existing_dd, ensure_ascii=False), hook_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "encounter": encounter}


# ── Generate campaign description ─────────────────────────────────────────────

class GenerateDescriptionReq(BaseModel):
    title: str = ""
    atmosphere: str = ""
    gm_plan: Optional[dict] = None


@router.post("/templates/{template_id}/generate-description")
def forge_generate_template_description(
    template_id: int,
    req: GenerateDescriptionReq,
    _: None = Depends(_require_admin),
):
    """Generate a short campaign description for the template overview tab."""
    conn = _get_db()
    try:
        tpl = conn.execute(
            "SELECT * FROM campaign_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
    finally:
        conn.close()

    title = req.title or tpl["title"]
    atmosphere = req.atmosphere or tpl["atmosphere"] or ""
    plan = req.gm_plan or {}
    premise = plan.get("premise", "")
    acts = plan.get("acts", [])
    acts_summary = "; ".join(a.get("title", "") for a in acts[:3] if a.get("title"))

    system_prompt = (
        "Jesteś copywriterem gier RPG. Piszesz krótkie, klimatyczne opisy kampanii. "
        "Zwróć TYLKO JSON: {\"description\": \"string\"} — 2-4 zdania po polsku, "
        "zachęcające gracza do wzięcia udziału w kampanii. Mroczny klimat WFRP."
    )
    user_prompt = (
        f"Tytuł kampanii: {title}\n"
        f"Klimat: {atmosphere or 'mroczne fantasy'}\n"
        f"Przesłanka: {premise or '(brak)'}\n"
        f"Akty: {acts_summary or '(brak)'}\n\n"
        "Napisz zachęcający opis kampanii dla gracza (nie spoiluj fabuły)."
    )

    from app.services.campaign_plan_service import _extract_json as _cps_extract_json
    try:
        raw = (generate_chat(messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]) or "").strip()
        result = _cps_extract_json(raw)
        if result is None:
            try:
                result = json.loads(raw)
            except Exception:
                result = {"description": raw[:400]}
        return {"ok": True, "description": result.get("description", raw[:400])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")


# ── Generate campaign-specific item ──────────────────────────────────────────

class GenerateItemReq(BaseModel):
    entity_type: str  # weapon, item, consumable


@router.post("/templates/{template_id}/generate-item")
def forge_generate_template_item(
    template_id: int,
    req: GenerateItemReq,
    _: None = Depends(_require_admin),
):
    """Generate a campaign-specific item/weapon/consumable for the template."""
    conn = _get_db()
    try:
        tpl = conn.execute(
            "SELECT * FROM campaign_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        gm_plan = json.loads(tpl["gm_plan_json"] or "{}")
    finally:
        conn.close()

    entity_type = req.entity_type
    if entity_type not in ("weapon", "item", "consumable"):
        raise HTTPException(status_code=400, detail="entity_type must be weapon, item, or consumable")

    EFFECT_JSON_STRICT_RULES = """
EFFECT_JSON — KONTRAKT MECHANICZNY (każde naruszenie = odrzucenie przez engine):

JEDYNE DOZWOLONE KLUCZE TOP-LEVEL — schema_version, effect_category, effects.
NIE WOLNO DODAWAĆ: once_per_scene, on_hit, active_effect, curse, trigger, bonus_damage,
tags, special, ritual_use, drawback, conditional, requirement, choice, duration, ani żadnych innych.

effect_category → TYLKO jeden z:
  "gear_bonus"          typy efektu: static_stat_modifier
  "character_condition" typy efektu: periodic_save, static_stat_modifier, block_action
  "aura"                typy efektu: periodic_save, static_stat_modifier, apply_condition,
                                     remove_condition, block_action

Klucze obiektu efektu → TYLKO: type, stat, value, tick, condition_key, dc_key, expires
  stat  → STR | DEX | CON | INT | WIS | CHA
  tick  → on_use | start_turn | each_round
  value → string: "1" lub "1d4"

OBOWIĄZKOWE ZASADY:
1. Zawsze generuj MECHANICZNY efekt — static_stat_modifier, apply_condition lub inny realny typ.
   NIE używaj "narrative_only" — to pusty typ bez żadnej mechaniki w engine.
2. Pole "note" ZAWSZE wypełnij opisem dla Mistrza Gry: co magicznie robi przedmiot,
   jak MG powinien to narrować graczowi, jakie są efekty fabularne.
3. Efekty warunkowe (on_hit, once_per_scene, vs enemy type, curse) → wyłącznie w "note".

DWA POPRAWNE PRZYKŁADY:

Pierścień +2 DEX (gear_bonus):
effect_json: {"schema_version":1,"effect_category":"gear_bonus","effects":[{"type":"static_stat_modifier","stat":"DEX","value":"2","tick":"on_use"}]}
note: "Pierścień emanuje subtelną magią zwinności. MG: postać porusza się z nadnaturalną gracją, +2 DEX aktywne przez cały czas noszenia."

Amulet aury strachu (aura, trwa 2 rundy):
effect_json: {"schema_version":1,"effect_category":"aura","effects":[{"type":"apply_condition","condition_key":"frightened","tick":"start_turn","expires":2}]}
note: "Amulet emanuje ciemną aurą grozy. MG: każdy wróg wchodzący w kontakt wzrokowy z noszącym musi sprawdzić WIS DC 13 lub otrzyma stan frightened na 2 rundy."
"""

    type_schemas = {
        "weapon": (
            '{"entity_type":"weapon","key":"slug","label":"Nazwa","damage_die":"1d6",'
            '"linked_stat":"STR","weapon_type":"melee|ranged","rarity":1,'
            '"description":"opis dla gracza","note":"zdolności specjalne i efekty dla MG",'
            '"effect_json":null}'
        ),
        "item": (
            '{"entity_type":"item","key":"slug","label":"Nazwa","item_type":"misc|gear|magic|quest",'
            '"value_gp":10,"rarity":2,"description":"opis dla gracza",'
            '"note":"efekty mechaniczne i narracja dla MG (tu opisz wszystko warunkowe/rytualne)",'
            '"effect_json":{"schema_version":1,"effect_category":"gear_bonus",'
            '"effects":[{"type":"static_stat_modifier","stat":"STR","value":"1","tick":"on_use"}]}}'
        ),
        "consumable": (
            '{"entity_type":"consumable","key":"slug","label":"Nazwa",'
            '"effect_type":"heal_hp|restore_mana|stat_buff|remove_condition|misc",'
            '"effect_dice":"1d4","effect_bonus":0,"effect_target":"self",'
            '"base_price":15,"rarity":1,"description":"opis dla gracza",'
            '"note":"szczegóły efektu dla MG"}'
        ),
    }
    type_labels = {"weapon": "broń", "item": "przedmiot", "consumable": "użytek/eliksir"}

    system_prompt = (
        f"Jesteś projektantem gier RPG. Tworzysz {type_labels[entity_type]} dla kampanii. "
        f"Zwróć TYLKO poprawny JSON pasujący do tego schematu:\n{type_schemas[entity_type]}\n"
        "Klucz (key): lowercase_slug. Powiąż przedmiot tematycznie z fabułą kampanii.\n"
        + (EFFECT_JSON_STRICT_RULES if entity_type in ("weapon", "item") else "")
    )
    user_prompt = (
        f"Kampania: {tpl['title']}\n"
        f"Klimat: {tpl['atmosphere'] or 'mroczne fantasy'}\n"
        f"Fabuła: {gm_plan.get('premise', '(brak)')}\n\n"
        f"Stwórz tematyczny {type_labels[entity_type]} pasujący do tej kampanii."
    )

    from app.services.campaign_plan_service import _extract_json as _cps_extract_json
    try:
        raw = (generate_chat(messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]) or "").strip()
        result = _cps_extract_json(raw)
        if result is None:
            try:
                result = json.loads(raw)
            except Exception:
                raise HTTPException(status_code=500, detail="LLM returned no valid JSON")
        result["entity_type"] = entity_type
        # Sanitize effect_json for weapon and item: wipe to null if LLM generated invalid schema
        if entity_type in ("weapon", "item") and result.get("effect_json") is not None:
            from app.services.admin_config import validate_effect_json_payload
            ej = result["effect_json"]
            if isinstance(ej, str):
                try:
                    ej = json.loads(ej)
                except Exception:
                    ej = None
            if ej is None or validate_effect_json_payload(ej):
                result["effect_json"] = None  # invalid schema — wipe; admin can fill manually
            else:
                # Also wipe if only narrative_only effects (no real mechanics)
                effects = ej.get("effects") or []
                all_narrative = all(e.get("type") == "narrative_only" for e in effects) if effects else True
                result["effect_json"] = None if all_narrative else ej
        return {"ok": True, "item": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")


@router.get("/templates/{template_id}/db-items")
def forge_get_template_db_items(template_id: int, _: None = Depends(_require_admin)):
    """List all game_config entries (weapons/items/consumables) linked to this template."""
    conn = _get_db()
    try:
        tpl = conn.execute("SELECT id FROM campaign_templates WHERE id=?", (template_id,)).fetchone()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        weapons = [dict(r) for r in conn.execute(
            """SELECT key, label, weapon_type, weapon_slot, damage_die, linked_stat, rarity,
                      two_handed, finesse, targeting, range_m, value_gp, magic_school,
                      description, note, effect_json,
                      'weapon' AS entry_type
               FROM game_config_weapons WHERE template_id=?""",
            (template_id,)
        )]
        items = [dict(r) for r in conn.execute(
            """SELECT key, label, item_type, value_gp, rarity, description, note, effect_json,
                      'item' AS entry_type
               FROM game_config_items WHERE template_id=? AND item_type != 'armor'""",
            (template_id,)
        )]
        armors = [dict(r) for r in conn.execute(
            """SELECT key, label, item_type, ac_bonus, rarity, description, note, effect_json,
                      'armor' AS entry_type
               FROM game_config_items WHERE template_id=? AND item_type = 'armor'""",
            (template_id,)
        )]
        consumables = [dict(r) for r in conn.execute(
            """SELECT key, label, effect_type, effect_dice, effect_bonus, base_price, charges,
                      rarity, description, note,
                      'consumable' AS entry_type
               FROM game_config_consumables WHERE template_id=?""",
            (template_id,)
        )]
        return {"weapons": weapons, "items": items, "armors": armors, "consumables": consumables}
    finally:
        conn.close()


@router.post("/templates/{template_id}/db-items/{entry_type}/{key}/promote")
def forge_promote_template_item(
    template_id: int,
    entry_type: str,
    key: str,
    _: None = Depends(_require_admin),
):
    """Promote a template-scoped item to global DB by removing template_id."""
    table_map = {
        "weapon": "game_config_weapons",
        "item": "game_config_items",
        "armor": "game_config_items",
        "consumable": "game_config_consumables",
    }
    table = table_map.get(entry_type)
    if not table:
        raise HTTPException(status_code=400, detail=f"Unknown entry_type: {entry_type}")
    conn = _get_db()
    try:
        row = conn.execute(
            f"SELECT key FROM {table} WHERE key=? AND template_id=?", (key, template_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"{entry_type} {key!r} not linked to template {template_id}")
        conn.execute(f"UPDATE {table} SET template_id=NULL WHERE key=?", (key,))
        conn.commit()
        return {"ok": True, "key": key, "entry_type": entry_type, "status": "promoted_to_global"}
    finally:
        conn.close()


# ── Encounters list / edit ────────────────────────────────────────────────────

@router.get("/encounters")
def forge_list_encounters(_: None = Depends(_require_admin)):
    """Return all hooks that have a generated encounter in draft_data.encounter."""
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT id, hook_type, title, status, description, draft_data FROM adventure_hooks "
            "WHERE draft_data LIKE '%\"encounter\"%' ORDER BY id DESC"
        ).fetchall()
        out = []
        for r in rows:
            dd = {}
            try:
                dd = json.loads(r["draft_data"] or "{}")
            except Exception:
                pass
            enc = dd.get("encounter")
            if not enc:
                continue
            out.append({
                "hook_id": r["id"],
                "hook_type": r["hook_type"],
                "hook_title": r["title"],
                "hook_status": r["status"],
                "hook_description": r["description"],
                "encounter": enc,
            })
        return {"encounters": out}
    finally:
        conn.close()


class PatchEncounterReq(BaseModel):
    encounter: dict


@router.patch("/encounters/{hook_id}")
def forge_patch_encounter(
    hook_id: int,
    req: PatchEncounterReq,
    _: None = Depends(_require_admin),
):
    """Update encounter JSON stored in adventure_hooks.draft_data.encounter."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT draft_data FROM adventure_hooks WHERE id = ?", (hook_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Hook not found")
        dd = {}
        try:
            dd = json.loads(row["draft_data"] or "{}")
        except Exception:
            pass
        dd["encounter"] = req.encounter
        conn.execute(
            "UPDATE adventure_hooks SET draft_data = ? WHERE id = ?",
            (json.dumps(dd, ensure_ascii=False), hook_id),
        )
        conn.commit()
        return {"ok": True, "hook_id": hook_id, "encounter": req.encounter}
    finally:
        conn.close()


# ── Debug: inject encounter into active campaign session ─────────────────────

from app.services.encounter_service import (
    ensure_encounter_enemies_in_db as _ensure_encounter_enemies_in_db,
)


class InjectEncounterReq(BaseModel):
    campaign_id: int
    hook_id: int


@router.post("/debug/inject-encounter")
def forge_debug_inject_encounter(
    req: InjectEncounterReq,
    _: None = Depends(_require_admin),
):
    """Set session_flags.active_encounter so the next GM turn uses this encounter.
    Auto-creates any missing game_config_enemies rows from encounter stats."""
    conn = _get_db()
    try:
        hook_row = conn.execute(
            "SELECT draft_data FROM adventure_hooks WHERE id = ?", (req.hook_id,)
        ).fetchone()
        if not hook_row:
            raise HTTPException(status_code=404, detail="Hook not found")
        dd = {}
        try:
            dd = json.loads(hook_row["draft_data"] or "{}")
        except Exception:
            pass
        encounter = dd.get("encounter")
        if not encounter:
            raise HTTPException(status_code=400, detail="Hook has no generated encounter. Run generate-encounter first.")

        # Ensure enemies exist in game_config_enemies (create on the fly if missing)
        encounter = _ensure_encounter_enemies_in_db(conn, encounter)
        conn.commit()

        sess_row = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (req.campaign_id,),
        ).fetchone()
        if not sess_row:
            raise HTTPException(status_code=404, detail="No active session for this campaign")
        flags = {}
        try:
            flags = json.loads(sess_row["session_flags"] or "{}")
        except Exception:
            pass
        flags["active_encounter"] = encounter
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), sess_row["id"]),
        )
        conn.commit()
        created_keys = [e.get("enemy_key") for e in (encounter.get("enemies") or []) if e.get("enemy_key")]
        return {
            "ok": True,
            "campaign_id": req.campaign_id,
            "encounter_title": encounter.get("title"),
            "enemy_keys": created_keys,
        }
    finally:
        conn.close()


@router.delete("/debug/inject-encounter/{campaign_id}")
def forge_debug_clear_encounter(
    campaign_id: int,
    _: None = Depends(_require_admin),
):
    """Clear active_encounter from session_flags."""
    conn = _get_db()
    try:
        sess_row = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not sess_row:
            raise HTTPException(status_code=404, detail="No session found")
        flags = {}
        try:
            flags = json.loads(sess_row["session_flags"] or "{}")
        except Exception:
            pass
        flags.pop("active_encounter", None)
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), sess_row["id"]),
        )
        conn.commit()
        return {"ok": True, "campaign_id": campaign_id, "cleared": True}
    finally:
        conn.close()


# ── Step E: Hex allocation for Kuźnia templates ───────────────────────────────

def _hex_distance(q1: int, r1: int, q2: int, r2: int) -> int:
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2


def _allocate_hex_for_template(conn: "sqlite3.Connection", template_id: int) -> "dict | None":
    """#1094 — core allocation logic, callable internally (auto-publish) or via endpoint.

    Hard-excludes hexes that:
    - have a non-empty label (named POI / named location on the world map)
    - already have a game_locations row anchored to that hex (world_hex_q/r match)
    Other templates' taken hexes are also skipped.
    Returns best hex dict {q, r, hex_type, label} or None if no free hex found.
    Does NOT write to DB — caller is responsible.
    """
    taken = {
        (int(r["start_hex_q"]), int(r["start_hex_r"]))
        for r in conn.execute(
            "SELECT start_hex_q, start_hex_r FROM campaign_templates "
            "WHERE start_hex_q IS NOT NULL AND id != ?",
            (template_id,),
        ).fetchall()
    }

    # Hexes already claimed by a game_location (world_hex_q/r set)
    try:
        occupied_by_location = {
            (int(r["world_hex_q"]), int(r["world_hex_r"]))
            for r in conn.execute(
                "SELECT world_hex_q, world_hex_r FROM game_locations "
                "WHERE world_hex_q IS NOT NULL AND world_hex_r IS NOT NULL AND is_active = 1"
            ).fetchall()
        }
    except Exception:
        occupied_by_location = set()

    world_hexes = [
        {"q": int(r["q"]), "r": int(r["r"]), "hex_type": r["hex_type"], "label": r["label"] or ""}
        for r in conn.execute(
            "SELECT q, r, hex_type, label FROM world_hexes WHERE map_level = 0 AND is_active = 1"
        ).fetchall()
    ]

    # #1108 — Two-tier allocation so terrain PREFERENCE always dominates centre
    # attraction. Previously `min_dist*10 + pref - center_dist*2` let a snow hex
    # near the centre beat a town hex farther out (Żar → tundra bug). Now we first
    # restrict to preferred terrain {town, plains}; only if none are free do we fall
    # back to any other free hex and flag it (is_fallback) for a publish-time warning.
    _PREFERRED_TYPES = {"town", "plains"}
    _PREF = {"town": 3, "plains": 2, "castle": 1}

    def _pick(pool):
        """Tie-break within a homogeneous-preference pool: keep far from other
        templates' starts (min_dist), gently favour terrain, mild centre pull."""
        chosen = None
        chosen_score = -1e9
        for h in pool:
            hq, hr = h["q"], h["r"]
            pref = _PREF.get(h["hex_type"], 0)
            min_dist = min((_hex_distance(hq, hr, tq, tr) for tq, tr in taken), default=999)
            center_dist = _hex_distance(0, 0, hq, hr)
            score = min_dist * 10 + pref - center_dist * 2
            if score > chosen_score:
                chosen_score = score
                chosen = h
        return chosen

    free = []
    for h in world_hexes:
        hq, hr = h["q"], h["r"]
        # Hard exclusions: named POI or existing location or another template's start
        if h["label"].strip():
            continue
        if (hq, hr) in occupied_by_location:
            continue
        if (hq, hr) in taken:
            continue
        free.append(h)

    if not free:
        return None

    preferred = [h for h in free if h["hex_type"] in _PREFERRED_TYPES]
    if preferred:
        return _pick(preferred)

    # No town/plains free → fall back to any free hex, flagged for a warning.
    best = _pick(free)
    if best is not None:
        best = {**best, "is_fallback": True}
    return best


def _hex_availability(conn: "sqlite3.Connection", template_id: int) -> "list[dict]":
    """#1108 — classify every overworld hex for the Kuźnia map picker modal.

    Returns one dict per active map_level=0 hex with:
      q, r, hex_type, label
      status         : 'free_good' | 'free_atypical' | 'occupied'
      is_current     : True if it is THIS template's current start_hex
      is_template_start : True if it is ANOTHER template's start_hex
    A hex is 'occupied' when it has a named POI label, an active game_location, or
    is another template's start. 'free_good' = town/plains/forest; other free
    terrain (snow/swamp/ruins/…) = 'free_atypical' (clickable with a warning).
    """
    _GOOD_TYPES = {"town", "plains", "forest"}

    current = conn.execute(
        "SELECT start_hex_q, start_hex_r FROM campaign_templates WHERE id = ?",
        (template_id,),
    ).fetchone()
    current_qr = None
    if current and current["start_hex_q"] is not None:
        current_qr = (int(current["start_hex_q"]), int(current["start_hex_r"]))

    other_starts = {
        (int(r["start_hex_q"]), int(r["start_hex_r"]))
        for r in conn.execute(
            "SELECT start_hex_q, start_hex_r FROM campaign_templates "
            "WHERE start_hex_q IS NOT NULL AND id != ?",
            (template_id,),
        ).fetchall()
    }

    try:
        occupied_by_location = {
            (int(r["world_hex_q"]), int(r["world_hex_r"]))
            for r in conn.execute(
                "SELECT world_hex_q, world_hex_r FROM game_locations "
                "WHERE world_hex_q IS NOT NULL AND world_hex_r IS NOT NULL AND is_active = 1"
            ).fetchall()
        }
    except Exception:
        occupied_by_location = set()

    out = []
    for r in conn.execute(
        "SELECT q, r, hex_type, label FROM world_hexes WHERE map_level = 0 AND is_active = 1"
    ).fetchall():
        q, rr = int(r["q"]), int(r["r"])
        label = (r["label"] or "").strip()
        htype = r["hex_type"] or ""
        qr = (q, rr)
        is_current = qr == current_qr
        is_other_start = qr in other_starts

        if is_current:
            # own current start stays clickable (re-confirm) → not 'occupied'
            status = "free_good" if htype in _GOOD_TYPES else "free_atypical"
        elif label or qr in occupied_by_location or is_other_start:
            status = "occupied"
        elif htype in _GOOD_TYPES:
            status = "free_good"
        else:
            status = "free_atypical"

        out.append({
            "q": q, "r": rr, "hex_type": htype, "label": label,
            "status": status,
            "is_current": is_current,
            "is_template_start": is_other_start,
        })
    return out


@router.post("/templates/{template_id}/allocate-hex")
def forge_allocate_hex(template_id: int, _: None = Depends(_require_admin)):
    """Find a free world hex cluster for this template and assign it.
    Prefers town/plains hexes far from other templates' start hexes.
    Hard-excludes named POI hexes and hexes with existing game_locations."""
    conn = _get_db()
    try:
        tpl = conn.execute(
            "SELECT id, title FROM campaign_templates WHERE id = ?",
            (template_id,),
        ).fetchone()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")

        world_hexes = [
            {"q": int(r["q"]), "r": int(r["r"]), "hex_type": r["hex_type"], "label": r["label"]}
            for r in conn.execute(
                "SELECT q, r, hex_type, label FROM world_hexes WHERE map_level = 0 AND is_active = 1"
            ).fetchall()
        ]

        if not world_hexes:
            raise HTTPException(status_code=422, detail="No world hexes — generate world first")

        best = _allocate_hex_for_template(conn, template_id)

        if not best:
            raise HTTPException(status_code=422, detail="Could not find suitable hex — all free hexes are occupied or named POI")

        conn.execute(
            "UPDATE campaign_templates SET start_hex_q = ?, start_hex_r = ? WHERE id = ?",
            (best["q"], best["r"], template_id),
        )
        conn.commit()

        # #1206 — anchor the plan's start location on the freshly allocated hex
        try:
            from app.services.template_start_anchor import ensure_template_locations
            ensure_template_locations(conn, template_id)
        except Exception as _tsl_err:
            logger.warning("template_start_location_error", error=str(_tsl_err))

        _DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
        hex_set = {(h["q"], h["r"]): h for h in world_hexes}
        cluster = [best]
        for dq, dr in _DIRS:
            nb = hex_set.get((best["q"] + dq, best["r"] + dr))
            if nb:
                cluster.append(nb)

        resp = {
            "ok": True,
            "template_id": template_id,
            "start_hex": {"q": best["q"], "r": best["r"], "label": best["label"], "hex_type": best["hex_type"]},
            "cluster": cluster,
        }
        if best.get("is_fallback"):
            resp["warning"] = (
                f"Brak wolnych hexów town/plains — przydzielono nietypowy teren "
                f"'{best['hex_type']}'. Rozważ ręczny wybór hexa na mapie."
            )
        return resp
    finally:
        conn.close()


@router.get("/templates/{template_id}/hex-availability")
def forge_hex_availability(template_id: int, _: None = Depends(_require_admin)):
    """#1108 — hex map picker data: every overworld hex classified
    free_good / free_atypical / occupied, plus current + other-template start markers."""
    conn = _get_db()
    try:
        tpl = conn.execute(
            "SELECT id FROM campaign_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        hexes = _hex_availability(conn, template_id)
        return {"ok": True, "template_id": template_id, "hexes": hexes}
    finally:
        conn.close()


class SetStartHexReq(BaseModel):
    q: int
    r: int


@router.post("/templates/{template_id}/set-start-hex")
def forge_set_start_hex(template_id: int, req: SetStartHexReq, _: None = Depends(_require_admin)):
    """#1108 — manually set a template's start hex from the map picker modal.

    Rejects hexes that are occupied (named POI / active game_location / another
    template's start). Atypical-but-free terrain (snow/swamp/…) is allowed; the
    frontend surfaces a warning before calling this. world_hexes is read-only."""
    conn = _get_db()
    try:
        tpl = conn.execute(
            "SELECT id FROM campaign_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")

        avail = {(h["q"], h["r"]): h for h in _hex_availability(conn, template_id)}
        hx = avail.get((req.q, req.r))
        if hx is None:
            raise HTTPException(status_code=422, detail="Hex nie istnieje na mapie świata")
        if hx["status"] == "occupied":
            raise HTTPException(
                status_code=409,
                detail="Hex zajęty (POI / lokacja / start innego szablonu) — wybierz wolny hex.",
            )

        conn.execute(
            "UPDATE campaign_templates SET start_hex_q = ?, start_hex_r = ? WHERE id = ?",
            (req.q, req.r, template_id),
        )
        conn.commit()

        # #1206 — anchor (or move) the plan's start location onto the chosen hex
        try:
            from app.services.template_start_anchor import ensure_template_locations
            ensure_template_locations(conn, template_id)
        except Exception as _tsl_err:
            logger.warning("template_start_location_error", error=str(_tsl_err))

        return {
            "ok": True,
            "template_id": template_id,
            "start_hex": {"q": req.q, "r": req.r, "hex_type": hx["hex_type"], "label": hx["label"]},
            "atypical": hx["status"] == "free_atypical",
        }
    finally:
        conn.close()


@router.delete("/templates/{template_id}/allocate-hex")
def forge_deallocate_hex(template_id: int, _: None = Depends(_require_admin)):
    """Remove hex allocation from a template."""
    conn = _get_db()
    try:
        conn.execute(
            "UPDATE campaign_templates SET start_hex_q = NULL, start_hex_r = NULL WHERE id = ?",
            (template_id,),
        )
        conn.commit()
        return {"ok": True, "template_id": template_id}
    finally:
        conn.close()


# ── Plan macro-location placement (admin relocation of world-map locations) ────

@router.get("/templates/{template_id}/location-hexes")
def forge_location_hexes(template_id: int, _: None = Depends(_require_admin)):
    """List the plan's overworld macro locations with their current world hex,
    plus the full hex-availability grid — data for the 'Rozmieszczenie lokacji'
    map picker so an admin can relocate any location that landed too close."""
    from app.services.template_start_anchor import _overworld_macro_locations
    from app.services.hex_location_link import resolve_location_to_hex
    conn = _get_db()
    try:
        tpl = conn.execute(
            "SELECT id, start_hex_q, start_hex_r, gm_plan_json FROM campaign_templates WHERE id = ?",
            (template_id,),
        ).fetchone()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        try:
            plan = json.loads(tpl["gm_plan_json"] or "{}")
        except Exception:
            plan = {}
        macro = _overworld_macro_locations(plan)
        labels = {
            str(l["key"]): str(l.get("name") or l["key"])
            for l in (plan.get("key_locations") or [])
            if isinstance(l, dict) and l.get("key")
        }
        locations = []
        for loc in macro:
            key = str(loc["key"])
            row = conn.execute(
                "SELECT id FROM game_locations WHERE key = ? AND is_active = 1 LIMIT 1", (key,)
            ).fetchone()
            hx = resolve_location_to_hex(conn, key) if row else None
            locations.append({
                "key": key,
                "name": labels.get(key, key),
                "q": hx[0] if hx else None,
                "r": hx[1] if hx else None,
                "placed": hx is not None,
                "exists": row is not None,
            })
        start = None
        if tpl["start_hex_q"] is not None:
            start = {"q": int(tpl["start_hex_q"]), "r": int(tpl["start_hex_r"])}
        return {
            "ok": True,
            "template_id": template_id,
            "start_hex": start,
            "locations": locations,
            "hexes": _hex_availability(conn, template_id),
        }
    finally:
        conn.close()


class SetLocationHexReq(BaseModel):
    location_key: str
    q: int
    r: int


@router.post("/templates/{template_id}/location-hexes/set")
def forge_set_location_hex(
    template_id: int, req: SetLocationHexReq, _: None = Depends(_require_admin)
):
    """Relocate ONE plan macro location to a chosen free overworld hex.

    Rejects a hex occupied by a named POI, another location, or any template's
    start hex (the location's OWN current hex is allowed — a no-op re-confirm).
    world_hexes rows are never created/deleted (Kresy map is Piotr-owned)."""
    from app.services.template_start_anchor import _overworld_macro_locations
    from app.services.hex_location_link import link_location_to_hex, resolve_location_to_hex
    conn = _get_db()
    try:
        tpl = conn.execute(
            "SELECT id, gm_plan_json FROM campaign_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        try:
            plan = json.loads(tpl["gm_plan_json"] or "{}")
        except Exception:
            plan = {}
        macro_keys = {str(l["key"]) for l in _overworld_macro_locations(plan)}
        if req.location_key not in macro_keys:
            raise HTTPException(
                status_code=422,
                detail="Lokacja nie jest makro-lokacją planu (hub/sub nie są przenoszone tu).",
            )
        row = conn.execute(
            "SELECT id FROM game_locations WHERE key = ? AND is_active = 1 LIMIT 1",
            (req.location_key,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=422, detail="Lokacja nie istnieje jeszcze w bazie.")

        # Validate the target hex exists on the world map.
        hx = conn.execute(
            "SELECT hex_type, label FROM world_hexes "
            "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1 LIMIT 1",
            (req.q, req.r),
        ).fetchone()
        if hx is None:
            raise HTTPException(status_code=422, detail="Hex nie istnieje na mapie świata.")

        current = resolve_location_to_hex(conn, req.location_key)
        is_own = current is not None and current == (req.q, req.r)
        if not is_own:
            if (hx["label"] or "").strip():
                raise HTTPException(status_code=409, detail="Hex to nazwany POI — wybierz wolny hex.")
            # occupied by another active location?
            occ = conn.execute(
                "SELECT key FROM game_locations WHERE world_hex_q = ? AND world_hex_r = ? "
                "AND is_active = 1 AND key != ? LIMIT 1",
                (req.q, req.r, req.location_key),
            ).fetchone()
            if occ:
                raise HTTPException(status_code=409, detail="Hex zajęty przez inną lokację.")
            # occupied by any template's start hex?
            st = conn.execute(
                "SELECT id FROM campaign_templates WHERE start_hex_q = ? AND start_hex_r = ? LIMIT 1",
                (req.q, req.r),
            ).fetchone()
            if st:
                raise HTTPException(status_code=409, detail="Hex zajęty jako start szablonu.")

        # release the old hex canon, then claim the new one
        if current is not None and not is_own:
            conn.execute(
                "UPDATE world_hexes SET location_key = NULL "
                "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1",
                (current[0], current[1]),
            )
        link_location_to_hex(conn, req.location_key, req.q, req.r)
        conn.commit()
        return {
            "ok": True,
            "template_id": template_id,
            "location_key": req.location_key,
            "q": req.q, "r": req.r,
            "hex_type": hx["hex_type"],
            "atypical": (hx["hex_type"] or "") not in ("town", "plains", "forest"),
        }
    finally:
        conn.close()


class RerollLocationHexesReq(BaseModel):
    min_spacing: int = 3


@router.post("/templates/{template_id}/location-hexes/reroll")
def forge_reroll_location_hexes(
    template_id: int,
    req: RerollLocationHexesReq | None = None,
    _: None = Depends(_require_admin),
):
    """Re-scatter ALL of the plan's macro locations with a wider minimum spacing —
    the fix for auto-placement that packed them too close together."""
    from app.services.template_start_anchor import ensure_plan_location_hexes
    conn = _get_db()
    try:
        tpl = conn.execute(
            "SELECT id, start_hex_q FROM campaign_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        if tpl["start_hex_q"] is None:
            raise HTTPException(
                status_code=422,
                detail="Szablon nie ma jeszcze startowego hexa — przydziel start najpierw.",
            )
        spacing = max(1, int((req.min_spacing if req else 3)))
        result = ensure_plan_location_hexes(conn, template_id, force=True, min_spacing=spacing)
        if result is None:
            raise HTTPException(status_code=422, detail="Brak makro-lokacji planu do rozmieszczenia.")
        return {"ok": True, "template_id": template_id, **result}
    finally:
        conn.close()
