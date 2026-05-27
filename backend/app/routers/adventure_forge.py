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

FORMAT JSON gdy proponujesz szkic:
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
{"key": "slug", "label": "Nazwa", "damage_die": "1d6", "linked_stat": "STR", "allowed_classes": "warrior,rogue", "description": "...", "weapon_type": "melee|ranged|armor", "rarity": 1}

ITEM (hook_type: item):
{"key": "slug", "label": "Nazwa", "item_type": "misc|tool|key|quest", "description": "...", "value_gp": 0, "rarity": 1}

CONSUMABLE (hook_type: consumable):
{"key": "slug", "label": "Nazwa", "description": "...", "effect_type": "heal|buff|misc", "base_price": 0, "rarity": 1}

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


def _promote_hook_to_db(conn: sqlite3.Connection, hook: dict) -> tuple[str, int]:
    """Insert hook draft_data into the appropriate game config table.
    Returns (table_name, new_record_id)."""
    d = hook["draft_data"]
    htype = hook["hook_type"]
    now = datetime.utcnow().isoformat()

    if htype in ("weapon", "armor"):
        table = "game_config_weapons"
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        label = d.get("label") or hook["title"]
        cur = conn.execute(
            """INSERT INTO game_config_weapons
               (key, label, damage_die, linked_stat, allowed_classes, description,
                weapon_type, rarity, ai_generated, approved, review_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 'permanent', ?, ?)""",
            (key, label,
             d.get("damage_die", "1d6"), d.get("linked_stat", "STR"),
             d.get("allowed_classes", "warrior"),
             d.get("description", hook.get("description", "")),
             d.get("weapon_type", "armor" if htype == "armor" else "melee"),
             int(d.get("rarity", 1)), now, now),
        )
        return table, cur.lastrowid

    elif htype == "item":
        table = "game_config_items"
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        label = d.get("label") or hook["title"]
        cur = conn.execute(
            """INSERT INTO game_config_items
               (key, label, item_type, description, value_gp, rarity,
                ai_generated, approved, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)""",
            (key, label,
             d.get("item_type", "misc"),
             d.get("description", hook.get("description", "")),
             int(d.get("value_gp", 0)), int(d.get("rarity", 1)), now, now),
        )
        return table, cur.lastrowid

    elif htype == "consumable":
        table = "game_config_consumables"
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        label = d.get("label") or hook["title"]
        cur = conn.execute(
            """INSERT INTO game_config_consumables
               (key, label, description, effect_type, base_price, rarity,
                ai_generated, approved, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)""",
            (key, label,
             d.get("description", hook.get("description", "")),
             d.get("effect_type", "misc"),
             int(d.get("base_price", 0)), int(d.get("rarity", 1)), now, now),
        )
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
             int(d.get("hp_base", 20)), int(d.get("ac_base", 12)),
             int(d.get("attack_bonus", 3)), d.get("damage_die", "1d6"),
             d.get("description", hook.get("description", "")),
             d.get("tier", "standard"), d.get("damage_type", "physical"),
             now, now),
        )
        return table, cur.lastrowid

    elif htype == "npc":
        table = "npcs"
        key = _ensure_unique_key(conn, table, d.get("key") or _slugify(hook["title"]))
        label = d.get("label") or hook["title"]
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
               VALUES (?, ?, ?, ?, ?, 1, 1, 'permanent', 'adventure_forge', ?, ?)""",
            (key, label,
             d.get("description", hook.get("description", "")),
             d.get("location_type", "macro"),
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


class PatchTemplateReq(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    difficulty_rating: Optional[int] = None
    atmosphere: Optional[str] = None
    gm_plan_json: Optional[dict] = None
    hook_ids: Optional[list[int]] = None
    status: Optional[str] = None


# ── Chat endpoints ────────────────────────────────────────────────────────────

@router.post("/chat/message")
def forge_chat_message(req: ForgeMessageReq, _: None = Depends(_require_admin)):
    session = _get_or_create_session(req.session_id)
    session["history"].append({"role": "user", "content": req.message})

    messages = [{"role": "system", "content": FORGE_SYSTEM_PROMPT}] + session["history"]
    try:
        reply = generate_chat(messages=messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    session["history"].append({"role": "assistant", "content": reply})
    draft, ready_to_save = _extract_draft(reply)
    if draft:
        session["draft"] = draft

    # Strip raw JSON block from displayed reply so chat stays readable
    display_reply = re.sub(r"```json.*?```", "", reply, flags=re.DOTALL).strip()
    if not display_reply:
        display_reply = reply

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
        conn.execute("UPDATE adventure_ideas SET status = 'archived' WHERE id = ?", (idea_id,))
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
               (title, description, difficulty_rating, atmosphere, gm_plan_json, hook_ids, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, 'draft', 'admin')""",
            (
                req.title, req.description, req.difficulty_rating, req.atmosphere,
                json.dumps(gm_plan, ensure_ascii=False),
                json.dumps(hook_ids, ensure_ascii=False),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM campaign_templates WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _template_to_dict(row)
    finally:
        conn.close()


@router.patch("/templates/{template_id}")
def forge_patch_template(template_id: int, req: PatchTemplateReq, _: None = Depends(_require_admin)):
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM campaign_templates WHERE id = ?", (template_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Template not found")
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


# ── Public template endpoint (player-facing) ─────────────────────────────────

public_router = APIRouter(prefix="/api/campaign-templates", tags=["campaign-templates"])


@public_router.get("")
def list_published_templates():
    """Return published campaign templates for player campaign creation."""
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM campaign_templates WHERE status = 'published' ORDER BY play_count DESC, created_at DESC"
        ).fetchall()
        return {"items": [_template_to_dict(r) for r in rows]}
    finally:
        conn.close()
