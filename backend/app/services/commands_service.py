# backend/services/commands_service.py
from dataclasses import dataclass
from typing import Any
from sqlalchemy.orm import Session

from models.character import Character

@dataclass
class CommandResult:
    ok: bool
    route: str
    command: str
    data: dict[str, Any]
    error: str | None = None


def is_command(text: str) -> bool:
    return text.strip().startswith("/")


def run_command(db: Session, character_id: int, text: str) -> CommandResult:
    raw = text.strip()
    parts = raw.split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    dispatch = {
        "/help": _cmd_help,
        "/sheet": _cmd_sheet,
        "/name": _cmd_name,
    }

    handler = dispatch.get(command)
    if not handler:
        return CommandResult(
            ok=False,
            route="command",
            command=command,
            data={},
            error=f"Unknown command: {command}",
        )

    return handler(db=db, character_id=character_id, arg=arg)


def _get_character(db: Session, character_id: int) -> Character | None:
    return db.query(Character).filter(Character.id == character_id).first()


def _cmd_help(db: Session, character_id: int, arg: str) -> CommandResult:
    return CommandResult(
        ok=True,
        route="command",
        command="/help",
        data={
            "message": "Commands: /help, /name, /sheet, /inv, /roll, /say, /do, /ooc"
        },
    )


def _cmd_sheet(db: Session, character_id: int, arg: str) -> CommandResult:
    character = _get_character(db, character_id)
    if not character:
        return CommandResult(
            ok=False,
            route="command",
            command="/sheet",
            data={},
            error="Character not found",
        )

    return CommandResult(
        ok=True,
        route="command",
        command="/sheet",
        data={
            "character": {
                "id": character.id,
                "name": character.name,
                "attributes": character.attributes_json,
                "skills": character.skills_json,
                "resources": character.resources_json,
            }
        },
    )


def _cmd_name(db: Session, character_id: int, arg: str) -> CommandResult:
    if not arg:
        return CommandResult(
            ok=False,
            route="command",
            command="/name",
            data={},
            error="Usage: /name <new_name>",
        )

    character = _get_character(db, character_id)from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import Character


@dataclass
class CommandResult:
    ok: bool
    route: str
    command: str
    result: dict[str, Any]
    error: str | None = None


def is_command(text: str) -> bool:
    return text.strip().startswith("/")


def run_command(db: Session, character_id: int, text: str) -> CommandResult:
    raw = (text or "").strip()
    if not raw:
        return CommandResult(
            ok=False,
            route="command",
            command="",
            result={},
            error="Empty command",
        )

    parts = raw.split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    dispatch = {
        "/help": _cmd_help,
        "/sheet": _cmd_sheet,
        "/name": _cmd_name,
    }

    handler = dispatch.get(command)
    if not handler:
        return CommandResult(
            ok=False,
            route="command",
            command=command,
            result={},
            error=f"Unknown command: {command}",
        )

    return handler(db=db, character_id=character_id, arg=arg)


def _get_character(db: Session, character_id: int):
    return db.query(Character).filter(Character.id == character_id).first()


def _cmd_help(db: Session, character_id: int, arg: str) -> CommandResult:
    return CommandResult(
        ok=True,
        route="command",
        command="/help",
        result={
            "message": "Commands: /help, /name, /sheet, /inv, /roll, /say, /do, /ooc"
        },
    )


def _cmd_sheet(db: Session, character_id: int, arg: str) -> CommandResult:
    character = _get_character(db, character_id)
    if not character:
        return CommandResult(
            ok=False,
            route="command",
            command="/sheet",
            result={},
            error="Character not found",
        )

    return CommandResult(
        ok=True,
        route="command",
        command="/sheet",
        result={
            "character": {
                "id": getattr(character, "id", None),
                "name": getattr(character, "name", None),
                "attributes": getattr(character, "attributes_json", None),
                "skills": getattr(character, "skills_json", None),
                "resources": getattr(character, "resources_json", None),
            }
        },
    )


def _cmd_name(db: Session, character_id: int, arg: str) -> CommandResult:
    if not arg:
        return CommandResult(
            ok=False,
            route="command",
            command="/name",
            result={},
            error="Usage: /name <new_name>",
        )

    character = _get_character(db, character_id)
    if not character:
        return CommandResult(
            ok=False,
            route="command",
            command="/name",
            result={},
            error="Character not found",
        )

    character.name = arg
    db.add(character)
    db.commit()
    db.refresh(character)

    return CommandResult(
        ok=True,
        route="command",
        command="/name",
        result={"character_name": character.name},
    )
    if not character:
        return CommandResult(
            ok=False,
            route="command",
            command="/name",
            data={},
            error="Character not found",
        )

    character.name = arg
    db.add(character)
    db.commit()
    db.refresh(character)

    return CommandResult(
        ok=True,
        route="command",
        command="/name",
        data={"character_name": character.name},
    )