import json
import os
import sqlite3
import time

from fastapi import HTTPException

from app.services.location_config_service import get_bool_flag
from app.services.location_intent_parser import LocationIntent
from app.services.location_validator import log_integrity_violation, validate_move

HANDLED_COMMANDS = frozenset({"/quest", "/export", "/move"})


def _export_session_to_file(conn: sqlite3.Connection, campaign_id: int) -> str:
    """Writes all turns for campaign_id to /data/exports/campaign_<id>_<ts>.txt"""
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


def handle(
    *,
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    text: str,
    cmd: str,
    turn_id,
    create_turn_log,
    _with_turn_trace,
):
    """Handle /quest, /export, /move slash commands.

    Returns the full API response dict if handled, None otherwise.
    """
    if cmd not in HANDLED_COMMANDS:
        return None

    route = "command"

    # /quest — list player's active quests + short narrative
    if cmd == "/quest":
        quest_rows = []
        try:
            quest_rows = conn.execute(
                """
                SELECT id, quest_type, title, narrative, status, created_turn
                FROM character_quests
                WHERE character_id = ? AND campaign_id = ? AND status = 'active'
                ORDER BY created_turn DESC, id DESC
                """,
                (character_id, campaign_id),
            ).fetchall()
        except Exception:
            quest_rows = []
        quests = []
        for r in quest_rows:
            narrative_str = str(r["narrative"] or "").strip()
            if len(narrative_str) > 220:
                narrative_str = narrative_str[:217].rstrip() + "…"
            quests.append({
                "id": int(r["id"]),
                "type": str(r["quest_type"] or "main"),
                "title": str(r["title"] or ""),
                "narrative": narrative_str,
                "created_turn": r["created_turn"],
            })
        if quests:
            lines = [f"📜 **Aktywne zadania** ({len(quests)}):", ""]
            for q in quests:
                type_badge = "⚔" if q["type"] == "main" else "•"
                lines.append(f"{type_badge} **{q['title']}**")
                if q["narrative"]:
                    lines.append(f"  {q['narrative']}")
                lines.append("")
            message = "\n".join(lines).rstrip()
        else:
            message = "📜 Brak aktywnych zadań."
        result = {"command": "quest", "quests": quests, "message": message}
        log = create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=character_id,
            user_text=text,
            assistant_text=json.dumps(result, ensure_ascii=False),
            route=route,
        )
        return _with_turn_trace({**log, "route": "command", "result": result}, turn_id)

    # /export
    if cmd == "/export":
        filepath = _export_session_to_file(conn, campaign_id)
        result = {"command": "export", "file": filepath}
        log = create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=character_id,
            user_text=text,
            assistant_text=json.dumps(result, ensure_ascii=False),
            route=route,
        )
        return _with_turn_trace({**log, "route": "command", "result": result}, turn_id)

    # /move — zmiana lokalizacji (Phase 8D)
    if cmd == "/move":
        target_location = text[5:].strip()  # Usuń "/move "
        if not target_location:
            raise HTTPException(status_code=400, detail="Podaj nazwę lokalizacji: /move [nazwa]")

        # Sprawdź czy Location Integrity jest włączone
        if not get_bool_flag("location_integrity_enabled", campaign_id, default=True):
            # System wyłączony — prosta zmiana bez walidacji
            result = {"command": "move", "location": target_location, "mode": "bypass"}
            log = create_turn_log(
                conn=conn,
                campaign_id=campaign_id,
                character_id=character_id,
                user_text=text,
                assistant_text=json.dumps(result, ensure_ascii=False),
                route=route,
            )
            return _with_turn_trace({**log, "route": "command", "result": result}, turn_id)

        # Walidacja przez Location Validator
        from dataclasses import dataclass  # noqa: F401

        intent = LocationIntent(action="move", target_label=target_location)
        result = validate_move(campaign_id, intent)

        if result.allowed:
            # Aktualizuj lokalizację w sesji
            if result.resolved_location_id:
                # #1157: sesja jest kluczowana przez campaign_id, NIE po PK `id`
                # (game_sessions.id != campaign_id). Zapis po `id = campaign_id`
                # trafiał w zły/nieistniejący wiersz i /move cicho nic nie zmieniał.
                conn.execute(
                    "UPDATE game_sessions SET current_location_id = ? WHERE campaign_id = ?",
                    (result.resolved_location_id, campaign_id)
                )
                conn.commit()

                # Pobierz nazwę nowej lokalizacji
                loc_row = conn.execute(
                    "SELECT label FROM game_locations WHERE id = ?",
                    (result.resolved_location_id,)
                ).fetchone()
                loc_name = loc_row["label"] if loc_row else target_location
            else:
                loc_name = target_location

            response_msg = f"Przenosisz się do: {loc_name}"
            if result.is_new_location:
                response_msg += " (nowa lokalizacja utworzona)"

            result_data = {
                "command": "move",
                "location": loc_name,
                "allowed": True,
                "is_new": result.is_new_location
            }
        else:
            # Blokada — loguj próbę
            log_integrity_violation(campaign_id, intent, result.block_reason or "Nieznany powód")

            response_msg = f"Nie możesz się tam przenieść: {result.block_reason}"
            result_data = {
                "command": "move",
                "location": target_location,
                "allowed": False,
                "reason": result.block_reason
            }

        log = create_turn_log(
            conn=conn,
            campaign_id=campaign_id,
            character_id=character_id,
            user_text=text,
            assistant_text=response_msg,
            route=route,
        )
        return _with_turn_trace({**log, "route": "command", "result": result_data}, turn_id)

    return None
