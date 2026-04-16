import json
import sqlite3

DB_PATH = "/data/ai_gm.db"


def _audit(
    conn: sqlite3.Connection,
    row_key: str,
    operation: str,
    old_values: dict | None,
    new_values: dict | None,
) -> None:
    conn.execute(
        """
        INSERT INTO admin_audit_log (table_name, row_key, operation, old_values, new_values)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "users",
            row_key,
            operation,
            json.dumps(old_values, ensure_ascii=False) if old_values is not None else None,
            json.dumps(new_values, ensure_ascii=False) if new_values is not None else None,
        ),
    )


def list_accounts() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                u.id,
                u.username,
                u.display_name,
                u.created_at,
                COALESCE(u.is_active, 1) AS is_active,
                COUNT(DISTINCT c.id) AS characters_count,
                COUNT(DISTINCT cp.id) AS campaigns_count
            FROM users u
            LEFT JOIN characters c ON c.user_id = u.id
            LEFT JOIN campaigns cp ON cp.owner_user_id = u.id
            GROUP BY u.id, u.username, u.display_name, u.created_at, u.is_active
            ORDER BY u.id ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _get_user(conn: sqlite3.Connection, account_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT id, username, display_name, created_at, COALESCE(is_active, 1) AS is_active
        FROM users
        WHERE id = ?
        """,
        (account_id,),
    ).fetchone()
    return dict(row) if row else None


def update_account(account_id: int, *, display_name: str | None, is_active: int | None) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _get_user(conn, account_id)
        if not current:
            raise KeyError("not_found")

        next_display_name = display_name if display_name is not None else current["display_name"]
        next_is_active = int(is_active) if is_active is not None else int(current["is_active"])
        if next_is_active not in (0, 1):
            raise ValueError("invalid_is_active")

        conn.execute(
            """
            UPDATE users
            SET display_name = ?, is_active = ?
            WHERE id = ?
            """,
            (next_display_name, next_is_active, account_id),
        )
        updated = _get_user(conn, account_id)
        _audit(conn, str(account_id), "UPDATE", current, updated)
        conn.commit()
        return updated or {}
    finally:
        conn.close()


def soft_delete_account(account_id: int) -> None:
    update_account(account_id, display_name=None, is_active=0)


def reset_account_sheet(account_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        exists = _get_user(conn, account_id)
        if not exists:
            raise KeyError("not_found")

        rows = conn.execute(
            "SELECT id, sheet_json FROM characters WHERE user_id = ?",
            (account_id,),
        ).fetchall()
        affected = 0
        for row in rows:
            old_sheet = row["sheet_json"] or "{}"
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                ("{}", row["id"]),
            )
            conn.execute(
                """
                INSERT INTO admin_audit_log (table_name, row_key, operation, old_values, new_values)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "characters",
                    str(row["id"]),
                    "RESET_SHEET",
                    old_sheet,
                    "{}",
                ),
            )
            affected += 1
        conn.commit()
        return {"ok": True, "characters_reset": affected}
    finally:
        conn.close()
