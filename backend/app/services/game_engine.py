import random
import sqlite3

from app.core.turn_engine import buildmessages, loadrecentturns
from app.services.config_service import build_runtime_config_block
from app.services.dice import parse_character_sheet
from app.services.llm_service import generate_chat
from app.services.solo_death_service import DEATH_SAVE_FAILURE_THRESHOLD


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


def build_narrative_messages(
    conn: sqlite3.Connection,
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    user_text: str,
    roll_result_message: str | None = None,
    roll_result_data: dict | None = None,
) -> list[dict]:
    recent_turns = loadrecentturns(conn, campaign["id"], limit=8)
    final_user_text = roll_result_message if roll_result_message else user_text
    messages = buildmessages(
        campaign=campaign,
        character=character,
        recentturns=recent_turns,
        usertext=final_user_text,
        runtime_config_block=build_runtime_config_block(),
    )

    death_append = _death_mechanica_system_append(character, roll_result_data)
    if death_append and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            first["content"] = f"{first.get('content', '').rstrip()}\n\n{death_append}"

    if not roll_result_data or not messages:
        return messages

    if roll_result_data.get("is_nat20"):
        roll_context = (
            "ROLL RESULT: CRITICAL SUCCESS (Natural 20). "
            "Narrate a dramatic, exceptional success. "
            "If combat: double damage dice."
        )
    elif roll_result_data.get("is_nat1"):
        roll_context = (
            "ROLL RESULT: CRITICAL FAILURE (Natural 1). "
            "Narrate a failure with an unexpected complication or twist. "
            "Do not just say the player failed — add a narrative consequence."
        )
    else:
        roll_context = (
            "ROLL RESULT: "
            f"{roll_result_data.get('test')} check — rolled {roll_result_data.get('total')} "
            f"(d20: {roll_result_data.get('raw')} + stat: {roll_result_data.get('stat_mod')} + "
            f"skill: {roll_result_data.get('skill_rank')} + proficiency: {roll_result_data.get('proficiency')})"
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
