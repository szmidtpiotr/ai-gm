import json
import sqlite3
from datetime import datetime, UTC
from typing import Any

DB_PATH = "/data/ai_gm.db"
SUPPORTED_MAJOR = "1"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _audit(conn: sqlite3.Connection, operation: str, old_values: dict | None, new_values: dict | None) -> None:
    conn.execute(
        """
        INSERT INTO admin_audit_log (table_name, row_key, operation, old_values, new_values)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "config_transfer",
            "global",
            operation,
            json.dumps(old_values, ensure_ascii=False) if old_values is not None else None,
            json.dumps(new_values, ensure_ascii=False) if new_values is not None else None,
        ),
    )


def _get_config_version(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT value FROM game_config_meta WHERE key = 'config_version' LIMIT 1"
    ).fetchone()
    return str(row["value"]) if row and row["value"] else "1.0.0"


def _set_config_version(conn: sqlite3.Connection, version: str) -> None:
    conn.execute(
        """
        INSERT INTO game_config_meta (key, value)
        VALUES ('config_version', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (version,),
    )


def _read_table(conn: sqlite3.Connection, table_name: str, order_by: str) -> list[dict[str, Any]]:
    rows = conn.execute(f"SELECT * FROM {table_name} ORDER BY {order_by}").fetchall()
    return [dict(r) for r in rows]


def export_config(exported_by: str = "dev-local") -> dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        payload = {
            "config_version": _get_config_version(conn),
            "exported_at": _now_iso(),
            "exported_by": exported_by,
            "tables": {
                "game_config_stats": _read_table(conn, "game_config_stats", "sort_order ASC, key ASC"),
                "game_config_skills": _read_table(conn, "game_config_skills", "sort_order ASC, key ASC"),
                "game_config_dc": _read_table(conn, "game_config_dc", "sort_order ASC, key ASC"),
            },
            "excluded": ["admin_tokens", "admin_audit_log", "user_accounts"],
        }
        _audit(conn, "EXPORT", None, {"config_version": payload["config_version"]})
        conn.commit()
        return payload
    finally:
        conn.close()


def _version_major(version: str) -> str:
    return (version or "1.0.0").split(".", 1)[0]


def _validate_import_payload(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return False, ["Payload must be an object"]
    if "config_version" not in payload:
        errors.append("Missing config_version")
    if "tables" not in payload or not isinstance(payload["tables"], dict):
        errors.append("Missing or invalid tables")
        return False, errors
    required_tables = ("game_config_stats", "game_config_skills", "game_config_dc")
    for table in required_tables:
        if table not in payload["tables"] or not isinstance(payload["tables"][table], list):
            errors.append(f"Missing or invalid table: {table}")
    return len(errors) == 0, errors


def import_config(payload: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    ok, errors = _validate_import_payload(payload)
    if not ok:
        return {"ok": False, "dry_run": dry_run, "errors": errors}

    incoming_version = str(payload.get("config_version") or "0.0.0")
    if _version_major(incoming_version) != SUPPORTED_MAJOR:
        return {
            "ok": False,
            "dry_run": dry_run,
            "errors": [f"Unsupported major config version: {incoming_version}"],
        }

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current_version = _get_config_version(conn)
        before_snapshot = export_config(exported_by="pre-import-snapshot")
        changes = {
            "stats": len(payload["tables"]["game_config_stats"]),
            "skills": len(payload["tables"]["game_config_skills"]),
            "dc": len(payload["tables"]["game_config_dc"]),
        }
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "warnings": [],
                "changes": changes,
                "target_version": incoming_version,
            }

        # Replace config tables atomically.
        conn.execute("DELETE FROM game_config_stats")
        conn.execute("DELETE FROM game_config_skills")
        conn.execute("DELETE FROM game_config_dc")

        for row in payload["tables"]["game_config_stats"]:
            conn.execute(
                """
                INSERT INTO game_config_stats (key, label, description, sort_order, locked_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row.get("key"),
                    row.get("label"),
                    row.get("description"),
                    int(row.get("sort_order", 0)),
                    row.get("locked_at"),
                ),
            )

        for row in payload["tables"]["game_config_skills"]:
            conn.execute(
                """
                INSERT INTO game_config_skills (key, label, linked_stat, rank_ceiling, sort_order, locked_at, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("key"),
                    row.get("label"),
                    row.get("linked_stat"),
                    int(row.get("rank_ceiling", 5)),
                    int(row.get("sort_order", 0)),
                    row.get("locked_at"),
                    row.get("description", "") or "",
                ),
            )

        for row in payload["tables"]["game_config_dc"]:
            conn.execute(
                """
                INSERT INTO game_config_dc (key, label, value, sort_order, locked_at, description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("key"),
                    row.get("label"),
                    int(row.get("value", 0)),
                    int(row.get("sort_order", 0)),
                    row.get("locked_at"),
                    row.get("description", "") or "",
                ),
            )

        _set_config_version(conn, incoming_version)
        _audit(
            conn,
            "IMPORT",
            {"pre_import": before_snapshot, "from_version": current_version},
            {"to_version": incoming_version, "changes": changes},
        )
        conn.commit()
        return {"ok": True, "dry_run": False, "changes": changes, "target_version": incoming_version}
    finally:
        conn.close()
