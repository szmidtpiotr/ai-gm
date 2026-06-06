from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

_VERSION_FILE = Path(__file__).parent.parent.parent / "VERSION"


def _read_version() -> str:
    try:
        return _VERSION_FILE.read_text().strip()
    except Exception:
        return "unknown"


@router.get("/version")
async def get_version():
    return {"version": _read_version()}
