import sqlite3

from app.services.llm_service import generate_chat
from app.system_prompt_loader import SYSTEM_PROMPT_TEXT

# Narrative turns use the unified prompt from backend/prompts/system_prompt.txt (see system_prompt_loader).
SYSTEMPROMPT = SYSTEM_PROMPT_TEXT


def loadrecentturns(conn: sqlite3.Connection, campaignid: int, limit: int = 8) -> list[sqlite3.Row]:
    # Tylko narracja — trasy `memory`, `helpme`, `command` itd. nie trafiają do kontekstu GM.
    rows = conn.execute(
        """
        SELECT user_text, assistant_text, route
        FROM campaign_turns
        WHERE campaign_id = ? AND route = 'narrative'
        ORDER BY id DESC
        LIMIT ?
        """,
        (campaignid, limit),
    ).fetchall()
    rows = list(rows)
    rows.reverse()
    return rows


def buildmessages(
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    recentturns: list[sqlite3.Row],
    usertext: str,
    runtime_config_block: str | None = None,
) -> list[dict]:
    systemid = campaign["system_id"] if campaign and campaign["system_id"] else "fantasy"
    language = campaign["language"] if campaign and campaign["language"] else "pl"
    charactername = character["name"] if character and character["name"] else "Bohater"

    system_content = (
        f"{SYSTEMPROMPT}\n"
        f"System gry: {systemid}\n"
        f"Język: {language}\n"
        f"Postać gracza: {charactername}"
    )
    if runtime_config_block:
        system_content = f"{system_content}\n\n{runtime_config_block}"

    messages = [
        {
            "role": "system",
            "content": system_content,
        }
    ]

    for turn in recentturns:
        if turn["route"] != "narrative":
            continue
        if turn["user_text"]:
            messages.append({"role": "user", "content": turn["user_text"]})
        if turn["assistant_text"]:
            messages.append({"role": "assistant", "content": turn["assistant_text"]})

    messages.append({"role": "user", "content": usertext})
    return messages


def runnarrativeturn(
    conn: sqlite3.Connection,
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    usertext: str,
    model: str,
) -> dict:
    recentturns = loadrecentturns(conn, campaign["id"], limit=8)
    messages = buildmessages(
        campaign=campaign,
        character=character,
        recentturns=recentturns,
        usertext=usertext,
    )
    reply = generate_chat(messages=messages, model=model)
    return {"message": reply}
