import json
import sqlite3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

DB_PATH = "/data/ai_gm.db"

class CommandRequest(BaseModel):
    character_id: int
    text: str

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.post("/commands/execute")
def execute_command(req: CommandRequest):
    text = req.text.strip()

    if not text.startswith("/"):
        raise HTTPException(status_code=400, detail="Not a command")

    parts = text.split(" ", 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM characters WHERE id = ?", (req.character_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Character not found")

    sheet = json.loads(row["sheet_json"])

    if cmd == "/help":
        conn.close()
        return {
            "ok": True,
            "type": "command",
            "command": "/help",
            "message": "Commands: /help, /name, /sheet, /inv, /roll, /say, /do, /ooc"
        }

    if cmd == "/name":
        if not arg:
            conn.close()
            raise HTTPException(status_code=400, detail="Usage: /name NEW_NAME")

        sheet["name"] = arg
        cur.execute(
            "UPDATE characters SET name = ?, sheet_json = ? WHERE id = ?",
            (arg, json.dumps(sheet), req.character_id)
        )
        conn.commit()
        conn.close()

        return {
            "ok": True,
            "type": "command",
            "command": "/name",
            "message": f"Name changed to: {arg}",
            "character_name": arg
        }

    if cmd == "/sheet":
        conn.close()
        return {
            "ok": True,
            "type": "command",
            "command": "/sheet",
            "sheet": sheet
        }

    conn.close()
    raise HTTPException(status_code=400, detail=f"Unknown command: {cmd}")
