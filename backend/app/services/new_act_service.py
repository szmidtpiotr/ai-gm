"""
T15: po ukończeniu głównego questa — nowy łuk w tym samym `campaign_id`
(regeneracja planu MG jak przy starcie + narracja łącząca w `campaign_turns`).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.core.db_runtime import resolve_db_path
from app.core.logging import get_logger

DB_PATH = resolve_db_path()
from app.services.gm_plan_generation_service import arc_payload_from_flat_llm, extract_first_json_object
from app.services.gm_plan_schema import (
    format_gm_plan_block,
    gm_plan_is_ready,
    merge_gm_plan_patch,
    normalize_gm_plan,
)
from app.services.llm_service import generate_chat
from app.services.user_llm_settings import get_user_llm_settings_full

logger = get_logger(__name__)

DEFAULT_MAIN_QUEST_KEY = "main_quest"

GM_PLAN_NEW_ACT_SYSTEM = """Jesteś asystentem projektowania kampanii RPG (notatki wewnętrzne MG).
Gracz właśnie ukończył GŁÓWNY quest fabularny bieżącego łuku. Zaproponuj NOWY łuk (kolejny „akt” tej samej kampanii) — nie kopiuj słowo w słowo starej roadmapy; zaproponuj świeże tropy i cele.
Zwróć WYŁĄCZNIE jeden obiekt JSON (bez markdown, bez komentarzy), kształt jak przy planie startowym:
{
  "roadmap": "string — 2–6 zdań: nowy kierunek fabularny po zamknięciu poprzedniego łuku",
  "scene_goals": ["3–6 krótkich celów pierwszej sceny nowego łuku"],
  "hooks": { "npcs": ["2–5 imion lub ról"], "locations": ["2–5 miejsc lub typów lokacji"] },
  "title": "krótki tytuł nowego łuku (max ok. 80 znaków)"
}
Pisz po polsku jeśli kampania jest po polsku."""

BRIDGE_NARRATIVE_SYSTEM = """Jesteś Mistrzem Gry w grze RPG (samonarracja, tekst dla gracza).
Napisz krótką narrację (3–6 zdań, styl „Ty…” lub bezosobowo według konwencji kampanii), która:
- szanuje ukończenie wskazanego questa,
- płynnie wprowadza nowy kierunek fabularny zgodny z podanym szkicem nowego łuku,
- nie wymienia statystyk, rzutów ani JSON — czysta scena.
Bez nagłówków markdown."""


def _quests_completed_list(sheet: dict[str, Any]) -> list[str]:
    v = sheet.get("quests_completed")
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if x is not None and str(x).strip()]


def main_quest_just_completed(
    old_sheet: dict[str, Any],
    new_sheet: dict[str, Any],
    main_quest_key: str,
) -> bool:
    old_set = set(_quests_completed_list(old_sheet))
    new_set = set(_quests_completed_list(new_sheet))
    return main_quest_key in new_set and main_quest_key not in old_set


def resolve_main_quest_key(plan: dict[str, Any]) -> str:
    ep = plan.get("engine_private") if isinstance(plan.get("engine_private"), dict) else {}
    k = ep.get("main_quest_key")
    if isinstance(k, str) and k.strip():
        return k.strip()
    return DEFAULT_MAIN_QUEST_KEY


def _fetch_transcript_excerpt(conn: sqlite3.Connection, campaign_id: int, max_chars: int = 8000) -> str:
    rows = conn.execute(
        """
        SELECT user_text, assistant_text
        FROM campaign_turns
        WHERE campaign_id = ? AND route = 'narrative'
        ORDER BY turn_number ASC
        """,
        (campaign_id,),
    ).fetchall()
    parts: list[str] = []
    for r in rows:
        u = (r["user_text"] or "").strip()
        a = (r["assistant_text"] or "").strip()
        if u or a:
            parts.append(f"Gracz: {u}\nMG: {a}\n")
    blob = "\n".join(parts)
    if len(blob) <= max_chars:
        return blob
    return "…\n" + blob[-max_chars:]


def _next_new_arc_id(plan: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Zwraca wolny identyfikator `act_N` i zaktualizowany fragment engine_private (next_act_seq)."""
    ep_in = plan.get("engine_private") if isinstance(plan.get("engine_private"), dict) else {}
    ep = dict(ep_in)
    seq = int(ep.get("next_act_seq") or 2)
    arcs = plan.get("arcs") if isinstance(plan.get("arcs"), dict) else {}
    while True:
        cand = f"act_{seq}"
        if cand not in arcs:
            ep["next_act_seq"] = seq + 1
            return cand, ep
        seq += 1


def _build_char_summary(char_row: sqlite3.Row) -> str:
    sheet_raw = char_row["sheet_json"] or "{}"
    try:
        sheet = json.loads(sheet_raw) if isinstance(sheet_raw, str) else dict(sheet_raw)
    except json.JSONDecodeError:
        sheet = {}
    if not isinstance(sheet, dict):
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
    location = (char_row["location"] or "").strip() or "nieznane miejsce"
    name = (char_row["name"] or "").strip() or "Bohater"
    return (
        f"Postać: {name}, Archetyp: {archetype_label}, "
        f"HP: {hp}"
        + (f", Mana: {mana}" if mana else "")
        + (f", Statystyki: {stat_lines}" if stat_lines else "")
        + (f", Umiejętności: {skill_lines}" if skill_lines else "")
        + (f", Tło: {background}" if background else "")
        + f", Lokalizacja: {location}."
    )


def _generate_new_act_flat_plan_llm(
    *,
    campaign_title: str,
    campaign_language: str,
    system_id: str,
    completed_quest_key: str,
    prior_plan_excerpt: str,
    transcript_excerpt: str,
    char_summary: str,
    model: str,
    llm_config: dict[str, Any],
) -> dict[str, Any] | None:
    user_content = (
        f"Tytuł kampanii: {campaign_title}\n"
        f"Język: {campaign_language}\n"
        f"System (id): {system_id}\n\n"
        f"Ukończony główny quest (klucz): {completed_quest_key}\n\n"
        f"Poprzedni plan MG (łuk który właśnie się domyka — kontekst, nie do kopiowania):\n{prior_plan_excerpt or '(brak)'}\n\n"
        f"Ostatnia fabuła (skrót transkryptu):\n{transcript_excerpt or '(pusto)'}\n\n"
        f"{char_summary}\n\n"
        "Zaproponuj JSON nowego łuku fabularnego (roadmap, cele sceny, haki, tytuł)."
    )
    messages = [
        {"role": "system", "content": GM_PLAN_NEW_ACT_SYSTEM},
        {"role": "user", "content": user_content},
    ]
    raw = (generate_chat(messages=messages, model=model, llm_config=llm_config) or "").strip()
    parsed = extract_first_json_object(raw)
    return parsed if isinstance(parsed, dict) else None


def _generate_bridge_narrative_llm(
    *,
    campaign_language: str,
    completed_quest_key: str,
    new_arc_title: str,
    new_roadmap: str,
    transcript_tail: str,
    model: str,
    llm_config: dict[str, Any],
) -> str:
    tail = transcript_tail[-4000:] if len(transcript_tail) > 4000 else transcript_tail
    user_content = (
        f"Język odpowiedzi: {campaign_language}\n\n"
        f"Klucz ukończonego głównego questa: {completed_quest_key}\n\n"
        f"Nowy łuk — tytuł: {new_arc_title}\n"
        f"Zarys: {new_roadmap}\n\n"
        f"Ostatnie wydarzenia (fragment transkryptu):\n{tail or '(brak)'}\n\n"
        "Napisz narrację spinającą zakończenie questa z początkiem nowego łuku."
    )
    messages = [
        {"role": "system", "content": BRIDGE_NARRATIVE_SYSTEM},
        {"role": "user", "content": user_content},
    ]
    return (generate_chat(messages=messages, model=model, llm_config=llm_config) or "").strip()


def _get_next_turn_number(conn: sqlite3.Connection, campaign_id: int) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(turn_number), 0) AS max_turn
        FROM campaign_turns
        WHERE campaign_id = ?
        """,
        (campaign_id,),
    ).fetchone()
    return int(row["max_turn"] or 0) + 1


def _insert_narrative_turn(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_id: int,
    user_text: str,
    assistant_text: str,
) -> int:
    turn_number = _get_next_turn_number(conn, campaign_id)
    conn.execute(
        """
        INSERT INTO campaign_turns (
            campaign_id,
            character_id,
            user_text,
            route,
            assistant_text,
            turn_number
        )
        VALUES (?, ?, ?, 'narrative', ?, ?)
        """,
        (campaign_id, character_id, user_text, assistant_text, turn_number),
    )
    return turn_number


def run_new_act_pipeline(
    conn: sqlite3.Connection,
    *,
    campaign_id: int,
    character_id: int,
    completed_quest_key: str,
) -> dict[str, Any]:
    """
    Zamyka aktywny łuk, dodaje nowy z LLM, dopisuje turę narracji spinającej.
    Zwraca m.in. {"ok": True, "new_arc_id", "bridge_turn_number"} lub {"ok": False, "error": ...}.
    """
    camp = conn.execute(
        """
        SELECT id, title, system_id, model_id, language, owner_user_id, gm_plan_json, status
        FROM campaigns WHERE id = ?
        """,
        (campaign_id,),
    ).fetchone()
    if not camp:
        return {"ok": False, "error": "campaign_not_found"}
    if str(camp["status"] or "").lower() == "ended":
        return {"ok": False, "error": "campaign_ended"}

    if not gm_plan_is_ready(str(camp["gm_plan_json"] or "")):
        logger.warning("new_act_skipped_no_gm_plan", campaign_id=campaign_id)
        return {"ok": False, "error": "gm_plan_not_ready"}

    owner_id = int(camp["owner_user_id"] or 0)
    llm_config = get_user_llm_settings_full(owner_id)
    model = str(camp["model_id"] or "").strip() or "gemma3:1b"
    model = (llm_config.get("model") or "").strip() or model

    base = normalize_gm_plan(str(camp["gm_plan_json"] or ""))
    main_key = resolve_main_quest_key(base)
    if completed_quest_key != main_key:
        return {"ok": False, "error": "completed_quest_not_main", "main_quest_key": main_key}

    char = conn.execute(
        "SELECT id, name, sheet_json, location FROM characters WHERE id = ? AND campaign_id = ?",
        (character_id, campaign_id),
    ).fetchone()
    if not char:
        return {"ok": False, "error": "character_not_found"}

    prior_block = format_gm_plan_block(str(camp["gm_plan_json"] or ""))
    transcript = _fetch_transcript_excerpt(conn, campaign_id)
    char_summary = _build_char_summary(char)

    flat = _generate_new_act_flat_plan_llm(
        campaign_title=str(camp["title"] or f"Kampania {campaign_id}"),
        campaign_language=str(camp["language"] or "pl"),
        system_id=str(camp["system_id"] or ""),
        completed_quest_key=completed_quest_key,
        prior_plan_excerpt=prior_block,
        transcript_excerpt=transcript,
        char_summary=char_summary,
        model=model,
        llm_config=llm_config,
    )
    if not flat:
        logger.warning("new_act_plan_llm_parse_failed", campaign_id=campaign_id)
        return {"ok": False, "error": "new_act_plan_llm_parse_failed"}

    new_arc_id, ep_update = _next_new_arc_id(base)
    arc_inner = arc_payload_from_flat_llm(flat)
    arc_inner["id"] = new_arc_id
    arc_inner["status"] = "active"

    active_id = base.get("active_arc_id")
    if isinstance(active_id, str) and active_id.strip():
        active_id = active_id.strip()
    else:
        active_id = "default" if "default" in (base.get("arcs") or {}) else None

    arcs_patch: dict[str, Any] = {new_arc_id: arc_inner}
    if active_id and isinstance(base.get("arcs"), dict) and active_id in base["arcs"]:
        arcs_patch[active_id] = {"status": "closed"}

    merge_payload: dict[str, Any] = {
        "arcs": arcs_patch,
        "active_arc_id": new_arc_id,
        "engine_private": ep_update,
    }
    merged = merge_gm_plan_patch(base, merge_payload)
    dumped = json.dumps(merged, ensure_ascii=False)

    if not gm_plan_is_ready(dumped):
        logger.warning("new_act_plan_empty_after_merge", campaign_id=campaign_id)
        return {"ok": False, "error": "new_act_plan_empty"}

    conn.execute(
        "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
        (dumped, campaign_id),
    )

    new_node = merged.get("arcs", {}).get(new_arc_id, {}) if isinstance(merged.get("arcs"), dict) else {}
    new_title = str(new_node.get("title") or flat.get("title") or "Nowy łuk").strip()
    new_roadmap = str(new_node.get("roadmap") or flat.get("roadmap") or "").strip()

    bridge = _generate_bridge_narrative_llm(
        campaign_language=str(camp["language"] or "pl"),
        completed_quest_key=completed_quest_key,
        new_arc_title=new_title,
        new_roadmap=new_roadmap,
        transcript_tail=transcript,
        model=model,
        llm_config=llm_config,
    )
    if not bridge:
        bridge = (
            "Historia znajduje nowy kierunek — dotychczasowe wydarzenia zamykają się, "
            "a przed tobą otwierają się świeże tropy."
        )

    user_line = f"[Nowy akt] Ukończono główny quest „{completed_quest_key}”. Rozpoczyna się: {new_title}."
    turn_no = _insert_narrative_turn(
        conn,
        campaign_id=campaign_id,
        character_id=character_id,
        user_text=user_line,
        assistant_text=bridge,
    )
    conn.commit()
    logger.info(
        "new_act_ok",
        campaign_id=campaign_id,
        new_arc_id=new_arc_id,
        turn_number=turn_no,
    )
    return {
        "ok": True,
        "new_arc_id": new_arc_id,
        "bridge_turn_number": turn_no,
        "main_quest_key": main_key,
    }


def maybe_trigger_new_act_after_main_quest(
    *,
    campaign_id: int,
    character_id: int,
    old_sheet: dict[str, Any],
    new_sheet: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Jeśli właśnie domknięto główny quest (wg `engine_private.main_quest_key` lub domyślnie `main_quest`),
    uruchamia pipeline nowego aktu. Wywołaj po zapisie `sheet_json` postaci.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT gm_plan_json FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not row:
            return None
        plan = normalize_gm_plan(str(row["gm_plan_json"] or ""))
        main_key = resolve_main_quest_key(plan)
        if not main_quest_just_completed(old_sheet, new_sheet, main_key):
            return None
        return run_new_act_pipeline(
            conn,
            campaign_id=campaign_id,
            character_id=character_id,
            completed_quest_key=main_key,
        )
    except Exception as e:
        logger.warning(
            "new_act_trigger_failed",
            campaign_id=campaign_id,
            character_id=character_id,
            error=str(e),
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()
