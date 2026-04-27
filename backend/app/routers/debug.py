import json
import os
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from app.core.db_runtime import resolve_db_path

DB_PATH = resolve_db_path()

router = APIRouter(prefix="/debug", tags=["debug"])


def _parse_json(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        campaign_row = conn.execute(
            """
            SELECT id
            FROM campaigns
            WHERE title = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            ("AI Test Campaign",),
        ).fetchone()
        if not campaign_row:
            raise HTTPException(status_code=404, detail="AI test campaign not found")
        campaign_id = int(campaign_row["id"])
        character_row = conn.execute(
            """
            SELECT id, sheet_json
            FROM characters
            WHERE campaign_id = ?
              AND user_id = COALESCE(?, user_id)
            ORDER BY id ASC
            LIMIT 1
            """,
            (campaign_id, int(player_row["id"]) if player_row else None),
        ).fetchone()
        if not character_row:
            raise HTTPException(status_code=404, detail="AI test character not found")
        character_id = int(character_row["id"])
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
            SET status = 'active', death_reason = NULL, ended_at = NULL, epitaph = NULL
            WHERE id = ?
            """,
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
