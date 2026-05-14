import random
import re
import sqlite3
import json

from app.core.logging import get_logger
from app.core.turn_engine import buildmessages, loadrecentturns
from app.services.config_service import build_runtime_config_block
from app.services.gm_plan_schema import format_gm_plan_block
from app.services.dice import infer_roll_type, parse_character_sheet
from app.services.llm_service import generate_chat
from app.services.solo_death_service import DEATH_SAVE_FAILURE_THRESHOLD


logger = get_logger(__name__)


def resolve_enemy_loot(enemy_key: str) -> list[dict]:
    """
    Roll this enemy's drop_chance, then weight-pick one row from its loot table.
    Returns [{source_type, source_key, qty}, ...] with no duplicated catalog data.
    """
    from app.services.admin_config import DB_PATH, list_loot_entries

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT loot_table_key, drop_chance FROM game_config_enemies WHERE key = ?",
            (enemy_key,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return []
    lt = row["loot_table_key"]
    if not lt:
        return []
    dc = float(row["drop_chance"] if row["drop_chance"] is not None else 1.0)
    if random.random() > dc:
        return []

    entries = list_loot_entries(str(lt))
    if not entries:
        return []
    total_w = sum(max(1, int(e.get("weight") or 0)) for e in entries)
    if total_w < 1:
        return []
    r = random.random() * total_w
    acc = 0.0
    chosen = entries[-1]
    for e in entries:
        w = max(1, int(e.get("weight") or 0))
        acc += w
        if r < acc:
            chosen = e
            break
    st = str(chosen.get("source_type") or "item")
    if st == "item":
        sk = chosen.get("item_key")
    elif st == "consumable":
        sk = chosen.get("consumable_key")
    else:
        sk = chosen.get("weapon_key")
    qmin = max(1, int(chosen.get("qty_min") or 1))
    qmax = max(qmin, int(chosen.get("qty_max") or qmin))
    qty = random.randint(qmin, qmax)
    return [{"source_type": st, "source_key": sk, "qty": qty}]


# Heuristic: player message may signal attack intent (Polish + common enemy words).
_COMBAT_VERB_HINT = re.compile(
    r"(atak|ataku|ciach|cios|tnę|doby|broń|miecz|topór|łuk|kusz|"
    r"noż|walcz|strzel|rzucam|pięści|bandyt|straż|goblin|ork|"
    r"przeciwn|wrog|zabij|zran|uderz|tnij|rani)",
    re.IGNORECASE,
)


def _inactive_combat_tag_reminder(user_text: str | None) -> str:
    """
    When no active combat in DB, the model often obeys FORMAT CUE (Roll …) instead of [COMBAT_START].
    Append a high-salience block so Phase 8 combat can start from GM text.
    """
    lines = (
        "[MECHANIKA — WALKA W SYSTEMIE: NIEAKTYWNA]\n"
        "W tej kampanii nie ma jeszcze aktywnej walki w silniku. Gdy w TEJ odpowiedzi dochodzi do pierwszego starcia "
        "(wrogowie atakują, leci pocisk, bójka, gracz dobiera broń by uderzyć lub strzelić w cel), "
        "OSTATNIA linia całej odpowiedzi MUSI być wyłącznie tagiem w osobnej linii: [COMBAT_START:klucz] "
        "(patrz INICJOWANIE WALKI, PRZYPADEK 2, sekcja HIERARCHIA).\n"
        "Zabronione jako ostatnia linia w tej sytuacji: jakakolwiek linia «Roll … d20» ze słownika — w tym Initiative i Attack."
    )
    if user_text and _COMBAT_VERB_HINT.search(user_text):
        lines += (
            "\n\n[TREŚĆ TURY GRACZA — możliwy atak]\n"
            "Wiadomość gracza sugeruje przemoc lub atak. Jeśli przechodzisz do walki, w TEJ odpowiedzi zakończ "
            "[COMBAT_START:…], a nie linią Roll ze słownika."
        )
    return lines


import re as _re_skill
_SKILL_VERB_HINT = _re_skill.compile(
    r"\b(próbuj|próbować|spróbuj|staram|chcę|chcę się|zamiarzam|usiłuj|"
    r"skrad|przekrad|przekonaj|perswad|oszuk|zastraszy|przeszuk|spost|zauważ|"
    r"wytrop|przetrwaj|wylecz|zidentyfik|zbadaj|ident|użyj|kradnę|włamuj|wyważam|"
    r"skaczę|wspinaj|bieg|uciekam|uchylam|unikam)\b",
    _re_skill.IGNORECASE,
)

_SKILL_KEYS_HINT = (
    "stealth, lockpick, acrobatics, perception, insight, survival, "
    "persuasion, deception, intimidation, athletics, arcana, medicine, lore"
)


def _skill_test_tag_instruction(conn, campaign_id: int, user_text: str | None) -> str | None:
    """
    Inject [SKILL_TEST] tag instructions when player text hints at a non-combat skill use.
    Also loads custom skills from DB to include in the hint.
    """
    if not user_text:
        return None
    if not _SKILL_VERB_HINT.search(user_text):
        return None

    # Load extra custom skills from DB
    extra_skills = _SKILL_KEYS_HINT
    try:
        if conn:
            rows = conn.execute(
                "SELECT key FROM game_config_skills WHERE is_active = 1 ORDER BY sort_order"
            ).fetchall()
            if rows:
                extra_skills = ", ".join(r[0] for r in rows)
    except Exception:
        pass

    return (
        "[MECHANIKA — TESTY UMIEJĘTNOŚCI]\n"
        "Wiadomość gracza sugeruje próbę użycia umiejętności (skradanie, perswazja, identyfikacja, itp.).\n"
        "Gdy gracz próbuje działania wymagającego testu umiejętności, OSADŹ w swojej odpowiedzi tag:\n"
        "  [SKILL_TEST:klucz_umiejętności:DC:wartość]\n"
        "Przykłady:\n"
        "  [SKILL_TEST:stealth:DC:13]   ← skradanie (DC zależy od trudności)\n"
        "  [SKILL_TEST:alchemy:DC:14]   ← identyfikacja substancji\n"
        "  [SKILL_TEST:persuasion:OPPOSED:WIS]  ← przekonanie NPC (przeciwstawny)\n"
        "Tag musi stać SAMODZIELNIE w swojej linii (pusta linia przed i po).\n"
        "NIE opisuj wyniku rzutu — tag przerwie narrację i gracz sam rzuci kością.\n"
        f"Dostępne umiejętności: {extra_skills}.\n"
        "Jeśli działanie gracza jest BANALNE (nie wymaga rzutu), nie używaj tagu — narraj wprost."
    )


def _death_mechanica_system_append(
    character: sqlite3.Row | None, roll_result_data: dict | None
) -> str | None:
    """
    While the character has 1–2 death save failures, force the GM to end each non-roll
    narrative with 'Roll Death Save d20'. Skip when this turn is a death save resolution.
    """
    if not character:
        return None
    sheet = parse_character_sheet(character["sheet_json"])
    failures = int(sheet.get("death_save_failures") or 0)
    if failures < 1 or failures >= DEATH_SAVE_FAILURE_THRESHOLD:
        return None
    if roll_result_data and roll_result_data.get("test") == "death_save":
        return None
    return (
        "[MECHANIKA — STAN ŚMIERCI]\n"
        "Postać jest nieprzytomna i walczy o życie.\n"
        f"Liczba nieudanych rzutów śmierci: {failures} / {DEATH_SAVE_FAILURE_THRESHOLD}\n"
        "Zasada: na końcu KAŻDEJ tury (nie rzutu) musisz dodać dokładnie tę linię jako ostatnią:\n"
        "Roll Death Save d20\n"
        "Nie narruj wyzdrowienia. Nie kończ stanu śmierci fabularnie. Tylko rzut może zmienić ten stan."
    )


def _inject_location_llm_context(
    conn: sqlite3.Connection, campaign_id: int, messages: list[dict]
) -> None:
    """8D-LOC-1: blok [LOCATION CONTEXT] jako druga wiadomość systemowa (po głównym system prompt)."""
    from app.services.location_config_service import get_bool_flag
    from app.services.location_context_injector import (
        build_location_context_block,
        get_session_id_for_campaign,
    )

    if not messages:
        return

    sid = get_session_id_for_campaign(conn, campaign_id)
    if sid is None:
        logger.info("location_context_skipped", session_id=None, reason="no_session")
        return
    if not get_bool_flag("location_integrity_enabled", sid, default=True):
        logger.info(
            "location_context_skipped", session_id=str(sid), reason="flag_disabled"
        )
        return

    try:
        loc_block = build_location_context_block(sid, conn)
        if loc_block:
            known_count = sum(
                1 for ln in loc_block.splitlines() if ln.startswith("  - { ")
            )
            messages.insert(1, {"role": "system", "content": loc_block})
            logger.info(
                "location_context_injected",
                session_id=str(sid),
                known_count=known_count,
            )
        else:
            logger.info(
                "location_context_skipped",
                session_id=str(sid),
                reason="no_current_location",
            )
    except Exception as exc:
        logger.warning(
            "location_context_injection_failed",
            session_id=str(sid),
            error=str(exc),
        )


def build_npc_context_block(conn: sqlite3.Connection, campaign_id: int) -> str | None:
    """
    Build [NPC CONTEXT] block for LLM:
    - location-assigned NPC for current location
    - global NPC (no rows in npc_locations)
    """
    from app.services.location_context_injector import get_session_id_for_campaign

    sid = get_session_id_for_campaign(conn, campaign_id)
    current_key: str | None = None
    if sid is not None:
        row = conn.execute(
            """
            SELECT gl.key
            FROM game_sessions gs
            LEFT JOIN game_locations gl ON gl.id = gs.current_location_id
            WHERE gs.id = ?
            """,
            (str(sid),),
        ).fetchone()
        if row and row["key"]:
            current_key = str(row["key"])

    if current_key:
        rows = conn.execute(
            """
            SELECT DISTINCT n.key, n.label, n.npc_type, n.description, n.personality_json
            FROM npcs n
            WHERE COALESCE(n.is_active, 1) = 1
              AND (
                EXISTS (
                    SELECT 1 FROM npc_locations nl
                    WHERE nl.npc_id = n.id AND nl.location_key = ?
                )
                OR NOT EXISTS (
                    SELECT 1 FROM npc_locations nl2 WHERE nl2.npc_id = n.id
                )
              )
            ORDER BY n.npc_type, n.label COLLATE NOCASE
            """,
            (current_key,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT n.key, n.label, n.npc_type, n.description, n.personality_json
            FROM npcs n
            WHERE COALESCE(n.is_active, 1) = 1
              AND NOT EXISTS (
                SELECT 1 FROM npc_locations nl WHERE nl.npc_id = n.id
              )
            ORDER BY n.npc_type, n.label COLLATE NOCASE
            """
        ).fetchall()

    if not rows:
        return None

    lines = ["[NPC CONTEXT]"]
    if current_key:
        lines.append(f'current_location_key: {json.dumps(current_key)}')
    else:
        lines.append("current_location_key: null")
    lines.append("npcs_in_scene:")

    for row in rows:
        personality = ""
        topics = ""
        secret = ""
        try:
            p = json.loads(row["personality_json"] or "{}")
            if isinstance(p, dict):
                personality = str(p.get("personality") or "").strip()
                tv = p.get("topics")
                if isinstance(tv, list):
                    topics = ", ".join(str(x).strip() for x in tv if str(x).strip())
                secret = str(p.get("secret") or "").strip()
        except Exception:
            personality = ""
            topics = ""
            secret = ""

        line = (
            f'- {row["label"]} ({row["npc_type"]})'
            f' [key={row["key"]}]'
        )
        if row["description"]:
            line += f": {row['description']}"
        if personality:
            line += f" | personality: {personality}"
        if topics:
            line += f" | topics: {topics}"
        if secret:
            line += f" | secret: {secret}"
        lines.append(line)
    return "\n".join(lines)


def _inject_npc_llm_context(
    conn: sqlite3.Connection, campaign_id: int, messages: list[dict]
) -> None:
    """9A-3: inject dynamic [NPC CONTEXT] as a system message."""
    if not messages:
        return
    try:
        npc_block = build_npc_context_block(conn, campaign_id)
        if not npc_block:
            logger.info("npc_context_skipped", campaign_id=campaign_id, reason="no_npcs")
            return
        insert_at = 2 if len(messages) > 1 and messages[1].get("role") == "system" else 1
        messages.insert(insert_at, {"role": "system", "content": npc_block})
        visible_count = sum(1 for ln in npc_block.splitlines() if ln.startswith("- "))
        logger.info("npc_context_injected", campaign_id=campaign_id, npc_count=visible_count)
    except sqlite3.OperationalError as exc:
        # 9A-3 should fail-open before 9A-1 migrations are applied.
        logger.info("npc_context_skipped", campaign_id=campaign_id, reason="schema_missing", error=str(exc))
    except Exception as exc:
        logger.warning("npc_context_injection_failed", campaign_id=campaign_id, error=str(exc))


def _inject_campaign_s11_context(
    conn: sqlite3.Connection,
    campaign: sqlite3.Row,
    messages: list[dict],
    *,
    current_user_text: str | None = None,
) -> None:
    """
    Append MG plan + latest AI summary to system prompt so LLM keeps arc beyond last N turns.
    """
    if not messages:
        return
    first = messages[0]
    if not isinstance(first, dict) or first.get("role") != "system":
        return

    cid = int(campaign["id"])
    keys = campaign.keys()
    raw_plan = campaign["gm_plan_json"] if "gm_plan_json" in keys else None

    block_parts: list[str] = []
    formatted = format_gm_plan_block(raw_plan)
    if formatted:
        block_parts.append(formatted)

    try:
        from app.services.history_summary_service import fetch_latest_saved_summary_for_narrative

        saved = fetch_latest_saved_summary_for_narrative(conn, cid)
    except sqlite3.OperationalError:
        saved = None

    if saved and (saved.get("summary_text") or "").strip():
        st = str(saved["summary_text"]).strip()
        tc = saved.get("included_turn_count")
        block_parts.append(
            f"## Dotychczasowa fabuła (skrót archiwalny, ~{tc} tur narracyjnych)\n{st}"
        )

    try:
        from app.services.gm_plan_divergence import (
            divergence_prompt_block,
            evaluate_campaign_plan_divergence,
        )

        divergence = evaluate_campaign_plan_divergence(
            conn,
            campaign_id=cid,
            raw_plan=raw_plan,
            current_user_text=current_user_text,
            limit=4,
        )
        divergence_block = divergence_prompt_block(divergence)
        if divergence_block:
            block_parts.append(divergence_block)
    except sqlite3.OperationalError:
        pass

    if not block_parts:
        return

    bundle = (
        "--- Kontekst kampanii (trzymaj spójność z planem i skrótem; improwizuj w ramach zasad silnika) ---\n\n"
        + "\n\n".join(block_parts)
    )
    first["content"] = f"{first.get('content', '').rstrip()}\n\n{bundle}"


def build_narrative_messages(
    conn: sqlite3.Connection | None,
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    user_text: str,
    roll_result_message: str | None = None,
    roll_result_data: dict | None = None,
) -> list[dict]:
    from app.services import combat_service as combat_svc

    has_db_conn = isinstance(conn, sqlite3.Connection)
    recent_turns = loadrecentturns(conn, campaign["id"], limit=8)
    final_user_text = roll_result_message if roll_result_message else user_text
    combat_block = combat_svc.get_combat_context_for_prompt(int(campaign["id"]))
    messages = buildmessages(
        campaign=campaign,
        character=character,
        recentturns=recent_turns,
        usertext=final_user_text,
        runtime_config_block=build_runtime_config_block(),
        combat_context_block=combat_block,
    )

    if has_db_conn:
        _inject_campaign_s11_context(conn, campaign, messages, current_user_text=user_text)
        _inject_location_llm_context(conn, int(campaign["id"]), messages)
        _inject_npc_llm_context(conn, int(campaign["id"]), messages)

    combat_log_block = combat_svc.get_combat_turns_context_for_prompt(int(campaign["id"]))
    if combat_log_block and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            first["content"] = f"{first.get('content', '').rstrip()}\n\n{combat_log_block}"

    death_append = _death_mechanica_system_append(character, roll_result_data)

    if (
        not combat_block
        and not roll_result_message
        and not death_append
        and messages
    ):
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            extra = _inactive_combat_tag_reminder(user_text)
            snap = combat_svc.load_combat_snapshot(int(campaign["id"]))
            if snap and str(snap.get("status") or "") == "ended":
                er = snap.get("ended_reason") or "ended"
                extra += (
                    "\n\n[STAN SILNIKA WALKI — POPRZEDNIA SESJA ZAKOŃCZONA]\n"
                    f"W bazie jest zapis zakończonej walki (powód: {er}). Gracz NIE ma teraz aktywnej walki "
                    "w mechanice — każda **nowa** potyczka wymaga na końcu Twojej odpowiedzi linii "
                    "[COMBAT_START:klucz_wroga] (wg słownika wrogów), chyba że gracz sam uruchomi walkę "
                    "komendą /atak w czacie (odczyt stanu walki).\n"
                    "Nie kontynuuj w myśleniu starej sesji (inicjatywa, HP z poprzedniej walki) — to osobna walka."
                )
            first["content"] = f"{first.get('content', '').rstrip()}\n\n{extra}"

    if has_db_conn and not combat_block and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            enemy_catalog = combat_svc.get_enemy_catalog_for_prompt(conn)
            if enemy_catalog:
                first["content"] = f"{first.get('content', '').rstrip()}\n\n{enemy_catalog}"

    # 8H-4: item catalog — także podczas aktywnej walki (Grant Item / nagrody z katalogu)
    if has_db_conn and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            item_catalog = combat_svc.get_item_catalog_for_prompt(conn)
            if item_catalog:
                first["content"] = f"{first.get('content', '').rstrip()}\n\n{item_catalog}"

    if death_append and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            first["content"] = f"{first.get('content', '').rstrip()}\n\n{death_append}"

    # Skill test tag instruction — injected when player text hints at skill use
    if not combat_block and not roll_result_message and has_db_conn and messages:
        _st_block = _skill_test_tag_instruction(conn, int(campaign["id"]), user_text)
        if _st_block:
            messages.append({"role": "system", "content": _st_block})

    if not roll_result_data or not messages:
        return messages

    _rt = roll_result_data.get("roll_type") or infer_roll_type(
        str(roll_result_data.get("test") or "")
    )
    _atk = _rt == "attack"
    if roll_result_data.get("is_nat20") and _atk:
        roll_context = (
            "ROLL RESULT: CRITICAL SUCCESS (Natural 20). "
            "Narrate a dramatic, exceptional success. "
            "If combat: double damage dice."
        )
    elif roll_result_data.get("is_nat1") and _atk:
        roll_context = (
            "ROLL RESULT: CRITICAL FAILURE (Natural 1). "
            "Narrate a failure with an unexpected complication or twist. "
            "Do not just say the player failed — add a narrative consequence."
        )
    else:
        weapon_bonus = int(roll_result_data.get("weapon_bonus") or 0)
        bonus_part = ""
        if weapon_bonus:
            bonus_part = f" + weapon: {weapon_bonus}"
        roll_context = (
            "ROLL RESULT: "
            f"{roll_result_data.get('test')} check — rolled {roll_result_data.get('total')} "
            f"(d20: {roll_result_data.get('raw')} + stat: {roll_result_data.get('stat_mod')} + "
            f"skill: {roll_result_data.get('skill_rank')} + proficiency: {roll_result_data.get('proficiency')}"
            f"{bonus_part})"
        )

    if roll_result_data.get("test") == "death_save":
        total_ds = int(roll_result_data.get("total") or 0)
        if total_ds >= 10 or roll_result_data.get("is_nat20"):
            roll_context += (
                "\n\n[USTABILIZOWANIE] Postać ustabilizowała się. Stan śmierci zakończony (mechanicznie: "
                "death_save_failures = 0). Zakończ ten stan w narracji; nie dodawaj na końcu linii "
                "\"Roll Death Save d20\"."
            )

    first = messages[0]
    if isinstance(first, dict) and first.get("role") == "system":
        first["content"] = f"{first.get('content', '').rstrip()}\n\n{roll_context}"
    return messages


def run_narrative_turn(
    conn: sqlite3.Connection,
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    user_text: str,
    model: str,
    ollama_base_url: str | None = None,
    llm_config: dict[str, str] | None = None,
    roll_result_message: str | None = None,
    roll_result_data: dict | None = None,
) -> dict:
    messages = build_narrative_messages(
        conn=conn,
        campaign=campaign,
        character=character,
        user_text=user_text,
        roll_result_message=roll_result_message,
        roll_result_data=roll_result_data,
    )
    reply = generate_chat(messages=messages, model=model, llm_config=llm_config)
    return {"message": reply}
