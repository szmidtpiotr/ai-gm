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
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from app.services.llm_service import generate_chat
from app.core.db_runtime import resolve_db_path

logger = structlog.get_logger()

DB_PATH = resolve_db_path()


# ── Slug helper ─────────────────────────────────────────────────────────────

_PL_MAP = {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
           "ó": "o", "ś": "s", "ź": "z", "ż": "z"}


def _slugify_beat(text: str) -> str:
    """Deterministic lowercase slug from a beat summary/title (first ~6 words)."""
    s = (text or "").lower().strip()
    s = re.sub(r"[ąćęłńóśźż]", lambda m: _PL_MAP.get(m.group(), m.group()), s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    # keep it short — first chunk of words, capped
    return "_".join(s.split("_")[:6])[:50] or "beat"


# ── Pydantic schema ────────────────────────────────────────────────────────

class PlotBeat(BaseModel):
    """A single story beat (#1017). Structured so the win machinery (#1009–#1014)
    can track it: `beat_key` is the stable identifier, `objective_type`/`objective_value`
    enable auto-complete, `optional` marks non-critical side scenes."""
    beat_key: str
    summary: str = ""
    objective_type: Literal["kill_enemy", "visit_location", "talk_to_npc", "find_item"] | None = None
    objective_value: str | None = None
    optional: bool = False
    # #1301 — reward spine: when this beat closes, the linked reward (by key into
    # CampaignPlan.rewards[].key) is granted to the player's inventory mid-campaign.
    reward_key: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, v: Any) -> Any:
        """Accept a bare string (legacy) or a dict missing beat_key — derive a slug."""
        if isinstance(v, str):
            return {"beat_key": _slugify_beat(v), "summary": v}
        if isinstance(v, dict):
            d = dict(v)
            if not d.get("beat_key"):
                d["beat_key"] = _slugify_beat(str(d.get("summary") or d.get("title") or ""))
            return d
        return v


class PlotAct(BaseModel):
    number: int
    title: str
    summary: str
    key_beats: list[PlotBeat] = []
    completed: bool = False

    @model_validator(mode="after")
    def _unique_beat_keys(self) -> "PlotAct":
        """Ensure beat_key uniqueness within the act (#1017)."""
        seen: set[str] = set()
        for b in self.key_beats:
            base = b.beat_key
            key = base
            i = 2
            while key in seen:
                key = f"{base}_{i}"
                i += 1
            b.beat_key = key
            seen.add(key)
        return self


class PlotEnding(BaseModel):
    id: str
    title: str
    type: Literal["primary", "alternate"]
    description: str
    requirements: list[str]


class PlotNPC(BaseModel):
    key: str
    name: str
    role: str
    importance: Literal["critical", "supporting", "replaceable"]
    deviation_consequence: Literal["ignore", "steer", "branch"]
    alive: bool = True


class PlotLocation(BaseModel):
    key: str
    name: str
    role: str
    visited: bool = False
    # #1306 — these were silently dropped by model_dump() (the fields the Kuźnia
    # prompt asks for but the schema never declared). Without `scale`/`parent` the
    # settlement structure (#1212) is lost on every generated plan → flat fallback
    # → wrong start_hex (the first visit_location target instead of the town hub).
    # `hex_q`/`hex_r` let #1307 mirror the placed overworld coords back into the plan.
    description: str = ""
    scale: Literal["hub", "sub", "standalone"] | None = None
    parent: str | None = None
    hex_q: int | None = None
    hex_r: int | None = None


class PlotEnemy(BaseModel):
    """Key enemy generated in the plan (#1085). Auto-created in game_config_enemies as pending."""
    key: str
    name: str
    tier: str = "standard"
    hp_base: int = 20
    ac_base: int = 12
    damage_die: str = "1d6"
    description: str = ""
    note: str = ""


class PlotReward(BaseModel):
    """#1301 — a story-anchored reward in the plan's loot spine.

    `tier` drives materialization: signature → bespoke unique pushed to pending
    review (rarity ≥4, real effect_json); notable/minor → pool clone by tier.
    `act`/`source_beat` drive mid-campaign pacing — the reward enters play when
    its beat closes, not only at the finale. `mechanical_effect` is a descriptive
    hint the deterministic mapper turns into a safe effect_json for signatures."""
    key: str
    label: str
    tier: Literal["signature", "notable", "minor"] = "notable"
    category: Literal["weapon", "item", "consumable"] = "item"
    act: int = 1
    source_beat: str | None = None
    acquisition: Literal["loot", "quest_reward", "npc_gift", "discovery"] = "quest_reward"
    story_hook: str = ""
    mechanical_effect: str = ""
    rarity: int = 3
    # #1308 — map rewards. `is_map` flags the reward as a fog-of-war map; `reveals`
    # lists the plan location keys it depicts. Materialization builds an item whose
    # effect_json carries a map_reveal(mode="location") payload, and the reward-spine
    # reveals those locations for the campaign the moment the map is obtained.
    is_map: bool = False
    reveals: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, v: Any) -> Any:
        """Derive a slug key from label when the LLM omits it; tolerate bare strings."""
        if isinstance(v, str):
            return {"key": _slugify_beat(v), "label": v}
        if isinstance(v, dict):
            d = dict(v)
            if not d.get("key"):
                d["key"] = _slugify_beat(str(d.get("label") or d.get("mechanical_effect") or ""))
            return d
        return v


class EnginePrivate(BaseModel):
    secret_predisposition_hint: str
    hidden_twist: str
    contingency: str


class CampaignPlan(BaseModel):
    title: str
    premise: str
    acts: list[PlotAct]
    endings: list[PlotEnding]
    key_npcs: list[PlotNPC]
    key_locations: list[PlotLocation]
    key_enemies: list[PlotEnemy] = []
    rewards: list[PlotReward] = []  # #1301 — loot spine, materialized after gen
    active_act: int = 1
    scene_log: list[str] = []
    deviations: list[str] = []
    branches: list[str] = []
    engine_private: EnginePrivate

    @model_validator(mode="after")
    def _unique_beat_keys_plan_wide(self) -> "CampaignPlan":
        """Disambiguate beat_key collisions across acts so each beat is plan-unique (#1017)."""
        seen: set[str] = set()
        for act in self.acts:
            for b in act.key_beats:
                base = b.beat_key
                key = base
                i = 2
                while key in seen:
                    key = f"{base}_{i}"
                    i += 1
                b.beat_key = key
                seen.add(key)
        return self


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
      "key_beats": [
        {"beat_key": "slug_beatu", "summary": "string — co się dzieje", "objective_type": "kill_enemy", "objective_value": "slug_celu", "optional": false}
      ],
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
      "alive": true
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
      "name": "string — nazwa wroga (po polsku)",
      "tier": "standard",
      "hp_base": 20,
      "ac_base": 12,
      "damage_die": "1d6",
      "description": "string — wygląd i styl walki",
      "note": "string — specjalne zdolności (opcjonalnie)"
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
3. 3-6 kluczowych postaci NPC (key_npcs). Co najmniej jedna krytyczna.
4. 2-5 lokacji (key_locations). Pierwsza lokacja to punkt startowy.
5. Akt 1 musi nawiązywać do co najmniej jednej Więzi bohatera.
6. Antagonista/główny konflikt musi dotykać co najmniej jednej Słabości bohatera.
7. Klucze NPC i lokacji (pola "key") muszą być lowercase_slug bez spacji, np. "innkeeper_boris", "loc_graustein".
8. BEATY (key_beats) to OBIEKTY, nigdy gołe stringi. Każdy beat: "beat_key" (lowercase_slug, unikalny w planie), "summary". Gdzie sensowne dodaj "objective_type" (kill_enemy/visit_location/talk_to_npc/find_item) + "objective_value" (slug celu). "optional": true dla scen pobocznych. Co najmniej jeden beat krytyczny (optional: false) na akt.
9. WROGOWIE (key_enemies): lista 1-3 głównych antagonistów/bossów kampanii (nie zwykłych wrogów — tylko kluczowe postacie z którymi walka jest częścią fabuły). "key" to lowercase_slug; "tier": weak/standard/elite/boss. Lista może być pusta tylko gdy kampania nie przewiduje żadnej walki.
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
    hero_chronicle: str = "",
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

    chronicle_text = ""
    if (hero_chronicle or "").strip():
        chronicle_text = (
            f"\n{hero_chronicle.strip()}\n"
            "Uwzględnij powyższą kronikę bohatera przy tworzeniu planu — "
            "nawiązuj do poprzednich czynów, powracających NPC, konsekwencji decyzji.\n"
        )

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
        f"{seeds_text}"
        f"{chronicle_text}\n"
        "Stwórz plan kampanii spersonalizowany pod tę postać. "
        "Fabuła powinna wynikać z jej więzi i słabości — nie być generyczna."
    )


# ── Ideas Bank query ───────────────────────────────────────────────────────

def _query_ideas_seeds(conn: sqlite3.Connection, limit: int = 3) -> list[dict]:
    """Pull top-rated approved seeds from campaign_ideas."""
    try:
        rows = conn.execute(
            """SELECT title, description
               FROM campaign_ideas
               WHERE category = 'seed'
               AND review_status = 'approved'
               ORDER BY quality_rating DESC, times_used ASC
               LIMIT ?""",
            (limit,)
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
    hero_chronicle: str = "",
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

    # Ideas Bank seeds
    seeds = _query_ideas_seeds(conn)

    user_prompt = _build_user_prompt(
        name=name,
        archetype=archetype,
        background_note=background_note,
        personality=personality,
        bonds=bonds,
        weaknesses=weaknesses,
        secret_predisposition=secret_predisposition,
        ideas_seeds=seeds,
        hero_chronicle=hero_chronicle,
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


def normalize_plan_beats(plan: dict | None) -> dict | None:
    """#1014 — normalize `acts[].key_beats` so every authored beat is a structured
    PlotBeat: derive a stable, plan-unique `beat_key` (slug from summary), preserve
    `optional` (default False), tolerate bare-string beats (legacy). Idempotent.

    Runs at template-save time so a beat entered in the Forge UI always carries the
    `beat_key` the win machinery (#1009–#1012) needs and the `optional` flag #1014
    exposes. Non-act / planless input is returned untouched (default-safe).
    """
    if not isinstance(plan, dict):
        return plan
    acts = plan.get("acts")
    if not isinstance(acts, list):
        return plan
    # Carry-through fields PlotBeat doesn't model but runtime/round-trip rely on.
    _EXTRA = ("visited", "skipped", "narrative_close", "label")
    seen: set[str] = set()
    for act in acts:
        if not isinstance(act, dict):
            continue
        beats = act.get("key_beats")
        if not isinstance(beats, list):
            continue
        norm: list[dict] = []
        for b in beats:
            try:
                d = PlotBeat.model_validate(b).model_dump()
            except ValidationError:
                continue
            base = d["beat_key"]
            key, i = base, 2
            while key in seen:
                key = f"{base}_{i}"
                i += 1
            d["beat_key"] = key
            seen.add(key)
            if isinstance(b, dict):
                for extra in _EXTRA:
                    if extra in b and extra not in d:
                        d[extra] = b[extra]
            norm.append(d)
        act["key_beats"] = norm
    return plan


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
