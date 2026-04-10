import sqlite3
from app.services.ollama_service import generate_chat


SYSTEM_PROMPT = """Jesteś mistrzem gry RPG prowadzącym krótką, klimatyczną sesję solo po polsku.
Prowadź narrację jasno i konkretnie.
Uwzględniaj ostatni kontekst rozmowy.
Nie powtarzaj dokładnie wypowiedzi gracza.
Kończ odpowiedź naturalnym rozwinięciem sceny albo pytaniem "Co robisz?" jeśli pasuje.
Jeśli wejście gracza jest bardzo krótkie lub niejasne, poproś o doprecyzowanie w świecie gry.
"""


def load_recent_turns(conn: sqlite3.Connection, campaign_id: int, limit: int = 8) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT user_text, assistant_text, route
        FROM campaign_turns
        WHERE campaign_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (campaign_id, limit),
    ).fetchall()

    rows = list(rows)
    rows.reverse()
    return rows


def build_messages(
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    recent_turns: list[sqlite3.Row],
    user_text: str,
) -> list[dict]:
    system_id = campaign["system_id"] if campaign and campaign["system_id"] else "fantasy"
    language = campaign["language"] if campaign and campaign["language"] else "pl"
    character_name = character["name"] if character and character["name"] else "Bohater"

    messages = [
        {
            "role": "system",
            "content": (
                f"{SYSTEM_PROMPT}\n"
                f"System gry: {system_id}\n"
                f"Język: {language}\n"
                f"Postać gracza: {character_name}\n"
            ),
        }
    ]

    for turn in recent_turns:
        if turn["user_text"]:
            messages.append({
                "role": "user",
                "content": turn["user_text"],
            })

        if turn["assistant_text"] and turn["route"] == "narrative":
            messages.append({
                "role": "assistant",
                "content": turn["assistant_text"],
            })

    messages.append({
        "role": "user",
        "content": user_text,
    })

    return messages


def run_narrative_turn(
    conn: sqlite3.Connection,
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    user_text: str,
    model: str,
) -> dict:
    recent_turns = load_recent_turns(conn, campaign["id"], limit=8)
    messages = build_messages(
        campaign=campaign,
        character=character,
        recent_turns=recent_turns,
        user_text=user_text,
    )

    reply = generate_chat(model=model, messages=messages)

    return {
        "message": reply
    }