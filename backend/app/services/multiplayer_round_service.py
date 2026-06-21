"""Multiplayer round service — collects player actions and triggers GM narration.

Flow:
1. Campaign in mode='multiplayer'; members tracked in campaign_members.
2. Each round: every member submits action_text via submit_action().
3. When all members submitted → _trigger_narration() → LLM → store JSON → mark done.
4. Players poll get_round_status(); fetch narrative via get_round_narration().
"""

import json
import random
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.db_runtime import resolve_db_path
from app.core.logging import get_logger
from app.services import llm_service
from app.services.dice import parse_character_sheet, resolve_roll

logger = get_logger(__name__)


# G5 #789 — injectable dice function for testability
def _d20() -> int:
    return random.randint(1, 20)


def _roll_initiative(character_id: int, conn: sqlite3.Connection) -> int:
    """G5 #789: Roll d20 + DEX modifier from character sheet."""
    dex_mod = 0
    if character_id:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id=?", (character_id,)
        ).fetchone()
        if row and row["sheet_json"]:
            try:
                sheet = json.loads(row["sheet_json"])
                stats = sheet.get("stats") or {}
                dex = int(stats.get("DEX", 10))
                dex_mod = (dex - 10) // 2
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    return _d20() + dex_mod


def resolve_initiative_conflicts(
    actions: list, scene_enemies: list
) -> list:
    """G5 #789: Sort actions by initiative_roll DESC; detect enemy-targeting conflicts.

    When multiple players' actions mention the same scene enemy, the highest-initiative
    player claims it. Lower-initiative players targeting the same enemy get
    conflict_note='Cel już martwy'. Does not mutate the input list or dicts.
    Returns a new sorted list.
    """
    sorted_actions = sorted(
        [dict(a) for a in actions],
        key=lambda a: (a.get("initiative_roll", 0),),
        reverse=True,
    )

    # Build deduplicated enemy name variants for matching
    _seen_names: set = set()
    enemy_names: list = []
    for e in (scene_enemies or []):
        for field in ("name", "key"):
            v = (e.get(field) or "").strip().lower()
            if v and len(v) > 2 and v not in _seen_names:
                _seen_names.add(v)
                enemy_names.append(v)

    claimed: dict = {}  # lowercase enemy name → user_id of first claimant

    for action in sorted_actions:
        text = (action.get("action_text") or "").lower()
        conflict_note = None

        for name in enemy_names:
            if name not in text:
                continue
            if name in claimed:
                conflict_note = "Cel już martwy"
                break
            claimed[name] = action.get("user_id", 0)

        if conflict_note:
            action["conflict_note"] = conflict_note

    return sorted_actions

# G8 (#792) — Pass 1: planner LLM decides which tests are needed (returns JSON array, no narrative)
_MP_PLANNER_PROMPT = """Jesteś planistą testów umiejętności dla sesji RPG.
Na podstawie akcji graczy zdecyduj, które testy umiejętności są potrzebne w tej rundzie.

Odpowiedz WYŁĄCZNIE poprawnym JSON array (bez dodatkowego tekstu, bez markdown):
[
  {"character_name": "ImiéPostaci", "test": "stealth", "dc": 12}
]

Nazwy kanoniczne testów (używaj wyłącznie tych):
stealth, athletics, awareness, persuasion, intimidation, medicine, survival, lore,
investigation, arcana, alchemy, melee_attack, ranged_attack, spell_attack,
fortitude_save, reflex_save, willpower_save, arcane_save, death_save.

Skala DC: easy=8, medium=12, hard=16, extreme=20, legendary=24+

Zasady:
- Uwzględnij tylko postaci, których akcje WYRAŹNIE wymagają rzutu (fizyczna trudność, przekonywanie, skradanie itp.).
- Akcje narracyjne (rozmowa bez perswazji, ruch po otwartym terenie) → brak testu.
- Odpowiedź MUSI być samym JSON array. Jeśli brak testów → odpowiedz [].
"""

# G8 (#792) — Pass 2: narrator LLM receives roll results as immutable facts
_MULTIPLAYER_SYSTEM_PROMPT = """Jesteś Mistrzem Gry w tekstowej grze RPG osadzonej w mrocznym świecie fantasy.
Odpowiadasz WYŁĄCZNIE po polsku.

## TRYB MULTIPLAYER — ZASADY NADRZĘDNE

Prowadzisz grupę graczy (2–4 osoby) w TRYBIE MULTIPLAYER. Wszystkie zasady solo nadal obowiązują, ale:

### NARRACJA W TRZECIEJ OSOBIE
- Narruj w TRZECIEJ osobie (nie "widzisz" lecz "widzą", "Aldric zauważa", "Mira czuje").
- Każdego gracza adresuj po imieniu jego postaci.
- Akcje wszystkich graczy w rundzie dzieją się RÓWNOCZEŚNIE — narruj je jako jedną spójną scenę.

### INICJATYWA I KOLEJNOŚĆ ROZSTRZYGANIA (G5)
- Akcje graczy są podane W KOLEJNOŚCI inicjatywy (wyższa = pierwsza; numer przed imieniem).
- Gracz z wyższą inicjatywą działa PIERWSZY — jego akcja rozstrzyga się jako pierwsza.
- Jeśli akcja gracza ma marker [KONFLIKT: Cel już martwy], ten gracz dotarł za późno.
  → Wstaw do player_notes dla tego gracza komunikat: "Cel już martwy — Twoja postać była za wolna".
  → Narruj że cel już nie żyje zanim bohater zdążył zaatakować.
  → NIE stosuj efektów ataku do martwego wroga (brak podwójnych obrażeń).
- [KONFLIKT: Cel już zabrany] — przedmiot/cel zniknął zanim gracz dotarł.
  → Wstaw do player_notes: "Cel już zabrany — ktoś był szybszy".

### JEDNOCZESNOŚĆ AKCJI
- Akcje graczy w rundzie rozstrzygają się w kolejności inicjatywy, ale narruj je jako płynną scenę.
- Każdy gracz ma swój moment — narruj ich działania jako jedną spójną scenę, nie serial wydarażeń.
- Jeśli akcje graczy są SPRZECZNE (jeden atakuje NPC którego drugi chce przekonać słowami):
  → Wyższy init ma pierwszeństwo — jego akcja narzuca rzeczywistość dla pozostałych.
  → Narruj naturalną konsekwencję konfliktu inicjatyw.

### WYNIKI RZUTÓW — FAKTY NIENARUSZALNE (G8)
Jeśli w wiadomości użytkownika widzisz sekcję [WYNIKI RZUTÓW]:
- Te wyniki są OBLICZONE PRZEZ KOD — nie możesz ich zmienić ani odwrócić.
- Sukces pozostaje sukcesem, porażka pozostaje porażką — nawet jeśli narracyjnie wolałbyś inaczej.
- Wstaw każdy wynik rzutu do narracji w formacie: 🎲 <Umiejętność>: <suma> vs DC <dc> ✓/✗
  Przykłady: "🎲 Skradanie: 14 vs DC 12 ✓", "🎲 Perswazja: 8 vs DC 16 ✗"
- Nat 20 = krytyczny sukces (napisz to wprost). Nat 1 = krytyczna porażka (napisz to wprost).

### FORMAT ODPOWIEDZI
Odpowiedź MUSI być poprawnym JSON:
{
  "narrative": "Narracja całej rundy w 3. osobie. Zawiera 🎲 linie dla każdego rzutu.",
  "player_notes": {
    "nazwa_postaci": "Prywatna informacja tylko dla tego gracza"
  }
}

- "player_notes" — prywatne notatki per gracz. Pomiń klucz jeśli brak prywatnej informacji.

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

        # G5 #789 — roll initiative before storing action
        initiative = _roll_initiative(character_id, conn)

        conn.execute(
            """
            INSERT INTO campaign_round_actions
                (round_id, campaign_id, user_id, character_id, character_name, action_text, initiative_roll)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(round_id, user_id) DO UPDATE SET
                action_text = excluded.action_text,
                character_name = excluded.character_name,
                submitted_at = datetime('now'),
                initiative_roll = excluded.initiative_roll
            """,
            (round_id, campaign_id, user_id, character_id, character_name, action_text, initiative),
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


def _llm_call(driver, cfg: dict, system_prompt: str, user_msg: str) -> str:
    return driver.generate_chat(
        base_url=cfg["base_url"],
        model=cfg["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        api_key=cfg.get("api_key", ""),
    )


def _parse_json_response(raw: str) -> dict | list:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1]
        clean = clean.rsplit("```", 1)[0].strip()
    return json.loads(clean)


def _load_character_sheet(char_id: int, conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id=?", (char_id,)
    ).fetchone()
    if not row:
        return {}
    return parse_character_sheet(row["sheet_json"])


def _format_roll_fact_line(fact: dict) -> str:
    if fact.get("is_nat20"):
        verdict = "✓ KRYTYCZNY SUKCES"
    elif fact.get("is_nat1"):
        verdict = "✗ KRYTYCZNA PORAŻKA"
    elif fact.get("success") is True:
        verdict = "✓"
    elif fact.get("success") is False:
        verdict = "✗"
    else:
        verdict = "—"  # no DC set; indeterminate
    dc_part = f"vs DC {fact['dc']} " if fact.get("dc") is not None else ""
    return (
        f"{fact['character_name']} / {fact['test']}: "
        f"k20={fact['raw']}, mod={fact['modifier']:+d}, suma {fact['total']} "
        f"{dc_part}→ {verdict}"
    )


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
            "SELECT character_name, action_text, user_id, initiative_roll, character_id "
            "FROM campaign_round_actions WHERE round_id = ? ORDER BY submitted_at",
            (round_id,),
        ).fetchall()

        # G8 #792 — preload character sheets for skill rolls
        char_sheets: dict[str, dict] = {}
        for a in actions:
            char_name = a["character_name"]
            char_id = int(a["character_id"]) if a["character_id"] else 0
            if char_id and char_name not in char_sheets:
                char_sheets[char_name] = _load_character_sheet(char_id, conn)
    finally:
        conn.close()

    if not actions:
        return

    # G4 #788 — include shared world state context so LLM knows current scene state
    ws_context = ""
    scene_enemies: list = []
    try:
        from app.services.world_state_service import get_world_state_flags
        ws = get_world_state_flags(campaign_id)
        parts = []
        scene_enemies = ws.get("scene_enemies") or []
        npcs = ws.get("scene_npcs") or []
        quests = ws.get("active_quests") or []
        if scene_enemies:
            names = [e.get("name", e.get("key", "?")) for e in scene_enemies]
            parts.append(f"Wrogowie w scenie: {', '.join(names)}")
        if npcs:
            names = [n.get("name", n.get("key", "?")) for n in npcs]
            parts.append(f"NPC w scenie: {', '.join(names)}")
        if quests:
            parts.append(f"Aktywne questy: {', '.join(str(q) for q in quests)}")
        if parts:
            ws_context = "[STAN ŚWIATA]\n" + "\n".join(parts) + "\n\n"
    except Exception as e:
        logger.warning("mp_world_state_context_failed", round_id=round_id, error=str(e)[:100])

    # G5 #789 — sort by initiative, detect conflicts
    action_dicts = [
        {
            "user_id": int(a["user_id"]),
            "character_name": a["character_name"],
            "action_text": a["action_text"],
            "initiative_roll": int(a["initiative_roll"]),
        }
        for a in actions
    ]
    resolved_actions = resolve_initiative_conflicts(action_dicts, scene_enemies)

    # Build initiative-ordered actions block with conflict markers
    action_lines = []
    for i, a in enumerate(resolved_actions, 1):
        line = f"{i}. {a['character_name']} (inicjatywa {a['initiative_roll']}): \"{a['action_text']}\""
        if a.get("conflict_note"):
            line += f" [KONFLIKT: {a['conflict_note']}]"
        action_lines.append(line)

    actions_block = "\n".join(action_lines)
    actions_header = (
        f"[RUNDA {round_number} — AKCJE GRACZY — kolejność wg inicjatywy]\n\n"
        f"{ws_context}"
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

        # G8 #792 — Pass 1: planner decides which skill tests are needed
        planner_raw = _llm_call(driver, cfg, _MP_PLANNER_PROMPT, actions_header)
        try:
            planned_tests = _parse_json_response(planner_raw)
            if not isinstance(planned_tests, list):
                planned_tests = []
        except Exception as e:
            logger.warning("mp_planner_parse_failed", round_id=round_id, error=str(e)[:100])
            planned_tests = []

        # G8 #792 — Roll code: resolve each planned test with the locked formula
        roll_facts: list[dict] = []
        for entry in planned_tests:
            if not isinstance(entry, dict):
                continue
            char_name = entry.get("character_name", "")
            test_name = entry.get("test", "")
            dc = entry.get("dc")
            sheet = char_sheets.get(char_name, {})
            try:
                dc_int = int(dc) if dc is not None else None
                result = resolve_roll(sheet, test_name, dc=dc_int)
                fact = {
                    "character_name": char_name,
                    "test": result["test"],
                    "raw": result["raw"],
                    "modifier": result["modifier"],
                    "total": result["total"],
                    "dc": dc_int,
                    "success": result["success"],
                    "is_nat20": result["is_nat20"],
                    "is_nat1": result["is_nat1"],
                }
                roll_facts.append(fact)
            except Exception as e:
                logger.warning(
                    "mp_roll_failed", char=char_name, test=test_name,
                    round_id=round_id, error=str(e)[:100]
                )

        # G8 #792 — Pass 2: narrator receives roll results as immutable facts
        narrator_user = actions_header
        if roll_facts:
            lines = [_format_roll_fact_line(f) for f in roll_facts]
            narrator_user += (
                "\n\n[WYNIKI RZUTÓW — FAKTY NIENARUSZALNE (rzucone przez kod)]\n"
                + "\n".join(lines)
            )

        raw = _llm_call(driver, cfg, _MULTIPLAYER_SYSTEM_PROMPT, narrator_user)
        parsed = _parse_json_response(raw)
    except Exception as e:
        logger.error("multiplayer_narration_failed", round_id=round_id, error=str(e)[:200])
        parsed = {
            "narrative": "Coś poszło nie tak z narracją — spróbuj ponownie.",
            "roll_cues": [],
            "player_notes": {},
        }
        roll_facts = []

    # G8 #792 — store roll_facts alongside narrative so frontend can display them
    parsed["roll_facts"] = roll_facts

    # G5 #789 — merge backend conflict notes into player_notes so they reach the player
    # regardless of whether LLM noticed the conflict
    for action in resolved_actions:
        if action.get("conflict_note"):
            char = action["character_name"]
            existing = parsed.get("player_notes", {}).get(char, "")
            if not existing:
                parsed.setdefault("player_notes", {})[char] = action["conflict_note"]

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

    # G4 #788 — persist shared world state snapshot after narration (one token per campaign)
    try:
        from app.services.world_state_service import auto_save_snapshot
        auto_save_snapshot(campaign_id, source="mp_round")
    except Exception as e:
        logger.warning("mp_world_state_snapshot_failed", campaign_id=campaign_id, error=str(e)[:100])

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
        # G8 #792 — filter roll_facts to show only this player's rolls
        all_roll_facts = data.get("roll_facts", [])
        my_roll_facts = [
            f for f in all_roll_facts if f.get("character_name") == character_name
        ] if character_name else []
        return {
            "round_id": round_id,
            "round_number": int(row["round_number"]),
            "narrative": data.get("narrative", ""),
            "roll_cues": data.get("roll_cues", []),
            "roll_facts": my_roll_facts,
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
            # G8 #792 — include this player's roll_facts for chat restore
            all_roll_facts = data.get("roll_facts", [])
            my_roll_facts = [
                f for f in all_roll_facts if f.get("character_name") == char_name
            ] if char_name else []
            result.append({
                "round_id": round_id,
                "round_number": int(r["round_number"]),
                "narrative": data.get("narrative", ""),
                "actions": [{"character_name": a["character_name"], "action_text": a["action_text"]} for a in actions],
                "my_note": my_note,
                "roll_facts": my_roll_facts,
            })
        return result
    finally:
        conn.close()


# ── G6 #790 — Party hex-move voting ───────────────────────────────────────────

def _resolve_move_votes(campaign_id: int, conn: sqlite3.Connection) -> Optional[dict]:
    """Count votes; return winner dict or None if tie can't be broken.

    Rules:
    - Hex with most votes wins (majority).
    - Tie → host's vote decides.
    - Clears votes + updates campaigns.party_hex_q/r on resolution.
    """
    camp = conn.execute(
        "SELECT host_user_id FROM campaigns WHERE id=?", (campaign_id,)
    ).fetchone()
    host_id = int(camp["host_user_id"]) if camp else 0

    votes = conn.execute(
        "SELECT user_id, target_q, target_r FROM campaign_move_votes WHERE campaign_id=?",
        (campaign_id,),
    ).fetchall()

    counts: dict = {}
    host_vote: Optional[tuple] = None
    for v in votes:
        key = (int(v["target_q"]), int(v["target_r"]))
        counts[key] = counts.get(key, 0) + 1
        if int(v["user_id"]) == host_id:
            host_vote = key

    if not counts:
        return None

    max_votes = max(counts.values())
    leaders = [k for k, c in counts.items() if c == max_votes]

    if len(leaders) == 1:
        winner_q, winner_r = leaders[0]
    else:
        # Tie → host's vote decides
        if host_vote and host_vote in leaders:
            winner_q, winner_r = host_vote
        else:
            # Host didn't vote for a tied hex — pick first tied hex (fallback)
            winner_q, winner_r = leaders[0]

    conn.execute(
        "UPDATE campaigns SET party_hex_q=?, party_hex_r=? WHERE id=?",
        (winner_q, winner_r, campaign_id),
    )
    conn.execute(
        "DELETE FROM campaign_move_votes WHERE campaign_id=?", (campaign_id,)
    )
    conn.commit()
    return {"winner_q": winner_q, "winner_r": winner_r}


def submit_move_vote(campaign_id: int, user_id: int, target_q: int, target_r: int) -> dict:
    """Submit (or replace) a player's hex-move vote.

    Returns current voting state. When all accepted members have voted, resolves
    immediately and returns resolved=True with winner coords.
    """
    conn = _db()
    try:
        camp = conn.execute(
            "SELECT host_user_id FROM campaigns WHERE id=? AND mode='multiplayer'",
            (campaign_id,),
        ).fetchone()
        if not camp:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Campaign not found")

        member = conn.execute(
            "SELECT 1 FROM campaign_members WHERE campaign_id=? AND user_id=? AND status='accepted'",
            (campaign_id, user_id),
        ).fetchone()
        if not member:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Not an active member of this campaign")

        conn.execute(
            """INSERT INTO campaign_move_votes (campaign_id, user_id, target_q, target_r)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(campaign_id, user_id) DO UPDATE SET target_q=excluded.target_q,
               target_r=excluded.target_r, voted_at=datetime('now')""",
            (campaign_id, user_id, target_q, target_r),
        )
        conn.commit()

        total = int(conn.execute(
            "SELECT COUNT(*) FROM campaign_members WHERE campaign_id=? AND status='accepted'",
            (campaign_id,),
        ).fetchone()[0])
        cast = int(conn.execute(
            "SELECT COUNT(*) FROM campaign_move_votes WHERE campaign_id=?",
            (campaign_id,),
        ).fetchone()[0])

        if cast >= total:
            result = _resolve_move_votes(campaign_id, conn)
            if result:
                return {"resolved": True, "winner_q": result["winner_q"], "winner_r": result["winner_r"],
                        "votes_cast": cast, "total_players": total}

        return {"resolved": False, "votes_cast": cast, "total_players": total}
    finally:
        conn.close()


def get_move_vote_status(campaign_id: int) -> dict:
    """Return current vote tallies for a campaign (without revealing individual choices)."""
    conn = _db()
    try:
        total = int(conn.execute(
            "SELECT COUNT(*) FROM campaign_members WHERE campaign_id=? AND status='accepted'",
            (campaign_id,),
        ).fetchone()[0])
        cast = int(conn.execute(
            "SELECT COUNT(*) FROM campaign_move_votes WHERE campaign_id=?",
            (campaign_id,),
        ).fetchone()[0])

        camp = conn.execute(
            "SELECT party_hex_q, party_hex_r FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        party_q = camp["party_hex_q"] if camp else None
        party_r = camp["party_hex_r"] if camp else None

        return {
            "resolved": False,
            "votes_cast": cast,
            "total_players": total,
            "party_hex_q": party_q,
            "party_hex_r": party_r,
        }
    finally:
        conn.close()


# ── G7 (#791) — MP Combat ────────────────────────────────────────────────────

def start_mp_combat(campaign_id: int, enemy_keys: list) -> dict:
    """G7 (#791) — Start MP combat for all campaign members.

    Collects character_ids of all accepted members with a character, then delegates
    to combat_service.initiate_combat_mp which builds the full sequential turn_order.
    """
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT character_id FROM campaign_members "
            "WHERE campaign_id=? AND status='accepted' AND character_id IS NOT NULL",
            (campaign_id,),
        ).fetchall()
        character_ids = [int(r["character_id"]) for r in rows]
    finally:
        conn.close()

    if not character_ids:
        raise ValueError("no characters in campaign for MP combat")

    from app.services.combat_service import initiate_combat_mp
    return initiate_combat_mp(campaign_id, character_ids, list(enemy_keys))


def submit_mp_combat_action(
    campaign_id: int,
    user_id: int,
    character_id: int,
    action_type: str,
    target_id: str | None = None,
    spell_key: str | None = None,
    raw_d20: int | None = None,
    roll_result: int | None = None,
) -> dict:
    """G7 (#791) — Player submits a combat action in MP sequential combat.

    After the player's action, enemy actors in turn_order are auto-resolved immediately
    until the next human player slot is reached.

    action_type: 'attack' | 'spell' | 'defense'
    """
    from app.services.combat_service import (
        get_active_combat, advance_turn, apply_mp_default_defense,
        resolve_attack,
    )

    actor_id = f"player:{character_id}"
    snap = get_active_combat(campaign_id)
    if not snap:
        raise ValueError("no active combat for campaign")
    if snap["current_turn"] != actor_id:
        raise ValueError(f"not {actor_id}'s turn (current: {snap['current_turn']})")

    enemy_results: list[dict] = []

    if action_type == "defense":
        result = apply_mp_default_defense(campaign_id, character_id)
        player_result = result
    else:
        result = resolve_attack(
            campaign_id=campaign_id,
            roll_result=roll_result,
            attacker=actor_id,
            raw_d20=raw_d20,
            spell_key=spell_key,
            target_id=target_id,
        )
        player_result = result
        # Advance turn after player action (unless already advanced via loot/end)
        current_snap = get_active_combat(campaign_id)
        if current_snap and current_snap["status"] == "active" and current_snap["current_turn"] == actor_id:
            advance_turn(campaign_id)

    # Auto-resolve enemy/NPC turns immediately until next human player turn
    MAX_AUTO = 20
    for _ in range(MAX_AUTO):
        current_snap = get_active_combat(campaign_id)
        if not current_snap or current_snap["status"] != "active":
            break
        cur = str(current_snap["current_turn"])
        # Stop at any human player slot
        if cur.startswith("player:"):
            break
        # Enemy turn — auto resolve
        enemy_r = resolve_attack(campaign_id, 0, attacker="enemy")
        enemy_results.append(enemy_r)
        # Advance to next turn (resolve_attack doesn't advance for enemies)
        snap_after = get_active_combat(campaign_id)
        if snap_after and snap_after["status"] == "active" and snap_after["current_turn"] == cur:
            advance_turn(campaign_id)

    final_snap = get_active_combat(campaign_id)
    return {
        "player_result": player_result,
        "enemy_results": enemy_results,
        "combat_state": final_snap,
    }
