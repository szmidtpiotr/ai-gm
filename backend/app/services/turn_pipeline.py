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
    # #1114: bare "wr[aó]c[aę]\b" wymagało końca słowa na "wraca" → 1. os. "wracam"
    # (i "zawracam"/"cofam się") nie łapały się i tura szła ścieżką narracyjną
    # (narrator opisywał powrót, hex stał w miejscu — desync). Inflekcje przez \w*.
    r"\b(id[ęeę]|idz[ie]*|wr[aó]c\w*|wroc\w*|zawr[aó]c\w*|zawroc\w*|cof\w*|wyruszam[y]?|podroz?uj(?:[eę]|emy)|podróżuj(?:[eę]|emy)|"
    r"jad[eę]|biegne|biegnę|zmierzam|ruszam[y]?|wchodz[eę]|wchodze|"
    r"przechodze|przechodzę|wedruję|wędruję|pojd[eę]|pójd[eę]|idz|chodz|chodzmy|idziemy|"
    # #1142: "maszeruję dalej na zachód" / "wychodzę na trakt" nie łapały się na fast-path
    # → tura-fantom (narracja marszu bez ruchu hexa). Uzupełnione czasowniki marszu.
    # PM3 #1222: "kieruję się" (bezpieczny czasownik ruchu). Miękkie warianty
    # (szukam/udaję/próbuję) obsługiwane wyłącznie przez ścieżkę known-hex z
    # przyimkiem celu — patrz _PT3_MOVE_VERB_RE + _KNOWN_HEX_DEST_RE.
    r"maszeruj\w*|wychodz[eę]|pod[ąa]ż\w*|krocz[eę]|kieruj\w*)\b",
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


def _region_unlock_hint(tr: dict) -> str:
    """PM2 (#1221): [SYSTEM:...] narrator hint when a move crossed into a new land.

    ``tr["region_unlocked"]`` is set by resolve_chain_travel on the arrival that
    first entered a region not yet in ``known_regions``. Empty string otherwise.
    """
    ru = tr.get("region_unlocked") or None
    if not ru:
        return ""
    return (
        f"\n[SYSTEM: Bohater wkracza do krainy {ru.get('label')} — nowy region. "
        "Wspomnij o rozeznaniu w nowym terenie (pyta ludzi, drogowskazy, mapy).]"
    )


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

# ── PM4 #1223: direct-vs-road route choice helpers ────────────────────────────

def _pm4_save_flags(conn: "sqlite3.Connection", campaign_id: int, flags: dict) -> None:
    """Persist the mutated session_flags dict for a campaign."""
    row = conn.execute(
        "SELECT id FROM game_sessions WHERE campaign_id = ? LIMIT 1", (campaign_id,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), row["id"]),
        )
        conn.commit()


def _pm4_hex_label(conn: "sqlite3.Connection", q: int, r: int) -> str:
    """Human label for a destination hex (linked location label > hex label > coords)."""
    row = conn.execute(
        "SELECT label, location_key FROM world_hexes WHERE q=? AND r=? AND is_active=1 LIMIT 1",
        (q, r),
    ).fetchone()
    if row and row["location_key"]:
        lr = conn.execute(
            "SELECT label FROM game_locations WHERE key = ? LIMIT 1", (row["location_key"],)
        ).fetchone()
        if lr and lr["label"]:
            return lr["label"]
    if row and row["label"]:
        return row["label"]
    return f"hex ({q},{r})"


def _pm4_build_travel_fact(tr: dict, label: str, mode_label: str) -> str:
    """[SYSTEM:…] narrator fact for a completed route-mode trip (mirrors PT3 facts)."""
    arr = tr.get("arrived_hex") or {}
    hex_info = tr.get("hex_data") or {}
    enc = tr.get("encounter")
    fact = (
        f"\n[SYSTEM: Podróż {mode_label} do {label} wykonana mechanicznie: gracz "
        f"przemieścił się na hex ({arr.get('q')},{arr.get('r')}), "
        f"teren: {hex_info.get('hex_type', 'nieznany')}, "
        f"czas podróży: {tr.get('total_hours', 0)}h."
    )
    if enc:
        fact += (
            f" Podróż przerwana spotkaniem: {enc.get('enemy_key')} — "
            f"opisz nadejście zagrożenia i ROZPOCZNIJ walkę: OSTATNIA linia "
            f"odpowiedzi MUSI być wyłącznie tagiem [COMBAT_START:{enc.get('enemy_key')}]."
        )
    if tr.get("weather_slowdown"):
        fact += (
            f" Pogoda ({tr.get('weather_slowdown')}) spowalniała marsz — "
            "wpleć trud drogi w opis."
        )
    fact += (
        " Opisz tę podróż w 2-4 zdaniach. NIE przenoś gracza do innej lokacji — "
        "ruch już rozstrzygnięty mechanicznie.]"
    )
    fact += _region_unlock_hint(tr)
    return fact


def _pm4_maybe_prompt(
    conn: "sqlite3.Connection",
    campaign_id: int,
    from_hex: tuple[int, int],
    to_hex: tuple[int, int],
    label: str,
    flags: dict,
) -> str | None:
    """Offer the direct/road choice before a long descriptive trip.

    When the destination is >ROAD_CHOICE_MIN_HEXES away AND a viable trakt runs
    near the direct path, DO NOT move: stash ``pending_travel_choice`` in
    session_flags and return the question [SYSTEM] fact. Otherwise return None
    (caller travels straight away).
    """
    if flags.get("pending_travel_choice"):
        return None
    from app.services.hex_travel_service import analyze_route, ROAD_CHOICE_MIN_HEXES
    info = analyze_route(from_hex, to_hex, conn)
    if info["dist"] <= ROAD_CHOICE_MIN_HEXES or not info["road_alt"]:
        return None
    flags["pending_travel_choice"] = {
        "destination": {"q": to_hex[0], "r": to_hex[1]},
        "label": label,
        "hinted": 0,
    }
    _pm4_save_flags(conn, campaign_id, flags)
    logger.info(
        "pm4_route_choice_prompted",
        campaign_id=campaign_id, to_hex=to_hex, dist=info["dist"],
    )
    return (
        f"\n[SYSTEM: zapytaj gracza — prosto przez {info['terrain_label']} czy traktem "
        "(dłużej, bezpieczniej)? NIE opisuj wyruszenia.]"
    )


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

    # PM4 #1223: player is answering a pending direct/road question. Runs BEFORE
    # detect_move_intent — the answer ("idę traktem" / "na przełaj") carries the
    # mode but no destination, so the normal move-intent parsers would miss it.
    pending = flags.get("pending_travel_choice")
    if pending and not _has_active_combat(conn, campaign_id):
        from app.services.hex_travel_service import (
            detect_route_choice as _drc,
            execute_travel as _exec_pending,
            TravelError as _TE_pending,
        )
        _choice = _drc(player_text)
        _dest_p = pending.get("destination") or {}
        _dq_p, _dr_p = int(_dest_p.get("q", 0)), int(_dest_p.get("r", 0))
        _label_p = pending.get("label") or f"hex ({_dq_p},{_dr_p})"
        _hinted = int(pending.get("hinted", 0))
        if _choice == "cancel" or (_choice is None and _hinted >= 1):
            # Player explicitly cancelled OR second non-answer → abandon pending travel.
            flags.pop("pending_travel_choice", None)
            _pm4_save_flags(conn, campaign_id, flags)
            return {
                "executed": False,
                "system_fact": (
                    f"\n[SYSTEM: gracz zrezygnował z podróży do {_label_p}. "
                    "Kontynuuj narrację normalnie — gracz zostaje w obecnej lokacji.]"
                ),
                "intent": None,
            }
        if _choice is None:
            # First unclear answer — re-hint exactly once, hero stays put.
            flags["pending_travel_choice"]["hinted"] = _hinted + 1
            _pm4_save_flags(conn, campaign_id, flags)
            return {
                "executed": False,
                "system_fact": (
                    f"\n[SYSTEM: gracz nie wskazał wyraźnie trasy do {_label_p}. Zapytaj "
                    "raz jeszcze krótko: prosto przez dzicz (szybciej, groźniej) czy "
                    "traktem (dłużej, bezpieczniej)? NIE opisuj wyruszenia.]"
                ),
                "intent": None,
            }
        # Execute the deferred trip in the chosen mode, then clear the pending flag.
        flags.pop("pending_travel_choice", None)
        _pm4_save_flags(conn, campaign_id, flags)
        try:
            tr_p = _exec_pending(
                conn, campaign_id, {"hex": {"q": _dq_p, "r": _dr_p}},
                actor=character_id, record_turn=False, route_mode=_choice,
            )
        except _TE_pending as _te_p:
            tr_p = {"ok": False, "error": _te_p.message}
        except Exception as _te_pg:  # never break a turn
            logger.warning("pm4_pending_travel_error", error=str(_te_pg), campaign_id=campaign_id)
            tr_p = {"ok": False, "error": "błąd podróży"}
        _mode_label = "traktem" if _choice == "road" else "na przełaj przez dzicz"
        if tr_p.get("ok"):
            logger.info(
                "pm4_travel_executed", campaign_id=campaign_id,
                route_mode=_choice, to_hex=(_dq_p, _dr_p),
            )
            return {
                "executed": True,
                "system_fact": _pm4_build_travel_fact(tr_p, _label_p, _mode_label),
                "intent": None,
            }
        return {
            "executed": False,
            "system_fact": (
                f"\n[SYSTEM: Gracz ruszył {_mode_label} do {_label_p}, ale mechanika "
                f"odmówiła: {tr_p.get('error', 'nieprzejezdny teren')}. Opisz przeszkodę "
                "narracyjnie. NIE opisuj dotarcia do celu.]"
            ),
            "intent": None,
        }

    # PT6 #1116: player continues interrupted travel after combat.
    # PT-F1 #1135: never resume while combat is active — "kontynuuję" typed mid-fight
    # must not walk the hero off the combat hex.
    tp = flags.get("travel_plan")
    if (
        tp
        and tp.get("interrupt_reason") == "encounter_prompted"
        and detect_travel_continuation(player_text)
        and not _has_active_combat(conn, campaign_id)
    ):
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
            route_mode=tp.get("route_mode", "direct"),  # PM4 #1223: resume keeps the mode
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
                    f" Nowe spotkanie: {enc_r.get('enemy_key')} — opisz nadejście zagrożenia "
                    f"i ROZPOCZNIJ walkę: OSTATNIA linia odpowiedzi MUSI być wyłącznie tagiem "
                    f"[COMBAT_START:{enc_r.get('enemy_key')}]."
                )
            else:
                fact_r += f" Gracz dotarł do celu: {dest_label_r}."
            if tr_r.get("weather_slowdown"):
                # PT-F6 #1140: weather fact was missing on the resume path (clock still
                # slowed, but the narrator wasn't told). Parity with the directional path.
                fact_r += (
                    f" Pogoda ({tr_r.get('weather_slowdown')}) spowalniała marsz — "
                    "wpleć trud drogi w opis."
                )
            fact_r += " Opisz wznowienie podróży w 2-4 zdaniach. NIE przenoś gracza — ruch rozstrzygnięty.]"
            # #1148: a fully-arrived plan must die HERE. resolve_chain_travel pops the
            # plan on arrival only when it actually walked (from != to); the flee case
            # ends with the hero already ON the destination hex, so the early-return
            # skipped the cleanup and the stale encounter_prompted plan hijacked every
            # later "idę dalej" back to the old destination (hex frozen until TTL).
            if (
                int(arr_r.get("q", 10**9)) == dq_r
                and int(arr_r.get("r", 10**9)) == dr_r
                and not enc_r
            ):
                try:
                    _gs_done_r = conn.execute(
                        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                        (campaign_id,),
                    ).fetchone()
                    if _gs_done_r:
                        _sf_done_r = json.loads(_gs_done_r["session_flags"] or "{}")
                        if _sf_done_r.pop("travel_plan", None) is not None:
                            conn.execute(
                                "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                                (json.dumps(_sf_done_r, ensure_ascii=False), _gs_done_r["id"]),
                            )
                            conn.commit()
                            logger.info("pt6_travel_plan_completed", campaign_id=campaign_id)
                except Exception as _done_err:
                    logger.warning("pt6_travel_plan_complete_failed", error=str(_done_err))
            logger.info("pt6_travel_resumed", campaign_id=campaign_id, destination=dest_label_r)
            return {"executed": True, "system_fact": fact_r, "intent": None}

    # PT-F1 #1135: after a 12h forced camp the hero has collapsed and MUST rest.
    # /travel-resume already refuses this; guard the raw directional/named path too
    # so a plain "idę dalej" can't crawl the hero 1 hex at a time instead of resting.
    # Gate on the actual fatigue state (hours_marched_today) — a long rest resets it
    # to 0 and lifts the block; a stale forced_camp_prompted reason alone doesn't.
    if (
        tp
        and str(tp.get("interrupt_reason") or "").startswith("forced_camp")
        and float(flags.get("hours_marched_today", 0) or 0) >= 12.0
    ):
        return {
            "executed": False,
            "system_fact": (
                "\n[SYSTEM: gracz padł z wyczerpania po 12h marszu i próbuje iść dalej "
                "bez odpoczynku. Odmów prozą — bohater musi najpierw odpocząć (/rest) "
                "lub przespać noc, zanim ruszy w dalszą drogę.]"
            ),
            "intent": None,
        }

    mv = detect_move_intent(player_text, cur)
    if not mv:
        # PT3/#1113 + PM3 #1222: descriptive / named-destination travel.
        # Trigger on either a classic vague-move verb OR a descriptive travel
        # phrase ("szukam drogi do mostu", "udaję się w stronę wioski") — the
        # latter carries its own move verb + destination preposition, so soft
        # verbs never fire on their own.
        from app.services.hex_travel_service import (
            _PT3_MOVE_VERB_RE as _pt3_verb_re,
            _KNOWN_HEX_DEST_RE as _kh_dest_re,
        )
        _vague = detect_vague_move_intent(player_text)
        _dest_phrase = bool(_pt3_verb_re.search(player_text) and _kh_dest_re.search(player_text))
        if _vague or _dest_phrase:
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
                    # PM4 #1223: long trip with a nearby trakt → ask direct/road first.
                    _pm4_q_n = _pm4_maybe_prompt(
                        conn, campaign_id,
                        (int(cur["q"]), int(cur["r"])), (dq_n, dr_n),
                        _loc_label_n, flags,
                    )
                    if _pm4_q_n:
                        return {"executed": False, "system_fact": _pm4_q_n, "intent": None}
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
                                f"opisz nadejście zagrożenia i ROZPOCZNIJ walkę: OSTATNIA linia "
                                f"odpowiedzi MUSI być wyłącznie tagiem "
                                f"[COMBAT_START:{enc_n.get('enemy_key')}]."
                            )
                        if tr_n.get("weather_slowdown"):
                            # PT-F6 #1140: weather fact parity on the named-destination path.
                            fact_n += (
                                f" Pogoda ({tr_n.get('weather_slowdown')}) spowalniała marsz — "
                                "wpleć trud drogi w opis."
                            )
                        fact_n += (
                            " Opisz tę podróż w 2-4 zdaniach. NIE przenoś gracza do innej"
                            " lokacji — ruch już rozstrzygnięty mechanicznie.]"
                        )
                        fact_n += _region_unlock_hint(tr_n)
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
                # (the #1253 post-LLM net commits it if the narrator forgets).
                return {"executed": False, "system_fact": None, "intent": None}

            # PM3 #1222: canonical resolver found nothing — try the known-hex
            # descriptive resolver ("do mostu", "w stronę wioski"). Matches known/
            # discovered hexes by label + Polish hex_type name; travels via the
            # unified execute_travel (R4) so the pin/clock/scene all advance.
            from app.services.hex_travel_service import (
                resolve_player_text_to_known_hex,
                execute_travel as _exec_travel_kh,
                TravelError as _TravelError_kh,
                KNOWN_HEX_UNKNOWN as _KH_UNKNOWN,
            )
            _kh = resolve_player_text_to_known_hex(
                player_text, conn, campaign_id, character_id
            )
            if _kh == _KH_UNKNOWN:
                # Point 4 (#1050 deadlock): a target was named but the hero doesn't
                # know where it is — do NOT move; tell the narrator to suggest asking
                # around, and NOT to describe setting out.
                _mm = _kh_dest_re.search(player_text)
                _tgt = (_mm.group(1).strip() if _mm else "cel")
                fact_u = (
                    f"\n[SYSTEM: gracz szuka drogi do \"{_tgt}\", bohater nie wie gdzie to "
                    "jest — zasugeruj wypytanie ludzi (karczma, przechodnie, drogowskazy). "
                    "NIE opisuj wyruszenia — bohater stoi w miejscu.]"
                )
                return {"executed": False, "system_fact": fact_u, "intent": None}
            if _kh:
                dq_k, dr_k = int(_kh[0]), int(_kh[1])
                # PM4 #1223: long trip with a nearby trakt → ask direct/road first.
                _kh_label = _pm4_hex_label(conn, dq_k, dr_k)
                _pm4_q_k = _pm4_maybe_prompt(
                    conn, campaign_id,
                    (int(cur["q"]), int(cur["r"])), (dq_k, dr_k),
                    _kh_label, flags,
                )
                if _pm4_q_k:
                    return {"executed": False, "system_fact": _pm4_q_k, "intent": None}
                try:
                    tr_k = _exec_travel_kh(
                        conn, campaign_id, {"hex": {"q": dq_k, "r": dr_k}},
                        actor=character_id, record_turn=False,
                    )
                except _TravelError_kh as _te_k:
                    tr_k = {"ok": False, "error": _te_k.message}
                except Exception as _te_gen:  # never break a turn
                    logger.warning("pm3_known_hex_travel_error", error=str(_te_gen), campaign_id=campaign_id)
                    tr_k = {"ok": False, "error": "błąd podróży"}
                if tr_k.get("ok"):
                    arr_k = tr_k.get("arrived_hex") or {}
                    hex_info_k = tr_k.get("hex_data") or {}
                    place_k = hex_info_k.get("label") or hex_info_k.get("hex_type") or "cel"
                    enc_k = tr_k.get("encounter")
                    fact_k = (
                        f"\n[SYSTEM: Podróż do „{place_k}” wykonana mechanicznie: gracz "
                        f"przemieścił się na hex ({arr_k.get('q')},{arr_k.get('r')}), "
                        f"teren: {hex_info_k.get('hex_type', 'nieznany')}, "
                        f"czas podróży: {tr_k.get('total_hours', 0)}h."
                    )
                    if enc_k:
                        fact_k += (
                            f" Podróż przerwana spotkaniem: {enc_k.get('enemy_key')} — "
                            f"opisz nadejście zagrożenia i ROZPOCZNIJ walkę: OSTATNIA linia "
                            f"odpowiedzi MUSI być wyłącznie tagiem "
                            f"[COMBAT_START:{enc_k.get('enemy_key')}]."
                        )
                    if tr_k.get("weather_slowdown"):
                        fact_k += (
                            f" Pogoda ({tr_k.get('weather_slowdown')}) spowalniała marsz — "
                            "wpleć trud drogi w opis."
                        )
                    fact_k += (
                        " Opisz tę podróż w 2-4 zdaniach. NIE przenoś gracza do innej "
                        "lokacji — ruch już rozstrzygnięty mechanicznie.]"
                    )
                    fact_k += _region_unlock_hint(tr_k)
                    logger.info(
                        "pm3_known_hex_travel",
                        campaign_id=campaign_id,
                        to_hex=(dq_k, dr_k),
                        from_hex=(cur.get("q"), cur.get("r")),
                    )
                    return {"executed": True, "system_fact": fact_k, "intent": None}

                fact_k = (
                    "\n[SYSTEM: Gracz próbuje dotrzeć do znanego miejsca, ale mechanika "
                    f"odmówiła: {tr_k.get('error', 'nieprzejezdny teren')}. Opisz przeszkodę "
                    "narracyjnie. NIE opisuj dotarcia do celu.]"
                )
                return {"executed": False, "system_fact": fact_k, "intent": None}

            # No named/known destination → vague hint only when the phrasing was a
            # genuine bare move ("idę dalej"); a soft dest-phrase that matched nothing
            # already returned above via KNOWN_HEX_UNKNOWN.
            if _vague:
                hint = _build_vague_move_hint(conn, flags)
                return {"executed": False, "system_fact": hint, "intent": None}
            return {"executed": False, "system_fact": None, "intent": None}
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
                f"opisz nadejście zagrożenia i ROZPOCZNIJ walkę: OSTATNIA linia "
                f"odpowiedzi MUSI być wyłącznie tagiem [COMBAT_START:{enc.get('enemy_key')}]."
            )
        if tr.get("weather_slowdown"):
            # PT15 #1128: pogoda spowalniała marsz — poproś narratora o powiązanie
            fact += (
                f" Pogoda ({tr.get('weather_slowdown')}) spowalniała marsz — "
                "wpleć w opis trud drogi (błoto, śnieg, wiatr) i wolniejsze tempo."
            )
        fact += (
            " Opisz tę podróż w 2-4 zdaniach. NIE przenoś gracza do innej lokacji — "
            "ruch już rozstrzygnięty mechanicznie.]"
        )
        fact += _region_unlock_hint(tr)
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
    campaign_id: int | None = None,
) -> str:
    """PT4 #1114: Build [SYSTEM:...] corrective fact for the next turn's narrator.

    consecutive >= 2 triggers a stronger hint that includes the neighbor hex list
    (same lookup pattern as _build_vague_move_hint).
    """
    loc_label = ""
    # PT-F7 #1141: derive the location key from current_location_id (single source).
    loc_key = ""
    if campaign_id is not None:
        from app.services.location_state_service import get_current_location_key
        loc_key = get_current_location_key(conn, campaign_id) or ""
    if not loc_key:
        loc_key = session_flags.get("location_key", "")
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
                conn, flags, consecutive, campaign_id=campaign_id
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


# PT-F1 #1135: how many turns a travel_plan may linger in a *_prompted / awaiting
# state before it is considered stale and dropped (prevents "kontynuuję" many
# turns later resuming toward a long-abandoned destination).
_PLAN_TTL_TURNS = 10

# PT-F1 #1135: fizzle-guard — if the narrator never turns a travel encounter into
# actual combat, fire the continue/rest/camp prompt after this many turns anyway.
_ENCOUNTER_FIZZLE_TURNS = 2


def _has_active_combat(conn: "sqlite3.Connection", campaign_id: int) -> bool:
    """PT-F1 #1135: True if an active_combat row exists for this campaign."""
    try:
        return conn.execute(
            "SELECT 1 FROM active_combat WHERE campaign_id = ? AND status = 'active' LIMIT 1",
            (campaign_id,),
        ).fetchone() is not None
    except Exception:
        return False


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

        def _persist() -> None:
            conn.execute(
                "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                (json.dumps(flags, ensure_ascii=False), gs["id"]),
            )
            conn.commit()

        reason = tp.get("interrupt_reason")

        # PT-F1 #1135: TTL — a plan sitting in a terminal *_prompted state past
        # _PLAN_TTL_TURNS turns is abandoned; drop it so a much-later "kontynuuję"
        # can't resume toward a stale destination.
        if isinstance(reason, str) and reason.endswith("_prompted"):
            tp["age"] = int(tp.get("age", 0)) + 1
            if tp["age"] > _PLAN_TTL_TURNS:
                flags.pop("travel_plan", None)
                logger.info("pt_f1_travel_plan_expired", campaign_id=campaign_id)
            _persist()
            return None

        if reason not in ("encounter", "dusk", "forced_camp"):
            return None

        dest_label = tp.get("destination_label") or (
            f"hex ({tp.get('destination_hex', {}).get('q')},{tp.get('destination_hex', {}).get('r')})"
        )
        remaining = int(tp.get("hours_remaining", 0))

        if reason == "encounter":
            # PT-F1 #1135: the encounter combat spawns POST-LLM, so on the turn the
            # encounter is written no active_combat exists yet. Defer the prompt until
            # the combat has actually happened AND ended:
            #   - combat active now  → remember we saw it (combat_seen), wait.
            #   - no combat, seen    → combat ended → fire the prompt.
            #   - no combat, unseen  → same encounter turn; wait, but fire anyway
            #                          after _ENCOUNTER_FIZZLE_TURNS (narrator never
            #                          started combat).
            if _has_active_combat(conn, campaign_id):
                if not tp.get("combat_seen"):
                    tp["combat_seen"] = True
                    _persist()
                return None
            if not tp.get("combat_seen"):
                tp["wait_turns"] = int(tp.get("wait_turns", 0)) + 1
                if tp["wait_turns"] < _ENCOUNTER_FIZZLE_TURNS:
                    _persist()
                    return None
                # fizzle timeout — narrator never fought; fall through and prompt.
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


def pop_local_travel_hint(conn: "sqlite3.Connection", campaign_id: int) -> "str | None":
    """PT10 #1120: Inject narrator hint when local travel was interrupted by encounter.

    Fires once (clears local_travel_hint after emitting). Returns None if no hint,
    combat still active, or already consumed.
    """
    try:
        gs = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not gs:
            return None
        flags = json.loads(gs["session_flags"] or "{}")
        hint_data = flags.get("local_travel_hint")
        if not hint_data:
            return None

        # Don't prompt while combat is still active — but remember we saw it
        # (#1147: mirrors pop_travel_plan_hint's combat_seen deferral).
        ac = conn.execute(
            "SELECT 1 FROM active_combat WHERE campaign_id = ? AND status = 'active' LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if ac:
            if (
                hint_data.get("kind") in ("combat", "combat_escalated")
                and not hint_data.get("combat_seen")
            ):
                hint_data["combat_seen"] = True
                flags["local_travel_hint"] = hint_data
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                    (json.dumps(flags, ensure_ascii=False), gs["id"]),
                )
                conn.commit()
            return None

        dest_label = hint_data.get("destination_label", "sub-lokacja")
        hint_kind = hint_data.get("kind", "combat")

        if hint_kind == "social":
            # PT-D2 #1125: social encounter resolved in-flight — movement reached
            # its destination. Narrate the soft social beat, do NOT prompt combat.
            _ev = hint_data.get("social_event", "spotkanie")
            _ok = hint_data.get("success")
            _flavor = {
                "pickpocket": "kieszonkowiec ociera się o gracza w tłumie",
                "drunk_harassment": "pijak zaczepia gracza",
                "card_cheat": "karciany oszust wabi gracza do gry",
                "quest_rumor": "ktoś rzuca ciekawą plotkę",
                "tout": "naganiacz próbuje wcisnąć gracza do kramu",
                "guard_check": "straż zatrzymuje gracza do kontroli",
            }.get(_ev, "drobne uliczne zajście")
            _res = (
                "Gracz w porę to wychwycił — opisz, jak zażegnuje sytuację."
                if _ok
                else "Sytuacja rozeszła się po kościach, ale zostawiła ślad."
            )
            hint = (
                f"\n[SYSTEM: W drodze do {dest_label} zaszło drobne zdarzenie: {_flavor}. "
                f"{_res} Wpleć to w 1-3 zdaniach; ruch dotarł do celu, NIE zaczynaj walki.]"
            )
        else:
            # combat / combat_escalated — #1147: the fight has to actually HAPPEN
            # before we ask continue-or-return. State machine mirrors the world path:
            #   1. not combat_prompted → instruct the narrator to start the fight
            #      ([COMBAT_START] cue; turns.py injection is the deterministic net),
            #      keep the hint.
            #   2. combat active → combat_seen (handled by the guard above), keep.
            #   3. combat over (seen) OR fizzle timeout → continue-or-return, pop.
            _enemy_key = hint_data.get("enemy_key")
            if (
                not hint_data.get("combat_prompted")
                and not hint_data.get("combat_seen")
                and _enemy_key
            ):
                hint_data["combat_prompted"] = True
                hint_data["wait_turns"] = 0
                flags["local_travel_hint"] = hint_data
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                    (json.dumps(flags, ensure_ascii=False), gs["id"]),
                )
                conn.commit()
                return (
                    f"\n[SYSTEM: W drodze do {dest_label} gracza dopada zbrojne "
                    f"starcie: {_enemy_key}. Opisz zasadzkę w 2-3 zdaniach "
                    f"i ROZPOCZNIJ walkę: OSTATNIA linia odpowiedzi MUSI być "
                    f"wyłącznie tagiem [COMBAT_START:{_enemy_key}].]"
                )
            if hint_data.get("combat_prompted") and not hint_data.get("combat_seen"):
                # combat never spawned yet — give the injection/narrator a bounded
                # number of turns before falling through to the prompt (fizzle-guard).
                hint_data["wait_turns"] = int(hint_data.get("wait_turns", 0)) + 1
                if hint_data["wait_turns"] < _ENCOUNTER_FIZZLE_TURNS:
                    flags["local_travel_hint"] = hint_data
                    conn.execute(
                        "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
                        (json.dumps(flags, ensure_ascii=False), gs["id"]),
                    )
                    conn.commit()
                    return None
            hint = (
                f"\n[SYSTEM: Gracz był w drodze do {dest_label}. "
                f"Walka przerwała ruch. Zapytaj gracza (prozą): "
                f"czy kontynuuje do {dest_label} czy wraca? "
                f"(W osadzie rozbicie obozu niedostępne — odpoczynek tylko w bezpiecznych miejscach.) "
                f"Nie decyduj za gracza — zadaj pytanie.]"
            )
        flags.pop("local_travel_hint")
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), gs["id"]),
        )
        conn.commit()
        return hint
    except Exception as e:
        logger.warning("pop_local_travel_hint_failed", error=str(e))
        return None


def pop_gold_notices(conn: "sqlite3.Connection", campaign_id: int) -> "str | None":
    """PT-D2 #1125: emit the delayed 💰 pickpocket notice once its counter matures.

    Called once per turn. Decrements every pending notice's turn counter and, for
    any that just reached zero, returns a narrator [SYSTEM:...] line that surfaces
    the loss as a 💰 bubble ("orientujesz się, że sakiewka jest lżejsza").
    Returns None when nothing is due. Never raises.
    """
    try:
        from app.services import social_encounter_service as ses

        gs = conn.execute(
            "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not gs:
            return None
        flags = json.loads(gs["session_flags"] or "{}")
        if not flags.get("pending_gold_notices"):
            return None

        # PT-F4 #1138: never surface the 💰 pickpocket bubble mid-combat — freeze the
        # counters (don't decrement) so the notice waits until after the fight, matching
        # pop_local_travel_hint's combat guard.
        if _has_active_combat(conn, campaign_id):
            return None

        due = ses.pop_due_gold_notices(flags)
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), gs["id"]),
        )
        conn.commit()

        if not due:
            return None

        total = sum(int(n.get("amount", 0)) for n in due)
        if total <= 0:
            return None
        return (
            f"\n[SYSTEM: 💰 Gracz orientuje się, że jego sakiewka jest lżejsza o {total} zł "
            f"— ktoś musiał go okraść wcześniej. Wpleć krótko (1 zdanie) to odkrycie.]"
        )
    except Exception as e:
        logger.warning("pop_gold_notices_failed", error=str(e))
        return None


# ── Main pipeline function (removed) ────────────────────────────────────────
# PT11 #1121: process_v2_turn (the orphaned V2 turn pipeline whose MOVEMENT
# branch reached _resolve_movement) was deleted — it had zero callers; the live
# tor is game_engine.run_narrative_turn → api/turns.py. See issue #1121.
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
    # #1142: destination hex without a location = wilderness — clear the stale
    # current_location_id (set_position treats None as "leave unchanged", so the old
    # sub-location would leak into the narrator context: "wciąż jesteś przy tartaku").
    set_position(
        conn,
        campaign_id=campaign_id,
        current_hex={"q": int(dest_q), "r": int(dest_r)},
        current_location_id=loc_id,
        clear_location_id=(loc_id is None),
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

    # PT-F7 #1141: no longer inject current_location_key into the flags dict — readers
    # (context_injector, game_engine, encounter gate, WSM, suggested_actions) derive it
    # directly from current_location_id via get_current_location_key(). One source only.

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
            # #1207 — LLM-emitted signal: objective-typed beats close only via event hooks
            if mark_beat_visited(campaign_id, beat_key, turn_number, conn, via_llm_tag=True):
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
        "SELECT id FROM campaign_turns WHERE campaign_id = ? "
        "AND (user_text = '' OR user_text IS NULL) LIMIT 1",
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

    # #1152: when the plan has no key_locations, ground the opening in the party's
    # real position (anchored location / hex terrain) so the intro doesn't invent a
    # place that contradicts engine state ("teleport" on the next narrative turn).
    starting_loc_name = starting_loc.get("name")
    if not starting_loc_name:
        try:
            from app.services.location_state_service import describe_start_position
            starting_loc_name = describe_start_position(conn, campaign_id)
        except Exception:
            starting_loc_name = None
    starting_loc_name = starting_loc_name or "nieznane miejsce"

    # #1208 — plan-declared starting hour: the opening prose must match the clock
    # (evening tavern narrated as evening, not a default morning).
    time_line = ""
    try:
        _sh = int(plan.get("start_hour"))
        if 0 <= _sh <= 23:
            from app.services.clock_service import _time_of_day_label
            time_line = f"\n  Pora dnia: {_time_of_day_label(_sh)}, około {_sh:02d}:00"
    except (TypeError, ValueError):
        pass

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
  Miejsce startowe: {starting_loc_name}{time_line}

ZASADY:
- Napisz 100-200 słów po polsku
- Umieść postać fizycznie w miejscu startowym
- Jeśli podano porę dnia — scena dzieje się DOKŁADNIE o tej porze (światło, odgłosy, ruch ludzi)
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

        # Store as turn 1 (empty user_text — column is NOT NULL; #1152: NULL here
        # made every prebuilt opening fail and fall to the generic inline fallback)
        conn.execute(
            """INSERT INTO campaign_turns
               (campaign_id, character_id, user_text, assistant_text, route, turn_number)
               VALUES (?, ?, '', ?, 'narrative', 1)""",
            (campaign_id, character_id, prose)
        )
        conn.commit()

        logger.info("opening_scene_generated", campaign_id=campaign_id)
        return prose

    except Exception as e:
        logger.warning("opening_scene_failed", campaign_id=campaign_id, error=str(e))
        return None
