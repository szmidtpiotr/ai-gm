"""
Campaign Plan Service — V2 Phase 02 Task 07

Generates a structured CampaignPlan from character identity (bonds, weaknesses,
secret_predisposition) + optional Ideas Bank seeds.

The plan has two parts:
  - Public plan (acts, endings, key_npcs, key_locations) → stored in gm_plan_json
  - engine_private (secret_predisposition hint, hidden twist, contingency)
    → stored in engine_private_json, never returned to player API

The LLM receives the full character identity and produces valid JSON that is
validated against the CampaignPlan Pydantic model before storage.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, Literal

import structlog
from pydantic import BaseModel, ConfigDict, ValidationError

from app.services.llm_service import generate_chat

logger = structlog.get_logger()

DB_PATH = "/data/ai_gm.db"


# ── Pydantic schema ────────────────────────────────────────────────────────

class PlotAct(BaseModel):
    number: int
    title: str
    summary: str
    key_beats: list[str]
    completed: bool = False


class PlotEnding(BaseModel):
    id: str
    title: str
    type: Literal["primary", "alternate"]
    description: str
    requirements: list[str]


class PlotEnemy(BaseModel):
    model_config = ConfigDict(extra='allow')
    key: str
    name: str
    role: str = ""
    tier: str = "standard"
    description: str = ""
    note: str = ""
    count: int = 1


class PlotNPC(BaseModel):
    model_config = ConfigDict(extra='allow')
    key: str
    name: str
    role: str
    importance: Literal["critical", "supporting", "replaceable"]
    deviation_consequence: Literal["ignore", "steer", "branch"]
    alive: bool = True
    personality_prompt: str = ""
    description: str = ""
    keyword_triggers: list[str] = []


class PlotLocation(BaseModel):
    model_config = ConfigDict(extra='allow')
    key: str
    name: str
    role: str
    description: str = ""
    visited: bool = False


class EnginePrivate(BaseModel):
    secret_predisposition_hint: str
    hidden_twist: str
    contingency: str


class CampaignPlan(BaseModel):
    model_config = ConfigDict(extra='allow')
    title: str
    premise: str
    acts: list[PlotAct]
    endings: list[PlotEnding]
    key_npcs: list[PlotNPC]
    key_locations: list[PlotLocation]
    key_enemies: list[PlotEnemy] = []
    active_act: int = 1
    scene_log: list[str] = []
    deviations: list[str] = []
    branches: list[str] = []
    engine_private: EnginePrivate


# ── Prompt builder ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
Jesteś doświadczonym Mistrzem Gry mrocznego fantasy (styl WFRP).
Twoim zadaniem jest stworzenie planu kampanii dla jednego gracza.
Zwróć WYŁĄCZNIE poprawny obiekt JSON — bez markdown, bez komentarzy, bez tekstu poza JSON.
Wszystkie wartości tekstowe pisz w języku polskim.

SCHEMAT JSON (wypełnij każde pole):
{
  "title": "string — krótki, mroczny tytuł kampanii",
  "premise": "string — 1-2 zdania opisujące główny konflikt",
  "acts": [
    {
      "number": 1,
      "title": "string — tytuł aktu",
      "summary": "string — 2-4 zdania opisujące łuk aktu",
      "key_beats": ["string", "string", "string"],
      "completed": false
    }
  ],
  "endings": [
    {
      "id": "ending_primary",
      "title": "string",
      "type": "primary",
      "description": "string — 2-3 zdania",
      "requirements": ["string", "string"]
    },
    {
      "id": "ending_alternate",
      "title": "string",
      "type": "alternate",
      "description": "string — 2-3 zdania",
      "requirements": ["string"]
    }
  ],
  "key_npcs": [
    {
      "key": "npc_key_slug",
      "name": "string",
      "role": "string",
      "importance": "critical",
      "deviation_consequence": "branch",
      "alive": true,
      "personality_prompt": "string — 1-2 zdania osobowości",
      "description": "string — wygląd i background",
      "keyword_triggers": ["string"]
    }
  ],
  "key_locations": [
    {
      "key": "location_key_slug",
      "name": "string",
      "role": "starting_point",
      "visited": false
    }
  ],
  "key_enemies": [
    {
      "key": "enemy_key_slug",
      "name": "string",
      "role": "string",
      "tier": "standard",
      "description": "string",
      "count": 1
    }
  ],
  "active_act": 1,
  "scene_log": [],
  "deviations": [],
  "branches": [],
  "engine_private": {
    "secret_predisposition_hint": "string — jak ta ukryta cecha wpłynie na kampanię",
    "hidden_twist": "string — zaskakujące odkrycie zaplanowane na Akt 2 lub 3",
    "contingency": "string — co się dzieje jeśli gracz zabije kluczową postać zbyt wcześnie"
  }
}

ZASADY OBOWIĄZKOWE:
1. Dokładnie 3 akty.
2. Dokładnie 2 zakończenia: jedno "primary", jedno "alternate". Oba muszą być moralnie niejednoznaczne — żadnego czystego triumfu ani czystego zła.
3. 3-6 kluczowych postaci NPC (key_npcs). Co najmniej jedna krytyczna. Każdy NPC musi mieć wypełnione personality_prompt i description.
4. 2-5 lokacji (key_locations). Pierwsza lokacja to punkt startowy.
5. Akt 1 musi nawiązywać do co najmniej jednej Więzi bohatera.
6. Antagonista/główny konflikt musi dotykać co najmniej jednej Słabości bohatera.
7. Klucze NPC i lokacji (pola "key") muszą być lowercase_slug bez spacji, np. "innkeeper_boris", "loc_graustein".
8. 1-3 kluczowych wrogów (key_enemies). Przynajmniej jeden odpowiada głównemu antagoniście lub typowemu zagrożeniu fabuły.
"""


def _build_user_prompt(
    name: str,
    archetype: str,
    background_note: str,
    personality: str,
    bonds: list[dict],
    weaknesses: list[dict],
    secret_predisposition: str,
    ideas_seeds: list[dict] | None = None,
) -> str:
    archetype_label = "Uczony" if archetype == "scholar" else "Wojownik"

    bonds_text = "\n".join(
        f"  - ({b.get('type','?')}) {b.get('description','')}"
        for b in (bonds or [])
    )
    weak_text = "\n".join(
        f"  - ({w.get('type','?')}) {w.get('description','')}"
        for w in (weaknesses or [])
    )

    seeds_text = ""
    if ideas_seeds:
        seeds_text = "\nINSPIRACJE Z BANKU POMYSŁÓW (możesz dostosować do postaci):\n"
        for s in ideas_seeds[:3]:
            seeds_text += f"  - {s.get('title','')}: {s.get('premise','')}\n"

    return (
        f"POSTAĆ:\n"
        f"  Imię: {name}\n"
        f"  Archetyp: {archetype_label}\n"
        f"  Tło: {background_note or '(brak)'}\n"
        f"  Osobowość: {personality or '(brak)'}\n"
        f"\nWIĘZI BOHATERA:\n{bonds_text or '  (brak)'}\n"
        f"\nSŁABOŚCI BOHATERA:\n{weak_text or '  (brak)'}\n"
        f"\nUKRYTA PREDYSPOZYCJA (TYLKO DLA MG, nie ujawniaj graczowi):\n"
        f"  {secret_predisposition or '(brak)'}\n"
        f"{seeds_text}\n"
        "Stwórz plan kampanii spersonalizowany pod tę postać. "
        "Fabuła powinna wynikać z jej więzi i słabości — nie być generyczna."
    )


# ── Adventure hooks seed query ────────────────────────────────────────────

def _query_hook_seeds(conn: sqlite3.Connection, campaign_id: int, limit: int = 5) -> list[dict]:
    """Pull hook seeds for campaign plan generation.
    Uses campaign's selected hooks first; falls back to global top-rated pool."""
    try:
        row = conn.execute(
            "SELECT selected_hook_ids FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        selected_ids = []
        if row:
            import json as _json
            selected_ids = _json.loads(row[0] or "[]")

        if selected_ids:
            placeholders = ",".join("?" * len(selected_ids))
            rows = conn.execute(
                f"""SELECT title, description FROM adventure_hooks
                    WHERE id IN ({placeholders}) AND status IN ('approved', 'promoted')""",
                selected_ids,
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT title, description FROM adventure_hooks
                   WHERE status IN ('approved', 'promoted')
                   ORDER BY quality_rating DESC, times_used ASC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [{"title": r[0], "premise": (r[1] or "")[:200]} for r in rows]
    except Exception:
        return []


# ── Core generation function ──────────────────────────────────────────────

def generate_v2_campaign_plan(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_data: dict,
    model: str,
    llm_config: dict,
    max_attempts: int = 2,
) -> tuple[bool, str | None]:
    """
    Generate and store a V2 CampaignPlan for the given campaign.

    Reads character data from `character_data` dict (should include identity
    with bonds, weaknesses, gm_only.secret_predisposition).

    On success: stores plan_json in gm_plan_json, engine_private in
    engine_private_json. Returns (True, None).
    On failure: returns (False, error_message).
    """
    # Extract character fields
    identity = character_data.get("identity") or {}
    gm_only = character_data.get("gm_only") or {}

    name = str(character_data.get("name") or "Bohater").strip()
    archetype = str(character_data.get("archetype") or "warrior").lower()
    background_note = str(
        character_data.get("background_note")
        or character_data.get("backstory")
        or identity.get("backstory")
        or ""
    ).strip()
    personality = str(identity.get("personality") or "").strip()

    bonds = identity.get("bonds") or []
    weaknesses = identity.get("weaknesses") or []
    secret_predisposition = str(gm_only.get("secret_predisposition") or "").strip()

    seeds = _query_hook_seeds(conn, campaign_id)

    user_prompt = _build_user_prompt(
        name=name,
        archetype=archetype,
        background_note=background_note,
        personality=personality,
        bonds=bonds,
        weaknesses=weaknesses,
        secret_predisposition=secret_predisposition,
        ideas_seeds=seeds,
    )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    last_err: str | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            raw = (generate_chat(messages=messages, model=model, llm_config=llm_config) or "").strip()
            plan_dict = _extract_json(raw)
            if not plan_dict:
                last_err = "LLM nie zwrócił poprawnego JSON planu V2"
                logger.warning("campaign_plan_v2_parse_failed", campaign_id=campaign_id, attempt=attempt)
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": "Zwróć TYLKO poprawny JSON bez żadnego tekstu."})
                continue

            # Validate with Pydantic
            try:
                plan = CampaignPlan.model_validate(plan_dict)
            except ValidationError as ve:
                last_err = f"Schema validation failed: {ve.error_count()} errors"
                logger.warning("campaign_plan_v2_validation_failed", campaign_id=campaign_id,
                               attempt=attempt, errors=str(ve)[:200])
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user",
                                  "content": f"Poprzednia odpowiedź nie przeszła walidacji: {last_err}. "
                                             "Popraw JSON i zwróć go ponownie."})
                continue

            # Separate engine_private from public plan
            plan_public = plan.model_dump()
            engine_private = plan_public.pop("engine_private", {})

            # Store both parts
            _store_plan(conn, campaign_id, plan_public, engine_private)

            logger.info("campaign_plan_v2_ok", campaign_id=campaign_id, attempt=attempt,
                        title=plan.title)
            return True, None

        except Exception as e:
            last_err = str(e)
            logger.warning("campaign_plan_v2_attempt_failed", campaign_id=campaign_id,
                           attempt=attempt, error=str(e))

    return False, last_err or "Nie udało się wygenerować planu kampanii"


def _extract_json(text: str) -> dict | None:
    """Extract first JSON object from LLM output."""
    t = (text or "").strip()
    if not t:
        return None
    # Strip markdown code blocks
    if "```" in t:
        for block in re.findall(r"```(?:json)?\s*([\s\S]*?)```", t, re.I):
            blk = block.strip()
            if blk.startswith("{"):
                t = blk
                break
    try:
        val = json.loads(t)
        return val if isinstance(val, dict) else None
    except json.JSONDecodeError:
        pass
    # Try to extract first {...} block
    m = re.search(r"\{[\s\S]*\}", t)
    if m:
        try:
            val = json.loads(m.group(0))
            return val if isinstance(val, dict) else None
        except json.JSONDecodeError:
            pass
    return None


def _store_plan(conn: sqlite3.Connection, campaign_id: int,
                plan_public: dict, engine_private: dict) -> None:
    """Store public plan in gm_plan_json and engine_private in engine_private_json."""
    plan_json = json.dumps(plan_public, ensure_ascii=False)
    private_json = json.dumps(engine_private, ensure_ascii=False)

    # Try to store engine_private separately (requires column — falls back gracefully)
    try:
        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ?, engine_private_json = ? WHERE id = ?",
            (plan_json, private_json, campaign_id)
        )
    except Exception:
        # Column may not exist yet on older DB — store full plan in gm_plan_json
        full = dict(plan_public)
        full["engine_private"] = engine_private
        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
            (json.dumps(full, ensure_ascii=False), campaign_id)
        )
    # Stage 9 follow-up: rename generic placeholder title to the LLM-picked one.
    try:
        from app.services.gm_plan_generation_service import _maybe_rename_campaign_from_plan
        _maybe_rename_campaign_from_plan(conn, campaign_id, plan_public)
    except Exception as e:
        logger.warning("campaign_title_rename_v2_failed", campaign_id=campaign_id, error=str(e))
    conn.commit()


def get_public_plan(gm_plan_json: str) -> dict:
    """
    Parse gm_plan_json and return the public-safe plan (engine_private stripped).
    Used by player-facing API endpoints.
    """
    try:
        plan = json.loads(gm_plan_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    plan.pop("engine_private", None)
    return plan
