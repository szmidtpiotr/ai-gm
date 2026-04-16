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


def list_stats() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, description, sort_order
        FROM game_config_stats
        ORDER BY sort_order ASC, key ASC
        """
    )


def list_skills() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, linked_stat, rank_ceiling, sort_order
        FROM game_config_skills
        ORDER BY sort_order ASC, key ASC
        """
    )


def list_dc() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, value, sort_order
        FROM game_config_dc
        ORDER BY sort_order ASC, key ASC
        """
    )
