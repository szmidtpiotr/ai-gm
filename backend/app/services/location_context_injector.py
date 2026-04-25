import json
import sqlite3

DB_PATH = "/data/ai_gm.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, uri=DB_PATH.startswith("file:"))
    conn.row_factory = sqlite3.Row
    return conn


def build_location_context(campaign_id: int) -> str:
    try:
        with _conn() as conn:
            row = conn.execute(
                """
                SELECT
                    c.current_location_id,
                    gl.label,
                    gl.location_type,
                    gl.description,
                    gl.rules,
                    gl.parent_id,
                    parent.label AS parent_label
                FROM campaigns c
                LEFT JOIN game_locations gl ON gl.id = c.current_location_id
                LEFT JOIN game_locations parent ON parent.id = gl.parent_id
                WHERE c.id = ?
                LIMIT 1
                """,
                (campaign_id,),
            ).fetchone()
            if not row or row["current_location_id"] is None:
                return ""

            adjacent_rows = conn.execute(
                """
                SELECT label
                FROM game_locations
                WHERE is_active = 1
                  AND (
                      id = ?
                      OR parent_id = ?
                      OR id = ?
                  )
                ORDER BY id ASC
                """,
                (row["parent_id"] if row["parent_id"] is not None else row["current_location_id"],
                 row["parent_id"] if row["parent_id"] is not None else row["current_location_id"],
                 row["parent_id"] if row["parent_id"] is not None else row["current_location_id"]),
            ).fetchall()
    except sqlite3.Error:
        # Optional block: context injector must not break narrative flow or tests without DB.
        return ""

    if not row or row["current_location_id"] is None:
        return ""
    if row["label"] is None:
        return ""

    parent_label = row["parent_label"] if row["parent_label"] else "brak"
    rules_raw = row["rules"]
    if rules_raw:
        try:
            rules = json.loads(str(rules_raw))
            rules_txt = json.dumps(rules, ensure_ascii=False)
        except json.JSONDecodeError:
            rules_txt = str(rules_raw)
    else:
        rules_txt = "{}"

    adjacent = ", ".join([str(r["label"]) for r in adjacent_rows if r["label"]]) or "brak"
    return (
        "[KONTEKST LOKALIZACJI — nie zmieniaj bez uzasadnienia]\n"
        f"Aktualna lokalizacja: {row['label']} ({row['location_type']}, rodzic: {parent_label})\n"
        f"Opis: {row['description'] or ''}\n"
        f"Zasady specjalne: {rules_txt}\n"
        f"Możliwe sąsiednie lokalizacje: {adjacent}\n"
        "Jeśli gracz próbuje przenieść się do odległej lokalizacji bez logicznej drogi:\n"
        "opisz podróż lub powiedz że jest niemożliwa."
    )
