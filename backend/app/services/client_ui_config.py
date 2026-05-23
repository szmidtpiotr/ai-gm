"""Editable client-facing UI: slash commands (opis + włącz/wyłącz per komenda) w game_config_meta."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.api.slash_command_registry import ADMIN_ONLY_COMMANDS, COMMAND_REGISTRY

DB_PATH = "/data/ai_gm.db"

META_KEY_SLASH_COMMANDS = "slash_commands_ui"

SEARCH_SLASH_COMMAND: dict[str, str] = {
    "command": "/search",
    "description": "Przeszukaj zabitą postać lub lokację",
}


def _default_admin_enabled(cmd: str) -> bool:
    """All commands available to admin by default."""
    return True


def _default_player_enabled(cmd: str) -> bool:
    """Admin-only commands hidden from players by default; everything else visible."""
    return cmd not in ADMIN_ONLY_COMMANDS


def _default_slash_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for k, v in COMMAND_REGISTRY.items():
        rows.append({
            "command": k,
            "description": str(v),
            "enabled": _default_player_enabled(k),
            "admin_enabled": _default_admin_enabled(k),
            "player_enabled": _default_player_enabled(k),
        })
    rows.append({
        "command": SEARCH_SLASH_COMMAND["command"],
        "description": SEARCH_SLASH_COMMAND["description"],
        "enabled": True,
        "admin_enabled": True,
        "player_enabled": True,
    })
    return rows


DEFAULT_SLASH_COMMANDS: list[dict[str, Any]] = _default_slash_rows()
ALLOWED_SLASH_COMMANDS = frozenset(x["command"] for x in DEFAULT_SLASH_COMMANDS)

_MAX_DESC = 4000
_MAX_CMD_LEN = 120


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM game_config_meta WHERE key = ? LIMIT 1", (key,)).fetchone()
    if not row or row["value"] is None:
        return None
    return str(row["value"])


def _coerce_enabled(v: Any, default: bool = True) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(int(v))
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return default


def get_merged_slash_commands() -> list[dict[str, Any]]:
    """Pełna lista (admin + logika serwera): command, description, admin_enabled, player_enabled, enabled (legacy = player_enabled)."""
    out: list[dict[str, Any]] = [dict(x) for x in DEFAULT_SLASH_COMMANDS]
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
    by_cmd: dict[str, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        cmd = str(item.get("command", "")).strip()
        if cmd not in ALLOWED_SLASH_COMMANDS:
            continue
        entry = by_cmd.setdefault(cmd, {})
        desc = str(item.get("description", "")).strip()
        if desc:
            entry["description"] = desc[:_MAX_DESC]
        # Legacy fallback: if only "enabled" stored, treat it as player_enabled
        if "admin_enabled" in item:
            entry["admin_enabled"] = _coerce_enabled(item.get("admin_enabled"), default=True)
        if "player_enabled" in item:
            entry["player_enabled"] = _coerce_enabled(item.get("player_enabled"), default=_default_player_enabled(cmd))
        elif "enabled" in item:
            entry["player_enabled"] = _coerce_enabled(item.get("enabled"), default=_default_player_enabled(cmd))
    for row in out:
        u = by_cmd.get(row["command"])
        if not u:
            continue
        if "description" in u:
            row["description"] = u["description"]
        if "admin_enabled" in u:
            row["admin_enabled"] = bool(u["admin_enabled"])
        if "player_enabled" in u:
            row["player_enabled"] = bool(u["player_enabled"])
            row["enabled"] = bool(u["player_enabled"])  # keep legacy in sync
    return out


def get_public_slash_commands() -> list[dict[str, str]]:
    """Tylko włączone dla gracza — dla autocomplete'a gracza, bez pól enabled/admin."""
    return [
        {"command": str(r["command"]), "description": str(r["description"])}
        for r in get_merged_slash_commands()
        if r.get("player_enabled", r.get("enabled", True)) is not False
    ]


def get_admin_slash_commands() -> list[dict[str, str]]:
    """Komendy widoczne dla admina (player_enabled OR admin_enabled)."""
    return [
        {"command": str(r["command"]), "description": str(r["description"])}
        for r in get_merged_slash_commands()
        if r.get("admin_enabled", True) is not False or r.get("player_enabled", True) is not False
    ]


def get_public_help_command_texts() -> dict[str, str]:
    """Skrócona mapa na /help — tylko włączone wpisy (+ /search jeśli włączony)."""
    out: dict[str, str] = {}
    for row in get_merged_slash_commands():
        if not row.get("enabled", True):
            continue
        k = str(row["command"])
        if k in COMMAND_REGISTRY:
            out[k] = str(row["description"])
        elif k == SEARCH_SLASH_COMMAND["command"]:
            out[k] = str(row["description"])
    return out


def is_slash_command_enabled(command_key: str) -> bool:
    for row in get_merged_slash_commands():
        if str(row.get("command")) == command_key:
            return bool(row.get("enabled", True))
    return True


def slash_registry_key_for_dispatch(text: str) -> str | None:
    """Klucz z listy admin (np. /mem [pytanie]) albo /search; alias /walka → /atak."""
    raw = (text or "").strip()
    if not raw.startswith("/"):
        return None
    first = raw.split(None, 1)[0].lower()
    if first == "/walka":
        return "/atak"
    if first == "/search":
        return "/search"
    for key in sorted(COMMAND_REGISTRY.keys(), key=lambda k: -len(str(k))):
        if str(key).split(None, 1)[0].lower() == first:
            return str(key)
    return None


def set_slash_commands_ui(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Zapis opisów i flag dla wszystkich znanych komend czatu.
    Każdy element: command, description, admin_enabled, player_enabled
    (legacy: 'enabled' jest akceptowane jako player_enabled).
    """
    if not isinstance(commands, list):
        raise ValueError("Request body must include a commands array.")

    seen: set[str] = set()
    payload: list[dict[str, Any]] = []

    for item in commands:
        if not isinstance(item, dict):
            raise ValueError("Each command entry must be an object with command, description, flags.")
        cmd = str(item.get("command", "")).strip()
        desc = str(item.get("description", "")).strip()
        if cmd not in ALLOWED_SLASH_COMMANDS:
            raise ValueError(f"Unknown or unsupported command: {cmd!r}.")
        if len(cmd) > _MAX_CMD_LEN:
            raise ValueError("Command string is too long.")
        if cmd in seen:
            raise ValueError("Duplicate command in request.")
        seen.add(cmd)
        if not desc:
            raise ValueError("Description cannot be empty.")
        admin_en = item.get("admin_enabled")
        player_en = item.get("player_enabled")
        if player_en is None and "enabled" in item:
            player_en = item.get("enabled")
        if admin_en is None:
            admin_en = _default_admin_enabled(cmd)
        if player_en is None:
            player_en = _default_player_enabled(cmd)
        if not isinstance(admin_en, bool) or not isinstance(player_en, bool):
            raise ValueError(f"admin_enabled/player_enabled for {cmd!r} must be booleans.")
        payload.append({
            "command": cmd,
            "description": desc[:_MAX_DESC],
            "admin_enabled": admin_en,
            "player_enabled": player_en,
            "enabled": player_en,  # legacy mirror
        })

    if seen != ALLOWED_SLASH_COMMANDS:
        n = len(ALLOWED_SLASH_COMMANDS)
        raise ValueError(f"Send all {n} slash commands with descriptions and flags.")

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
