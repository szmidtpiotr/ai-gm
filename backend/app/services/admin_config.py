import json
import sqlite3


DB_PATH = "/data/ai_gm.db"


def _fetch_all(query: str) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _fetch_one(conn: sqlite3.Connection, query: str, params: tuple) -> dict | None:
    row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def _audit(
    conn: sqlite3.Connection,
    table_name: str,
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
            table_name,
            row_key,
            operation,
            json.dumps(old_values, ensure_ascii=False) if old_values is not None else None,
            json.dumps(new_values, ensure_ascii=False) if new_values is not None else None,
        ),
    )


def list_stats() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, description, sort_order, locked_at
        FROM game_config_stats
        ORDER BY sort_order ASC, key ASC
        """
    )


def list_skills() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at
        FROM game_config_skills
        ORDER BY sort_order ASC, key ASC
        """
    )


def list_dc() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, value, sort_order, locked_at
        FROM game_config_dc
        ORDER BY sort_order ASC, key ASC
        """
    )


def update_stat(
    key: str,
    *,
    label: str | None,
    description: str | None,
    sort_order: int | None,
    force: bool,
) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            "SELECT key, label, description, sort_order, locked_at FROM game_config_stats WHERE key = ?",
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        updates = {
            "label": label if label is not None else current["label"],
            "description": description if description is not None else current["description"],
            "sort_order": sort_order if sort_order is not None else current["sort_order"],
        }
        conn.execute(
            """
            UPDATE game_config_stats
            SET label = ?, description = ?, sort_order = ?
            WHERE key = ?
            """,
            (updates["label"], updates["description"], updates["sort_order"], key),
        )
        new_row = _fetch_one(
            conn,
            "SELECT key, label, description, sort_order, locked_at FROM game_config_stats WHERE key = ?",
            (key,),
        )
        _audit(conn, "game_config_stats", key, "UPDATE", current, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_skill(
    key: str,
    *,
    label: str | None,
    linked_stat: str | None,
    rank_ceiling: int | None,
    sort_order: int | None,
    force: bool,
) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at
            FROM game_config_skills WHERE key = ?
            """,
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        final_linked_stat = linked_stat if linked_stat is not None else current["linked_stat"]
        stat_exists = _fetch_one(conn, "SELECT key FROM game_config_stats WHERE key = ?", (final_linked_stat,))
        if not stat_exists:
            raise ValueError("invalid_linked_stat")

        final_rank = rank_ceiling if rank_ceiling is not None else current["rank_ceiling"]
        if final_rank < 1:
            raise ValueError("invalid_rank_ceiling")

        updates = {
            "label": label if label is not None else current["label"],
            "linked_stat": final_linked_stat,
            "rank_ceiling": final_rank,
            "sort_order": sort_order if sort_order is not None else current["sort_order"],
        }
        conn.execute(
            """
            UPDATE game_config_skills
            SET label = ?, linked_stat = ?, rank_ceiling = ?, sort_order = ?
            WHERE key = ?
            """,
            (
                updates["label"],
                updates["linked_stat"],
                updates["rank_ceiling"],
                updates["sort_order"],
                key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at
            FROM game_config_skills WHERE key = ?
            """,
            (key,),
        )
        _audit(conn, "game_config_skills", key, "UPDATE", current, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_dc(
    key: str,
    *,
    label: str | None,
    value: int | None,
    sort_order: int | None,
    force: bool,
) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            "SELECT key, label, value, sort_order, locked_at FROM game_config_dc WHERE key = ?",
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        updates = {
            "label": label if label is not None else current["label"],
            "value": value if value is not None else current["value"],
            "sort_order": sort_order if sort_order is not None else current["sort_order"],
        }
        if updates["value"] < 1:
            raise ValueError("invalid_dc_value")

        conn.execute(
            """
            UPDATE game_config_dc
            SET label = ?, value = ?, sort_order = ?
            WHERE key = ?
            """,
            (updates["label"], updates["value"], updates["sort_order"], key),
        )
        new_row = _fetch_one(
            conn,
            "SELECT key, label, value, sort_order, locked_at FROM game_config_dc WHERE key = ?",
            (key,),
        )
        _audit(conn, "game_config_dc", key, "UPDATE", current, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def create_skill(
    *,
    key: str,
    label: str,
    linked_stat: str,
    rank_ceiling: int = 5,
    sort_order: int = 0,
) -> dict:
    if rank_ceiling < 1:
        raise ValueError("invalid_rank_ceiling")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_skills WHERE key = ?", (key,))
        if existing:
            raise ValueError("skill_exists")

        stat_exists = _fetch_one(conn, "SELECT key FROM game_config_stats WHERE key = ?", (linked_stat,))
        if not stat_exists:
            raise ValueError("invalid_linked_stat")

        conn.execute(
            """
            INSERT INTO game_config_skills (key, label, linked_stat, rank_ceiling, sort_order, locked_at)
            VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (key, label, linked_stat, rank_ceiling, sort_order),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at
            FROM game_config_skills WHERE key = ?
            """,
            (key,),
        )
        _audit(conn, "game_config_skills", key, "INSERT", None, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def _character_uses_skill(conn: sqlite3.Connection, skill_key: str) -> tuple[int, int | None]:
    rows = conn.execute("SELECT id, sheet_json FROM characters").fetchall()
    for row in rows:
        sheet_raw = row["sheet_json"] or "{}"
        try:
            parsed = json.loads(sheet_raw)
        except Exception:
            parsed = {}
        skills = parsed.get("skills") if isinstance(parsed, dict) else None
        if isinstance(skills, dict) and skill_key in skills:
            return row["id"], int(skills.get(skill_key) or 0)
    return 0, None


def delete_skill(key: str, *, force: bool) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at
            FROM game_config_skills WHERE key = ?
            """,
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        character_id, rank = _character_uses_skill(conn, key)
        if character_id:
            raise LookupError(f"skill_in_use:{character_id}:{rank}")

        conn.execute("DELETE FROM game_config_skills WHERE key = ?", (key,))
        _audit(conn, "game_config_skills", key, "DELETE", current, None)
        conn.commit()
    finally:
        conn.close()
