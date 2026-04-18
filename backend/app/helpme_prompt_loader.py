"""
OOC advisor prompt for /helpme.

Edit: backend/prompts/helpme-gm.txt (restart backend).
Override: env HELPME_GM_PROMPT_PATH
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _backend_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_file() -> str:
    path_str = (os.environ.get("HELPME_GM_PROMPT_PATH") or "").strip()
    if path_str:
        path = Path(path_str).expanduser().resolve()
    else:
        path = _backend_root() / "prompts" / "helpme-gm.txt"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as e:
        logger.error("Cannot read /helpme prompt from %s (%s).", path, e)
        raise RuntimeError(f"/helpme prompt file missing: {path}") from e
    if not text:
        raise RuntimeError(f"/helpme prompt file is empty: {path}")
    return text if text.endswith("\n") else text + "\n"


HELPME_GM_PROMPT_TEXT: str = _read_file()


def load_helpme_prompt_text() -> str:
    return HELPME_GM_PROMPT_TEXT
