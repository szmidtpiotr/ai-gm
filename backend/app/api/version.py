from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()

_BASE = Path(__file__).parent.parent.parent
_VERSION_FILE = _BASE / "VERSION"
_CHANGELOG_FILE = _BASE / "CHANGELOG.md"


def _read_version() -> str:
    try:
        return _VERSION_FILE.read_text().strip()
    except Exception:
        return "unknown"


@router.get("/version")
async def get_version():
    return {"version": _read_version()}


@router.get("/changelog", response_class=PlainTextResponse)
async def get_changelog():
    try:
        return _CHANGELOG_FILE.read_text()
    except Exception:
        return "# Changelog\n\nNie znaleziono pliku CHANGELOG.md."
