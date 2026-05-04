"""
T05: generate initial `campaigns.gm_plan_json` via LLM after character creation (retry loop).
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.logging import get_logger
from app.services.gm_plan_schema import gm_plan_is_ready, merge_gm_plan_patch, normalize_gm_plan
from app.services.llm_service import generate_chat

logger = get_logger(__name__)

GM_PLAN_GENERATION_SYSTEM = """Jesteś asystentem projektowania kampanii RPG (notatki dla MG).
Zwróć WYŁĄCZNIE jeden obiekt JSON (bez markdown, bez komentarzy, bez tekstu przed/po), kształt:
{
  "roadmap": "string — 2–6 zdań: łuk fabularny, główne tropy i kierunek pierwszych scen",
  "scene_goals": ["3–6 krótkich celów pierwszej sceny startowej"],
  "hooks": { "npcs": ["2–5 imion lub ról"], "locations": ["2–5 miejsc lub typów lokacji"] },
  "title": "krótki tytuł aktywnego łuku (max ok. 80 znaków)"
}
Pisz po polsku jeśli kampania jest po polsku. To są notatki wewnętrzne MG — nie stylizuj na dialog z graczem."""


def extract_first_json_object(text: str) -> dict[str, Any] | None:
    t = (text or "").strip()
    if not t:
        return None
    if "```" in t:
        for block in re.findall(r"```(?:json)?\s*([\s\S]*?)```", t, flags=re.I):
            blk = block.strip()
            if blk.startswith("{"):
                t = blk
                break
    try:
        val = json.loads(t)
        return val if isinstance(val, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", t)
    if not m:
        return None
    try:
        val = json.loads(m.group(0))
        return val if isinstance(val, dict) else None
    except json.JSONDecodeError:
        return None


def _llm_flat_to_w1_patch(llm_obj: dict[str, Any]) -> dict[str, Any]:
    title = str(llm_obj.get("title") or "").strip() or "Start kampanii"
    roadmap = str(llm_obj.get("roadmap") or "").strip()
    goals = llm_obj.get("scene_goals")
    if not isinstance(goals, list):
        goals = []
    goals = [str(g).strip() for g in goals if g is not None and str(g).strip()]
    hooks_in = llm_obj.get("hooks")
    hooks: dict[str, Any] = {}
    if isinstance(hooks_in, dict):
        npcs = hooks_in.get("npcs")
        locs = hooks_in.get("locations")
        if isinstance(npcs, list):
            hooks["npcs"] = [str(x).strip() for x in npcs if x is not None and str(x).strip()]
        if isinstance(locs, list):
            hooks["locations"] = [str(x).strip() for x in locs if x is not None and str(x).strip()]
    return {
        "arcs": {
            "default": {
                "id": "default",
                "title": title,
                "status": "active",
                "roadmap": roadmap,
                "scene_goals": goals,
                "hooks": hooks,
            }
        },
        "active_arc_id": "default",
    }


def arc_payload_from_flat_llm(llm_obj: dict[str, Any]) -> dict[str, Any]:
    """
    Węzeł łuku (jeden arc) z płaskiego JSON z LLM — ten sam kształt co przy generacji startowej (T05).
    Używane przy T15 (nowy akt): wstrzyknięcie pod nowym `arc_id` zamiast `default`.
    """
    return _llm_flat_to_w1_patch(llm_obj)["arcs"]["default"]


def generate_initial_gm_plan_with_retries(
    conn,
    *,
    campaign_id: int,
    campaign_title: str,
    campaign_language: str,
    system_id: str,
    char_summary: str,
    user_id: int,
    model: str,
    llm_config: dict[str, Any],
    max_attempts: int = 3,
) -> tuple[bool, str | None]:
    """
    Persists to campaigns.gm_plan_json on success. Returns (ok, error_message).
    """
    user_content = (
        f"Tytuł kampanii: {campaign_title}\n"
        f"Język: {campaign_language}\n"
        f"System (id): {system_id}\n\n"
        f"{char_summary}\n\n"
        "Na tej podstawie wypełnij JSON planu MG (roadmap, cele sceny, haki, tytuł łuku)."
    )
    messages = [
        {"role": "system", "content": GM_PLAN_GENERATION_SYSTEM},
        {"role": "user", "content": user_content},
    ]

    last_err: str | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            raw = (generate_chat(messages=messages, model=model, llm_config=llm_config) or "").strip()
            parsed = extract_first_json_object(raw)
            if not parsed:
                last_err = "LLM nie zwrócił poprawnego JSON planu"
                logger.warning(
                    "gm_plan_generation_parse_failed",
                    campaign_id=campaign_id,
                    attempt=attempt,
                    preview=(raw[:400] if raw else ""),
                )
                continue
            patch = _llm_flat_to_w1_patch(parsed)
            base = normalize_gm_plan(None)
            merged = merge_gm_plan_patch(base, patch)
            dumped = json.dumps(merged, ensure_ascii=False)
            if not gm_plan_is_ready(dumped):
                last_err = "Wygenerowany plan jest zbyt pusty (brak roadmapy/celów/haków)"
                logger.warning("gm_plan_generation_empty_plan", campaign_id=campaign_id, attempt=attempt)
                continue
            conn.execute(
                "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
                (dumped, campaign_id),
            )
            conn.commit()
            logger.info("gm_plan_generation_ok", campaign_id=campaign_id, attempt=attempt)
            return True, None
        except Exception as e:
            last_err = str(e)
            logger.warning(
                "gm_plan_generation_attempt_failed",
                campaign_id=campaign_id,
                attempt=attempt,
                error=str(e),
            )
    return False, last_err or "Nie udało się wygenerować planu MG"


def retry_initial_gm_plan_for_campaign(
    conn,
    *,
    campaign_id: int,
    owner_user_id: int,
    max_attempts: int = 3,
) -> tuple[bool, str | None]:
    """
    Ponowna generacja planu na podstawie pierwszej postaci w kampanii (owner).
    Zwraca (ok, error_message).
    """
    from app.services.user_llm_settings import get_user_llm_settings_full

    camp = conn.execute(
        """
        SELECT id, title, system_id, model_id, language, owner_user_id
        FROM campaigns WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()
    if not camp:
        return False, "campaign_not_found"
    if int(camp["owner_user_id"]) != int(owner_user_id):
        return False, "forbidden"

    char = conn.execute(
        """
        SELECT id, name, system_id, sheet_json, location
        FROM characters
        WHERE campaign_id = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (campaign_id,),
    ).fetchone()
    if not char:
        return False, "Brak postaci w kampanii — nie można zbudować kontekstu planu."

    sheet_raw = char["sheet_json"] or "{}"
    try:
        sheet = json.loads(sheet_raw) if isinstance(sheet_raw, str) else dict(sheet_raw)
    except json.JSONDecodeError:
        sheet = {}
    archetype = str(sheet.get("archetype", "warrior")).strip().lower()
    hp = sheet.get("max_hp", "?")
    mana = sheet.get("max_mana", 0)
    stats = sheet.get("stats", {}) or {}
    skills = sheet.get("skills", {}) or {}
    background = str(sheet.get("background") or "").strip()
    stat_lines = ", ".join(f"{k}:{v}" for k, v in stats.items()) if stats else ""
    skill_lines = ", ".join(
        f"{k}:{v}" for k, v in skills.items() if isinstance(v, (int, float)) and v > 0
    ) if skills else ""
    archetype_label = "Uczony" if archetype == "scholar" else "Wojownik"
    location = (char["location"] or "").strip() or "nieznane miejsce"
    name = (char["name"] or "").strip() or "Bohater"

    char_summary = (
        f"Postać: {name}, Archetyp: {archetype_label}, "
        f"HP: {hp}"
        + (f", Mana: {mana}" if mana else "")
        + (f", Statystyki: {stat_lines}" if stat_lines else "")
        + (f", Umiejętności: {skill_lines}" if skill_lines else "")
        + (f", Tło: {background}" if background else "")
        + f", Lokalizacja startowa: {location}."
    )

    llm_config = get_user_llm_settings_full(int(owner_user_id))
    model = str(camp["model_id"] or "").strip() or "gemma3:1b"
    model = (llm_config.get("model") or "").strip() or model

    return generate_initial_gm_plan_with_retries(
        conn,
        campaign_id=campaign_id,
        campaign_title=str(camp["title"] or f"Kampania {campaign_id}"),
        campaign_language=str(camp["language"] or "pl"),
        system_id=str(camp["system_id"] or ""),
        char_summary=char_summary,
        user_id=int(owner_user_id),
        model=model,
        llm_config=llm_config,
        max_attempts=max_attempts,
    )
