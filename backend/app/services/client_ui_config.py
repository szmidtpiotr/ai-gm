"""Editable client-facing UI strings stored in game_config_meta (e.g. chat slash-command descriptions)."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

DB_PATH = "/data/ai_gm.db"

META_KEY_SLASH_COMMANDS = "slash_commands_ui"

DEFAULT_SLASH_COMMANDS: list[dict[str, str]] = [
    {"command": "/help", "description": "Show available commands list"},
    {"command": "/helpme", "description": "Ask GM for out-of-character advice (OOC mode)"},
    {"command": "/sheet", "description": "Display your current character sheet"},
    {"command": "/mem", "description": "Show campaign memory — location, NPCs, active quests"},
]

ALLOWED_SLASH_COMMANDS = frozenset(x["command"] for x in DEFAULT_SLASH_COMMANDS)

_CMD_RE = re.compile(r"^/[a-z0-9_-]{1,40}$")

_MAX_DESC = 4000


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM game_config_meta WHERE key = ? LIMIT 1", (key,)).fetchone()
    if not row or row["value"] is None:
        return None
    return str(row["value"])


def get_merged_slash_commands() -> list[dict[str, str]]:
    """Defaults plus optional overrides from SQLite."""
    out = [dict(x) for x in DEFAULT_SLASH_COMMANDS]
    with _conn() as conn:
        raw = _get_meta(conn, META_KEY_SLASH_COMMANDS)
    if not raw:
        return out
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return out
    if not isinstance(data, list):
        return out
    by_cmd: dict[str, str] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        cmd = str(item.get("command", "")).strip()
        if cmd not in ALLOWED_SLASH_COMMANDS:
            continue
        desc = str(item.get("description", "")).strip()
        if desc:
            by_cmd[cmd] = desc[:_MAX_DESC]
    for row in out:
        if row["command"] in by_cmd:
            row["description"] = by_cmd[row["command"]]
    return out


def set_slash_commands_ui(commands: list[dict[str, Any]]) -> list[dict[str, str]]:
    """
    Persist descriptions for all known slash commands.
    Each item must include command + non-empty description.
    """
    if not isinstance(commands, list):
        raise ValueError("Request body must include a commands array.")

    seen: set[str] = set()
    payload: list[dict[str, str]] = []

    for item in commands:
        if not isinstance(item, dict):
            raise ValueError("Each command entry must be an object with command and description.")
        cmd = str(item.get("command", "")).strip()
        desc = str(item.get("description", "")).strip()
        if cmd not in ALLOWED_SLASH_COMMANDS:
            raise ValueError("Each command must be one of /help, /helpme, /sheet, /mem.")
        if cmd in seen:
            raise ValueError("Duplicate command in request.")
        seen.add(cmd)
        if not _CMD_RE.match(cmd):
            raise ValueError("Invalid command format.")
        if not desc:
            raise ValueError("Description cannot be empty.")
        payload.append({"command": cmd, "description": desc[:_MAX_DESC]})

    if seen != ALLOWED_SLASH_COMMANDS:
        raise ValueError("Send all four slash commands with descriptions.")

    raw = json.dumps(payload, ensure_ascii=False)
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO game_config_meta (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (META_KEY_SLASH_COMMANDS, raw),
        )
        conn.commit()

    return get_merged_slash_commands()
