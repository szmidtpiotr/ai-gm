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


def _read_world_bible_file() -> str:
    """
    Lore layer (issue #940) — SEPARATE from the locked mechanics contract.

    Static global world seed loaded ALONGSIDE system_prompt.txt, never woven into it.
    Source of truth is docs/world/LORE_v1_KANON.md; this file is derived from it.
    Optional: a missing/empty file is not an error — lore is additive, mechanics still work.

    Override path: env WORLD_BIBLE_PATH (absolute path to a .txt file).
    """
    path_str = (os.environ.get("WORLD_BIBLE_PATH") or "").strip()
    if path_str:
        path = Path(path_str).expanduser().resolve()
    else:
        path = _backend_root() / "prompts" / "world_bible.txt"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        logger.info("World bible file not present at %s — narration runs without lore layer.", path)
        return ""
    return text


# Loaded once at import. Empty string when the file is absent (lore is optional).
WORLD_BIBLE_TEXT: str = _read_world_bible_file()


def load_system_prompt_text() -> str:
    """Return the unified system prompt (identical for all fantasy GM call sites)."""
    return SYSTEM_PROMPT_TEXT


def load_world_bible_text() -> str:
    """Return the world lore seed (issue #940), or '' when no world_bible file exists."""
    return WORLD_BIBLE_TEXT


def compose_narrator_system_prompt(base: str | None = None) -> str:
    """
    Mechanics contract (system_prompt) + lore layer (world_bible) as ONE system message.

    The two stay separate files; this only concatenates them at the call site so the
    locked contract is never edited. Lore appended AFTER the contract. When no world
    bible exists, returns the base prompt unchanged.
    """
    base_text = (base if base is not None else SYSTEM_PROMPT_TEXT).rstrip()
    if not WORLD_BIBLE_TEXT:
        return base_text + "\n"
    return f"{base_text}\n\n{WORLD_BIBLE_TEXT}\n"
