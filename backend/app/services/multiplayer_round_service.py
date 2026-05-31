"""Multiplayer round service — collects player actions and triggers GM narration.

Flow:
1. Campaign in mode='multiplayer'; members tracked in campaign_members.
2. Each round: every member submits action_text via submit_action().
3. When all members submitted → _trigger_narration() → LLM → store JSON → mark done.
4. Players poll get_round_status(); fetch narrative via get_round_narration().
"""

import json
import sqlite3
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
        cur = conn.execute(
            "INSERT INTO campaign_rounds (campaign_id, round_number, status) VALUES (?, ?, 'collecting')",
            (campaign_id, next_num),
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
        round_row = conn.execute(
            "SELECT * FROM campaign_rounds WHERE campaign_id = ? AND status = 'collecting' "
            "ORDER BY round_number DESC LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not round_row:
            last = conn.execute(
                "SELECT MAX(round_number) as mx FROM campaign_rounds WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            next_num = (int(last["mx"]) + 1) if last and last["mx"] else 1
            cur = conn.execute(
                "INSERT INTO campaign_rounds (campaign_id, round_number, status) VALUES (?, ?, 'collecting')",
                (campaign_id, next_num),
            )
            conn.commit()
            round_id = cur.lastrowid
        else:
            round_id = int(round_row["id"])

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
        conn.commit()

        submitted = int(conn.execute(
            "SELECT COUNT(*) as cnt FROM campaign_round_actions WHERE round_id = ?",
            (round_id,),
        ).fetchone()["cnt"])
        total = _get_campaign_member_count(campaign_id, conn)

        status = "collecting"
        if total > 0 and submitted >= total:
            conn.execute(
                "UPDATE campaign_rounds SET status='narrating', closed_at=datetime('now') WHERE id=?",
                (round_id,),
            )
            conn.commit()
            status = "narrating"

        return {
            "round_id": round_id,
            "status": status,
            "submitted": submitted,
            "total": total,
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
        if not row:
            return
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
        return {
            "round_id": round_id,
            "round_number": int(row["round_number"]),
            "status": row["status"],
            "deadline": row["deadline"],
            "submitted_count": submitted,
            "total_players": total,
            "my_submitted": my_action is not None,
            "my_action": my_action["action_text"] if my_action else None,
        }
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
        data = json.loads(row["narrative_json"])
        character_name = row["character_name"]
        my_note = None
        if character_name and data.get("player_notes"):
            my_note = data["player_notes"].get(character_name)
        return {
            "round_id": int(row["id"]),
            "round_number": int(row["round_number"]),
            "narrative": data.get("narrative", ""),
            "roll_cues": data.get("roll_cues", []),
            "my_note": my_note,
        }
    finally:
        conn.close()
