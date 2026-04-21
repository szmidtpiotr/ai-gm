import json
import sqlite3

from app.services.llm_service import generate_chat
from app.system_prompt_loader import SYSTEM_PROMPT_TEXT

# Narrative turns use the unified prompt from backend/prompts/system_prompt.txt (see system_prompt_loader).
SYSTEMPROMPT = SYSTEM_PROMPT_TEXT

# Must match frontend `window.COMBAT_ROLL_PREFIX` — rich combat roll card in DB user_text.
COMBAT_ROLL_CTX_PREFIX = "__AI_GM_COMBAT_ROLL_V1__"


def _user_text_for_llm_context(raw: str | None) -> str:
    """Strip structured combat roll JSON from history so the LLM sees short prose only."""
    s = (raw or "").strip()
    if not s.startswith(COMBAT_ROLL_CTX_PREFIX):
        return s or ""
    tail = s[len(COMBAT_ROLL_CTX_PREFIX) :].lstrip("\r\n \t")
    try:
        d = json.loads(tail)
    except (json.JSONDecodeError, TypeError, ValueError):
        return s
    if not isinstance(d, dict):
        return s
    if d.get("kind") == "player_flee":
        summary = (d.get("summary_line") or "").strip()
        intent = (d.get("intent") or "").strip()
        if summary and intent:
            return f"{intent}\n\n{summary}"
        if summary:
            return summary
        return (
            "Gracz zakończył walkę w silniku przez ucieczkę. Opisz dynamicznie moment wycofania "
            "się z walki i natychmiastowe konsekwencje (2–4 zdania). Nie kończ pytaniem o następną akcję."
        )
    summary = (d.get("summary_line") or "").strip()
    intent = (d.get("intent") or "").strip()
    if summary and intent:
        return f"{intent}\n\n{summary}"
    return summary or s


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
    combat_context_block: str | None = None,
) -> list[dict]:
    systemid = campaign["system_id"] if campaign and campaign["system_id"] else "fantasy"
    language = campaign["language"] if campaign and campaign["language"] else "pl"
    charactername = character["name"] if character and character["name"] else "Bohater"

    system_content = f"{SYSTEMPROMPT}\n"
    if combat_context_block:
        system_content = f"{system_content.rstrip()}\n\n{combat_context_block.strip()}\n"
    system_content = (
        f"{system_content}"
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
            messages.append(
                {"role": "user", "content": _user_text_for_llm_context(turn["user_text"])}
            )
        if turn["assistant_text"]:
            messages.append({"role": "assistant", "content": turn["assistant_text"]})

    messages.append({"role": "user", "content": _user_text_for_llm_context(usertext)})
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
