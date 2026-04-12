import sqlite3

from app.services.ollama_service import generatechat

SYSTEMPROMPT = (
    "Jesteś mistrzem gry RPG prowadzącym krótką, klimatyczną sesję solo po polsku. "
    "Prowadź narrację jasno i konkretnie. Uwzględniaj ostatni kontekst rozmowy. "
    "Nie powtarzaj dokładnie wypowiedzi gracza. "
    "Kończ odpowiedź naturalnym rozwinięciem sceny albo pytaniem 'Co robisz?', jeśli pasuje. "
    "Jeśli wejście gracza jest bardzo krótkie lub niejasne, poproś o doprecyzowanie w świecie gry."
)


def loadrecentturns(conn: sqlite3.Connection, campaignid: int, limit: int = 8) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT user_text, assistant_text, route
        FROM campaign_turns
        WHERE campaign_id = ?
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
) -> list[dict]:
    systemid = campaign["system_id"] if campaign and campaign["system_id"] else "fantasy"
    language = campaign["language"] if campaign and campaign["language"] else "pl"
    charactername = character["name"] if character and character["name"] else "Bohater"

    messages = [
        {
            "role": "system",
            "content": (
                f"{SYSTEMPROMPT}\n"
                f"System gry: {systemid}\n"
                f"Język: {language}\n"
                f"Postać gracza: {charactername}"
            ),
        }
    ]

    for turn in recentturns:
        if turn["user_text"]:
            messages.append({"role": "user", "content": turn["user_text"]})
        if turn["assistant_text"] and turn["route"] == "narrative":
            messages.append({"role": "assistant", "content": turn["assistant_text"]})

    messages.append({"role": "user", "content": usertext})
    return messages


def runnarrativeturn(
    conn: sqlite3.Connection,
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    usertext: str,
    model: str,
    ollamabaseurl: str | None = None,
) -> dict:
    recentturns = loadrecentturns(conn, campaign["id"], limit=8)
    messages = buildmessages(
        campaign=campaign,
        character=character,
        recentturns=recentturns,
        usertext=usertext,
    )
    reply = generatechat(model=model, messages=messages, base_url=ollamabaseurl)
    return {"message": reply}