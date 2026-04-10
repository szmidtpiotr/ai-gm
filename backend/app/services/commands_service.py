import json
import sqlite3
from dataclasses import dataclass
from typing import Any

DB_PATH = "/data/ai_gm.db"


@dataclass
class CommandResult:
    ok: bool
    type: str
    command: str
    payload: dict[str, Any]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def is_command(text: str) -> bool:
    return (text or "").strip().startswith("/")


def execute_command_logic(character_id: int, text: str) -> CommandResult:
    text = (text or "").strip()

    if not text.startswith("/"):
        raise ValueError("Not a command")

    parts = text.split(" ", 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        row = cur.fetchone()

        if not row:
            raise LookupError("Character not found")

        sheet = json.loads(row["sheet_json"])

        if cmd == "/help":
            return CommandResult(
                ok=True,
                type="command",
                command="/help",
                payload={
                    "ok": True,
                    "type": "command",
                    "command": "/help",
                    "message": "Commands: /help, /name, /sheet, /inv, /roll, /say, /do, /ooc"
                },
            )

        if cmd == "/name":
            if not arg:
                raise ValueError("Usage: /name NEW_NAME")

            sheet["name"] = arg
            cur.execute(
                "UPDATE characters SET name = ?, sheet_json = ? WHERE id = ?",
                (arg, json.dumps(sheet), character_id)
            )
            conn.commit()

            return CommandResult(
                ok=True,
                type="command",
                command="/name",
                payload={
                    "result": {  # ← Wrap in "result"
                        "character_name": arg
                    }
                },
            )

        if cmd == "/sheet":
            return CommandResult(
                ok=True,
                type="command",
                command="/sheet",
                payload={
                    "result": {  # ← Wrap in "result" for frontend
                        "sheet": sheet
                    }
                },
            )

        raise ValueError(f"Unknown command: {cmd}")
    finally:
        conn.close()