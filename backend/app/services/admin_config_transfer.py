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


def _allowed_classes_to_db(value: Any) -> str:
    """Normalize export/import shapes to JSON text for game_config_weapons.allowed_classes."""
    if value is None:
        return "[]"
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return "[]"
        try:
            json.loads(s)
            return s
        except json.JSONDecodeError:
            parts = [p.strip() for p in s.split(",") if p.strip()]
            return json.dumps(parts, ensure_ascii=False)
    return "[]"


# Read-only snapshot for tools (LLM context, design docs). Not used by import_config.
_CATALOG_SNAPSHOT_SPECS: tuple[tuple[str, str], ...] = (
    ("game_config_meta", "key ASC"),
    ("game_config_stats", "sort_order ASC, key ASC"),
    ("game_config_skills", "sort_order ASC, key ASC"),
    ("game_config_dc", "sort_order ASC, key ASC"),
    ("game_config_weapons", "key ASC"),
    ("game_config_enemies", "key ASC"),
    ("game_config_conditions", "key ASC"),
    ("game_config_items", "key ASC"),
    ("game_config_consumables", "key ASC"),
    ("game_config_loot_tables", "key ASC"),
    ("game_config_loot_entries", "loot_table_key ASC, id ASC"),
)


def export_catalog_snapshot(exported_by: str = "dev-local") -> dict[str, Any]:
    """
    Full JSON snapshot of all game catalogue / mechanics tables (items, weapons, consumables,
    enemies, loot, …). Intended for read-only context (e.g. attach to an LLM prompt) — not
    the same shape as ``export_config`` used for atomic config import.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        tables: dict[str, list[dict[str, Any]]] = {}
        for table_name, order_by in _CATALOG_SNAPSHOT_SPECS:
            tables[table_name] = _read_table(conn, table_name, order_by)
        payload = {
            "export_kind": "catalog_snapshot",
            "config_version": _get_config_version(conn),
            "exported_at": _now_iso(),
            "exported_by": exported_by,
            "tables": tables,
            "notes": (
                "Read-only catalogue dump for design / LLM context. "
                "Do not use as input to POST /admin/config/import (different subset and semantics)."
            ),
        }
        _audit(conn, "EXPORT_CATALOG_SNAPSHOT", None, {"config_version": payload["config_version"]})
        conn.commit()
        return payload
    finally:
        conn.close()


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
                "game_config_weapons": _read_table(conn, "game_config_weapons", "key ASC"),
                "game_config_enemies": _read_table(conn, "game_config_enemies", "key ASC"),
                "game_config_conditions": _read_table(conn, "game_config_conditions", "key ASC"),
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
    optional_tables = (
        "game_config_weapons",
        "game_config_enemies",
        "game_config_conditions",
    )
    for table in optional_tables:
        if table in payload["tables"] and not isinstance(payload["tables"][table], list):
            errors.append(f"Invalid table (must be array): {table}")
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
        tbl = payload["tables"]
        changes = {
            "stats": len(tbl["game_config_stats"]),
            "skills": len(tbl["game_config_skills"]),
            "dc": len(tbl["game_config_dc"]),
        }
        if "game_config_weapons" in tbl:
            changes["weapons"] = len(tbl["game_config_weapons"])
        if "game_config_enemies" in tbl:
            changes["enemies"] = len(tbl["game_config_enemies"])
        if "game_config_conditions" in tbl:
            changes["conditions"] = len(tbl["game_config_conditions"])
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

        if "game_config_weapons" in tbl:
            conn.execute("DELETE FROM game_config_weapons")
            for row in tbl["game_config_weapons"]:
                conn.execute(
                    """
                    INSERT INTO game_config_weapons (
                        key, label, damage_die, linked_stat, allowed_classes,
                        is_active, locked_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("key"),
                        row.get("label"),
                        row.get("damage_die"),
                        row.get("linked_stat"),
                        _allowed_classes_to_db(row.get("allowed_classes")),
                        1 if int(row.get("is_active", 1)) else 0,
                        row.get("locked_at"),
                        row.get("created_at") or _now_iso(),
                        row.get("updated_at") or _now_iso(),
                    ),
                )

        if "game_config_enemies" in tbl:
            conn.execute("DELETE FROM game_config_enemies")
            for row in tbl["game_config_enemies"]:
                conn.execute(
                    """
                    INSERT INTO game_config_enemies (
                        key, label, hp_base, ac_base, attack_bonus, damage_die,
                        description, is_active, locked_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("key"),
                        row.get("label"),
                        int(row.get("hp_base", 0)),
                        int(row.get("ac_base", 0)),
                        int(row.get("attack_bonus", 0)),
                        row.get("damage_die"),
                        row.get("description"),
                        1 if int(row.get("is_active", 1)) else 0,
                        row.get("locked_at"),
                        row.get("created_at") or _now_iso(),
                        row.get("updated_at") or _now_iso(),
                    ),
                )

        if "game_config_conditions" in tbl:
            conn.execute("DELETE FROM game_config_conditions")
            for row in tbl["game_config_conditions"]:
                conn.execute(
                    """
                    INSERT INTO game_config_conditions (
                        key, label, effect_json, description, is_active,
                        locked_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("key"),
                        row.get("label"),
                        row.get("effect_json") or "{}",
                        row.get("description"),
                        1 if int(row.get("is_active", 1)) else 0,
                        row.get("locked_at"),
                        row.get("created_at") or _now_iso(),
                        row.get("updated_at") or _now_iso(),
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
