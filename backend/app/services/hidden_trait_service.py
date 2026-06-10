"""F17 — Hidden Trait system.

Character passive traits from a predefined pool.
Each trait holds an F1-style effect_json and is assigned to sheet_json.hidden_trait.
LLM reveal tracked via sheet_json.hidden_trait_revealed.
"""
import json
from typing import Optional


def get_trait_pool(conn) -> list[dict]:
    """Return all active traits from game_config_hidden_traits."""
    rows = conn.execute(
        "SELECT key, label, description, trigger_keywords, effect_json "
        "FROM game_config_hidden_traits WHERE is_active = 1"
    ).fetchall()
    return [dict(r) for r in rows]


def assign_trait(conn, character_id: int, trait_key: str) -> None:
    """Assign a trait to a character (replaces any previous trait).

    Raises ValueError if trait_key not found or not active.
    """
    row = conn.execute(
        "SELECT key FROM game_config_hidden_traits WHERE key = ? AND is_active = 1",
        (trait_key,),
    ).fetchone()
    if not row:
        raise ValueError(f"Hidden trait '{trait_key}' not found or not active")

    sheet_row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (int(character_id),)
    ).fetchone()
    sheet = json.loads(sheet_row["sheet_json"] or "{}") if sheet_row else {}

    sheet["hidden_trait"] = trait_key
    # Reset reveal state when a new trait is assigned
    sheet.pop("hidden_trait_revealed", None)

    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet), int(character_id)),
    )
    conn.commit()


def get_character_trait(conn, character_id: int) -> Optional[str]:
    """Return the trait key assigned to the character, or None."""
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (int(character_id),)
    ).fetchone()
    if not row:
        return None
    sheet = json.loads(row["sheet_json"] or "{}")
    return sheet.get("hidden_trait")


def reveal_trait(conn, character_id: int) -> None:
    """Mark a character's hidden trait as revealed.

    No-op if character has no trait.
    """
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (int(character_id),)
    ).fetchone()
    if not row:
        return
    sheet = json.loads(row["sheet_json"] or "{}")
    if not sheet.get("hidden_trait"):
        return
    sheet["hidden_trait_revealed"] = True
    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet), int(character_id)),
    )
    conn.commit()


def is_trait_revealed(conn, character_id: int) -> bool:
    """Return True if the character's hidden trait has been revealed."""
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (int(character_id),)
    ).fetchone()
    if not row:
        return False
    sheet = json.loads(row["sheet_json"] or "{}")
    return bool(sheet.get("hidden_trait_revealed"))
