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
    generate_clarification_suggestions
)
from app.services.world_state_machine import WorldStateMachine, build_session_flags
from app.services.mechanic_resolver import resolve as mechanic_resolve
from app.services.context_injector import ContextInjector
from app.services.world_service import (
    process_create_tags, get_current_location_info,
    build_available_content_index, build_v2_npc_context_block
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

    # ── Step 1: Parse input ────────────────────────────────────────────────
    if is_structured_action(user_input):
        parsed = parse_structured_action(user_input)
    else:
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

    # ── Step 6: World State Update ────────────────────────────────────────
    turn_number = _get_next_turn_number(campaign_id, conn)
    _apply_world_state(mechanic_result, context, character_id, campaign_id, turn_number, conn)
    _update_session_flags(wsm_result, session_flags, mechanic_result, conn, campaign_id)

    # XS1: Beat complete XP
    xp_delta = _process_beat_signals(mechanic_result, campaign_id, character_id, turn_number, conn)
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
        turn_number=turn_number,
    )

    # ── Step 8: LLM Narrator ──────────────────────────────────────────────
    try:
        prose_raw = generate_chat(
            messages=[{"role": "user", "content": narrator_prompt}],
            model=model,
            llm_config=llm_config,
            call_type="narrator",
            campaign_id=campaign_id,
        ) or ""
    except Exception as e:
        logger.warning("turn_pipeline_narrator_error", error=str(e))
        prose_raw = _fallback_prose(action_type, mechanic_result)

    # Clear one-shot active_encounter after it was consumed by the narrator
    if refreshed_flags.get("active_encounter"):
        refreshed_flags.pop("active_encounter", None)
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (json.dumps(refreshed_flags, ensure_ascii=False), campaign_id),
        )
        conn.commit()

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
        "UPDATE game_sessions SET current_location_id = ? WHERE campaign_id = ?",
        (loc_row[0], campaign_id)
    )
    conn.execute(
        "UPDATE game_locations SET usage_count = usage_count + 1 WHERE id = ?",
        (loc_row[0],),
    )
    conn.commit()


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
        _cid_for_log = None
        try:
            _cid_for_log = int(campaign_id) if campaign_id else None
        except Exception:
            pass
        prose = generate_chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            llm_config=llm_config,
            call_type="intro_scene",
            campaign_id=_cid_for_log,
        ) or ""

        if not prose.strip():
            prose = f"{name} przybywa do celu. Coś w powietrzu zdaje się nie tak."

        # Store as turn 1 (no user_text)
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
