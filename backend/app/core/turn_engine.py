import json
import sqlite3

from app.services.llm_service import generate_chat
from app.system_prompt_loader import compose_narrator_system_prompt

# Narrative turns use the unified prompt (backend/prompts/system_prompt.txt) plus the
# separate lore layer (world_bible.txt, issue #940) — see system_prompt_loader.
SYSTEMPROMPT = compose_narrator_system_prompt()

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
    # #650 (B6b): atak czarem — bez tego LLM widzi tylko surowy JSON trafienia + wyposażoną
    # broń (laska) w bloku ekwipunku i opisuje cios bronią zamiast zaklęcia. Daj mu jawną
    # instrukcję, że to MAGIA. Silnik liczy trafienie/obrażenia — tu tylko poprawiamy OPIS.
    if d.get("kind") == "player_attack" and str(d.get("attack_mode") or "").lower() == "spell":
        spell_label = (str(d.get("spell_label") or "").strip()) or "zaklęcie"
        target = (str(d.get("target_name") or "").strip()) or "wroga"
        if d.get("player_nat1"):
            outcome = "Zaklęcie wymyka się spod kontroli (krytyczna porażka)"
        elif d.get("hit"):
            dmg = d.get("damage") or 0
            outcome = f"Zaklęcie trafia ({dmg} obrażeń)" if dmg else "Zaklęcie trafia"
        else:
            outcome = "Zaklęcie chybia (cel uniknął)"
        return (
            f"Bohater rzuca zaklęcie „{spell_label}” na {target}. {outcome}. "
            "Opisz to jako akt MAGII (a NIE cios bronią fizyczną — bohater NIE atakuje "
            "laską ani mieczem) w MAKSYMALNIE 2-3 krótkich, dynamicznych zdaniach: "
            "sam splot zaklęcia i jego skutek, bez rozwlekłych opisów otoczenia i dygresji."
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
    characterrace = "human"
    if character:
        try:
            characterrace = str(character["race"] or "human").strip().lower()
        except (IndexError, KeyError, TypeError):
            characterrace = "human"
    system_content = (
        f"{system_content}"
        f"System gry: {systemid}\n"
        f"Język: {language}\n"
        f"Postać gracza: {charactername}\n"
        f"Rasa postaci: {characterrace}"
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
