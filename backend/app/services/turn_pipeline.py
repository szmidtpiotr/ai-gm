"""
Turn Pipeline — V2 Phase 04 Task 11

The 9-step V2 turn processing pipeline.

Step 1: Receive input (free text or button action tag)
Step 2: Intent Parser — free text → ACTION tag (LLM call A)
Step 3: WSM validation — action legal in current state?
Step 4: DB Lookup — load records needed for resolution
Step 5: Mechanic Resolver — dice + outcome (no DB writes)
Step 6: World State Update — DB writes
Step 7: Context Injector — assemble narrator prompt
Step 8: LLM Narrator — narrate outcome (LLM call B)
Step 9: Return response with prose + state delta
"""

from __future__ import annotations

import json
import sqlite3
import time
import structlog

from app.services.intent_parser import (
    parse_intent, parse_structured_action, is_structured_action,
    generate_clarification_suggestions, ParsedIntent
)
from app.services.world_state_machine import WorldStateMachine, build_session_flags
from app.services.mechanic_resolver import resolve as mechanic_resolve
from app.services.context_injector import ContextInjector
from app.services.world_service import (
    process_create_tags, get_current_location_info,
    build_available_content_index, build_v2_npc_context_block,
    maybe_lazy_enrich_subloc,
)
from app.services.campaign_plan_runtime import (
    get_narrator_context_block, mark_beat_visited, mark_npc_dead, log_deviation
)
from app.services.vitality_service import stat_modifier
from app.services.llm_service import generate_chat
from app.services.skill_service import (
    calc_skill_modifier_info, intercept_skill_test_tag, intercept_trap_tag,
    build_skill_result_context,
)

logger = structlog.get_logger()

DB_PATH = "/data/ai_gm.db"

import re as _re_tp

# ── U30 / PT1: Keyword fast-path for MOVE intent ─────────────────────────────
# Single source of truth: hex_directions.py (PT1 fix for zachód ≠ południowy-zachód)

from app.services.hex_directions import DIRECTION_KEYWORDS as _DIRECTION_KEYWORDS

_MOVE_VERB_PATTERN = _re_tp.compile(
    r"\b(id[ęeę]|idz[ie]*|wr[aó]c[aę]|wroc[ae]|wyruszam[y]?|podroz?uj(?:[eę]|emy)|podróżuj(?:[eę]|emy)|"
    r"jad[eę]|biegne|biegnę|zmierzam|ruszam[y]?|wchodz[eę]|wchodze|"
    r"przechodze|przechodzę|wedruję|wędruję|pojd[eę]|pójd[eę]|idz|chodz|chodzmy|idziemy)\b",
    _re_tp.IGNORECASE | _re_tp.UNICODE,
)

_TRAVEL_NARRATIVE_MARKERS = _re_tp.compile(
    r"\b(wyruszasz?|podróżuj[ea]sz?|wyruszasz?|przemierzasz?|idziesz|wędrujesz?|"
    r"zmierzasz?|docierasz?|przybywa[sj]|wkraczasz?|opuszczasz?|opuszc[za]sz?|"
    r"przybywasz?|zbliżasz?|oddalasz?)\b",
    _re_tp.IGNORECASE | _re_tp.UNICODE,
)


def detect_move_intent(
    player_message: str,
    current_hex: dict | None,
    neighbors: dict | None = None,
) -> dict | None:
    """U30 keyword fast-path: detect directional MOVE intent WITHOUT LLM call.

    Returns None when the message doesn't look like directional movement.
    Returns {"action_type": "MOVEMENT", "params": {...}} on match.
    neighbors: {"north": (q,r), ...} — caller provides reachable neighbors.
    """
    text = player_message.strip().lower()

    # Must contain a movement verb
    if not _MOVE_VERB_PATTERN.search(text):
        return None

    # Look for cardinal direction keywords
    current_q = int((current_hex or {}).get("q", 0))
    current_r = int((current_hex or {}).get("r", 0))

    for direction_name, (dq, dr) in _DIRECTION_KEYWORDS.items():
        if direction_name in text:
            dest_q = current_q + dq
            dest_r = current_r + dr
            return {
                "action_type": "MOVEMENT",
                "params": {
                    "direction": direction_name,
                    "destination_q": dest_q,
                    "destination_r": dest_r,
                },
            }

    return None


# ── #1050: Vague move intent detection + hint builder ────────────────────────

def detect_vague_move_intent(player_message: str) -> bool:
    """Return True when message has movement verb but no cardinal direction (#1050).

    Triggers narrator hint injection so the LLM asks where the player wants to go
    instead of inventing a destination.
    """
    text = player_message.strip().lower()
    if not _MOVE_VERB_PATTERN.search(text):
        return False
    for direction_name in _DIRECTION_KEYWORDS:
        if direction_name in text:
            return False
    return True


def _build_vague_move_hint(conn: "sqlite3.Connection", session_flags: dict) -> str:
    """Build [SYSTEM: ...] hint for narrator when player movement intent is vague (#1050).

    Looks up adjacent hex labels from world_hexes so the narrator can offer real options.
    """
    cur = session_flags.get("current_hex") or {"q": 0, "r": 0}
    q, r = int(cur.get("q", 0)), int(cur.get("r", 0))

    from app.services.hex_travel_service import hex_neighbors
    neighbor_coords = hex_neighbors(q, r)

    location_hints: list[str] = []
    max_hints = 4
    for nq, nr in neighbor_coords:
        if len(location_hints) >= max_hints:
            break
        row = conn.execute(
            "SELECT label, hex_type, location_key FROM world_hexes "
            "WHERE q=? AND r=? AND is_active=1 AND map_level=0",
            (nq, nr),
        ).fetchone()
        if not row:
            continue
        name = row["label"] or row["hex_type"] or f"({nq},{nr})"
        if row["location_key"]:
            loc = conn.execute(
                "SELECT label FROM game_locations WHERE key=? LIMIT 1",
                (row["location_key"],),
            ).fetchone()
            if loc and loc["label"]:
                name = loc["label"]
        location_hints.append(name)

    if location_hints:
        options = ", ".join(location_hints)
        body = (
            "Gracz nie podał kierunku ani celu podróży. Zapytaj dokąd zmierza. "
            f"Możliwe pobliskie miejsca: {options}. "
            "NIE opisuj wyruszenia — gracz stoi w miejscu."
        )
    else:
        body = (
            "Gracz nie podał kierunku ani celu podróży. Zapytaj dokąd zmierza. "
            "NIE opisuj wyruszenia — gracz stoi w miejscu."
        )
    return f"\n[SYSTEM: {body}]"


# ── U30: Anty-desync guard ────────────────────────────────────────────────────

def _check_travel_desync(
    narrative: str,
    action_type: str,
    campaign_id: int,
) -> bool:
    """U30: Detect when LLM narrates travel but no MOVEMENT mechanic fired.

    Logs 'travel_narrated_without_move' warning and returns True when desync detected.
    Returns False when clean (MOVEMENT did happen, or no travel language in narrative).
    """
    if action_type == "MOVEMENT":
        return False
    if not _TRAVEL_NARRATIVE_MARKERS.search(narrative or ""):
        return False
    logger.warning(
        "travel_narrated_without_move",
        campaign_id=campaign_id,
        action_type=action_type,
        snippet=(narrative or "")[:120],
    )
    return True


# ── U30 (#578): shared live-tor helpers ───────────────────────────────────────
# Both the JSON handler (create_turn) and the streaming handler (create_turn_stream)
# resolve directional MOVE intents through ONE helper so "idę na północ" moves the hex
# on both endpoints, and run ONE guard that records narration↔state desync.

def execute_directional_travel(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    character_sheet: dict,
    player_text: str,
) -> dict:
    """U30 directional fast-path — resolve a free-text MOVE intent mechanically BEFORE the LLM.

    Reads the current hex from `game_sessions.session_flags`, detects a directional MOVE
    intent (`detect_move_intent`), and on match calls `resolve_chain_travel`. On success the
    game clock is advanced. Returns:
      {"executed": bool, "system_fact": str|None, "intent": dict|None}
    `system_fact` is a [SYSTEM: …] line to inject into the narrator prompt so the LLM narrates
    the resolved move (or the refusal). `executed` is True only when the hex actually changed.
    """
    gs = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    flags = json.loads((gs["session_flags"] if gs else None) or "{}")
    cur = flags.get("current_hex") or {"q": 0, "r": 0}

    # PT6 #1116: player continues interrupted travel after combat
    tp = flags.get("travel_plan")
    if tp and tp.get("interrupt_reason") == "encounter_prompted" and detect_travel_continuation(player_text):
        from app.services.hex_travel_service import resolve_chain_travel as _rct_resume
        dest_hex = tp.get("destination_hex") or {}
        dq_r, dr_r = int(dest_hex.get("q", 0)), int(dest_hex.get("r", 0))
        dest_label_r = tp.get("destination_label") or f"hex ({dq_r},{dr_r})"
        tr_r = _rct_resume(
            campaign_id=campaign_id,
            character_id=character_id,
            from_hex=(int(cur["q"]), int(cur["r"])),
            to_hex=(dq_r, dr_r),
            character_sheet=character_sheet,
            conn=conn,
        )
        if tr_r.get("ok"):
            try:
                from app.services.clock_service import advance_clock
                hrs_r = float(tr_r.get("total_hours") or 0.0)
                if hrs_r > 0:
                    advance_clock(campaign_id, hrs_r, "travel", conn=conn)
                    conn.commit()
            except Exception as _clk_r:
                logger.warning("pt6_resume_clock_failed", error=str(_clk_r))
            arr_r = tr_r.get("arrived_hex") or {}
            enc_r = tr_r.get("encounter")
            hex_info_r = tr_r.get("hex_data") or {}
            fact_r = (
                f"\n[SYSTEM: Gracz wznowił podróż do {dest_label_r}. "
                f"Przemieścił się na hex ({arr_r.get('q')},{arr_r.get('r')}), "
                f"teren: {hex_info_r.get('hex_type', 'nieznany')}, "
                f"czas: {tr_r.get('total_hours', 0)}h."
            )
            if enc_r:
                fact_r += (
                    f" Nowe spotkanie: {enc_r.get('enemy_key')} — opisz nadejście zagrożenia."
                )
            else:
                fact_r += f" Gracz dotarł do celu: {dest_label_r}."
            fact_r += " Opisz wznowienie podróży w 2-4 zdaniach. NIE przenoś gracza — ruch rozstrzygnięty.]"
            logger.info("pt6_travel_resumed", campaign_id=campaign_id, destination=dest_label_r)
            return {"executed": True, "system_fact": fact_r, "intent": None}

    mv = detect_move_intent(player_text, cur)
    if not mv:
        # PT3/#1113: before vague-move hint, check for a named destination on a different hex
        if detect_vague_move_intent(player_text):
            from app.services.hex_travel_service import (
                resolve_player_text_to_location_key,
                detect_named_destination_hex,
                resolve_chain_travel as _rct_named,
            )
            _named_key = resolve_player_text_to_location_key(player_text, conn)
            if _named_key:
                _named_hex = detect_named_destination_hex(_named_key, cur, conn)
                if _named_hex:
                    # Cross-hex named destination → chain travel (same as directional)
                    dq_n, dr_n = _named_hex
                    _loc_row_n = conn.execute(
                        "SELECT label FROM game_locations WHERE key = ? LIMIT 1",
                        (_named_key,),
                    ).fetchone()
                    _loc_label_n = _loc_row_n["label"] if _loc_row_n else _named_key
                    tr_n = _rct_named(
                        campaign_id=campaign_id,
                        character_id=character_id,
                        from_hex=(int(cur["q"]), int(cur["r"])),
                        to_hex=(dq_n, dr_n),
                        character_sheet=character_sheet,
                        conn=conn,
                    )
                    if tr_n.get("ok"):
                        try:
                            from app.services.clock_service import advance_clock
                            hours_n = float(tr_n.get("total_hours") or 0.0)
                            if hours_n > 0:
                                advance_clock(campaign_id, hours_n, "travel", conn=conn)
                                conn.commit()
                        except Exception as _clk_err:
                            logger.warning("pt3_clock_advance_failed", error=str(_clk_err))

                        arr_n = tr_n.get("arrived_hex") or {}
                        hex_info_n = tr_n.get("hex_data") or {}
                        enc_n = tr_n.get("encounter")
                        fact_n = (
                            f"\n[SYSTEM: Podróż do {_loc_label_n} wykonana mechanicznie: gracz "
                            f"przemieścił się na hex ({arr_n.get('q')},{arr_n.get('r')}), "
                            f"teren: {hex_info_n.get('hex_type', 'nieznany')}, "
                            f"czas podróży: {tr_n.get('total_hours', 0)}h."
                        )
                        if enc_n:
                            fact_n += (
                                f" Podróż przerwana spotkaniem: {enc_n.get('enemy_key')} — "
                                "opisz nadejście zagrożenia."
                            )
                        fact_n += (
                            " Opisz tę podróż w 2-4 zdaniach. NIE przenoś gracza do innej"
                            " lokacji — ruch już rozstrzygnięty mechanicznie.]"
                        )
                        logger.info(
                            "pt3_named_destination_travel",
                            campaign_id=campaign_id,
                            location_key=_named_key,
                            from_hex=(cur.get("q"), cur.get("r")),
                            to_hex=_named_hex,
                        )
                        return {"executed": True, "system_fact": fact_n, "intent": None}

                    fact_n = (
                        f"\n[SYSTEM: Gracz próbuje dotrzeć do '{_loc_label_n}', "
                        f"ale mechanika odmówiła: {tr_n.get('error', 'nieprzejezdny teren')}. "
                        "Opisz przeszkodę narracyjnie. NIE opisuj dotarcia do celu.]"
                    )
                    return {"executed": False, "system_fact": fact_n, "intent": None}

                # Named dest found but same hex → let LLM handle via location_intent
                return {"executed": False, "system_fact": None, "intent": None}

            # No named destination found → fall through to vague hint
            hint = _build_vague_move_hint(conn, flags)
            return {"executed": False, "system_fact": hint, "intent": None}
        return {"executed": False, "system_fact": None, "intent": None}

    from app.services.hex_travel_service import resolve_chain_travel

    dq = int(mv["params"]["destination_q"])
    dr = int(mv["params"]["destination_r"])
    tr = resolve_chain_travel(
        campaign_id=campaign_id,
        character_id=character_id,
        from_hex=(int(cur["q"]), int(cur["r"])),
        to_hex=(dq, dr),
        character_sheet=character_sheet,
        conn=conn,
    )

    if tr.get("ok"):
        try:
            from app.services.clock_service import advance_clock
            hours = float(tr.get("total_hours") or 0.0)
            if hours > 0:
                advance_clock(campaign_id, hours, "travel", conn=conn)
                conn.commit()
        except Exception as clk_err:  # clock must never break a turn
            logger.warning("u30_clock_advance_failed", error=str(clk_err))

        arr = tr.get("arrived_hex") or {}
        hex_info = tr.get("hex_data") or {}
        enc = tr.get("encounter")
        fact = (
            f"\n[SYSTEM: Podróż wykonana mechanicznie: gracz przemieścił się na hex "
            f"({arr.get('q')},{arr.get('r')}), teren: {hex_info.get('hex_type', 'nieznany')}, "
            f"czas podróży: {tr.get('total_hours', 0)}h."
        )
        if enc:
            fact += (
                f" Podróż przerwana spotkaniem: {enc.get('enemy_key')} — "
                "opisz nadejście zagrożenia."
            )
        fact += (
            " Opisz tę podróż w 2-4 zdaniach. NIE przenoś gracza do innej lokacji — "
            "ruch już rozstrzygnięty mechanicznie.]"
        )
        return {"executed": True, "system_fact": fact, "intent": mv}

    fact = (
        f"\n[SYSTEM: Gracz próbuje podróżować w kierunku "
        f"'{mv['params'].get('direction')}', ale mechanika odmówiła: "
        f"{tr.get('error', 'nieprzejezdny teren')}. Opisz przeszkodę narracyjnie. "
        "NIE opisuj dotarcia do celu.]"
    )
    return {"executed": False, "system_fact": fact, "intent": mv}


def _build_desync_correction_fact(
    conn: "sqlite3.Connection",
    session_flags: dict,
    consecutive: int,
) -> str:
    """PT4 #1114: Build [SYSTEM:...] corrective fact for the next turn's narrator.

    consecutive >= 2 triggers a stronger hint that includes the neighbor hex list
    (same lookup pattern as _build_vague_move_hint).
    """
    loc_label = ""
    loc_key = session_flags.get("current_location_key") or session_flags.get("location_key", "")
    if loc_key:
        row = conn.execute(
            "SELECT label FROM game_locations WHERE key = ? LIMIT 1", (loc_key,)
        ).fetchone()
        if row and row["label"]:
            loc_label = row["label"]
    if not loc_label:
        cur = session_flags.get("current_hex") or {}
        loc_label = f"hex ({cur.get('q', '?')},{cur.get('r', '?')})"

    base = (
        f"W poprzedniej turze narracja opisała podróż, ale pozycja gracza się NIE zmieniła "
        f"— gracz nadal jest w: {loc_label}. "
        "Skoryguj narrację lub poproś gracza o kierunek/cel podróży. "
        "NIE opisuj wyruszenia ani wędrówki — gracz stoi w miejscu."
    )

    if consecutive >= 2:
        cur = session_flags.get("current_hex") or {"q": 0, "r": 0}
        q, r = int(cur.get("q", 0)), int(cur.get("r", 0))
        from app.services.hex_travel_service import hex_neighbors
        location_hints: list[str] = []
        for nq, nr in hex_neighbors(q, r):
            if len(location_hints) >= 4:
                break
            row = conn.execute(
                "SELECT label, hex_type, location_key FROM world_hexes "
                "WHERE q=? AND r=? AND is_active=1 AND map_level=0",
                (nq, nr),
            ).fetchone()
            if not row:
                continue
            name = row["label"] or row["hex_type"] or f"({nq},{nr})"
            if row["location_key"]:
                loc_row = conn.execute(
                    "SELECT label FROM game_locations WHERE key=? LIMIT 1",
                    (row["location_key"],),
                ).fetchone()
                if loc_row and loc_row["label"]:
                    name = loc_row["label"]
            location_hints.append(name)
        if location_hints:
            base += f" Pobliskie miejsca: {', '.join(location_hints)}."

    return f"\n[SYSTEM: {base}]"


def _reset_desync_counter(conn: sqlite3.Connection, campaign_id: int) -> None:
    """PT4 #1114: Clear consecutive desync counter from session_flags on a clean turn."""
    try:
        gs = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not gs:
            return
        flags = json.loads(gs["session_flags"] or "{}")
        if flags.get("travel_desync_consecutive", 0) > 0:
            flags.pop("travel_desync_consecutive", None)
            flags.pop("travel_desync_correction", None)
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                (json.dumps(flags, ensure_ascii=False), gs["id"]),
            )
            conn.commit()
    except Exception as e:
        logger.warning("travel_desync_counter_reset_failed", error=str(e))


def guard_travel_desync(
    conn: sqlite3.Connection,
    campaign_id: int,
    narrative: str,
    move_executed: bool,
    turn_number: int = 0,
) -> bool:
    """U30.4 anti-desync guard, wired into the live tor (#578).

    When the narrator claims travel (`_TRAVEL_NARRATIVE_MARKERS`) but no mechanical move
    happened this turn, record `travel_narrated_without_move` in `llm_tag_errors` so the
    desync is measurable (gate criterion B6) and visible. Returns True when a desync is
    flagged. Never raises.

    PT4 #1114: on desync, also saves a corrective [SYSTEM:...] fact to session_flags
    so the NEXT turn's narrator prompt is corrected. Tracks consecutive desync count —
    2+ consecutive triggers a stronger hint with the neighbor hex list.
    """
    if move_executed:
        _reset_desync_counter(conn, campaign_id)
        return False
    if not _TRAVEL_NARRATIVE_MARKERS.search(narrative or ""):
        return False
    logger.warning(
        "travel_narrated_without_move",
        campaign_id=campaign_id,
        snippet=(narrative or "")[:120],
    )
    try:
        from app.services.llm_tag_parser import log_tag_error
        log_tag_error(
            conn, campaign_id, turn_number, (narrative or "")[:120],
            "travel_narrated_without_move",
        )
    except Exception as log_err:  # logging must not crash a turn
        logger.warning("travel_desync_log_failed", error=str(log_err))

    # PT4 #1114: save corrective fact for next turn
    try:
        gs = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if gs:
            flags = json.loads(gs["session_flags"] or "{}")
            consecutive = flags.get("travel_desync_consecutive", 0) + 1
            flags["travel_desync_consecutive"] = consecutive
            flags["travel_desync_correction"] = _build_desync_correction_fact(
                conn, flags, consecutive
            )
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                (json.dumps(flags, ensure_ascii=False), gs["id"]),
            )
            conn.commit()
            logger.info(
                "travel_desync_correction_saved",
                campaign_id=campaign_id,
                consecutive=consecutive,
            )
    except Exception as corr_err:
        logger.warning("travel_desync_correction_save_failed", error=str(corr_err))

    return True


def pop_desync_correction(conn: sqlite3.Connection, campaign_id: int) -> str | None:
    """PT4 #1114: Read and clear travel desync correction from session_flags.

    Returns the [SYSTEM:...] correction string to inject into the current turn's
    narrator prompt, or None if no pending correction.
    """
    try:
        gs = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not gs:
            return None
        flags = json.loads(gs["session_flags"] or "{}")
        correction = flags.pop("travel_desync_correction", None)
        if correction:
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                (json.dumps(flags, ensure_ascii=False), gs["id"]),
            )
            conn.commit()
        return correction
    except Exception as e:
        logger.warning("pop_desync_correction_failed", error=str(e))
        return None


# ── PT6 #1116: travel_plan post-combat hint ───────────────────────────────────

_TRAVEL_CONTINUATION_KEYWORDS = [
    "kontynuuj", "idę dalej", "ruszam dalej", "lecę dalej", "wróćmy na szlak",
    "wracam na szlak", "tak dalej", "resume", "continue travel",
    "tak, kontynuuję", "tak idę dalej",
]


def detect_travel_continuation(player_text: str) -> bool:
    """PT6 #1116: Detect 'continue travel' intent from post-combat player prose."""
    t = player_text.lower().strip()
    return any(kw in t for kw in _TRAVEL_CONTINUATION_KEYWORDS)


def pop_travel_plan_hint(conn: "sqlite3.Connection", campaign_id: int) -> str | None:
    """PT6 #1116 + PT7 #1117: Inject narrator hint when travel was interrupted.

    Handles three interrupt reasons:
    - "encounter": combat interrupted travel → ask continue/rest/camp
    - "dusk": 8h daily budget reached → ask continue (night march, risky) or camp
    - "forced_camp": 12h hard cap → inform player of forced camp

    Fires once per interrupt (marks reason as *_prompted). Returns None if no
    travel_plan, combat still active, or hint already shown.
    """
    try:
        gs = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not gs:
            return None
        flags = json.loads(gs["session_flags"] or "{}")
        tp = flags.get("travel_plan")
        if not tp:
            return None

        reason = tp.get("interrupt_reason")
        if reason not in ("encounter", "dusk", "forced_camp"):
            return None

        dest_label = tp.get("destination_label") or (
            f"hex ({tp.get('destination_hex', {}).get('q')},{tp.get('destination_hex', {}).get('r')})"
        )
        remaining = int(tp.get("hours_remaining", 0))

        if reason == "encounter":
            # Don't prompt while combat is still ongoing
            ac = conn.execute(
                "SELECT 1 FROM active_combat WHERE campaign_id = ? AND status = 'active' LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if ac:
                return None
            hint = (
                f"\n[SYSTEM: Gracz był w trakcie podróży do {dest_label}, "
                f"zostało ~{remaining}h drogi. Walka przerwała wyprawę. "
                f"Zapytaj gracza (prozą): czy kontynuuje podróż do {dest_label}, "
                f"chce odpocząć (/rest), czy rozbija obóz. Nie decyduj za gracza — zadaj pytanie.]"
            )
            flags["travel_plan"]["interrupt_reason"] = "encounter_prompted"

        elif reason == "dusk":
            # PT7: dusk prompt — ask player: camp or continue (night march, risky)
            hint = (
                f"\n[SYSTEM: zapada zmierzch po 8h marszu. "
                f"Zapytaj gracza: czy rozbija obóz (/camp), czy maszeruje dalej "
                f"mimo zmęczenia i ciemności? Cel: {dest_label} (~{remaining}h drogi). "
                f"Nocny marsz = zwiększone ryzyko napaści (×1.5). "
                f"Nie decyduj za gracza — zadaj pytanie prozą.]"
            )
            flags["travel_plan"]["interrupt_reason"] = "dusk_prompted"

        elif reason == "forced_camp":
            # PT7: hard cap — player collapses, forced camp
            hint = (
                f"\n[SYSTEM: gracz pada z sił po 12h marszu — "
                f"wymuszone zatrzymanie. Opisz rozbicie obozu w trybie awaryjnym. "
                f"Cel {dest_label} czeka na świt. Nocne czuwanie = zwiększone ryzyko napaści.]"
            )
            flags["travel_plan"]["interrupt_reason"] = "forced_camp_prompted"

        else:
            return None

        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), gs["id"]),
        )
        conn.commit()
        return hint
    except Exception as e:
        logger.warning("pop_travel_plan_hint_failed", error=str(e))
        return None


# ── Main pipeline function ─────────────────────────────────────────────────

def process_v2_turn(
    user_input: str,
    campaign_id: int,
    character_id: int,
    session_flags: dict,
    llm_config: dict,
    model: str,
    conn: sqlite3.Connection,
) -> dict:
    """
    Full 9-step V2 turn pipeline.

    Returns dict with:
      prose: str — Polish narrative for player
      state: dict — HP, mana, location, XP deltas
      system_message: str | None — for validation failures (no LLM)
      current_location: dict | None
      turn_number: int
      action_type: str
    """
    t_start = time.perf_counter()
    _skill_pending = None  # set if narrator embeds [SKILL_TEST] or [TRAP] tag
    _vague_move = False  # #1050: set when player has movement verb but no direction

    # ── Step 1: Parse input ────────────────────────────────────────────────
    if is_structured_action(user_input):
        parsed = parse_structured_action(user_input)
    elif _move := detect_move_intent(user_input, session_flags.get("current_hex")):
        # U30 keyword fast-path: directional text → MOVEMENT without LLM call
        parsed = ParsedIntent(action_type=_move["action_type"], params=_move["params"], raw_tag="")
    else:
        # #1050: detect vague movement before LLM parse so we can inject hint later
        _vague_move = detect_vague_move_intent(user_input)
        loc_info = get_current_location_info(conn, campaign_id)
        location_key = (session_flags.get("current_location_key") or
                        (loc_info["key"] if loc_info else ""))

        npc_rows = conn.execute(
            """SELECT n.key, n.label FROM location_npc_assignments lna
               JOIN npcs n ON n.key = lna.npc_key
               WHERE lna.location_key = ? AND n.is_active = 1 LIMIT 5""",
            (location_key,)
        ).fetchall() if location_key else []

        enemy_rows = conn.execute(
            """SELECT e.key, e.label FROM location_enemy_assignments lea
               JOIN game_config_enemies e ON e.key = lea.enemy_key
               WHERE lea.location_key = ? AND e.is_active = 1 LIMIT 5""",
            (location_key,)
        ).fetchall() if location_key else []

        combat_roster = session_flags.get("combat_roster", [])
        char_row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        sheet = json.loads((char_row or {}).get("sheet_json") or "{}") if char_row else {}
        inv_keys = [
            k for k in (r["item_key"] or r["weapon_key"] for r in conn.execute(
                "SELECT item_key, weapon_key FROM character_inventory WHERE character_id = ?",
                (character_id,)
            ).fetchall())
            if k and k != "__narrative__"
        ] if character_id else []

        dest_keys = [r[0] for r in conn.execute(
            """SELECT to_location_key FROM location_connections WHERE from_location_key = ? AND is_active=1
               UNION SELECT from_location_key FROM location_connections
               WHERE to_location_key = ? AND is_bidirectional=1 AND is_active=1""",
            (location_key, location_key)
        ).fetchall()] if location_key else []

        parsed = parse_intent(
            player_message=user_input,
            game_state=session_flags.get("state", "NARRATIVE"),
            current_location_key=location_key,
            current_location_name=loc_info["label"] if loc_info else "",
            combat_roster=combat_roster,
            npcs_present=[{"key": r["key"], "name": r["label"]} for r in npc_rows],
            inventory_keys=inv_keys,
            available_destination_keys=dest_keys,
            llm_config=llm_config,
        )

    action_type = parsed.action_type
    params = parsed.params

    # ── Step 3: WSM Validation ─────────────────────────────────────────────
    if action_type in ("CLARIFY", "BLOCKED"):
        suggestions = generate_clarification_suggestions(
            session_flags.get("state", "NARRATIVE"),
            session_flags.get("combat_roster", []),
            [],
            []
        )
        msg = "Nie rozumiem. Co próbujesz zrobić?"
        if suggestions:
            msg += "\n" + "\n".join(f"  • {s}" for s in suggestions)
        return _system_response(msg, session_flags, campaign_id, conn)

    wsm = WorldStateMachine(conn)
    wsm_result = wsm.validate_and_route(
        session_flags=session_flags,
        action_type=action_type,
        params=params,
        character_id=character_id,
        campaign_id=campaign_id,
    )

    if not wsm_result.valid:
        return _system_response(wsm_result.blocked_message or "Akcja zablokowana.",
                                 session_flags, campaign_id, conn)

    # ── Step 4: DB Lookup ─────────────────────────────────────────────────
    context = _load_action_context(action_type, params, character_id, campaign_id, session_flags, conn)

    # ── SKILL_ATTEMPT early-return: send Roll Popup to player ─────────────
    if action_type == "SKILL_ATTEMPT":
        return _return_skill_test_pending(
            params, context, session_flags, wsm_result,
            campaign_id, character_id, conn
        )

    # ── Step 5: Mechanic Resolver ─────────────────────────────────────────
    mechanic_result = mechanic_resolve(action_type, params, context)
    mechanic_result["action_type"] = action_type  # ensure action_type propagated for downstream checks

    # ── Step 6: World State Update ────────────────────────────────────────
    turn_number = _get_next_turn_number(campaign_id, conn)
    _apply_world_state(mechanic_result, context, character_id, campaign_id, turn_number, conn)
    _update_session_flags(wsm_result, session_flags, mechanic_result, conn, campaign_id)
    _update_turns_at_location(mechanic_result, session_flags, conn, campaign_id)
    _update_hex_world_state(mechanic_result, session_flags, conn, campaign_id)

    # XS1: Beat complete XP (LLM-emitted [BEAT_COMPLETE] tag)
    xp_delta = _process_beat_signals(mechanic_result, campaign_id, character_id, turn_number, conn)
    # U8 #532: Beat auto-complete from objective conditions (kill/visit/talk/item)
    _auto_complete_beats_by_mechanic(action_type, mechanic_result, context, campaign_id, turn_number, conn)
    # XS6: First NPC talk XP
    xp_delta += _process_npc_first_talk(action_type, params.get("npc_key") or params.get("target", ""),
                                         character_id, campaign_id, turn_number, conn)
    # XS15: Session start bonus
    xp_delta += _process_session_start(character_id, campaign_id, turn_number, conn)

    # ── Step 7: Context Injector ──────────────────────────────────────────
    refreshed_flags = _reload_session_flags(campaign_id, conn) or session_flags

    # Add available content index + V2 NPC context to mechanic result for injector
    location_key = refreshed_flags.get("current_location_key", "")
    content_index = build_available_content_index(conn, location_key, character_id=character_id)
    npc_context = build_v2_npc_context_block(conn, location_key,
                                              player_text=user_input,
                                              topic=params.get("topic", ""))
    campaign_context = get_narrator_context_block(campaign_id, conn)

    if content_index:
        mechanic_result["available_content_index"] = content_index
    if npc_context:
        mechanic_result["npc_context"] = npc_context
    if campaign_context:
        mechanic_result["campaign_context"] = campaign_context

    narrator_prompt = ContextInjector(conn).build(
        session_flags=refreshed_flags,
        mechanic_result=mechanic_result,
        action_type=action_type,
        character_id=character_id,
        campaign_id=campaign_id,
        player_message=user_input,
    )

    # #1050: inject vague-move hint so narrator asks for destination, not invents one
    if _vague_move:
        narrator_prompt += _build_vague_move_hint(conn, refreshed_flags)

    # ── Step 8: LLM Narrator ──────────────────────────────────────────────
    try:
        prose_raw = generate_chat(
            messages=[{"role": "user", "content": narrator_prompt}],
            model=model,
            llm_config=llm_config,
        ) or ""
    except Exception as e:
        logger.warning("turn_pipeline_narrator_error", error=str(e))
        prose_raw = _fallback_prose(action_type, mechanic_result)

    # Process CREATE tags and NPC_KILLED from narrator response
    prose, _ = process_create_tags(prose_raw, conn, campaign_id)

    # Intercept [SKILL_TEST:...] and [TRAP:...] tags from narrator prose
    sheet_row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (character_id,)).fetchone()
    _sheet = json.loads((sheet_row[0] if sheet_row else None) or "{}")
    prose, _skill_pending = intercept_skill_test_tag(prose, conn, campaign_id, character_id)
    if not _skill_pending:
        prose, _skill_pending = intercept_trap_tag(prose, conn, campaign_id, character_id, _sheet)
    if _skill_pending:
        # Store pending in session_flags and set state
        session_flags["pending_skill_test"] = _skill_pending
        session_flags["state"] = "SKILL_TEST_PENDING"
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (json.dumps(session_flags, ensure_ascii=False), campaign_id),
        )
        conn.commit()

    # XS2-XS4/XS7-XS8/XS12: Parse narrative XP tags from LLM prose
    xp_delta += _process_narrative_xp_tags(prose, character_id, campaign_id, turn_number, conn)

    # XS5: First macro-location visit (check after location may have changed)
    current_loc_row = conn.execute(
        "SELECT gl.key FROM game_sessions gs "
        "JOIN game_locations gl ON gl.id = gs.current_location_id "
        "WHERE gs.campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if current_loc_row:
        from app.services.xp_sources import grant_first_location_visit
        xp_delta += grant_first_location_visit(
            conn, character_id, campaign_id, current_loc_row["key"], turn_number
        )

    if xp_delta:
        conn.commit()

    # ── Step 9: Assemble response ─────────────────────────────────────────
    current_loc = get_current_location_info(conn, campaign_id)
    char_state = _get_character_state(character_id, conn)

    # Log to action_log
    _write_action_log(
        conn, campaign_id, character_id, turn_number,
        user_input, f"[{action_type}]", mechanic_result, prose,
        char_state.get("current_hp"), char_state.get("hp_after", char_state.get("current_hp")),
    )

    latency_ms = int((time.perf_counter() - t_start) * 1000)
    logger.info("turn_pipeline_complete", action=action_type, outcome=mechanic_result.get("outcome"),
                turn=turn_number, ms=latency_ms)

    return {
        "prose": prose,
        "state": {
            "character_hp": char_state.get("current_hp"),
            "character_max_hp": char_state.get("max_hp"),
            "wound_label": _wound_label(char_state.get("current_hp", 0), char_state.get("max_hp", 1)),
            "current_location": current_loc.get("key") if current_loc else None,
            "xp_delta": xp_delta,
        },
        "current_location": current_loc,
        "turn_number": turn_number,
        "action_type": action_type,
        "mechanic_result": mechanic_result,
        "system_messages": [],
        "skill_test_pending": _skill_pending,
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _return_skill_test_pending(
    params: dict,
    context: dict,
    session_flags: dict,
    wsm_result,
    campaign_id: int,
    character_id: int,
    conn: sqlite3.Connection,
) -> dict:
    """Return a skill_test_pending payload without resolving — player must send d20."""
    import uuid
    skill_key = params.get("skill_key", "perception")
    sheet = context.get("character_sheet") or {}
    mod_info = calc_skill_modifier_info(sheet, skill_key)
    skill_test_id = f"st-{uuid.uuid4().hex[:8]}"

    from app.services.skill_service import _skill_label, _get_counter
    counter = _get_counter(conn, skill_key)

    pending = {
        "skill_test_id": skill_test_id,
        "skill_key": skill_key,
        "skill_label": _skill_label(skill_key),
        "counter": counter,
        "modifier_breakdown": mod_info,
        "params": params,
    }

    # Store in session
    session_flags["pending_skill_test"] = pending
    session_flags["state"] = "SKILL_TEST_PENDING"
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(session_flags, ensure_ascii=False), campaign_id),
    )
    conn.commit()

    char_state = _get_character_state(character_id, conn)
    current_loc = get_current_location_info(conn, campaign_id)
    return {
        "prose": None,
        "skill_test_pending": pending,
        "state": {
            "character_hp": char_state.get("current_hp"),
            "character_max_hp": char_state.get("max_hp"),
            "wound_label": _wound_label(char_state.get("current_hp", 0), char_state.get("max_hp", 1)),
            "current_location": current_loc.get("key") if current_loc else None,
            "xp_delta": 0,
        },
        "current_location": current_loc,
        "action_type": "SKILL_ATTEMPT",
        "system_messages": [],
    }


def _system_response(message: str, session_flags: dict, campaign_id: int,
                      conn: sqlite3.Connection) -> dict:
    loc = get_current_location_info(conn, campaign_id)
    return {
        "prose": None,
        "system_message": message,
        "state": {},
        "current_location": loc,
        "turn_number": None,
        "action_type": "SYSTEM",
        "system_messages": [message],
    }


def _load_action_context(
    action_type: str, params: dict, character_id: int,
    campaign_id: int, session_flags: dict, conn: sqlite3.Connection
) -> dict:
    """Batch load DB records needed for mechanical resolution."""
    ctx: dict = {}

    # Character sheet
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if row:
        try:
            ctx["character_sheet"] = json.loads(row[0] or "{}")
        except Exception:
            ctx["character_sheet"] = {}

    # Current location
    loc_info = get_current_location_info(conn, campaign_id)
    if loc_info:
        loc_row = conn.execute(
            "SELECT key, label, description, safe_for_rest, location_type FROM game_locations WHERE key = ?",
            (loc_info["key"],)
        ).fetchone()
        if loc_row:
            ctx["location"] = dict(loc_row)

    # Target enemy (for ATTACK)
    target_key = params.get("target", "")
    if target_key and action_type in ("ATTACK",):
        roster = session_flags.get("combat_roster", [])
        enemy_in_combat = next((e for e in roster if e.get("key") == target_key), None)
        if enemy_in_combat:
            ctx["target_enemy"] = enemy_in_combat
        else:
            # Try DB
            erow = conn.execute(
                "SELECT key, label, hp_base, ac_base, dex_modifier FROM game_config_enemies WHERE key = ?",
                (target_key,)
            ).fetchone()
            if erow:
                ctx["target_enemy"] = dict(erow)
                ctx["target_enemy"]["hp"] = erow["hp_base"]

    # Target NPC (for DIALOGUE, EXAMINE, SHOP)
    npc_key = params.get("npc_key", params.get("target", ""))
    if npc_key and action_type in ("DIALOGUE", "SHOP", "EXAMINE"):
        nrow = conn.execute(
            "SELECT key, label, npc_type, personality_prompt, keyword_triggers, is_shop FROM npcs WHERE key = ?",
            (npc_key,)
        ).fetchone()
        if nrow:
            ctx["target_npc"] = dict(nrow)

    # Equipped weapon
    weap_row = conn.execute(
        """SELECT gw.key, gw.label, gw.damage_die, gw.linked_stat, gw.weapon_type, gw.finesse
           FROM character_inventory ci
           JOIN game_config_weapons gw ON gw.key = ci.weapon_key
           WHERE ci.character_id = ? AND ci.equipped = 1 AND ci.weapon_key IS NOT NULL
           LIMIT 1""",
        (character_id,)
    ).fetchone()
    if weap_row:
        ctx["equipped_weapon"] = dict(weap_row)

    # Destination location
    dest_key = params.get("destination_key", "")
    if dest_key:
        drow = conn.execute(
            "SELECT key, label, description, safe_for_rest FROM game_locations WHERE key = ?",
            (dest_key,)
        ).fetchone()
        if drow:
            ctx["destination_location"] = dict(drow)

    # Item record
    item_key = params.get("item_key", "")
    if item_key:
        irow = conn.execute(
            "SELECT key, label, item_type, effect_json, value_gp FROM game_config_items WHERE key = ?",
            (item_key,)
        ).fetchone()
        if irow:
            ctx["item_record"] = dict(irow)
        else:
            # Check consumables
            crow = conn.execute(
                "SELECT key, label, effect_type, effect_dice, effect_bonus FROM game_config_consumables WHERE key = ?",
                (item_key,)
            ).fetchone()
            if crow:
                ctx["item_record"] = dict(crow)

    # Skill info
    skill_key = params.get("skill_key", "")
    if skill_key:
        sk_row = conn.execute(
            "SELECT counter_type, counter_key, default_dc FROM skill_counters WHERE player_skill_key = ? LIMIT 1",
            (skill_key,)
        ).fetchone() if _table_exists(conn, "skill_counters") else None

        if sk_row:
            ctx["skill_counter"] = {"counter_type": sk_row[0], "counter_key": sk_row[1], "dc": sk_row[2] or 12}
        else:
            ctx["skill_counter"] = {"dc": 12}

    # Combat state
    ctx["combat_state"] = {"combatants": session_flags.get("combat_roster", [])}

    return ctx


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _apply_world_state(
    result: dict, context: dict, character_id: int, campaign_id: int,
    turn_number: int, conn: sqlite3.Connection
) -> None:
    """Write mechanic result to DB."""
    action_type = result.get("action_type", "")
    outcome = result.get("outcome", "")

    # HP changes
    hp_after = result.get("hp_after")
    if hp_after is not None and action_type in ("REST", "ITEM_USE"):
        _update_character_hp(character_id, int(hp_after), conn)

    mana_after = result.get("mana_after")
    if mana_after is not None:
        _update_character_mana(character_id, int(mana_after), conn)

    # Enemy HP (attack hits)
    if action_type == "ATTACK" and result.get("hit"):
        target_key = result.get("target_key", "")
        target_dead = result.get("target_dead", False)
        if target_key and target_dead:
            _handle_enemy_death(campaign_id, target_key, conn)

    # Movement
    if action_type == "MOVEMENT" and outcome == "SUCCESS":
        dest_key = result.get("to_location_key", "")
        if dest_key:
            _update_character_location(campaign_id, dest_key, conn)

    # NPC killed from mechanic result
    if result.get("npc_killed"):
        mark_npc_dead(campaign_id, result["npc_killed"], conn)


def _handle_enemy_death(campaign_id: int, enemy_key: str, conn: sqlite3.Connection) -> None:
    consequence = mark_npc_dead(campaign_id, enemy_key, conn)
    if consequence in ("major", "catastrophic"):
        log_deviation(campaign_id, f"Enemy {enemy_key} killed (consequence: {consequence})",
                      consequence, conn)


def _update_character_hp(character_id: int, hp: int, conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (character_id,)).fetchone()
    if not row:
        return
    sheet = json.loads(row[0] or "{}")
    sheet["current_hp"] = hp
    conn.execute("UPDATE characters SET sheet_json = ? WHERE id = ?",
                 (json.dumps(sheet), character_id))
    conn.commit()


def _update_character_mana(character_id: int, mana: int, conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (character_id,)).fetchone()
    if not row:
        return
    sheet = json.loads(row[0] or "{}")
    sheet["current_mana"] = mana
    conn.execute("UPDATE characters SET sheet_json = ? WHERE id = ?",
                 (json.dumps(sheet), character_id))
    conn.commit()


def _update_character_location(campaign_id: int, location_key: str,
                                 conn: sqlite3.Connection) -> None:
    loc_row = conn.execute(
        "SELECT id FROM game_locations WHERE key = ?", (location_key,)
    ).fetchone()
    if not loc_row:
        return
    conn.execute(
        "UPDATE game_locations SET usage_count = usage_count + 1 WHERE id = ?",
        (loc_row[0],),
    )
    from app.services.location_state_service import set_position
    set_position(conn, campaign_id=campaign_id, current_location_id=int(loc_row[0]))
    conn.commit()
    try:
        maybe_lazy_enrich_subloc(conn, location_key)
    except Exception:
        logger.warning("lazy_subloc_enrich_failed", location_key=location_key, exc_info=True)


def _update_session_flags(wsm_result, session_flags: dict, mechanic_result: dict,
                            conn: sqlite3.Connection, campaign_id: int) -> None:
    if wsm_result.new_state:
        flags_update = wsm_result.state_flags_update or {}
        session_flags["state"] = wsm_result.new_state
        session_flags.update(flags_update)

        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (json.dumps(session_flags), campaign_id)
        )
        conn.commit()


def _update_turns_at_location(
    mechanic_result: dict, session_flags: dict, conn: sqlite3.Connection, campaign_id: int
) -> None:
    """Track consecutive turns without location change for STORY_STALE injection."""
    if mechanic_result.get("action_type") == "MOVEMENT" and mechanic_result.get("outcome") == "SUCCESS":
        session_flags["turns_at_location"] = 0
    else:
        session_flags["turns_at_location"] = session_flags.get("turns_at_location", 0) + 1
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(session_flags, ensure_ascii=False), campaign_id),
    )
    conn.commit()


def _update_hex_world_state(
    mechanic_result: dict, session_flags: dict, conn: sqlite3.Connection, campaign_id: int
) -> None:
    """After successful hex movement, sync current_hex (and location_key if set) in session_flags."""
    if mechanic_result.get("action_type") != "MOVEMENT" or mechanic_result.get("outcome") != "SUCCESS":
        return
    dest_q = mechanic_result.get("destination_q")
    dest_r = mechanic_result.get("destination_r")
    # U30 fix #518: text movement provides to_location_key but not q/r — resolve via world_hexes
    # #1043: guard — LLM-resolved destination via to_location_key cannot jump the whole
    # region in a single turn. Named-location moves up to MAX_LLM_HEX_JUMP are allowed;
    # beyond that the move is blocked and the hex stays (prevents far-corner teleport).
    # Directional fast-path (destination_q/r explicit) is exempt — detect_move_intent
    # already enforces ±1 steps, so no extra guard needed there.
    MAX_LLM_HEX_JUMP = 15  # numbers policy starting value — whole region ~30-50 hexes
    if dest_q is None or dest_r is None:
        to_loc_key = mechanic_result.get("to_location_key")
        if to_loc_key:
            from app.services.hex_travel_service import resolve_location_key_to_hex, hex_distance
            coords = resolve_location_key_to_hex(to_loc_key, conn)
            if coords:
                old_hex = session_flags.get("current_hex") or {}
                old_q = old_hex.get("q")
                old_r = old_hex.get("r")
                if old_q is not None and old_r is not None:
                    dist = hex_distance(int(old_q), int(old_r), coords[0], coords[1])
                    if dist > MAX_LLM_HEX_JUMP:
                        logger.warning(
                            "narrative_hex_jump_blocked_location_key",
                            from_hex=(old_q, old_r),
                            to_hex=coords,
                            distance=dist,
                            location_key=to_loc_key,
                            campaign_id=campaign_id,
                        )
                        return
                dest_q, dest_r = coords
                logger.info("u30_hex_resolved_from_location_key",
                            location_key=to_loc_key, q=dest_q, r=dest_r,
                            campaign_id=campaign_id)
    if dest_q is None or dest_r is None:
        return

    # Resolve location_id from destination hex (if any)
    hex_row = conn.execute(
        "SELECT location_key FROM world_hexes WHERE q = ? AND r = ? AND is_active = 1",
        (int(dest_q), int(dest_r)),
    ).fetchone()
    loc_key = hex_row["location_key"] if hex_row else None
    loc_id: int | None = None
    if loc_key:
        loc_row = conn.execute(
            "SELECT id FROM game_locations WHERE key = ? AND COALESCE(is_active, 1) = 1",
            (loc_key,),
        ).fetchone()
        if loc_row:
            loc_id = int(loc_row["id"])

    from app.services.location_state_service import set_position
    set_position(
        conn,
        campaign_id=campaign_id,
        current_hex={"q": int(dest_q), "r": int(dest_r)},
        current_location_id=loc_id,
        clear_local_hex=True,
    )
    # Keep in-memory dict in sync for downstream callers this turn
    session_flags["current_hex"] = {"q": int(dest_q), "r": int(dest_r)}
    conn.commit()


def _reload_session_flags(campaign_id: int, conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT session_flags, current_location_id FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,)
    ).fetchone()
    if not row:
        return None
    flags = json.loads(row[0] or "{}")

    # Add current location key to flags for context injector
    if row[1]:
        loc = conn.execute("SELECT key FROM game_locations WHERE id = ?", (row[1],)).fetchone()
        if loc:
            flags["current_location_key"] = loc[0]

    return flags


def _process_beat_signals(
    mechanic_result: dict, campaign_id: int, character_id: int,
    turn_number: int, conn: sqlite3.Connection
) -> int:
    """XS1 — Process beat_signals, grant pending XP for each completed beat."""
    from app.services.xp_sources import grant_beat_complete
    xp = 0
    for signal in mechanic_result.get("beat_signals", []):
        if signal.startswith("BEAT_COMPLETE:"):
            beat_key = signal.split(":", 1)[1]
            if mark_beat_visited(campaign_id, beat_key, turn_number, conn):
                xp += grant_beat_complete(conn, character_id, campaign_id, beat_key, turn_number)
    return xp


def _auto_complete_beats_by_mechanic(
    action_type: str, result: dict, context: dict,
    campaign_id: int, turn_number: int, conn: sqlite3.Connection,
) -> None:
    """U8 #532 — Auto-complete beats whose objective_type matches the mechanic outcome.

    #1011 — fires the analogous quest auto-complete on the same events so a quest with a
    condition closes itself without the narrator's [QUEST_COMPLETE] tag.
    """
    from app.services.campaign_plan_runtime import auto_complete_beats_by_event
    from app.services.quest_persist_service import auto_complete_quests_by_event

    def _fire(event_type: str, target: str) -> None:
        auto_complete_beats_by_event(campaign_id, event_type, target, turn_number, conn)
        auto_complete_quests_by_event(conn, campaign_id, event_type, target, turn_number)

    if action_type == "ATTACK" and result.get("target_dead"):
        enemy = context.get("target_enemy") or {}
        target = enemy.get("label") or result.get("target_key", "")
        if target:
            _fire("kill_enemy", target)

    elif action_type == "MOVEMENT" and result.get("outcome") == "SUCCESS":
        dest = context.get("destination_location") or {}
        target = dest.get("label") or result.get("to_location_key", "")
        if target:
            _fire("visit_location", target)

    elif action_type == "DIALOGUE":
        npc = context.get("target_npc") or {}
        # #550: fall back to result npc fields when context NPC lookup failed (key mismatch)
        target = (npc.get("label") or npc.get("key") or
                  result.get("npc_name") or result.get("npc_key") or "")
        if target:
            _fire("talk_to_npc", target)

    elif action_type in ("ITEM_USE", "EXAMINE"):
        item = context.get("item_record") or {}
        target = item.get("label") or item.get("key", "")
        if target:
            _fire("find_item", target)


def _process_npc_first_talk(
    action_type: str, npc_key: str | None,
    character_id: int, campaign_id: int, turn_number: int,
    conn: sqlite3.Connection,
) -> int:
    """XS6 — Grant 5 XP on first DIALOGUE with each unique NPC."""
    if action_type != "DIALOGUE" or not npc_key:
        return 0
    from app.services.xp_sources import grant_first_npc_talk
    return grant_first_npc_talk(conn, character_id, campaign_id, npc_key, turn_number)


def _process_narrative_xp_tags(
    narrative: str, character_id: int, campaign_id: int,
    turn_number: int, conn: sqlite3.Connection,
) -> int:
    """XS2/XS3/XS4/XS7/XS8/XS12 — parse LLM narrative for XP tags."""
    if not narrative:
        return 0
    from app.services.xp_sources import process_narrative_xp_tags
    result = process_narrative_xp_tags(narrative, conn, character_id, campaign_id, turn_number)
    return result.get("total_granted", 0)


def _process_session_start(
    character_id: int, campaign_id: int, turn_number: int, conn: sqlite3.Connection,
) -> int:
    """XS15 — grant session start bonus if ≥30 min since last turn."""
    from app.services.xp_sources import grant_session_start
    return grant_session_start(conn, character_id, campaign_id, turn_number)


def _get_next_turn_number(campaign_id: int, conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(turn_number), 0) + 1 FROM campaign_turns WHERE campaign_id = ?",
        (campaign_id,)
    ).fetchone()
    return int(row[0]) if row else 1


def _get_character_state(character_id: int, conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT sheet_json FROM characters WHERE id = ?", (character_id,)).fetchone()
    if not row:
        return {}
    sheet = json.loads(row[0] or "{}")
    return {
        "current_hp": sheet.get("current_hp", 0),
        "max_hp": sheet.get("max_hp", 1),
        "current_mana": sheet.get("current_mana", 0),
        "max_mana": sheet.get("max_mana", 0),
    }


def _write_action_log(
    conn: sqlite3.Connection, campaign_id: int, character_id: int, turn_number: int,
    user_text: str, action_tag: str, mechanic_result: dict, narrative_text: str,
    hp_before, hp_after,
) -> None:
    try:
        conn.execute(
            """INSERT OR IGNORE INTO action_log
               (campaign_id, character_id, turn_number, action_type, action_params,
                mechanic_result, narrative_text)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                campaign_id, character_id, turn_number,
                mechanic_result.get("action_type", "UNKNOWN"),
                json.dumps({"user_text": user_text}),
                json.dumps(mechanic_result),
                narrative_text or "",
            )
        )
        conn.commit()
    except Exception as e:
        logger.warning("action_log_write_failed", error=str(e))


def _wound_label(hp: int, max_hp: int) -> str:
    if max_hp <= 0:
        return "Unknown"
    pct = (hp / max_hp) * 100
    if pct >= 100:
        return "Zdrowy/a"
    if pct >= 75:
        return "Lekko zadrapany/a"
    if pct >= 50:
        return "Ranny/a"
    if pct >= 25:
        return "Poważnie ranny/a"
    if pct >= 10:
        return "Ciężko ranny/a"
    if hp > 0:
        return "Na skraju śmierci"
    return "Nieprzytomny/a"


def _fallback_prose(action_type: str, result: dict) -> str:
    templates = {
        "ATTACK": "Twój cios trafia cel." if result.get("hit") else "Atak chybia.",
        "MOVEMENT": f"Przemieszczasz się do {result.get('to_location_name', 'nowego miejsca')}.",
        "REST": "Odpoczywasz przez chwilę.",
        "EXAMINE": "Przyglądasz się uważnie.",
        "DIALOGUE": "Rozmawiasz z rozmówcą.",
    }
    return templates.get(action_type, "Akcja zostaje wykonana.")


# ── Opening scene ─────────────────────────────────────────────────────────

def generate_opening_scene(
    campaign_id: int,
    character_id: int,
    model: str,
    llm_config: dict,
    conn: sqlite3.Connection,
) -> str | None:
    """
    Generate the opening scene narration for a new campaign.
    Stores in campaign_turns as turn 1 (no user_text).
    Returns the prose or None on failure.
    """
    # Check not already generated
    existing = conn.execute(
        "SELECT id FROM campaign_turns WHERE campaign_id = ? AND user_text IS NULL LIMIT 1",
        (campaign_id,)
    ).fetchone()
    if existing:
        logger.info("opening_scene_already_exists", campaign_id=campaign_id)
        return None

    char_row = conn.execute(
        "SELECT name, sheet_json FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if not char_row:
        return None

    sheet = json.loads(char_row["sheet_json"] or "{}")
    identity = sheet.get("identity") or {}
    gm_only = sheet.get("gm_only") or {}
    name = char_row["name"] or "Bohater"
    archetype = sheet.get("archetype", "warrior")

    # Get campaign plan context
    from app.services.campaign_plan_runtime import get_plan
    plan = get_plan(campaign_id, conn)
    act1 = plan.get("acts", [{}])[0] if plan.get("acts") else {}
    starting_loc = next(
        (loc for loc in plan.get("key_locations", []) if "start" in loc.get("role", "").lower()),
        plan.get("key_locations", [{}])[0] if plan.get("key_locations") else {}
    )

    # Build opening scene prompt
    bonds_text = "\n".join(
        f"  - {b.get('description', '')}" for b in (identity.get("bonds") or [])
    )
    weak_text = "\n".join(
        f"  - {w.get('description', '')}" for w in (identity.get("weaknesses") or [])
    )

    prompt = f"""\
Jesteś narratorem mrocznej fantasy. Napisz scenę otwierającą dla nowej kampanii.

POSTAĆ:
  Imię: {name}
  Archetyp: {archetype}
  Wygląd: {identity.get('appearance', '')}
  Osobowość: {identity.get('personality', '')}
  Więzi:
{bonds_text or '  (brak)'}
  Słabości:
{weak_text or '  (brak)'}

KAMPANIA:
  Tytuł aktu 1: {act1.get('title', '')}
  Streszczenie: {act1.get('summary', '')}
  Miejsce startowe: {starting_loc.get('name', 'nieznane miejsce')}

ZASADY:
- Napisz 100-200 słów po polsku
- Umieść postać fizycznie w miejscu startowym
- Nawiąż do jednej więzi lub słabości postaci
- Stwórz napięcie lub ciekawość — coś jest nie tak
- NIE mów graczowi co ma zrobić
- NIE używaj imienia postaci jako pierwszego słowa
"""

    try:
        prose = generate_chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            llm_config=llm_config,
        ) or ""

        if not prose.strip():
            prose = f"{name} przybywa do celu. Coś w powietrzu zdaje się nie tak."

        # Store as turn 1 (no user_text)
        conn.execute(
            """INSERT INTO campaign_turns
               (campaign_id, character_id, user_text, assistant_text, route, turn_number)
               VALUES (?, ?, NULL, ?, 'narrative', 1)""",
            (campaign_id, character_id, prose)
        )
        conn.commit()

        logger.info("opening_scene_generated", campaign_id=campaign_id)
        return prose

    except Exception as e:
        logger.warning("opening_scene_failed", campaign_id=campaign_id, error=str(e))
        return None
