import sqlite3

from app.core.turn_engine import buildmessages, loadrecentturns
from app.services.config_service import build_runtime_config_block
from app.services.llm_service import generate_chat


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
