"""
Prompt rules for AI-generated campaign summaries (historia).

Edit: backend/prompts/history_summary_prompt.txt (restart backend to apply).

Override path: env HISTORY_SUMMARY_PROMPT_PATH (absolute path to a .txt file).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _backend_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_history_summary_prompt_file() -> str:
    path_str = (os.environ.get("HISTORY_SUMMARY_PROMPT_PATH") or "").strip()
    if path_str:
        path = Path(path_str).expanduser().resolve()
    else:
        path = _backend_root() / "prompts" / "history_summary_prompt.txt"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as e:
        logger.error(
            "Cannot read history summary prompt from %s (%s).",
            path,
            e,
        )
        raise RuntimeError(f"History summary prompt file missing or unreadable: {path}") from e
    if not text:
        raise RuntimeError(f"History summary prompt file is empty: {path}")
    return text if text.endswith("\n") else text + "\n"


HISTORY_SUMMARY_PROMPT_TEXT: str = _read_history_summary_prompt_file()


def load_history_summary_prompt_text() -> str:
    return HISTORY_SUMMARY_PROMPT_TEXT
