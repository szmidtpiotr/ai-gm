"""
Adventure Forge Router — Kuźnia Kampanii
AI-assisted adventure idea creation → hooks → real DB records → campaign templates
"""

import json
import re
import sqlite3
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from app.services.admin_auth import verify_admin_token
from app.services.llm_service import generate_chat


def _safe_int(val, default):
    try:
        return int(val) if val is not None and val != "" else default
    except (ValueError, TypeError):
        return default


_LOC_TYPE_MAP = {"sub": "sub"}  # everything else → macro

DB_PATH = "/data/ai_gm.db"

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
        row = conn.execute(f"SELECT id FROM {table} WHERE key = ?", (key,)).fetchone()
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


def _promote_hook_to_db(conn: sqlite3.Connection, hook: dict) -> tuple[str, int]:
    """Insert hook draft_data into the appropriate game config table.
    Returns (table_name, new_record_id)."""
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
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        label = d.get("label") or hook["title"]
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
        _u11c_sync(conn, table, key)
        return table, cur.lastrowid

    elif htype == "item":
        table = "game_config_items"
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        label = d.get("label") or hook["title"]
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
        _u11c_sync(conn, table, key)
        return table, cur.lastrowid

    elif htype == "consumable":
        table = "game_config_consumables"
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        label = d.get("label") or hook["title"]
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

    return {
        "ok": not missing_npcs and not missing_beats,
        "missing_npcs": missing_npcs,
        "missing_beats": missing_beats,
    }


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
            # Apply any required_* changes coming in the same request first, so
            # validation runs against the about-to-be-saved values.
            if req.required_npc_keys is not None or req.required_beats is not None:
                if req.required_npc_keys is not None:
                    conn.execute("UPDATE campaign_templates SET required_npc_keys = ? WHERE id = ?",
                                 (json.dumps(req.required_npc_keys, ensure_ascii=False), template_id))
                if req.required_beats is not None:
                    conn.execute("UPDATE campaign_templates SET required_beats = ? WHERE id = ?",
                                 (json.dumps(req.required_beats, ensure_ascii=False), template_id))
                conn.commit()
            vres = validate_template_publish(template_id, conn)
            if not vres["ok"]:
                raise HTTPException(status_code=422, detail={
                    "error": "template_incomplete",
                    "message": "Nie można opublikować — brakuje wymaganych elementów.",
                    "missing_npcs": vres["missing_npcs"],
                    "missing_beats": vres["missing_beats"],
                })
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
            params.append(json.dumps(req.gm_plan_json, ensure_ascii=False))
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


# ── Generate full CampaignPlan for a template ─────────────────────────────────

def _build_generate_plan_system_prompt(act_count: int) -> str:
    """Build the generate-plan system prompt with exactly act_count act entries in the schema.
    Showing the correct number in the example is the only reliable way to get LLMs to honour it."""
    acts_entries = ",\n    ".join(
        f'{{"number": {i}, "title": "string", "summary": "string", "key_beats": ["string","string","string"], "completed": false}}'
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
    {{"key": "slug", "name": "string", "role": "string", "description": "string — 2-3 zdania opisu dla MG (klimat, wygląd, przeznaczenie)", "visited": false}}
  ],
  "key_enemies": [
    {{"key": "slug", "name": "string", "tier": "standard", "hp_base": 20, "ac_base": 12, "damage_die": "1d6", "description": "string — wygląd i charakter wroga", "note": "string — specjalne zdolności i taktyki dla MG"}}
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

        messages = [
            {"role": "system", "content": _build_generate_plan_system_prompt(final_act_count)},
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
        config = {k: v for k, v in llm_cfg.items() if k != "model"}

        last_err = None
        for attempt in range(1, 3):
            try:
                raw = (generate_chat(messages=messages, model=model, llm_config=config) or "").strip()
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
                conn.commit()
                return {"ok": True, "template_id": template_id, "gm_plan_json": plan_public}
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
                    "SELECT key, label, 'weapon' AS entry_type, rarity, damage_die, NULL AS effect_type, description FROM game_config_weapons WHERE template_id = ?", (tid,)
                ).fetchall()
                cons = conn.execute(
                    "SELECT key, label, 'consumable' AS entry_type, rarity, NULL AS damage_die, effect_type, description FROM game_config_consumables WHERE template_id = ?", (tid,)
                ).fetchall()
                its = conn.execute(
                    "SELECT key, label, 'item' AS entry_type, rarity, NULL AS damage_die, effect_type, description FROM game_config_items WHERE template_id = ?", (tid,)
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


@router.post("/templates/{template_id}/allocate-hex")
def forge_allocate_hex(template_id: int, _: None = Depends(_require_admin)):
    """Find a free world hex cluster for this template and assign it.
    Prefers town/plains hexes far from other templates' start hexes."""
    conn = _get_db()
    try:
        tpl = conn.execute(
            "SELECT id, title FROM campaign_templates WHERE id = ?",
            (template_id,),
        ).fetchone()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")

        taken = [
            (int(r["start_hex_q"]), int(r["start_hex_r"]))
            for r in conn.execute(
                "SELECT start_hex_q, start_hex_r FROM campaign_templates "
                "WHERE start_hex_q IS NOT NULL AND id != ?",
                (template_id,),
            ).fetchall()
        ]

        world_hexes = [
            {"q": int(r["q"]), "r": int(r["r"]), "hex_type": r["hex_type"], "label": r["label"]}
            for r in conn.execute(
                "SELECT q, r, hex_type, label FROM world_hexes WHERE map_level = 0 AND is_active = 1"
            ).fetchall()
        ]

        if not world_hexes:
            raise HTTPException(status_code=422, detail="No world hexes — generate world first")

        _PREF = {"town": 3, "plains": 2, "castle": 1}
        best = None
        best_score = -1
        for h in world_hexes:
            pref = _PREF.get(h["hex_type"], 0)
            min_dist = min((_hex_distance(h["q"], h["r"], tq, tr) for tq, tr in taken), default=999)
            # Penalise hexes far from world centre so templates cluster in the middle
            center_dist = _hex_distance(0, 0, h["q"], h["r"])
            score = min_dist * 10 + pref - center_dist * 2
            if score > best_score:
                best_score = score
                best = h

        if not best:
            raise HTTPException(status_code=422, detail="Could not find suitable hex")

        conn.execute(
            "UPDATE campaign_templates SET start_hex_q = ?, start_hex_r = ? WHERE id = ?",
            (best["q"], best["r"], template_id),
        )
        conn.commit()

        _DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
        hex_set = {(h["q"], h["r"]): h for h in world_hexes}
        cluster = [best]
        for dq, dr in _DIRS:
            nb = hex_set.get((best["q"] + dq, best["r"] + dr))
            if nb:
                cluster.append(nb)

        return {
            "ok": True,
            "template_id": template_id,
            "start_hex": {"q": best["q"], "r": best["r"], "label": best["label"], "hex_type": best["hex_type"]},
            "cluster": cluster,
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
