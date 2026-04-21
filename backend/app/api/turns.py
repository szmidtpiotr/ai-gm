import json
import logging
import os
import re
import sqlite3

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.turn_engine import COMBAT_ROLL_CTX_PREFIX
from app.services.dice import (
    ROLL_CARD_PREFIX,
    build_gm_defense_roll_payload,
    build_roll_card_payload,
    format_roll_for_llm,
    parse_character_sheet,
    parse_roll_command,
    resolve_test_name,
    resolve_roll,
)
from app.services.game_engine import build_narrative_messages, run_narrative_turn
from app.services.helpme_advisor_service import run_helpme_advisor
from app.services.llm_service import (
    generate_chat,
    generate_chat_stream,
    get_effective_config,
    get_health,
)
from app.services.solo_death_service import apply_death_save_outcome, end_solo_campaign_on_death
from app.services.user_llm_settings import get_user_llm_settings_full

router = APIRouter()
DB_PATH = "/data/ai_gm.db"
logger = logging.getLogger(__name__)


def _flush_stdout_logs() -> None:
    """Promtail reads Docker log streams; flush root handlers so JSON lines ship immediately."""
    for h in logging.root.handlers:
        try:
            h.flush()
        except Exception:
            pass


COMBAT_START_RE = re.compile(r"\[COMBAT_START:([^\]]+)\]", re.IGNORECASE)


def _maybe_start_combat_from_gm_tag(
    campaign_id: int, character_id: int, assistant_text: str
) -> dict | None:
    """Parse [COMBAT_START:...] from GM text and initiate combat if allowed."""
    match = COMBAT_START_RE.search(assistant_text or "")
    if not match:
        logger.info("combat_gm_tag_absent campaign_id=%s", campaign_id)
        return None

    enemy_keys_raw = match.group(1)
    enemy_keys = [k.strip() for k in enemy_keys_raw.split(",") if k.strip()]

    if not enemy_keys:
        logger.warning("combat_gm_tag_empty campaign_id=%s", campaign_id)
        return None

    from app.services import combat_service as cs

    existing = cs.get_active_combat(campaign_id)
    if existing:
        logger.info("combat_gm_tag_skip_already_active campaign_id=%s", campaign_id)
        return None

    try:
        combat_state = cs.initiate_combat(campaign_id, character_id, enemy_keys)
        logger.info(
            "combat_gm_tag_started campaign_id=%s enemy_keys=%s combat_id=%s",
            campaign_id,
            enemy_keys,
            combat_state.get("id"),
        )
        return combat_state
    except Exception as e:
        logger.error("combat_gm_tag_error campaign_id=%s error=%s", campaign_id, str(e))
        return None


def _truncate_for_story_log(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + "…[truncated]"


def _maybe_advance_combat_after_player_narrative(campaign_id: int) -> dict | None:
    """
    After the player's narrative message is resolved and GM text is saved, advance combat
    initiative when it was the player's turn (so the next actor can act).
    """
    logger.info("combat_advance_check campaign_id=%s", campaign_id)
    from app.services import combat_service as cs

    combat = cs.get_active_combat(campaign_id)
    if not combat or combat.get("status") != "active":
        logger.info(
            "combat_advance_skip campaign_id=%s reason=no_active_or_not_active",
            campaign_id,
        )
        return None
    if str(combat.get("current_turn") or "") != "player":
        logger.info(
            "combat_advance_skip campaign_id=%s reason=not_player_turn current_turn=%s",
            campaign_id,
            combat.get("current_turn"),
        )
        return None
    try:
        new_turn = cs.advance_turn(campaign_id)
    except ValueError:
        logger.warning("advance_turn after narrative failed for campaign %s", campaign_id)
        return None
    logger.info(
        "combat_advance_ok campaign_id=%s new_combat_turn=%s",
        campaign_id,
        new_turn,
    )
    return {"combat_advanced": True, "new_combat_turn": new_turn}


def log_narrative_turn_structured(
    *,
    route: str,
    campaign_id: int,
    character_id: int | None,
    turn_row: dict,
    user_text: str,
    assistant_text: str,
) -> None:
    """
    Emit one JSON log line (via root JsonFormatter) for Loki/Grafana — near-live story
    without syncing SQLite to the observability VM. Disable with NARRATIVE_STORY_LOG=0.

    Optional: NARRATIVE_LOG_MAX_CHARS caps user_text / assistant_text size (0 = no cap).
    """
    if route != "narrative":
        return
    if os.getenv("NARRATIVE_STORY_LOG", "1").strip().lower() in ("0", "false", "no"):
        return
    try:
        max_chars = int(os.getenv("NARRATIVE_LOG_MAX_CHARS", "0") or "0")
    except ValueError:
        max_chars = 0
    try:
        logger.info(
            "narrative_turn",
            extra={
                "extra_fields": {
                    "event": "narrative_turn",
                    # String IDs so Loki/Grafana `| json | campaign_id=~"1033"` matches reliably.
                    "campaign_id": str(campaign_id),
                    "character_id": "" if character_id is None else str(character_id),
                    "turn_id": "" if turn_row.get("id") is None else str(turn_row.get("id")),
                    "turn_number": "" if turn_row.get("turn_number") is None else str(turn_row.get("turn_number")),
                    "created_at": turn_row.get("created_at"),
                    "user_text": _truncate_for_story_log(user_text or "", max_chars),
                    "assistant_text": _truncate_for_story_log(assistant_text or "", max_chars),
                }
            },
        )
        _flush_stdout_logs()
    except Exception:
        # Never fail a turn because logging broke
        pass


def log_memory_turn_structured(
    *,
    campaign_id: int,
    character_id: int | None,
    turn_row: dict,
    user_text: str,
    assistant_text: str,
) -> None:
    """Emit JSON log line for /mem turns (Loki: event=memory_turn). Same opt-out as narrative."""
    if os.getenv("NARRATIVE_STORY_LOG", "1").strip().lower() in ("0", "false", "no"):
        return
    try:
        max_chars = int(os.getenv("NARRATIVE_LOG_MAX_CHARS", "0") or "0")
    except ValueError:
        max_chars = 0
    try:
        logger.info(
            "memory_turn",
            extra={
                "extra_fields": {
                    "event": "memory_turn",
                    "campaign_id": str(campaign_id),
                    "character_id": "" if character_id is None else str(character_id),
                    "turn_id": "" if turn_row.get("id") is None else str(turn_row.get("id")),
                    "turn_number": "" if turn_row.get("turn_number") is None else str(turn_row.get("turn_number")),
                    "created_at": turn_row.get("created_at"),
                    "user_text": _truncate_for_story_log(user_text or "", max_chars),
                    "assistant_text": _truncate_for_story_log(assistant_text or "", max_chars),
                }
            },
        )
        _flush_stdout_logs()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Command registry — used by /help and the command dispatcher
# ---------------------------------------------------------------------------
COMMAND_REGISTRY = {
    "/help": "Show this list of available commands",
    "/sheet": "Display your full character sheet",
    "/roll": "Roll d20 + modifier for the last GM-requested roll",
    "/name <new name>": "Rename your character",
    "/history": "Show the last 10 turns of the session",
    "/mem [pytanie]": "Pytanie o przeszłość z podsumowań — bez wpływu na narrację (żółte dymki)",
    "/helpme [pytanie]": "Doradca OOC — wskazówki bez zmiany fabuły (czerwone dymki); nie wpływa na kontekst narracji",
    "/export": "Export the full session to a text file on the server (/data/exports/)",
}


class TurnCreate(BaseModel):
    character_id: int
    text: str
    system: str | None = None
    engine: str | None = None
    game_id: int | None = None


class SearchPayload(BaseModel):
    character_id: int
    target: str | None = None
    context: dict | None = None


def _stream_combat_roll_extras(user_text_val: str) -> tuple[dict | None, dict | None]:
    """
    For combat follow-up turns (COMBAT_ROLL prefix): optional GM defense bubble payload
    and optional combat-ended hint for the client (victory after last kill).
    """
    s = (user_text_val or "").strip()
    if not s.startswith(COMBAT_ROLL_CTX_PREFIX):
        return None, None
    tail = s[len(COMBAT_ROLL_CTX_PREFIX) :].lstrip("\r\n \t")
    try:
        payload = json.loads(tail)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, None
    # player_flee (and other kinds): no [GM_ROLL] / [COMBAT_ENDED] — flee ends via /combat/flee
    if not isinstance(payload, dict) or payload.get("kind") != "player_attack":
        return None, None
    gm_roll: dict | None = None
    if payload.get("hit"):
        label = (payload.get("target_name") or "").strip() or "Wróg"
        gm_roll = build_gm_defense_roll_payload(
            enemy_key=str(payload.get("enemy_key") or ""),
            enemy_label=label,
        )
    combat_ended: dict | None = None
    if payload.get("combat_victory"):
        name = (
            (payload.get("target_name") or payload.get("enemy_name") or "Wróg").strip() or "Wróg"
        )
        combat_ended = {"reason": "enemy_killed", "enemy_name": name}
    return gm_roll, combat_ended


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def validate_roll_cue_name(assistant_text: str) -> str | None:
    lines = (assistant_text or "").splitlines()
    if not lines:
        return None
    last_line = (lines[-1] or "").strip()
    cue_match = re.match(r"^Roll (.+?) (d\d+)$", last_line, re.I)
    if not cue_match:
        return None
    raw_test_name = (cue_match.group(1) or "").strip()
    canonical = resolve_test_name(raw_test_name)
    if canonical is None:
        logger.warning("Unknown LLM roll cue test name ignored: %s", raw_test_name)
    return canonical


def resolve_model_name(
    requested_model: str | None,
    campaign_model: str | None,
    llm_config: dict[str, str] | None = None,
) -> str:
    effective = get_effective_config(llm_config)
    if effective["provider"] == "openai":
        return (requested_model or campaign_model or effective["model"]).strip()

    health = get_health(llm_config)
    available = health.get("models") or []
    if not available:
        return (requested_model or campaign_model or effective["model"]).strip()
    if requested_model and requested_model in available:
        return requested_model
    if campaign_model and campaign_model in available:
        return campaign_model
    if effective["model"] in available:
        return effective["model"]
    return available[0]


def get_campaign_or_404(conn: sqlite3.Connection, campaign_id: int):
    campaign = conn.execute(
        "SELECT * FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def get_character_or_404(
    conn: sqlite3.Connection, campaign_id: int, character_id: int
):
    character = conn.execute(
        "SELECT * FROM characters WHERE id = ? AND campaign_id = ?",
        (character_id, campaign_id),
    ).fetchone()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character


def get_active_campaign_or_gone(conn: sqlite3.Connection, campaign_id: int):
    """404 if missing, 410 if campaign has ended (solo death / GM-ended)."""
    campaign = get_campaign_or_404(conn, campaign_id)
    if str(campaign["status"] or "").lower() == "ended":
        raise HTTPException(status_code=410, detail="This campaign has ended.")
    return campaign


def get_next_turn_number(conn: sqlite3.Connection, campaign_id: int) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(turn_number), 0) AS max_turn
        FROM campaign_turns
        WHERE campaign_id = ?
        """,
        (campaign_id,),
    ).fetchone()
    return int(row["max_turn"] or 0) + 1


def create_turn_log(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int | None,
    user_text: str,
    assistant_text: str | None,
    route: str,
):
    cur = conn.cursor()
    turn_number = get_next_turn_number(conn, campaign_id)

    cur.execute(
        """
        INSERT INTO campaign_turns (
            campaign_id,
            character_id,
            user_text,
            route,
            assistant_text,
            turn_number
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (campaign_id, character_id, user_text, route, assistant_text, turn_number),
    )

    turn_id = cur.lastrowid

    row = cur.execute(
        """
        SELECT id, campaign_id, turn_number, created_at
        FROM campaign_turns
        WHERE id = ?
        """,
        (turn_id,),
    ).fetchone()

    conn.commit()

    return {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "turn_number": row["turn_number"],
        "created_at": row["created_at"],
    }


# ---------------------------------------------------------------------------
# Helper: export session to text file
# ---------------------------------------------------------------------------

def _export_session_to_file(conn: sqlite3.Connection, campaign_id: int) -> str:
    """Writes all turns for campaign_id to /data/exports/campaign_<id>_<ts>.txt"""
    import time

    rows = conn.execute(
        """
        SELECT turn_number, user_text, assistant_text, created_at
        FROM campaign_turns
        WHERE campaign_id = ?
        ORDER BY turn_number ASC
        """,
        (campaign_id,),
    ).fetchall()

    campaign = conn.execute(
        "SELECT title, system_id FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()

    export_dir = "/data/exports"
    os.makedirs(export_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    filename = f"{export_dir}/campaign_{campaign_id}_{ts}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        title = campaign["title"] if campaign else f"Campaign {campaign_id}"
        system = campaign["system_id"] if campaign else "unknown"
        f.write(f"=== {title} [{system}] ===\n")
        f.write(f"Exported: {ts}\n")
        f.write("=" * 60 + "\n\n")

        for row in rows:
            f.write(f"[Turn {row['turn_number']}] {row['created_at']}\n")
            f.write(f"PLAYER: {row['user_text']}\n")
            if row["assistant_text"]:
                f.write(f"GM:     {row['assistant_text']}\n")
            f.write("\n")

    return filename


# ---------------------------------------------------------------------------
# GET turns list
# ---------------------------------------------------------------------------

@router.get("/campaigns/{campaign_id}/turns")
def list_campaign_turns(
    campaign_id: int, limit: int = Query(default=30, ge=1, le=100)
):
    conn = get_db()
    try:
        get_active_campaign_or_gone(conn, campaign_id)

        rows = conn.execute(
            """
            SELECT
                t.id,
                t.campaign_id,
                t.character_id,
                t.user_text,
                t.route,
                t.assistant_text,
                t.created_at,
                t.turn_number,
                c.name AS character_name
                ,c.user_id AS character_user_id
            FROM campaign_turns t
            LEFT JOIN characters c ON c.id = t.character_id
            WHERE t.campaign_id = ?
            ORDER BY t.turn_number DESC
            LIMIT ?
            """,
            (campaign_id, limit),
        ).fetchall()

        turns = []
        for row in rows:
            r_route = row["route"]
            turns.append(
                {
                    "id": row["id"],
                    "turn_number": row["turn_number"],
                    "campaign_id": row["campaign_id"],
                    "character_id": row["character_id"],
                    "character_name": row["character_name"],
                    "character_user_id": row["character_user_id"],
                    "user_text": row["user_text"],
                    "assistant_text": row["assistant_text"],
                    "route": r_route,
                    "ooc": r_route == "helpme",
                    "created_at": row["created_at"],
                }
            )

        turns.reverse()

        return {
            "campaign_id": campaign_id,
            "turns": turns,
            "count": len(turns),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Export session endpoint
# ---------------------------------------------------------------------------

@router.post("/campaigns/{campaign_id}/export")
def export_session(campaign_id: int):
    """Exports the full session to a .txt file under /data/exports/"""
    conn = get_db()
    try:
        get_campaign_or_404(conn, campaign_id)
        filepath = _export_session_to_file(conn, campaign_id)
        return {"status": "ok", "file": filepath}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# POST turn (non-streaming)
# ---------------------------------------------------------------------------

@router.post("/campaigns/{campaign_id}/turns")
def create_turn(
    campaign_id: int,
    payload: TurnCreate,
    x_ollama_base_url: str | None = Header(default=None),
):
    conn = get_db()
    try:
        campaign = get_active_campaign_or_gone(conn, campaign_id)
        character = get_character_or_404(conn, campaign_id, payload.character_id)
        llm_config = get_user_llm_settings_full(character["user_id"])
        text = (payload.text or "").strip()

        if not text:
            raise HTTPException(status_code=400, detail="Text is required")

        roll_request = parse_roll_command(text)
        roll_result_message = None
        roll_result_data = None
        user_text_stored = text
        if roll_request:
            character_sheet = parse_character_sheet(character["sheet_json"])
            roll_result = resolve_roll(
                character_sheet=character_sheet,
                test_name=roll_request["skill"],
                raw_roll=roll_request.get("raw_roll"),
                dc=roll_request.get("dc"),
            )
            roll_result_data = roll_result
            roll_result_message = format_roll_for_llm(roll_result)
            user_text_stored = ROLL_CARD_PREFIX + "\n" + json.dumps(
                build_roll_card_payload(
                    roll_result,
                    character_name=(character["name"] or "Bohater"),
                    replay_command=text.strip(),
                ),
                ensure_ascii=False,
            )

        if roll_result_data and roll_result_data.get("test") == "death_save":
            sheet_dict = parse_character_sheet(character["sheet_json"])
            new_sheet, died_here = apply_death_save_outcome(sheet_dict, roll_result_data)
            conn.execute(
                """
                UPDATE characters SET sheet_json = ?
                WHERE id = ? AND campaign_id = ?
                """,
                (
                    json.dumps(new_sheet, ensure_ascii=False),
                    payload.character_id,
                    campaign_id,
                ),
            )
            conn.commit()
            character = get_character_or_404(conn, campaign_id, payload.character_id)
            if died_here:
                loc = (character["location"] or "unknown place").strip()
                dr = f"Failed three death saves ({loc})"
                epitaph = end_solo_campaign_on_death(
                    conn,
                    campaign_id=campaign_id,
                    character_row=character,
                    death_reason=dr,
                )
                user_line = user_text_stored if roll_request else (roll_result_message or text)
                log = create_turn_log(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    user_text=user_line,
                    assistant_text=epitaph,
                    route="narrative",
                )
                log_narrative_turn_structured(
                    route="narrative",
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    turn_row=log,
                    user_text=user_line,
                    assistant_text=epitaph,
                )
                return {
                    "id": log["id"],
                    "campaign_id": log["campaign_id"],
                    "turn_number": log["turn_number"],
                    "created_at": log["created_at"],
                    "route": "narrative",
                    "result": {"message": epitaph},
                    "campaign_ended": True,
                }

        if text.startswith("/") and not roll_request:
            route = "command"
            cmd = text.split(" ", 1)[0].lower()

            # /help
            if cmd == "/help":
                result = {
                    "command": "help",
                    "commands": COMMAND_REGISTRY,
                }
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return {**log, "route": "command", "result": result}

            # /name
            if cmd == "/name":
                new_name = text[5:].strip()
                if not new_name:
                    raise HTTPException(status_code=400, detail="Character name is required")
                conn.execute(
                    "UPDATE characters SET name = ? WHERE id = ? AND campaign_id = ?",
                    (new_name, payload.character_id, campaign_id),
                )
                conn.commit()
                result = {"command": "name", "character_name": new_name}
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return {**log, "route": "command", "result": result}

            # /sheet
            if cmd == "/sheet":
                result = {
                    "command": "sheet",
                    "character": {
                        "id": character["id"],
                        "name": character["name"],
                        "campaign_id": character["campaign_id"],
                        "user_id": character["user_id"],
                        "system_id": character["system_id"],
                        "sheet_json": character["sheet_json"],
                        "location": character["location"],
                        "is_active": character["is_active"],
                        "created_at": character["created_at"],
                    },
                }
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return {**log, "route": "command", "result": result}

            # /history
            if cmd == "/history":
                rows = conn.execute(
                    """
                    SELECT turn_number, user_text, assistant_text, created_at
                    FROM campaign_turns
                    WHERE campaign_id = ?
                    ORDER BY turn_number DESC
                    LIMIT 10
                    """,
                    (campaign_id,),
                ).fetchall()
                history = [
                    {
                        "turn": r["turn_number"],
                        "player": r["user_text"],
                        "gm": r["assistant_text"],
                        "at": r["created_at"],
                    }
                    for r in reversed(rows)
                ]
                result = {"command": "history", "turns": history}
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return {**log, "route": "command", "result": result}

            # /helpme — OOC advisor (route=helpme; nie wchodzi do kontekstu narracji)
            if cmd == "/helpme":
                topic = re.sub(r"^/helpme\s*", "", text, count=1, flags=re.I).strip()
                owner_id = int(campaign["owner_user_id"])
                llm_owner = get_user_llm_settings_full(owner_id)
                model_h = resolve_model_name(
                    requested_model=payload.engine,
                    campaign_model=campaign["model_id"],
                    llm_config=llm_owner,
                )
                try:
                    out = run_helpme_advisor(
                        conn=conn,
                        campaign=campaign,
                        character=character,
                        topic=topic,
                        user_id=owner_id,
                        model=model_h,
                    )
                except RuntimeError as e:
                    raise HTTPException(status_code=502, detail=str(e)) from None
                msg = (out.get("message") or "").strip()
                if not msg:
                    raise HTTPException(status_code=502, detail="Empty /helpme response")
                log = create_turn_log(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    user_text=text.strip(),
                    assistant_text=msg,
                    route="helpme",
                )
                return {
                    "id": log["id"],
                    "campaign_id": log["campaign_id"],
                    "turn_number": log["turn_number"],
                    "created_at": log["created_at"],
                    "route": "helpme",
                    "ooc": True,
                    "result": {"message": msg},
                }

            # /export
            if cmd == "/export":
                filepath = _export_session_to_file(conn, campaign_id)
                result = {"command": "export", "file": filepath}
                log = create_turn_log(
                    conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                    user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
                )
                return {**log, "route": "command", "result": result}

            # Unknown command
            result = {"command": cmd, "message": f"Unknown command '{cmd}'. Type /help for a list."}
            log = create_turn_log(
                conn=conn, campaign_id=campaign_id, character_id=payload.character_id,
                user_text=text, assistant_text=json.dumps(result, ensure_ascii=False), route=route,
            )
            return {**log, "route": "command", "result": result}

        route = "narrative"
        model = resolve_model_name(
            requested_model=payload.engine,
            campaign_model=campaign["model_id"],
            llm_config=llm_config,
        )

        result = run_narrative_turn(
            conn=conn,
            campaign=campaign,
            character=character,
            user_text=text,
            model=model,
            ollama_base_url=x_ollama_base_url,
            llm_config=llm_config,
            roll_result_message=roll_result_message,
            roll_result_data=roll_result_data,
        )

        assistant_text = (result.get("message") or "").strip()
        if not assistant_text:
            raise HTTPException(status_code=500, detail="Empty narrative response")

        from app.services import combat_service as _cs

        combat_before = _cs.get_active_combat(campaign_id)
        combat_was_active = bool(combat_before) and str(
            combat_before.get("current_turn") or ""
        ) == "player"

        clean_assistant = COMBAT_START_RE.sub("", assistant_text).rstrip()
        validate_roll_cue_name(clean_assistant.strip())

        log = create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            user_text=user_text_stored if roll_request else text,
            assistant_text=clean_assistant,
            route=route,
        )
        log_narrative_turn_structured(
            route=route,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            turn_row=log,
            user_text=user_text_stored if roll_request else text,
            assistant_text=clean_assistant,
        )

        new_combat = _maybe_start_combat_from_gm_tag(
            campaign_id, payload.character_id, assistant_text
        )
        combat_extra = None
        if combat_was_active and not new_combat:
            combat_extra = _maybe_advance_combat_after_player_narrative(campaign_id)

        result_out = (
            {**result, "message": clean_assistant} if isinstance(result, dict) else result
        )

        out: dict = {
            "id": log["id"],
            "campaign_id": log["campaign_id"],
            "turn_number": log["turn_number"],
            "created_at": log["created_at"],
            "route": "narrative",
            "result": result_out,
        }
        if new_combat is not None:
            out["combat_state"] = new_combat
        if combat_extra:
            out.update(combat_extra)
        return out

    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# POST turn streaming (SSE)
# ---------------------------------------------------------------------------

@router.post("/campaigns/{campaign_id}/turns/stream")
def create_turn_stream(
    campaign_id: int,
    payload: TurnCreate,
    x_ollama_base_url: str | None = Header(default=None),
):
    """
    Streaming version of the turn endpoint.
    Returns a text/event-stream (SSE) response.
    Each chunk: 'data: <token>\\n\\n'
    Final chunk: 'data: [DONE]\\n\\n'
    The full assembled text is saved to campaign_turns after streaming completes.
    """
    conn = get_db()
    try:
        campaign = get_active_campaign_or_gone(conn, campaign_id)
        character = get_character_or_404(conn, campaign_id, payload.character_id)
        llm_config = get_user_llm_settings_full(character["user_id"])
        text = (payload.text or "").strip()

        if not text:
            raise HTTPException(status_code=400, detail="Text is required")

        if re.match(r"^/helpme(\s|$)", text, re.I):
            topic = re.sub(r"^/helpme\s*", "", text, count=1, flags=re.I).strip()
            owner_id = int(campaign["owner_user_id"])
            llm_owner = get_user_llm_settings_full(owner_id)
            model_h = resolve_model_name(
                requested_model=payload.engine,
                campaign_model=campaign["model_id"],
                llm_config=llm_owner,
            )
            try:
                out = run_helpme_advisor(
                    conn=conn,
                    campaign=campaign,
                    character=character,
                    topic=topic,
                    user_id=owner_id,
                    model=model_h,
                )
            except RuntimeError as e:
                err = str(e)

                def helpme_err_stream():
                    yield f"data: [ERROR] {err}\n\n"

                return StreamingResponse(
                    helpme_err_stream(),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

            msg = (out.get("message") or "").strip()
            if not msg:

                def helpme_empty_stream():
                    yield "data: [ERROR] Empty /helpme response\n\n"

                return StreamingResponse(
                    helpme_empty_stream(),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

            user_line = text.strip()
            create_turn_log(
                conn=conn,
                campaign_id=campaign_id,
                character_id=payload.character_id,
                user_text=user_line,
                assistant_text=msg,
                route="helpme",
            )

            def helpme_token_stream():
                safe = msg.replace("\\", "\\\\").replace("\n", "\\n")
                yield f"data: {safe}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                helpme_token_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        roll_request = parse_roll_command(text)
        roll_result_message = None
        roll_result_data = None
        user_text_stored = text
        if roll_request:
            character_sheet = parse_character_sheet(character["sheet_json"])
            roll_result = resolve_roll(
                character_sheet=character_sheet,
                test_name=roll_request["skill"],
                raw_roll=roll_request.get("raw_roll"),
                dc=roll_request.get("dc"),
            )
            roll_result_data = roll_result
            roll_result_message = format_roll_for_llm(roll_result)
            user_text_stored = ROLL_CARD_PREFIX + "\n" + json.dumps(
                build_roll_card_payload(
                    roll_result,
                    character_name=(character["name"] or "Bohater"),
                    replay_command=text.strip(),
                ),
                ensure_ascii=False,
            )

        if roll_result_data and roll_result_data.get("test") == "death_save":
            sheet_dict = parse_character_sheet(character["sheet_json"])
            new_sheet, died_here = apply_death_save_outcome(sheet_dict, roll_result_data)
            conn.execute(
                """
                UPDATE characters SET sheet_json = ?
                WHERE id = ? AND campaign_id = ?
                """,
                (
                    json.dumps(new_sheet, ensure_ascii=False),
                    payload.character_id,
                    campaign_id,
                ),
            )
            conn.commit()
            character = get_character_or_404(conn, campaign_id, payload.character_id)
            if died_here:
                loc = (character["location"] or "unknown place").strip()
                dr = f"Failed three death saves ({loc})"
                epitaph = end_solo_campaign_on_death(
                    conn,
                    campaign_id=campaign_id,
                    character_row=character,
                    death_reason=dr,
                )
                user_line = user_text_stored if roll_request else (roll_result_message or text)
                log = create_turn_log(
                    conn=conn,
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    user_text=user_line,
                    assistant_text=epitaph,
                    route="narrative",
                )
                log_narrative_turn_structured(
                    route="narrative",
                    campaign_id=campaign_id,
                    character_id=payload.character_id,
                    turn_row=log,
                    user_text=user_line,
                    assistant_text=epitaph,
                )

                def death_token_stream():
                    safe = epitaph.replace("\\", "\\\\").replace("\n", "\\n")
                    yield f"data: {safe}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    death_token_stream(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    },
                )

        # Commands are not streamed (except /roll, which is turned into a narrative input)
        if text.startswith("/") and not roll_request:
            def command_stream():
                yield f"data: [CMD] {text}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(command_stream(), media_type="text/event-stream")

        model = resolve_model_name(
            requested_model=payload.engine,
            campaign_model=campaign["model_id"],
            llm_config=llm_config,
        )

        llm_user_text = roll_result_message or text
        messages = build_narrative_messages(
            conn=conn,
            campaign=campaign,
            character=character,
            user_text=text,
            roll_result_message=roll_result_message,
            roll_result_data=roll_result_data,
        )

        campaign_id_val = campaign_id
        character_id_val = payload.character_id
        user_text_val = user_text_stored if roll_request else llm_user_text
        gm_roll_pre_payload, combat_ended_pre_payload = _stream_combat_roll_extras(user_text_val)

        def token_generator():
            """
            Order: (1) optional [GM_ROLL], (2) optional [COMBAT_ENDED] before narrative,
            (3) LLM chunks, (4) persist turn, (5) [COMBAT_STARTED] / [COMBAT], (6) [DONE].
            """
            from app.services import combat_service as cs_snap

            combat_before = cs_snap.get_active_combat(campaign_id_val)
            combat_was_active = bool(combat_before) and str(
                combat_before.get("current_turn") or ""
            ) == "player"

            if gm_roll_pre_payload:
                yield f"data: [GM_ROLL]{json.dumps(gm_roll_pre_payload, ensure_ascii=False)}\n\n"
            if combat_ended_pre_payload:
                yield f"data: [COMBAT_ENDED]{json.dumps(combat_ended_pre_payload, ensure_ascii=False)}\n\n"

            collected: list[str] = []
            saw_done = False
            for chunk in generate_chat_stream(
                messages=messages,
                model=model,
                llm_config=llm_config,
            ):
                if chunk.startswith("data: [ERROR]"):
                    yield chunk
                    return
                if chunk.startswith("data: [DONE]"):
                    saw_done = True
                    break
                token = chunk[6:].rstrip("\n")
                collected.append(token)
                yield chunk

            if not saw_done:
                logger.warning(
                    "stream ended without data [DONE] for campaign_id=%s; skipping save",
                    campaign_id_val,
                )
                return

            full_raw = "".join(collected).replace("\\n", "\n")
            new_combat = None
            combat_extra = None
            if full_raw.strip():
                clean_text = COMBAT_START_RE.sub("", full_raw).rstrip()
                validate_roll_cue_name(clean_text.strip())
                save_conn = get_db()
                try:
                    stream_log = create_turn_log(
                        conn=save_conn,
                        campaign_id=campaign_id_val,
                        character_id=character_id_val,
                        user_text=user_text_val,
                        assistant_text=clean_text,
                        route="narrative",
                    )
                    log_narrative_turn_structured(
                        route="narrative",
                        campaign_id=campaign_id_val,
                        character_id=character_id_val,
                        turn_row=stream_log,
                        user_text=user_text_val,
                        assistant_text=clean_text,
                    )
                    new_combat = _maybe_start_combat_from_gm_tag(
                        campaign_id_val, character_id_val, full_raw
                    )
                    if combat_was_active and not new_combat:
                        combat_extra = _maybe_advance_combat_after_player_narrative(
                            campaign_id_val
                        )
                finally:
                    save_conn.close()
            if new_combat:
                yield f"data: [COMBAT_STARTED]{json.dumps(new_combat)}\n\n"
            if combat_extra:
                yield f"data: [COMBAT]{json.dumps(combat_extra)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            token_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        conn.close()


@router.post("/campaigns/{campaign_id}/search")
def search_body_or_location(
    campaign_id: int,
    payload: SearchPayload,
):
    conn = get_db()
    try:
        campaign = get_active_campaign_or_gone(conn, campaign_id)
        character = get_character_or_404(conn, campaign_id, payload.character_id)

        enemy_name = (payload.context or {}).get("enemy_name") or payload.target or "postać"

        if not payload.target:
            search_user_text = f"[Gracz przeszukuje: {enemy_name}]"
        else:
            search_user_text = f"[Gracz przeszukuje: {payload.target}]"

        llm_config = get_user_llm_settings_full(character["user_id"])
        model = resolve_model_name(
            requested_model=None,
            campaign_model=campaign["model_id"],
            llm_config=llm_config,
        )

        messages = build_narrative_messages(
            conn=conn,
            campaign=campaign,
            character=character,
            user_text=search_user_text,
            roll_result_message=None,
            roll_result_data=None,
        )

        answer = generate_chat(messages=messages, model=model, llm_config=llm_config)
        answer = (answer or "").strip()

        log = create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=payload.character_id,
            user_text=search_user_text,
            assistant_text=answer,
            route="narrative",
        )

        return {
            "answer": answer,
            "turn_number": log["turn_number"] if isinstance(log, dict) else None,
            "created_at": log["created_at"] if isinstance(log, dict) else None,
        }
    finally:
        conn.close()
