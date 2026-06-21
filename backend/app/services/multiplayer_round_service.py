"""Multiplayer round service — collects player actions and triggers GM narration.

Flow:
1. Campaign in mode='multiplayer'; members tracked in campaign_members.
2. Each round: every member submits action_text via submit_action().
3. When all members submitted → _trigger_narration() → LLM → store JSON → mark done.
4. Players poll get_round_status(); fetch narrative via get_round_narration().
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.db_runtime import resolve_db_path
from app.core.logging import get_logger
from app.services import llm_service

logger = get_logger(__name__)

_MULTIPLAYER_SYSTEM_PROMPT = """Jesteś Mistrzem Gry w tekstowej grze RPG osadzonej w mrocznym świecie fantasy.
Odpowiadasz WYŁĄCZNIE po polsku.

## TRYB MULTIPLAYER — ZASADY NADRZĘDNE

Prowadzisz grupę graczy (2–4 osoby) w TRYBIE MULTIPLAYER. Wszystkie zasady solo nadal obowiązują, ale:

### NARRACJA W TRZECIEJ OSOBIE
- Narruj w TRZECIEJ osobie (nie "widzisz" lecz "widzą", "Aldric zauważa", "Mira czuje").
- Każdego gracza adresuj po imieniu jego postaci.
- Akcje wszystkich graczy w rundzie dzieją się RÓWNOCZEŚNIE — narruj je jako jedną spójną scenę.

### JEDNOCZESNOŚĆ AKCJI
- Wszyscy gracze w rundzie działają w tym samym momencie.
- Nie ma kolejki — narruj jakby wszyscy ruszyli jednocześnie.
- Jeśli akcje graczy są SPRZECZNE (jeden atakuje NPC którego drugi chce przekonać słowami):
  → Najpierw opisz co każdy próbuje zrobić.
  → Następnie rozstrzygnij konflikt logicznie (przemoc wyklucza dialog w tej rundzie).
  → Narruj naturalną konsekwencję konfliktu.

### FORMAT ODPOWIEDZI
Odpowiedź MUSI być poprawnym JSON:
{
  "narrative": "Narracja całej rundy w 3. osobie. Opis akcji wszystkich graczy i ich wyników.",
  "roll_cues": [
    {"player": "nazwa_postaci", "skill": "Nazwa umiejętności", "dc": 12, "reason": "krótki powód"}
  ],
  "player_notes": {
    "nazwa_postaci": "Prywatna informacja tylko dla tego gracza"
  }
}

- "roll_cues" — lista rzutów których potrzebuje GM. Puste [] jeśli nie ma.
- "player_notes" — prywatne notatki per gracz. Pomiń klucz jeśli brak prywatnej informacji.
- Jeśli akcja gracza wymaga rzutu — uwzględnij w roll_cues, nie blokuj narracji.

### STYL
- Max 5 akapitów na narrację zbiorową.
- Każda postać powinna mieć swój moment w narracji.
- Nie powtarzaj opisów otoczenia — tylko zmiany i nowe akcje.
"""


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _get_campaign_member_count(campaign_id: int, conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM campaign_members WHERE campaign_id = ? AND status='accepted'",
        (campaign_id,),
    ).fetchone()
    return int(row["cnt"]) if row else 0


def _get_round_timer_minutes(campaign_id: int, conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(round_timer_minutes, round_timer_hours*60, 1440) as t FROM campaigns WHERE id=?",
        (campaign_id,),
    ).fetchone()
    return int(row["t"]) if row else 1440


def _make_deadline(timer_minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=timer_minutes)).isoformat()


def get_or_create_current_round(campaign_id: int) -> dict:
    conn = _db()
    try:
        row = conn.execute(
            "SELECT * FROM campaign_rounds WHERE campaign_id = ? AND status != 'done' "
            "ORDER BY round_number DESC LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if row:
            return dict(row)
        last = conn.execute(
            "SELECT MAX(round_number) as mx FROM campaign_rounds WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        next_num = (int(last["mx"]) + 1) if last and last["mx"] else 1
        timer_min = _get_round_timer_minutes(campaign_id, conn)
        deadline = _make_deadline(timer_min)
        cur = conn.execute(
            "INSERT INTO campaign_rounds (campaign_id, round_number, status, deadline) VALUES (?, ?, 'collecting', ?)",
            (campaign_id, next_num, deadline),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM campaign_rounds WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def submit_action(
    campaign_id: int,
    user_id: int,
    character_id: int,
    character_name: str,
    action_text: str,
) -> dict:
    conn = _db()
    try:
        # Accept both collecting AND narrating rounds (prevents phantom new rounds on re-edit races)
        round_row = conn.execute(
            "SELECT * FROM campaign_rounds WHERE campaign_id = ? AND status IN ('collecting', 'narrating') "
            "ORDER BY round_number DESC LIMIT 1",
            (campaign_id,),
        ).fetchone()

        just_transitioned = False
        if not round_row:
            last = conn.execute(
                "SELECT MAX(round_number) as mx FROM campaign_rounds WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            next_num = (int(last["mx"]) + 1) if last and last["mx"] else 1
            timer_min = _get_round_timer_minutes(campaign_id, conn)
            deadline = _make_deadline(timer_min)
            cur = conn.execute(
                "INSERT INTO campaign_rounds (campaign_id, round_number, status, deadline) VALUES (?, ?, 'collecting', ?)",
                (campaign_id, next_num, deadline),
            )
            conn.commit()
            round_id = cur.lastrowid
            prev_status = "collecting"
        else:
            round_id = int(round_row["id"])
            prev_status = round_row["status"]

        conn.execute(
            """
            INSERT INTO campaign_round_actions
                (round_id, campaign_id, user_id, character_id, character_name, action_text)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(round_id, user_id) DO UPDATE SET
                action_text = excluded.action_text,
                character_name = excluded.character_name,
                submitted_at = datetime('now')
            """,
            (round_id, campaign_id, user_id, character_id, character_name, action_text),
        )
        conn.execute(
            "UPDATE campaign_members SET absence_warnings = 0 WHERE campaign_id=? AND user_id=?",
            (campaign_id, user_id),
        )
        conn.commit()

        submitted = int(conn.execute(
            "SELECT COUNT(*) as cnt FROM campaign_round_actions WHERE round_id = ?",
            (round_id,),
        ).fetchone()["cnt"])
        total = _get_campaign_member_count(campaign_id, conn)

        status = prev_status  # preserve narrating if already set
        if prev_status == "collecting" and total > 0 and submitted >= total:
            conn.execute(
                "UPDATE campaign_rounds SET status='narrating', closed_at=datetime('now') WHERE id=?",
                (round_id,),
            )
            conn.commit()
            status = "narrating"
            just_transitioned = True

        return {
            "round_id": round_id,
            "status": status,
            "submitted": submitted,
            "total": total,
            "just_transitioned": just_transitioned,
        }
    finally:
        conn.close()


def trigger_narration(round_id: int) -> None:
    conn = _db()
    try:
        row = conn.execute(
            "SELECT r.*, r.campaign_id FROM campaign_rounds r WHERE r.id = ?",
            (round_id,),
        ).fetchone()
        if not row or row["status"] != "narrating":
            return  # already done or not ready
        campaign_id = int(row["campaign_id"])
        round_number = int(row["round_number"])

        actions = conn.execute(
            "SELECT character_name, action_text FROM campaign_round_actions WHERE round_id = ? ORDER BY submitted_at",
            (round_id,),
        ).fetchall()
    finally:
        conn.close()

    if not actions:
        return

    actions_block = "\n".join(
        f"{a['character_name']}: \"{a['action_text']}\"" for a in actions
    )
    user_msg = (
        f"[RUNDA {round_number} — AKCJE GRACZY — wszyscy działają jednocześnie]\n\n"
        f"{actions_block}"
    )

    try:
        cfg = llm_service.get_effective_config()
        provider = cfg["provider"]
        if provider == "openai":
            driver = llm_service.OpenAIDriver()
        elif provider == "azure":
            driver = llm_service.AzureDriver()
        else:
            driver = llm_service.OllamaDriver()

        raw = driver.generate_chat(
            base_url=cfg["base_url"],
            model=cfg["model"],
            messages=[
                {"role": "system", "content": _MULTIPLAYER_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            api_key=cfg.get("api_key", ""),
        )

        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
            clean = clean.rsplit("```", 1)[0].strip()
        parsed = json.loads(clean)
    except Exception as e:
        logger.error("multiplayer_narration_failed", round_id=round_id, error=str(e)[:200])
        parsed = {
            "narrative": "Coś poszło nie tak z narracją — spróbuj ponownie.",
            "roll_cues": [],
            "player_notes": {},
        }

    conn = _db()
    try:
        conn.execute(
            "UPDATE campaign_rounds SET status='done', narrative_json=? WHERE id=?",
            (json.dumps(parsed, ensure_ascii=False), round_id),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("multiplayer_narration_done", round_id=round_id, campaign_id=campaign_id)

    try:
        from app.services.push_notification_service import send_push_to_campaign_players
        send_push_to_campaign_players(
            campaign_id,
            "Narracja gotowa 📜",
            "Mistrz Gry opisał rundę. Czas na Twoją kolejną akcję!",
            url="/",
        )
    except Exception as e:
        logger.warning("push_narration_failed", error=str(e)[:100])


def get_round_status(campaign_id: int, user_id: int) -> Optional[dict]:
    conn = _db()
    try:
        row = conn.execute(
            "SELECT * FROM campaign_rounds WHERE campaign_id = ? ORDER BY round_number DESC LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not row:
            return None
        round_id = int(row["id"])
        submitted = int(conn.execute(
            "SELECT COUNT(*) as cnt FROM campaign_round_actions WHERE round_id = ?",
            (round_id,),
        ).fetchone()["cnt"])
        total = _get_campaign_member_count(campaign_id, conn)
        my_action = conn.execute(
            "SELECT action_text FROM campaign_round_actions WHERE round_id = ? AND user_id = ?",
            (round_id, user_id),
        ).fetchone()
        # Deliver pending host-transfer note (one-time, clear on read)
        host_note = None
        camp_row = conn.execute(
            "SELECT host_note FROM campaigns WHERE id=? AND host_user_id=?",
            (campaign_id, user_id),
        ).fetchone()
        if camp_row and camp_row["host_note"]:
            host_note = camp_row["host_note"]
            conn.execute("UPDATE campaigns SET host_note=NULL WHERE id=?", (campaign_id,))
            conn.commit()
        # G2 #786 — absence warnings per player
        warnings_rows = conn.execute(
            "SELECT user_id, COALESCE(absence_warnings, 0) as absence_warnings "
            "FROM campaign_members WHERE campaign_id=? AND status='accepted'",
            (campaign_id,),
        ).fetchall()
        warnings_by_player = {int(r["user_id"]): int(r["absence_warnings"]) for r in warnings_rows}
        vote_kick_suggested = any(w >= 3 for w in warnings_by_player.values())
        return {
            "round_id": round_id,
            "round_number": int(row["round_number"]),
            "status": row["status"],
            "deadline": row["deadline"],
            "submitted_count": submitted,
            "total_players": total,
            "my_submitted": my_action is not None,
            "my_action": my_action["action_text"] if my_action else None,
            "host_note": host_note,
            "absence_warnings_by_player": warnings_by_player,
            "vote_kick_suggested": vote_kick_suggested,
        }
    finally:
        conn.close()


def leave_campaign(campaign_id: int, user_id: int) -> dict:
    conn = _db()
    try:
        conn.execute(
            "UPDATE campaign_members SET status='left' WHERE campaign_id=? AND user_id=?",
            (campaign_id, user_id),
        )
        camp = conn.execute(
            "SELECT host_user_id FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        new_host_id = None
        new_host_name = None
        if camp and int(camp["host_user_id"]) == user_id:
            next_member = conn.execute(
                """SELECT m.user_id, u.display_name, u.username
                   FROM campaign_members m
                   JOIN users u ON u.id = m.user_id
                   WHERE m.campaign_id=? AND m.user_id!=? AND m.status='accepted'
                   ORDER BY m.id ASC LIMIT 1""",
                (campaign_id, user_id),
            ).fetchone()
            if next_member:
                new_host_id = int(next_member["user_id"])
                new_host_name = next_member["display_name"] or next_member["username"]
                conn.execute(
                    "UPDATE campaigns SET host_user_id=?, host_note=? WHERE id=?",
                    (new_host_id, "Zostałeś nowym Mistrzem Gry tej kampanii! Poprzedni gospodarz opuścił sesję.", campaign_id),
                )
            else:
                conn.execute(
                    "UPDATE campaigns SET status='inactive' WHERE id=?",
                    (campaign_id,),
                )
        conn.commit()
        try:
            from app.services.push_notification_service import send_push_to_campaign_players
            import threading
            if new_host_id:
                threading.Thread(
                    target=send_push_to_campaign_players,
                    args=(campaign_id, "Gracz opuścił grę", "Gracz opuścił sesję."),
                    kwargs={"url": "/", "exclude_user_id": user_id},
                    daemon=True,
                ).start()
        except Exception as e:
            logger.warning("push_leave_failed", error=str(e)[:100])
        return {"left": True, "new_host_user_id": new_host_id, "new_host_name": new_host_name}
    finally:
        conn.close()


def get_round_narration(campaign_id: int, user_id: int) -> Optional[dict]:
    conn = _db()
    try:
        row = conn.execute(
            "SELECT r.*, c.character_name FROM campaign_rounds r "
            "LEFT JOIN campaign_round_actions c ON c.round_id=r.id AND c.user_id=? "
            "WHERE r.campaign_id=? AND r.status='done' "
            "ORDER BY r.round_number DESC LIMIT 1",
            (user_id, campaign_id),
        ).fetchone()
        if not row or not row["narrative_json"]:
            return None
        round_id = int(row["id"])
        data = json.loads(row["narrative_json"])
        character_name = row["character_name"]
        my_note = None
        if character_name and data.get("player_notes"):
            my_note = data["player_notes"].get(character_name)
        actions = conn.execute(
            "SELECT character_name, action_text FROM campaign_round_actions "
            "WHERE round_id=? ORDER BY submitted_at",
            (round_id,),
        ).fetchall()
        return {
            "round_id": round_id,
            "round_number": int(row["round_number"]),
            "narrative": data.get("narrative", ""),
            "roll_cues": data.get("roll_cues", []),
            "my_note": my_note,
            "actions": [{"character_name": a["character_name"], "action_text": a["action_text"]} for a in actions],
        }
    finally:
        conn.close()


def sweep_expired_rounds() -> None:
    """Close expired collecting rounds; insert [BRAK AKCJI] for missing players.

    Idempotent: only touches status='collecting' rounds whose deadline has passed.
    """
    conn = _db()
    try:
        expired = conn.execute(
            "SELECT id, campaign_id FROM campaign_rounds "
            "WHERE status='collecting' AND datetime(deadline) < datetime('now')"
        ).fetchall()
    finally:
        conn.close()

    for row in expired:
        round_id = int(row["id"])
        campaign_id = int(row["campaign_id"])
        try:
            _close_expired_round(round_id, campaign_id)
        except Exception as e:
            logger.error("sweep_close_failed", round_id=round_id, error=str(e)[:200])


def _close_expired_round(round_id: int, campaign_id: int) -> None:
    import threading

    conn = _db()
    try:
        r = conn.execute(
            "SELECT status FROM campaign_rounds WHERE id=?", (round_id,)
        ).fetchone()
        if not r or r["status"] != "collecting":
            return

        missing = conn.execute(
            """SELECT m.user_id, c.id as char_id, c.name as char_name
               FROM campaign_members m
               LEFT JOIN characters c ON c.campaign_id=m.campaign_id AND c.user_id=m.user_id
               WHERE m.campaign_id=? AND m.status='accepted'
               AND m.user_id NOT IN (
                   SELECT user_id FROM campaign_round_actions WHERE round_id=?
               )""",
            (campaign_id, round_id),
        ).fetchall()

        for m in missing:
            char_id = m["char_id"] or 0
            char_name = m["char_name"] or f"Gracz{m['user_id']}"
            conn.execute(
                """INSERT OR IGNORE INTO campaign_round_actions
                   (round_id, campaign_id, user_id, character_id, character_name, action_text)
                   VALUES (?, ?, ?, ?, ?, '[BRAK AKCJI]')""",
                (round_id, campaign_id, m["user_id"], char_id, char_name),
            )
            conn.execute(
                "UPDATE campaign_members SET absence_warnings = absence_warnings + 1 "
                "WHERE campaign_id=? AND user_id=?",
                (campaign_id, m["user_id"]),
            )

        conn.execute(
            "UPDATE campaign_rounds SET status='narrating', closed_at=datetime('now') WHERE id=?",
            (round_id,),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("sweep_round_closed", round_id=round_id, campaign_id=campaign_id)
    threading.Thread(target=trigger_narration, args=(round_id,), daemon=True).start()


def get_rounds_history(campaign_id: int, user_id: int) -> list:
    """Return all completed rounds with actions + narration for full chat restore."""
    conn = _db()
    try:
        rounds = conn.execute(
            "SELECT * FROM campaign_rounds WHERE campaign_id=? AND status='done' ORDER BY round_number",
            (campaign_id,),
        ).fetchall()
        result = []
        for r in rounds:
            round_id = int(r["id"])
            if not r["narrative_json"]:
                continue
            data = json.loads(r["narrative_json"])
            actions = conn.execute(
                "SELECT character_name, action_text FROM campaign_round_actions "
                "WHERE round_id=? ORDER BY submitted_at",
                (round_id,),
            ).fetchall()
            my_action = conn.execute(
                "SELECT character_name FROM campaign_round_actions WHERE round_id=? AND user_id=?",
                (round_id, user_id),
            ).fetchone()
            char_name = my_action["character_name"] if my_action else None
            my_note = None
            if char_name and data.get("player_notes"):
                my_note = data["player_notes"].get(char_name)
            result.append({
                "round_id": round_id,
                "round_number": int(r["round_number"]),
                "narrative": data.get("narrative", ""),
                "actions": [{"character_name": a["character_name"], "action_text": a["action_text"]} for a in actions],
                "my_note": my_note,
            })
        return result
    finally:
        conn.close()
