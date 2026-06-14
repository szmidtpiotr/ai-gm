import json
import os
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Query, Body
from pydantic import BaseModel
from app.core.db_runtime import resolve_db_path

DB_PATH = resolve_db_path()

router = APIRouter(prefix="/debug", tags=["debug"])


# Stage 8 D2 — admin check helper (returns True/False without raising).
def _user_is_admin(user_id: int | None) -> bool:
    if not user_id:
        return False
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT is_admin FROM users WHERE id = ?", (int(user_id),)
        ).fetchone()
        return bool(row and int(row[0] or 0) == 1)
    finally:
        conn.close()


class DebugCommandRequest(BaseModel):
    character_id: int
    text: str
    user_id: int | None = None


@router.get("/last-turn")
def get_last_turn_debug(
    character_id: int = Query(...),
    user_id: int | None = Query(None, description="Legacy fallback — prefer Authorization: Bearer."),
    authorization: str | None = Header(default=None),
):
    """Stage 8 D5 — last-turn debug snapshot for the drawer.

    Pulls the most recent campaign_turns row + character sheet + session_flags
    so the player-debug drawer can render 6 tabs of state without the turn
    endpoint having to inline anything. Admin-only.
    """
    # Stage 10-C A6: prefer JWT role=admin; fall back to legacy DB lookup.
    from app.core.jwt_auth import require_admin_role
    require_admin_role(authorization, user_id)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        char = conn.execute(
            "SELECT id, campaign_id, name, sheet_json FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        if not char:
            raise HTTPException(status_code=404, detail="Character not found")
        campaign_id = char["campaign_id"]
        try:
            sheet = json.loads(char["sheet_json"] or "{}")
        except Exception:
            sheet = {}
        # Last turn for this campaign. Schema is minimal in DEV
        # (no intent_text/mechanic_result/etc. columns yet) — start with the
        # rich SELECT and fall back to bare columns on OperationalError.
        last_turn = None
        if campaign_id:
            try:
                row = conn.execute(
                    """
                    SELECT id, campaign_id, turn_number, route, user_text, assistant_text,
                           intent_text, mechanic_result, debug_meta, llm_response_json,
                           created_at
                    FROM campaign_turns
                    WHERE campaign_id = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (campaign_id,),
                ).fetchone()
            except sqlite3.OperationalError:
                row = conn.execute(
                    """
                    SELECT id, campaign_id, turn_number, route, user_text, assistant_text,
                           created_at
                    FROM campaign_turns
                    WHERE campaign_id = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (campaign_id,),
                ).fetchone()
            if row:
                last_turn = dict(row)
                # Decode JSON-bearing columns when present.
                for k in ("intent_text", "mechanic_result", "debug_meta", "llm_response_json"):
                    raw = last_turn.get(k)
                    if isinstance(raw, str) and raw.strip().startswith(("{", "[")):
                        try:
                            last_turn[k] = json.loads(raw)
                        except Exception:
                            pass
        # Session flags for state machine + zones + dungeon run
        session_flags = {}
        if campaign_id:
            srow = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE id = ?", (str(campaign_id),)
            ).fetchone()
            if srow and srow["session_flags"]:
                try:
                    session_flags = json.loads(srow["session_flags"])
                except Exception:
                    pass

        # Stage 8 follow-up: derive Intent/Mechanic from what's actually persisted.
        # campaign_turns is a bare table (no journaled intent/mechanic/llm/timing
        # columns yet) — we pull what's discoverable instead of returning null.
        intent_block = None
        mechanic_block = None
        assistant_raw = (last_turn or {}).get("assistant_text") if last_turn else None
        if last_turn:
            # Intent: route + user_text + any structured JSON in assistant_text
            parsed_assistant = None
            if isinstance(assistant_raw, str) and assistant_raw.strip().startswith("{"):
                try:
                    parsed_assistant = json.loads(assistant_raw)
                except Exception:
                    parsed_assistant = None
            intent_block = {
                "route": last_turn.get("route"),
                "user_text": last_turn.get("user_text"),
                "location_intent": (parsed_assistant or {}).get("location_intent"),
                "roll_cue": (parsed_assistant or {}).get("roll_cue"),
            }
        # Mechanic: prefer the live combat_state from session_flags, else show
        # the latest combat_turns row for this campaign.
        if isinstance(session_flags.get("combat_state"), dict):
            mechanic_block = {"source": "session_flags.combat_state",
                              "combat_state": session_flags["combat_state"]}
        elif campaign_id:
            try:
                ctrow = conn.execute(
                    """
                    SELECT id, turn_index, actor_type, actor_key, target_key,
                           action_type, event_type, payload_json, created_at
                    FROM combat_turns
                    WHERE campaign_id = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (campaign_id,),
                ).fetchone()
                if ctrow:
                    ct = dict(ctrow)
                    raw_payload = ct.get("payload_json")
                    if isinstance(raw_payload, str) and raw_payload.strip().startswith(("{", "[")):
                        try:
                            ct["payload_json"] = json.loads(raw_payload)
                        except Exception:
                            pass
                    mechanic_block = {"source": "combat_turns (last row)", "row": ct}
            except sqlite3.OperationalError:
                pass

        return {
            "character_id": int(char["id"]),
            "campaign_id": campaign_id,
            "name": char["name"],
            "game_state": {
                "sheet": sheet,
                "session_flags": session_flags,
            },
            "last_intent": intent_block or {
                "note": "Brak danych — wykonaj turę, aby wypełnić tę zakładkę.",
            },
            "mechanic_result": mechanic_block or {
                "note": "Brak aktywnej walki ani wpisu w combat_turns dla tej kampanii.",
            },
            "llm_prompts": {
                "note": "LLM prompts nie są jeszcze journalowane w campaign_turns. Planowane: dodać `llm_response_json` + `llm_prompts_json` kolumny i wpisywać podczas turn_pipeline.",
                "narrator_envelope_raw": _slice_debug({"x": assistant_raw}, "x") if assistant_raw else None,
            },
            "narrator_output": assistant_raw,
            "performance_timing": {
                "note": "Performance timing nie jest jeszcze journalowane. Planowane: zbierać per-phase czasy w turn_pipeline i zapisywać do debug_meta.",
            },
            "last_turn_meta": {
                "id": (last_turn or {}).get("id") if last_turn else None,
                "turn_number": (last_turn or {}).get("turn_number") if last_turn else None,
                "route": (last_turn or {}).get("route") if last_turn else None,
                "created_at": (last_turn or {}).get("created_at") if last_turn else None,
            } if last_turn else None,
            "c1_debug": {
                "turns_at_location": session_flags.get("turns_at_location", 0),
                "prev_turn_hex": session_flags.get("_prev_turn_hex"),
                "current_hex": session_flags.get("current_hex"),
                "story_stale_threshold": 5,
                "story_stale_active": int(session_flags.get("turns_at_location", 0)) >= 5,
            },
        }
    finally:
        conn.close()


def _slice_debug(last_turn: dict | None, key: str, limit: int = 8192) -> any:
    """Truncate large JSON blobs so the wire stays sane."""
    if not last_turn:
        return None
    val = last_turn.get(key)
    if val is None:
        return None
    if isinstance(val, str) and len(val) > limit:
        return val[:limit] + "… [truncated]"
    return val


@router.post("/command")
def debug_command(
    req: DebugCommandRequest,
    authorization: str | None = Header(default=None),
):
    """Stage 8 D2 — admin-only slash-command execution surface.

    Accepts `/debug ...` text and routes through commands_service so the same
    code powers both the in-game composer (which gates by is_admin client-side
    plus this server-side check) and any direct API harness we add later.
    """
    from app.core.jwt_auth import require_admin_role
    require_admin_role(authorization, req.user_id)
    text = (req.text or "").strip()
    # /roll [skill] is sugar for /debug roll [skill]
    if text.startswith("/roll"):
        skill_arg = text[5:].strip()
        text = f"/debug roll {skill_arg}".strip()
    if not text.startswith("/debug"):
        raise HTTPException(status_code=400, detail="Only /debug and /roll commands are accepted here")
    try:
        from app.services.commands_service import execute_command_logic
        result = execute_command_logic(req.character_id, text)
        return result.payload
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


def _parse_json(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ai_test_config_campaign_character_ids() -> tuple[int | None, int | None]:
    """
    W Dockerze katalog zwykle montuje /data/ai_test_config.json; seed zapisuje tam campaign_id/character_id.
    Bez tego reset brał «najnowszą» kampanię o tytule AI Test Campaign (ORDER BY id DESC) — pusty duplikat → 404.
    """
    path = (os.getenv("AI_TEST_CONFIG_PATH") or "/data/ai_test_config.json").strip()
    if not path or not os.path.isfile(path):
        return None, None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        raw_c = data.get("campaign_id")
        raw_h = data.get("character_id")
        cid = int(raw_c) if raw_c is not None and str(raw_c).strip() != "" else None
        chid = int(raw_h) if raw_h is not None and str(raw_h).strip() != "" else None
        return cid, chid
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None, None


@router.get("/player_state")
def get_player_state(character_id: int = Query(...)):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id, location, sheet_json, COALESCE(gold_gp, 0) AS gold_gp
            FROM characters
            WHERE id = ?
            """,
            (character_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Character not found")

    sheet = _parse_json(row["sheet_json"], {})
    inventory: list[dict] = []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        inv_rows = conn.execute(
            """
            SELECT item_key, weapon_key, consumable_key, slot
            FROM character_inventory
            WHERE character_id = ?
            ORDER BY id ASC
            """,
            (character_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        inv_rows = []
    finally:
        conn.close()

    for inv in inv_rows:
        item_key = inv["item_key"] or inv["weapon_key"] or inv["consumable_key"]
        if not item_key:
            continue
        inventory.append(
            {
                "item_key": str(item_key),
                "slot": inv["slot"],
            }
        )

    quests_completed = (
        sheet.get("quests_completed")
        or sheet.get("completed_quests")
        or sheet.get("quest_completed")
        or []
    )
    quests_active = (
        sheet.get("quests_active")
        or sheet.get("active_quests")
        or sheet.get("quest_active")
        or []
    )

    return {
        "character_id": int(row["id"]),
        "location": str(row["location"] or ""),
        "hp": int(sheet.get("current_hp", 0) or 0),
        "max_hp": int(sheet.get("max_hp", sheet.get("current_hp", 0)) or 0),
        "gold_gp": int(row["gold_gp"] or 0),
        "inventory": inventory,
        "quests_completed": [str(x) for x in quests_completed if x is not None],
        "quests_active": [str(x) for x in quests_active if x is not None],
    }


def _decision_type(user_text: str, assistant_text: str, route: str) -> str:
    blob = f"{user_text} {assistant_text}".lower()
    if "location" in blob or "teleport" in blob:
        return "location_change"
    if "item" in blob or "loot" in blob or "gold" in blob:
        return "item_grant"
    if route == "combat":
        return "combat_action"
    return "narrative"


def _decision_reason(user_text: str, assistant_text: str) -> str:
    blob = f"{user_text} {assistant_text}".lower()
    if "quest" in blob and ("complete" in blob or "completed" in blob):
        return "quest_complete"
    if "teleport" in blob:
        return "admin_teleport"
    return "gm_override"


@router.get("/gm_decisions")
def get_gm_decisions(
    session_id: str = Query(...),
    limit: int = Query(20, ge=1, le=200),
):
    try:
        campaign_id = int(session_id)
    except ValueError:
        return {"session_id": session_id, "decisions": []}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT created_at, route, user_text, assistant_text, turn_number
            FROM campaign_turns
            WHERE campaign_id = ?
            ORDER BY turn_number DESC, id DESC
            LIMIT ?
            """,
            (campaign_id, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()

    decisions = []
    for row in rows:
        user_text = str(row["user_text"] or "")
        assistant_text = str(row["assistant_text"] or "")
        route = str(row["route"] or "narrative")
        decisions.append(
            {
                "timestamp": str(row["created_at"] or _iso_now()),
                "type": _decision_type(user_text, assistant_text, route),
                "reason": _decision_reason(user_text, assistant_text),
                "is_legal": True,
                "details": {
                    "turn_number": row["turn_number"],
                    "route": route,
                    "user_text": user_text,
                    "assistant_text": assistant_text,
                },
            }
        )

    return {"session_id": session_id, "decisions": decisions}


@router.get("/validation_flags")
def get_validation_flags(test_run_id: str = Query(...)):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT created_at, event, is_legal, reason, old_state, new_state
            FROM debug_validation_log
            WHERE test_run_id = ?
            ORDER BY id DESC
            """,
            (test_run_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()

    flags = []
    for row in rows:
        flags.append(
            {
                "timestamp": str(row["created_at"] or _iso_now()),
                "event": str(row["event"] or "UNKNOWN"),
                "is_legal": bool(int(row["is_legal"] or 0)),
                "reason": str(row["reason"] or ""),
                "old_state": _parse_json(row["old_state"], {}),
                "new_state": _parse_json(row["new_state"], {}),
            }
        )

    return {"test_run_id": test_run_id, "flags": flags}


@router.get("/settings/feature_flags")
def feature_flags():
    """Publiczny endpoint flag funkcji dla frontendu."""
    return {"ai_test_mode": os.getenv("AI_TEST_MODE") == "1"}


@router.post("/reset_test_env")
def reset_test_env():
    if os.getenv("AI_TEST_MODE") != "1":
        raise HTTPException(status_code=404, detail="Not found")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        player_row = conn.execute(
            "SELECT id FROM users WHERE username = ? LIMIT 1",
            ("ai_test_player",),
        ).fetchone()
        gm_row = conn.execute(
            "SELECT id FROM users WHERE username = ? LIMIT 1",
            ("ai_test_gm",),
        ).fetchone()

        cfg_campaign_id, cfg_character_id = _ai_test_config_campaign_character_ids()
        character_row = None
        campaign_id: int | None = None

        if cfg_character_id is not None:
            character_row = conn.execute(
                """
                SELECT id, sheet_json, campaign_id
                FROM characters
                WHERE id = ?
                """,
                (cfg_character_id,),
            ).fetchone()
            if character_row:
                campaign_id = int(character_row["campaign_id"])

        if campaign_id is None and cfg_campaign_id is not None:
            crow = conn.execute(
                "SELECT id FROM campaigns WHERE id = ? AND title = ?",
                (cfg_campaign_id, "AI Test Campaign"),
            ).fetchone()
            if crow:
                campaign_id = int(crow["id"])

        if campaign_id is None:
            campaign_row = conn.execute(
                """
                SELECT id
                FROM campaigns
                WHERE title = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                ("AI Test Campaign",),
            ).fetchone()
            if not campaign_row:
                raise HTTPException(status_code=404, detail="AI test campaign not found")
            campaign_id = int(campaign_row["id"])

        if not character_row:
            character_row = conn.execute(
                """
                SELECT id, sheet_json, campaign_id
                FROM characters
                WHERE campaign_id = ?
                  AND user_id = COALESCE(?, user_id)
                ORDER BY id ASC
                LIMIT 1
                """,
                (campaign_id, int(player_row["id"]) if player_row else None),
            ).fetchone()

        if not character_row:
            character_row = conn.execute(
                """
                SELECT id, sheet_json, campaign_id
                FROM characters
                WHERE campaign_id = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (campaign_id,),
            ).fetchone()

        if not character_row:
            raise HTTPException(
                status_code=404,
                detail="AI test character not found (uruchom seed: python -m scripts.seed_ai_test_env w katalogu backend, AI_TEST_MODE=1)",
            )
        character_id = int(character_row["id"])
        campaign_id = int(character_row["campaign_id"])
        sheet = _parse_json(character_row["sheet_json"], {})
        max_hp = int(sheet.get("max_hp", sheet.get("current_hp", 0)) or 0)
        sheet["current_hp"] = max_hp

        conn.execute("BEGIN")
        try:
            run_rows = conn.execute(
                "SELECT test_run_id FROM game_sessions WHERE campaign_id = ? AND test_run_id IS NOT NULL",
                (campaign_id,),
            ).fetchall()
            run_ids = [str(r["test_run_id"]) for r in run_rows if r["test_run_id"]]
        except sqlite3.OperationalError:
            run_ids = []
        try:
            if run_ids:
                conn.executemany(
                    "DELETE FROM debug_validation_log WHERE test_run_id = ?",
                    [(run_id,) for run_id in run_ids],
                )
            else:
                conn.execute("DELETE FROM debug_validation_log WHERE test_run_id LIKE 'ai_test_%'")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("DELETE FROM campaign_turns WHERE campaign_id = ?", (campaign_id,))
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("DELETE FROM combat_turns WHERE campaign_id = ?", (campaign_id,))
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("DELETE FROM active_combat WHERE campaign_id = ?", (campaign_id,))
        except sqlite3.OperationalError:
            pass
        conn.execute(
            "UPDATE characters SET sheet_json = ?, location = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), "Start", character_id),
        )
        conn.execute(
            """
            UPDATE campaigns
            SET status = 'active', death_reason = NULL, ended_at = NULL, epitaph = NULL,
                model_id = NULL
            WHERE id = ?
            """,
            (campaign_id,),
        )
        # Ensure a game_sessions row exists so the in-game clock (#390) and
        # world-state flags function in the test env like real campaigns; reset
        # the clock to the 09:00 baseline so clock-tick tests start fresh.
        sess = conn.execute(
            "SELECT id FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not sess:
            conn.execute(
                "INSERT INTO game_sessions (id, campaign_id, session_flags, ingame_hours) "
                "VALUES (?, ?, '{\"ingame_hours\": 9}', 9)",
                (f"sess-test-{campaign_id}", campaign_id),
            )
        else:
            conn.execute(
                "UPDATE game_sessions SET session_flags = '{\"ingame_hours\": 9}', ingame_hours = 9 "
                "WHERE campaign_id = ?",
                (campaign_id,),
            )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"reset failed: {exc}") from None
    finally:
        conn.close()

    return {
        "reset": True,
        "campaign_id": campaign_id,
        "character_id": character_id,
        "player_id": int(player_row["id"]) if player_row else None,
        "gm_id": int(gm_row["id"]) if gm_row else None,
        "timestamp": _iso_now(),
    }


# ── B7 (#354) — DEV Inspector: live intent + world state + gate result ────────

@router.get("/campaigns/{campaign_id}/state", tags=["debug"])
def get_campaign_debug_state(
    campaign_id: int,
    user_id: int | None = Query(None),
    authorization: str | None = Header(default=None),
):
    """Return live diagnostic state for a campaign: intent, world_state, gate_result.

    Reconstructs intent from last player turn text + re-runs gate validation
    against current world state. Admin-only.
    """
    if authorization:
        token = authorization.removeprefix("Bearer ").strip()
        from app.services.admin_auth import verify_admin_token
        if not verify_admin_token(token):
            # Fall back to JWT admin check (player UI sends access token)
            from app.core.jwt_auth import require_admin_role
            require_admin_role(authorization, user_id)
    elif not _user_is_admin(user_id):
        raise HTTPException(status_code=403, detail="Admin role required")

    from app.services.world_state_service import get_world_state_flags
    from app.services.intent_service import parse_intent
    from app.services.gate_service import validate_action

    # ── World State ──────────────────────────────────────────────────────────
    try:
        ws = get_world_state_flags(campaign_id)
    except Exception:
        ws = {
            "scene_enemies": [], "scene_npcs": [], "active_quests": [],
            "player_conditions": [], "scene_cleared": False,
        }

    # ── Last player turn text ────────────────────────────────────────────────
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT user_text FROM campaign_turns
               WHERE campaign_id = ?
               ORDER BY id DESC LIMIT 1""",
            (campaign_id,),
        ).fetchone()
    finally:
        conn.close()

    last_input = row["user_text"] if row else None

    # ── Intent ───────────────────────────────────────────────────────────────
    if last_input:
        pi = parse_intent(last_input, campaign_id)
        intent = {
            "action_type": pi.action_type,
            "target": pi.target,
            "confidence": pi.confidence,
            "raw_input": pi.raw_input,
        }
    else:
        intent = None

    # ── Gate result ──────────────────────────────────────────────────────────
    if last_input:
        try:
            gate = validate_action(
                campaign_id,
                last_input,
                intent={"action_type": (intent or {}).get("action_type", "UNKNOWN"),
                        "target": (intent or {}).get("target")},
            )
            gate_result = {
                "blocked": not gate.allowed,
                "reason": gate.reason,
                "feedback": gate.feedback,
            }
        except Exception as e:
            gate_result = {"blocked": False, "reason": None, "feedback": str(e)}
    else:
        gate_result = {"blocked": False, "reason": None, "feedback": None}

    # ── C1 debug ─────────────────────────────────────────────────────────────
    c1_debug: dict = {}
    narrative_state: dict = {}  # D6 (#381) — surfaced in Inspector
    try:
        from app.services.game_engine import build_travel_hint_block

        conn2 = sqlite3.connect(DB_PATH)
        conn2.row_factory = sqlite3.Row
        try:
            sf_row = conn2.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if sf_row and sf_row["session_flags"]:
                _sf = json.loads(sf_row["session_flags"] or "{}")
                narrative_state = _sf.get("narrative_state") or {}
                _stale = int(_sf.get("turns_at_location", 0))
                _discovered = _sf.get("discovered_hexes", [])
                _travel_hint = build_travel_hint_block(_discovered, _stale)
                c1_debug = {
                    "turns_at_location": _stale,
                    "prev_turn_hex": _sf.get("_prev_turn_hex"),
                    "current_hex": _sf.get("current_hex"),
                    "story_stale_threshold": 5,
                    "story_stale_active": _stale >= 5,
                    "travel_hints": _travel_hint,
                    "discovered_locations_count": len(_discovered) if _discovered else 0,
                }
        finally:
            conn2.close()
    except Exception:
        pass

    return {
        "campaign_id": campaign_id,
        "intent": intent,
        "world_state": ws,
        "gate_result": gate_result,
        "last_player_input": last_input,
        "c1_debug": c1_debug,
        "narrative_state": narrative_state,
    }


@router.get("/robbery-preview", tags=["debug"])
def robbery_preview(level: int = Query(1, ge=1, le=20)):
    """U24 (#574) — read-only podgląd mechaniki napadu (counterplay).

    Deterministyczny kontrakt dla Playwright: DC obrony wg poziomu z zamka
    {8,12,16,20,24} + stałe granic (próg biedy, limit 24h, % kradzieży).
    Nie zmienia żadnego stanu. Mechanika decyduje — narrację robi LLM.
    """
    from app.services import robbery_service as _rs

    dc_lock = sorted(set(_rs._DC_LOCK))
    dc_by_level = {str(lvl): _rs.robbery_defense_dc(lvl) for lvl in range(1, 16)}
    return {
        "ok": True,
        "requested_level": level,
        "defense_dc": _rs.robbery_defense_dc(level),
        "dc_lock": dc_lock,
        "dc_by_level": dc_by_level,
        "poverty_threshold_gp": _rs.POVERTY_THRESHOLD_GP,
        "rate_limit_hours": _rs.RATE_LIMIT_HOURS,
        "gold_percent": _rs.get_robbery_config(_open_conn()).get("gold_percent"),
        "default_defense_stat": _rs.DEFAULT_DEFENSE_STAT,
    }


def _open_conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c
