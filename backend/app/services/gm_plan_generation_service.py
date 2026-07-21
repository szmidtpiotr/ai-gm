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


# Stage 9 follow-up: title placeholders we'll happily overwrite when the LLM
# plan produces a real title. Anything outside this pattern (admin-edited or
# user-renamed) is left alone.
_GENERIC_TITLE_RE = re.compile(
    r"^(?:Przygoda\s+\S+|Kampania(?:\s+#?\d+)?|Nowa\s+kampania|Bez\s+tytułu)$",
    re.IGNORECASE,
)


def _maybe_rename_campaign_from_plan(conn, campaign_id: int, plan: dict) -> None:
    """When the LLM plan carries a `title` and the current campaign title is
    still the generic placeholder, swap it for the atmospheric one.

    The plan shape is the W1 schema (`title` at top level). Some legacy plans
    nest it under `arcs[0].title` — handle both.
    """
    plan_title = ""
    if isinstance(plan, dict):
        # W1 schema: top-level title. V2 schema: arcs.default.title (dict)
        # or arcs[0].title (list — legacy).
        plan_title = str(plan.get("title") or "").strip()
        if not plan_title:
            arcs = plan.get("arcs")
            if isinstance(arcs, dict) and arcs:
                # Prefer the active arc, else the first one.
                active_arc = next(
                    (a for a in arcs.values()
                     if isinstance(a, dict) and str(a.get("status") or "").lower() == "active"),
                    None,
                ) or next(iter(arcs.values()))
                if isinstance(active_arc, dict):
                    plan_title = str(active_arc.get("title") or "").strip()
            elif isinstance(arcs, list) and arcs:
                first = arcs[0]
                if isinstance(first, dict):
                    plan_title = str(first.get("title") or "").strip()
    if not plan_title or len(plan_title) > 120:
        return  # nothing to write or suspicious length

    row = conn.execute(
        "SELECT title FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()
    if not row:
        return
    current = str((row[0] if isinstance(row, tuple) else row["title"]) or "").strip()
    if not _GENERIC_TITLE_RE.match(current):
        return  # admin/user has set a custom title — preserve it

    conn.execute(
        "UPDATE campaigns SET title = ? WHERE id = ?",
        (plan_title, campaign_id),
    )
    logger.info(
        "campaign_title_renamed_from_plan",
        campaign_id=campaign_id,
        old_title=current,
        new_title=plan_title,
    )

GM_PLAN_GENERATION_SYSTEM = """Jesteś asystentem projektowania kampanii RPG (notatki dla MG).
Zwróć WYŁĄCZNIE jeden obiekt JSON (bez markdown, bez komentarzy, bez tekstu przed/po), kształt:
{
  "roadmap": "string — 2–6 zdań: łuk fabularny, główne tropy i kierunek pierwszych scen",
  "scene_goals": ["3–6 krótkich celów pierwszej sceny startowej"],
  "hooks": { "npcs": ["2–5 imion lub ról"], "locations": ["2–5 miejsc lub typów lokacji"] },
  "title": "krótki tytuł aktywnego łuku (max ok. 80 znaków)"
}
Pisz po polsku jeśli kampania jest po polsku. To są notatki wewnętrzne MG — nie stylizuj na dialog z graczem."""


# #968: continuation variant — used when the campaign already has played turns.
# Builds a plan that picks up the story instead of restarting from scene 1.
GM_PLAN_CONTINUATION_SYSTEM = """Jesteś asystentem projektowania kampanii RPG (notatki dla MG).
Kampania jest JUŻ W TRAKCIE — poniżej dostaniesz streszczenie dotychczasowej rozgrywki.
Zbuduj plan KONTYNUUJĄCY fabułę od bieżącego momentu — NIE restartuj, NIE zaczynaj od sceny startowej.
Zwróć WYŁĄCZNIE jeden obiekt JSON (bez markdown, bez komentarzy, bez tekstu przed/po), kształt:
{
  "roadmap": "string — 2–6 zdań: dalszy łuk fabularny nawiązujący do dotychczasowych wydarzeń",
  "scene_goals": ["3–6 krótkich celów NAJBLIŻSZYCH scen (kontynuacja, nie start)"],
  "hooks": { "npcs": ["2–5 imion lub ról pasujących do obecnej sytuacji"], "locations": ["2–5 miejsc lub typów lokacji"] },
  "title": "krótki tytuł bieżącego/kolejnego łuku (max ok. 80 znaków)"
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


def _build_fallback_plan() -> dict[str, Any]:
    """Minimal GM plan used when all LLM generation attempts fail."""
    return {
        "schema_version": 2,
        "arcs": {
            "default": {
                "id": "default",
                "title": "Start przygody",
                "status": "active",
                "roadmap": "Bohater wyrusza w nieznane. Historia się dopiero zaczyna.",
                "scene_goals": ["Zapoznaj się z okolicą", "Znajdź kogoś, kto może pomóc"],
                "hooks": {
                    "npcs": ["Tajemniczy nieznajomy"],
                    "locations": ["Karczma", "Rynek"],
                },
            }
        },
        "active_arc_id": "default",
        "engine_private": {},
    }


# ── #1018: V2 structured plan (acts/key_beats/endings) for the player + admin tor ──


def _build_v2_fallback_plan() -> dict[str, Any]:
    """Minimal but *winnable* V2 plan used when LLM generation fails.

    Structured so the #1009–#1017 victory machinery can still drive it: 3 acts
    with non-optional beats (each marked `narrative_close` so it is closable via
    the narrator's [BEAT_COMPLETE] tag and never an orphan), plus two endings.
    """
    return {
        "title": "Start przygody",
        "premise": "Bohater wyrusza w nieznane. Historia dopiero się zaczyna.",
        "acts": [
            {
                "number": 1, "title": "Początek",
                "summary": "Bohater poznaje okolicę i natrafia na pierwszy trop.",
                "key_beats": [
                    {"beat_key": "poznaj_okolice", "summary": "Zapoznaj się z okolicą",
                     "optional": False, "narrative_close": True},
                    {"beat_key": "znajdz_pierwszy_trop", "summary": "Znajdź pierwszy trop",
                     "optional": False, "narrative_close": True},
                ],
                "completed": False,
            },
            {
                "number": 2, "title": "Rozwinięcie",
                "summary": "Konflikt narasta i wymaga konfrontacji.",
                "key_beats": [
                    {"beat_key": "stawienie_czola", "summary": "Stań do konfrontacji z przeszkodą",
                     "optional": False, "narrative_close": True},
                ],
                "completed": False,
            },
            {
                "number": 3, "title": "Finał",
                "summary": "Główny wątek dochodzi do rozstrzygnięcia.",
                "key_beats": [
                    {"beat_key": "domknij_glowny_watek", "summary": "Domknij główny wątek",
                     "optional": False, "narrative_close": True},
                ],
                "completed": False,
            },
        ],
        "endings": [
            {"id": "ending_primary", "title": "Zwycięstwo", "type": "primary",
             "description": "Bohater osiąga cel, choć nie bez kosztów.",
             "requirements": ["domknij_glowny_watek"]},
            {"id": "ending_alternate", "title": "Gorzki kompromis", "type": "alternate",
             "description": "Cel osiągnięty inną drogą, z moralnym ciężarem.",
             "requirements": []},
        ],
        "key_npcs": [
            {"key": "tajemniczy_nieznajomy", "name": "Tajemniczy nieznajomy",
             "role": "przewodnik", "importance": "supporting",
             "deviation_consequence": "steer", "alive": True},
        ],
        "key_locations": [
            {"key": "loc_start", "name": "Karczma", "role": "starting_point", "visited": False},
        ],
        "active_act": 1,
        "scene_log": [], "deviations": [], "branches": [],
        "engine_private": {
            "secret_predisposition_hint": "",
            "hidden_twist": "",
            "contingency": "",
        },
    }


def _store_v2_plan(
    conn,
    campaign_id: int,
    plan_public: dict[str, Any],
    engine_private: dict[str, Any],
    *,
    degraded: bool,
) -> None:
    """Persist a V2 plan: public part → gm_plan_json, engine_private → engine_private_json,
    plus plan_degraded. Falls back to inlining engine_private if the column is absent."""
    plan_json = json.dumps(plan_public, ensure_ascii=False)
    private_json = json.dumps(engine_private or {}, ensure_ascii=False)
    deg = 1 if degraded else 0
    try:
        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ?, engine_private_json = ?, plan_degraded = ? WHERE id = ?",
            (plan_json, private_json, deg, campaign_id),
        )
    except Exception:
        full = dict(plan_public)
        full["engine_private"] = engine_private or {}
        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ?, plan_degraded = ? WHERE id = ?",
            (json.dumps(full, ensure_ascii=False), deg, campaign_id),
        )
    try:
        _maybe_rename_campaign_from_plan(conn, campaign_id, plan_public)
    except Exception as e:
        logger.warning("campaign_title_rename_v2_failed", campaign_id=campaign_id, error=str(e))
    conn.commit()


def generate_initial_gm_plan_v2_with_retries(
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
    identity: dict[str, Any] | None = None,
    gm_only: dict[str, Any] | None = None,
    story_so_far: str = "",
    max_attempts: int = 3,
    hero_chronicle: str = "",
) -> tuple[bool, str | None]:
    """#1018 — generate a structured **V2** GM plan (acts/key_beats/endings) for the
    player "Nowa Kampania" tor and the admin "Regeneruj plan" (#966) tor.

    Validated against `CampaignPlan` + `normalize_plan_beats` (auto-slug beat_key),
    engine_private split off into `engine_private_json`. Backward compatible: old
    `arcs` plans still load (the loader keeps its arcs→acts fallback); only NEW
    campaigns get V2.

    Degrade-guard preserved: when the LLM keeps breaking the schema (weak PROD
    model — see project_prod_llm_degraded_plans), a *winnable* V2 fallback plan is
    written with plan_degraded=1 and (True, None) is returned so the campaign still
    starts. When `story_so_far` is provided the plan is generated in CONTINUATION
    mode (#968).
    """
    from pydantic import ValidationError

    from app.services.campaign_plan_service import (
        CampaignPlan,
        _SYSTEM_PROMPT,
        normalize_plan_beats,
    )

    story_so_far = (story_so_far or "").strip()
    identity = identity or {}
    gm_only = gm_only or {}

    # #1527 - plan GM nazywa NPC, lokacje i wrogow; bez konwencji rodza sie
    # wspolczesne polskie imiona i realne toponimy. Region planu nie jest tu
    # znany, wiec wchodzi regula ogolna #997.
    from app.services.world_naming_service import naming_prompt_block
    system_prompt = _SYSTEM_PROMPT + "\n\n" + naming_prompt_block(None, "")
    if story_so_far:
        system_prompt = (
            system_prompt
            + "\n\nUWAGA — KAMPANIA JEST JUŻ W TRAKCIE. Zbuduj plan KONTYNUUJĄCY fabułę "
              "od bieżącego momentu (na podstawie dotychczasowej rozgrywki poniżej). "
              "NIE restartuj historii, NIE zaczynaj od sceny startowej — akt 1 ma "
              "podejmować wątki z dotychczasowych wydarzeń."
        )

    user_lines: list[str] = [
        f"Tytuł kampanii: {campaign_title}",
        f"Język: {campaign_language}",
        f"System (id): {system_id}",
        "",
        char_summary,
    ]
    bonds = identity.get("bonds") or []
    weaknesses = identity.get("weaknesses") or []
    if bonds:
        user_lines.append(
            "\nWIĘZI BOHATERA:\n"
            + "\n".join(
                f"  - ({b.get('type', '?')}) {b.get('description', '')}"
                for b in bonds
                if isinstance(b, dict)
            )
        )
    if weaknesses:
        user_lines.append(
            "\nSŁABOŚCI BOHATERA:\n"
            + "\n".join(
                f"  - ({w.get('type', '?')}) {w.get('description', '')}"
                for w in weaknesses
                if isinstance(w, dict)
            )
        )
    secret = str(gm_only.get("secret_predisposition") or "").strip()
    if secret:
        user_lines.append(f"\nUKRYTA PREDYSPOZYCJA (TYLKO DLA MG, nie ujawniaj graczowi): {secret}")
    if (hero_chronicle or "").strip():
        user_lines.append(
            "\n" + hero_chronicle.strip()
            + "\nUwzględnij powyższą kronikę bohatera — nawiązuj do poprzednich czynów, "
              "powracających NPC i konsekwencji decyzji przy budowie nowego planu."
        )
    if story_so_far:
        user_lines.append(
            "\nDOTYCHCZASOWA ROZGRYWKA (streszczenie + ostatnie tury):\n" + story_so_far
        )
        user_lines.append(
            "\nNa tej podstawie zbuduj plan KONTYNUUJĄCY fabułę (akty z beatami, zakończenia)."
        )
    else:
        user_lines.append(
            "\nNa tej podstawie stwórz pełny, spersonalizowany plan kampanii "
            "(akty z beatami, zakończenia, kluczowe NPC i lokacje)."
        )
    user_content = "\n".join(user_lines)

    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    last_err: str | None = None
    last_raw: str = ""
    for attempt in range(1, max_attempts + 1):
        if attempt > 1 and last_raw:
            messages = base_messages + [
                {"role": "assistant", "content": last_raw},
                {
                    "role": "user",
                    "content": (
                        f"Poprzednia odpowiedź nie była poprawnym planem V2. Błąd: {last_err}. "
                        "Zwróć WYŁĄCZNIE poprawny obiekt JSON zgodny ze schematem "
                        "(acts[].key_beats[] jako OBIEKTY z beat_key, endings[]), bez tekstu przed/po."
                    ),
                },
            ]
        else:
            messages = base_messages

        try:
            raw = (generate_chat(messages=messages, model=model, llm_config=llm_config) or "").strip()
            last_raw = raw
            parsed = extract_first_json_object(raw)
            if not parsed:
                last_err = "LLM nie zwrócił poprawnego JSON planu V2"
                logger.warning(
                    "gm_plan_v2_parse_failed",
                    campaign_id=campaign_id,
                    attempt=attempt,
                    preview=(raw[:400] if raw else ""),
                )
                continue
            try:
                plan = CampaignPlan.model_validate(parsed)
            except ValidationError as ve:
                last_err = f"Walidacja schematu V2 nieudana: {ve.error_count()} błędów"
                logger.warning(
                    "gm_plan_v2_validation_failed",
                    campaign_id=campaign_id,
                    attempt=attempt,
                    errors=str(ve)[:300],
                )
                continue
            plan_public = plan.model_dump()
            engine_private = plan_public.pop("engine_private", {})
            normalize_plan_beats(plan_public)
            _store_v2_plan(conn, campaign_id, plan_public, engine_private, degraded=False)
            # #1284 — materialize plan key_enemies into real playable enemies (+ loot)
            # so Nowa Kampania / Regeneruj-plan campaigns aren't stuck with plan-only
            # fiction enemies that combat can never resolve. Non-fatal — plan is saved.
            try:
                from app.services.world_service import materialize_plan_enemies

                mat = materialize_plan_enemies(conn, plan_public.get("key_enemies") or [])
                if mat:
                    logger.info(
                        "gm_plan_enemies_materialized",
                        campaign_id=campaign_id,
                        count=len(mat),
                    )
            except Exception as _me:
                logger.warning(
                    "gm_plan_enemy_materialize_failed",
                    campaign_id=campaign_id,
                    error=str(_me),
                )
            logger.info(
                "gm_plan_v2_ok", campaign_id=campaign_id, attempt=attempt, title=plan.title
            )
            return True, None
        except Exception as e:
            last_err = str(e)
            logger.warning(
                "gm_plan_v2_attempt_failed",
                campaign_id=campaign_id,
                attempt=attempt,
                error=str(e),
            )

    # All attempts failed — winnable V2 fallback so the campaign always starts.
    fallback = _build_v2_fallback_plan()
    fb_private = fallback.pop("engine_private", {})
    try:
        _store_v2_plan(conn, campaign_id, fallback, fb_private, degraded=True)
        logger.warning(
            "gm_plan_v2_fallback_used", campaign_id=campaign_id, last_error=last_err
        )
    except Exception as e:
        logger.error("gm_plan_v2_fallback_save_failed", campaign_id=campaign_id, error=str(e))
    return True, None


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
    story_so_far: str = "",
    max_attempts: int = 3,
) -> tuple[bool, str | None]:
    """
    Persists to campaigns.gm_plan_json on success. Returns (ok, error_message).
    On complete failure writes a fallback plan and sets plan_degraded=1 — always returns (True, None).

    #968: when `story_so_far` is provided (campaign already has played turns), the
    plan is generated in CONTINUATION mode — picks up the story instead of
    restarting from the opening scene.
    """
    story_so_far = (story_so_far or "").strip()
    if story_so_far:
        system_prompt = GM_PLAN_CONTINUATION_SYSTEM
        user_content = (
            f"Tytuł kampanii: {campaign_title}\n"
            f"Język: {campaign_language}\n"
            f"System (id): {system_id}\n\n"
            f"{char_summary}\n\n"
            f"DOTYCHCZASOWA ROZGRYWKA (streszczenie + ostatnie tury):\n{story_so_far}\n\n"
            "Na tej podstawie zbuduj JSON planu MG KONTYNUUJĄCY fabułę od bieżącego momentu "
            "(roadmap nawiązuje do wydarzeń, cele = najbliższe sceny, haki pasują do obecnej sytuacji)."
        )
    else:
        system_prompt = GM_PLAN_GENERATION_SYSTEM
        user_content = (
            f"Tytuł kampanii: {campaign_title}\n"
            f"Język: {campaign_language}\n"
            f"System (id): {system_id}\n\n"
            f"{char_summary}\n\n"
            "Na tej podstawie wypełnij JSON planu MG (roadmap, cele sceny, haki, tytuł łuku)."
        )
    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    last_err: str | None = None
    last_raw: str = ""
    for attempt in range(1, max_attempts + 1):
        # On retry: inject previous bad response + error context so LLM knows what went wrong
        if attempt > 1 and last_raw:
            messages = base_messages + [
                {"role": "assistant", "content": last_raw},
                {
                    "role": "user",
                    "content": (
                        f"Poprzednia odpowiedź nie była poprawnym JSON planu. Błąd: {last_err}. "
                        "Spróbuj ponownie — zwróć WYŁĄCZNIE obiekt JSON bez żadnego tekstu przed ani po."
                    ),
                },
            ]
        else:
            messages = base_messages

        try:
            raw = (generate_chat(messages=messages, model=model, llm_config=llm_config) or "").strip()
            last_raw = raw
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
            empty_plan = normalize_gm_plan(None)
            merged = merge_gm_plan_patch(empty_plan, patch)
            dumped = json.dumps(merged, ensure_ascii=False)
            if not gm_plan_is_ready(dumped):
                last_err = "Wygenerowany plan jest zbyt pusty (brak roadmapy/celów/haków)"
                last_raw = raw
                logger.warning("gm_plan_generation_empty_plan", campaign_id=campaign_id, attempt=attempt)
                continue
            conn.execute(
                "UPDATE campaigns SET gm_plan_json = ?, plan_degraded = 0 WHERE id = ?",
                (dumped, campaign_id),
            )
            try:
                _maybe_rename_campaign_from_plan(conn, campaign_id, merged)
            except Exception as e:
                logger.warning("campaign_title_rename_failed", campaign_id=campaign_id, error=str(e))
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

    # All attempts failed — use fallback plan so campaign always starts
    fallback = _build_fallback_plan()
    fallback_dumped = json.dumps(fallback, ensure_ascii=False)
    try:
        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ?, plan_degraded = 1 WHERE id = ?",
            (fallback_dumped, campaign_id),
        )
        conn.commit()
        logger.warning(
            "gm_plan_generation_fallback_used",
            campaign_id=campaign_id,
            last_error=last_err,
        )
    except Exception as e:
        logger.error("gm_plan_fallback_save_failed", campaign_id=campaign_id, error=str(e))
    return True, None


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

    # #968: when the campaign has played turns, feed the story-so-far so the plan
    # continues the narrative instead of restarting from the opening scene.
    story_so_far = _build_story_so_far(conn, campaign_id)

    # #1096 — inject hero chronicle so regenerated plan knows the character's past.
    # regenerate=True lazily refreshes the flattened whole-life legend digest.
    hero_chronicle = ""
    try:
        from app.services.chapter_summary_service import get_hero_chronicle
        hero_chronicle = get_hero_chronicle(
            conn, int(char["id"]), user_id=int(owner_user_id), regenerate=True
        )
    except Exception:
        pass

    # #1018 — admin "Regeneruj plan" (#966) now produces a V2 plan
    # (acts/key_beats/endings) so regenerated campaigns are winnable, matching the
    # player tor. Pass through any V2 identity present on the sheet.
    return generate_initial_gm_plan_v2_with_retries(
        conn,
        campaign_id=campaign_id,
        campaign_title=str(camp["title"] or f"Kampania {campaign_id}"),
        campaign_language=str(camp["language"] or "pl"),
        system_id=str(camp["system_id"] or ""),
        char_summary=char_summary,
        user_id=int(owner_user_id),
        model=model,
        llm_config=llm_config,
        identity=sheet.get("identity") if isinstance(sheet, dict) else None,
        gm_only=sheet.get("gm_only") if isinstance(sheet, dict) else None,
        story_so_far=story_so_far,
        max_attempts=max_attempts,
        hero_chronicle=hero_chronicle,
    )


def _build_story_so_far(conn, campaign_id: int, *, recent_turns: int = 8) -> str:
    """#968: assemble a 'story so far' block (latest saved summary + last N turns)
    for history-aware GM plan regeneration. Empty string when nothing was played."""
    parts: list[str] = []
    try:
        from app.services.history_summary_service import (
            fetch_latest_saved_summary_for_narrative,
        )
        summ = fetch_latest_saved_summary_for_narrative(conn, campaign_id)
        if summ and str(summ.get("summary_text") or "").strip():
            parts.append("Streszczenie: " + str(summ["summary_text"]).strip())
    except Exception:
        pass

    try:
        rows = conn.execute(
            """
            SELECT user_text, assistant_text, turn_number
            FROM campaign_turns
            WHERE campaign_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (campaign_id, recent_turns),
        ).fetchall()
    except Exception:
        rows = []

    lines: list[str] = []
    for r in reversed(rows or []):
        try:
            u = str((r["user_text"] if not isinstance(r, tuple) else r[0]) or "").strip()
            a = str((r["assistant_text"] if not isinstance(r, tuple) else r[1]) or "").strip()
        except Exception:
            continue
        if u:
            lines.append(f"Gracz: {u[:300]}")
        if a:
            lines.append(f"MG: {a[:300]}")
    if lines:
        parts.append("Ostatnie tury:\n" + "\n".join(lines))

    return "\n\n".join(parts).strip()
