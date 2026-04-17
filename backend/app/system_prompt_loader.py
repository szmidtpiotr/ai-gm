"""
Unified fantasy GM system prompt — single file on disk.

Edit: backend/prompts/system_prompt.txt (restart backend to apply).

Override path: env SYSTEM_PROMPT_PATH (absolute path to a .txt file).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _backend_root() -> Path:
    # app/system_prompt_loader.py -> parent.parent = backend/
    return Path(__file__).resolve().parent.parent


def _read_system_prompt_file() -> str:
    path_str = (os.environ.get("SYSTEM_PROMPT_PATH") or "").strip()
    if path_str:
        path = Path(path_str).expanduser().resolve()
    else:
        path = _backend_root() / "prompts" / "system_prompt.txt"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as e:
        logger.error(
            "Cannot read system prompt from %s (%s). Restore backend/prompts/system_prompt.txt or set SYSTEM_PROMPT_PATH.",
            path,
            e,
        )
        raise RuntimeError(f"System prompt file missing or unreadable: {path}") from e
    if not text:
        raise RuntimeError(f"System prompt file is empty: {path}")
    return text if text.endswith("\n") else text + "\n"


# Loaded once at import — same string for turn_engine, opening scene, and /api/gm/chat fantasy.
SYSTEM_PROMPT_TEXT: str = _read_system_prompt_file()


def load_system_prompt_text() -> str:
    """Return the unified system prompt (identical for all fantasy GM call sites)."""
    return SYSTEM_PROMPT_TEXT
