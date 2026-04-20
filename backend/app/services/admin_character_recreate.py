"""
Admin: rebuild a character sheet in place (same characters.id).

Keeps campaign_turns and all FKs tied to this character_id intact.
"""

from __future__ import annotations

import json
import sqlite3

DB_PATH = "/data/ai_gm.db"


def list_characters_admin() -> list[dict]:
    """All characters with id, name, campaign and owner — for admin recreate UI."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.name,
                c.campaign_id,
                c.user_id,
                cp.title AS campaign_title
            FROM characters c
            JOIN campaigns cp ON cp.id = c.campaign_id
            ORDER BY c.id ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_characters_by_owner(user_id: int) -> list[dict]:
    """Characters for one user, including sheet_json for inline admin editor."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.name,
                c.campaign_id,
                c.user_id,
                cp.title AS campaign_title,
                c.sheet_json
            FROM characters c
            JOIN campaigns cp ON cp.id = c.campaign_id
            WHERE c.user_id = ?
            ORDER BY c.id ASC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _audit_character(conn: sqlite3.Connection, character_id: int, operation: str, old: str | None, new: str | None) -> None:
    try:
        conn.execute(
            """
            INSERT INTO admin_audit_log (table_name, row_key, operation, old_values, new_values)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("characters", str(character_id), operation, old, new),
        )
    except sqlite3.OperationalError:
        pass


def _clear_inventory_if_exists(conn: sqlite3.Connection, character_id: int) -> None:
    try:
        conn.execute("DELETE FROM inventory_items WHERE character_id = ?", (character_id,))
    except sqlite3.OperationalError:
        pass


def delete_character_admin(character_id: int) -> dict:
    """
    Remove a hero row and all dependent data for this character_id.
    Deletes campaign_turns and inventory_items for this character, then the characters row.
    Campaign and campaign_ai_summaries rows are left intact (campaign may become character-less).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT c.id, c.name, c.campaign_id, c.user_id
            FROM characters c
            WHERE c.id = ?
            """,
            (character_id,),
        ).fetchone()
        if not row:
            raise KeyError("character_not_found")

        audit_old = f"id={character_id},name={row['name']},campaign_id={row['campaign_id']},user_id={row['user_id']}"
        conn.execute("BEGIN")
        conn.execute("DELETE FROM campaign_turns WHERE character_id = ?", (character_id,))
        _clear_inventory_if_exists(conn, character_id)
        conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        _audit_character(conn, character_id, "DELETE_CHARACTER", audit_old, None)
        conn.commit()
        return {"ok": True, "deleted_id": character_id, "campaign_id": int(row["campaign_id"])}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def recreate_character_in_place(
    character_id: int,
    *,
    name: str | None,
    sheet_json: dict,
    clear_inventory: bool = True,
) -> dict:
    """
    Replace character name + sheet_json after _build_character_sheet (same as player create flow).
    Does not insert a new row — character_id is unchanged.
    """
    from app.api.characters import _build_character_sheet

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT c.id, c.name, c.sheet_json, c.system_id, cam.system_id AS campaign_system_id
            FROM characters c
            JOIN campaigns cam ON cam.id = c.campaign_id
            WHERE c.id = ?
            """,
            (character_id,),
        ).fetchone()
        if not row:
            raise KeyError("character_not_found")

        campaign_system = str(row["campaign_system_id"] or "").strip()

        old_sheet = row["sheet_json"] or "{}"
        new_name = (name.strip() if isinstance(name, str) and name.strip() else str(row["name"] or "").strip())
        if not new_name:
            raise ValueError("name_required")

        base = dict(sheet_json) if isinstance(sheet_json, dict) else {}
        built = _build_character_sheet(base, base.get("archetype"))

        if clear_inventory:
            _clear_inventory_if_exists(conn, character_id)

        new_sheet_str = json.dumps(built, ensure_ascii=False)
        conn.execute(
            """
            UPDATE characters
            SET name = ?, sheet_json = ?
            WHERE id = ?
            """,
            (new_name, new_sheet_str, character_id),
        )
        _audit_character(conn, character_id, "RECREATE_SHEET_IN_PLACE", old_sheet, new_sheet_str)
        conn.commit()
        return {
            "ok": True,
            "character_id": character_id,
            "name": new_name,
            "campaign_system_id": campaign_system or None,
        }
    finally:
        conn.close()
