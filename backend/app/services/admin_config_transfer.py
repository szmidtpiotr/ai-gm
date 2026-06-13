import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime, UTC, timedelta
from typing import Any

from app.services.admin_config import normalize_effect_json_value

DB_PATH = "/data/ai_gm.db"
SUPPORTED_MAJOR = "1"
IMPORT_BACKUP_DIR = os.getenv("ADMIN_IMPORT_BACKUP_DIR", "/backups/imports")
IMPORT_BACKUP_KEEP_LAST = 10
IMPORT_BACKUP_MAX_AGE_DAYS = 30
IMPORT_BACKUP_MIN_KEEP = 3
_IMPORT_CONFIG_REQUIRED_TABLES = ("game_config_stats", "game_config_skills", "game_config_dc")
_IMPORT_CONFIG_OPTIONAL_TABLES = (
    "game_config_weapons",
    "game_config_enemies",
    "game_config_conditions",
)
_SNAPSHOT_ONLY_TABLES = (
    "game_config_xp_rewards",
    "game_config_items",
    "game_config_consumables",
    "game_config_loot_tables",
    "game_config_loot_entries",
)
_NARROW_WEAPON_IMPORT_COLUMNS = {
    "key",
    "label",
    "damage_die",
    "weapon_type",
    "linked_stat",
    "allowed_classes",
    "two_handed",
    "finesse",
    "range_m",
    "targeting",
    "aoe_radius_m",
    "magic_school",
    "weight_kg",
    "description",
    "note",
    "value_gp",
    "is_active",
    "locked_at",
    "created_at",
    "updated_at",
}


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


def _resolve_import_backup_dir() -> Path:
    preferred = Path(IMPORT_BACKUP_DIR)
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred
    except OSError:
        fallback = Path(DB_PATH).resolve().parent / "backups" / "imports"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _align_backup_path_owner(path: Path) -> None:
    try:
        st = Path(DB_PATH).stat()
        os.chown(path, st.st_uid, st.st_gid)
    except OSError:
        return


def _prune_import_backups(backup_dir: Path) -> list[str]:
    files = sorted(
        backup_dir.glob("ai_gm_pre_import_*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return []

    cutoff = datetime.now(UTC) - timedelta(days=IMPORT_BACKUP_MAX_AGE_DAYS)
    recent_files: list[Path] = []
    expired_files: list[Path] = []
    for path in files:
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        if modified_at >= cutoff:
            recent_files.append(path)
        else:
            expired_files.append(path)

    keep_candidates = recent_files + expired_files[:IMPORT_BACKUP_MIN_KEEP]
    keep_set = set(keep_candidates[:IMPORT_BACKUP_KEEP_LAST])
    pruned: list[str] = []
    for path in files:
        if path in keep_set:
            continue
        try:
            path.unlink()
            pruned.append(path.name)
        except OSError:
            continue
    return pruned


def _create_pre_import_backup(conn: sqlite3.Connection, import_kind: str) -> dict[str, Any]:
    backup_dir = _resolve_import_backup_dir()
    _align_backup_path_owner(backup_dir)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    safe_kind = "".join(ch if ch.isalnum() else "_" for ch in str(import_kind or "import").strip().lower()).strip("_")
    if not safe_kind:
        safe_kind = "import"
    backup_path = backup_dir / f"ai_gm_pre_import_{safe_kind}_{timestamp}.db"

    dest_conn = sqlite3.connect(str(backup_path))
    try:
        conn.backup(dest_conn)
    finally:
        dest_conn.close()
    _align_backup_path_owner(backup_path)

    pruned = _prune_import_backups(backup_dir)
    return {
        "path": str(backup_path),
        "filename": backup_path.name,
        "size_bytes": backup_path.stat().st_size if backup_path.exists() else 0,
        "retention": {
            "keep_last": IMPORT_BACKUP_KEEP_LAST,
            "max_age_days": IMPORT_BACKUP_MAX_AGE_DAYS,
            "min_keep": IMPORT_BACKUP_MIN_KEEP,
        },
        "pruned": pruned,
    }


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
    ("game_config_xp_rewards", "category ASC, sort_order ASC, key ASC"),
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
                "Canonical full-catalog dump for design / LLM context and cross-environment migration. "
                "To restore these tables in the admin Game Design section, use "
                "POST /api/admin/config/catalog-snapshot/import (not POST /admin/config/import)."
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
            "export_kind": "config_bundle",
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
            "notes": (
                "Narrow config bundle for stats / skills / DC and selected legacy tables. "
                "For full catalog migration (items, consumables, loot, xp rewards, full weapon schema) "
                "prefer GET/POST /api/admin/config/catalog-snapshot."
            ),
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
    for table in _IMPORT_CONFIG_REQUIRED_TABLES:
        if table not in payload["tables"] or not isinstance(payload["tables"][table], list):
            errors.append(f"Missing or invalid table: {table}")
    for table in _IMPORT_CONFIG_OPTIONAL_TABLES:
        if table in payload["tables"] and not isinstance(payload["tables"][table], list):
            errors.append(f"Invalid table (must be array): {table}")
    return len(errors) == 0, errors


def _import_config_warnings(payload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        return warnings

    export_kind = str(payload.get("export_kind") or "").strip().lower()
    if export_kind == "catalog_snapshot":
        warnings.append(
            "Ten plik wygląda na catalog_snapshot. Pełny katalog importuj przez /api/admin/config/catalog-snapshot/import, "
            "bo /api/admin/config/import obsługuje tylko wąski rdzeń configu."
        )

    present_snapshot_tables = [name for name in _SNAPSHOT_ONLY_TABLES if isinstance(tables.get(name), list)]
    if present_snapshot_tables:
        warnings.append(
            "import_config zignoruje tabele pełnego katalogu: "
            + ", ".join(present_snapshot_tables)
            + ". Dla items / loot / xp_rewards / consumables użyj catalog snapshot."
        )

    weapon_extra_cols: set[str] = set()
    for raw in tables.get("game_config_weapons") or []:
        if not isinstance(raw, dict):
            continue
        weapon_extra_cols.update(str(k) for k in raw.keys() if k not in _NARROW_WEAPON_IMPORT_COLUMNS)
    if weapon_extra_cols:
        warnings.append(
            "import_config zapisuje broń w węższym formacie i może uciąć kolumny: "
            + ", ".join(sorted(weapon_extra_cols))
            + ". Pełne rekordy broni importuj przez catalog snapshot."
        )

    return warnings


def _catalog_snapshot_warnings(payload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        return warnings
    if "game_config_meta" in tables:
        warnings.append(
            "game_config_meta z pliku zostanie zignorowane przy imporcie snapshotu "
            "(nie nadpisujemy slash commands / ustawień technicznych)."
        )
    return warnings


def _validate_effect_json_rows(
    rows: list[Any],
    *,
    table_name: str,
    effect_required: bool,
) -> list[str]:
    errors: list[str] = []
    for idx, raw in enumerate(rows):
        if not isinstance(raw, dict):
            continue
        effect_json = raw.get("effect_json")
        label = f"{table_name}[{idx}]"
        if effect_json is None or (isinstance(effect_json, str) and not effect_json.strip()):
            if effect_required:
                errors.append(f"{label}.effect_json is required")
            continue
        try:
            normalize_effect_json_value(effect_json)
        except ValueError as exc:
            code = str(exc)
            if code == "invalid_effect_json":
                errors.append(f"{label}.effect_json must be valid JSON")
            elif code == "invalid_effect_json_schema":
                errors.append(f"{label}.effect_json must follow effect_json schema v1")
            else:
                errors.append(f"{label}.effect_json is invalid")
    return errors


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

    tables = payload.get("tables") or {}
    warnings = _import_config_warnings(payload)
    errors.extend(
        _validate_effect_json_rows(
            tables.get("game_config_conditions") or [],
            table_name="game_config_conditions",
            effect_required=True,
        )
    )
    if errors:
        return {"ok": False, "dry_run": dry_run, "errors": errors}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current_version = _get_config_version(conn)
        before_snapshot = export_config(exported_by="pre-import-snapshot")
        backup_meta: dict[str, Any] | None = None
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
                "warnings": warnings,
                "changes": changes,
                "target_version": incoming_version,
            }

        backup_meta = _create_pre_import_backup(conn, "config")

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
                        key, label, damage_die, weapon_type, linked_stat, allowed_classes,
                        two_handed, finesse, range_m, targeting, aoe_radius_m, magic_school,
                        weight_kg, description, note, value_gp,
                        is_active, locked_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("key"),
                        row.get("label"),
                        row.get("damage_die"),
                        row.get("weapon_type") or "melee",
                        row.get("linked_stat"),
                        _allowed_classes_to_db(row.get("allowed_classes")),
                        1 if int(row.get("two_handed", 0) or 0) else 0,
                        1 if int(row.get("finesse", 0) or 0) else 0,
                        row.get("range_m"),
                        row.get("targeting") or "single",
                        row.get("aoe_radius_m"),
                        row.get("magic_school"),
                        float(row.get("weight_kg", 0.0) or 0.0),
                        row.get("description") or "",
                        row.get("note"),
                        int(row.get("value_gp", 0) or 0),
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
                        key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
                        description, is_active, locked_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("key"),
                        row.get("label"),
                        int(row.get("hp_base", 0)),
                        int(row.get("ac_base", 0)),
                        int(row.get("attack_bonus", 0)),
                        int(row.get("dex_modifier", 0) or 0),
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
        # U11c dual-write: rebuild game_items from the freshly imported legacy tables.
        try:
            from app.services.game_items_service import reconcile_all
            reconcile_all(conn)
        except Exception:
            pass
        _audit(
            conn,
            "IMPORT",
            {"pre_import": before_snapshot, "from_version": current_version},
            {"to_version": incoming_version, "changes": changes},
        )
        conn.commit()
        return {
            "ok": True,
            "dry_run": False,
            "warnings": warnings,
            "changes": changes,
            "target_version": incoming_version,
            "backup": backup_meta,
        }
    finally:
        conn.close()


# Game-design catalogue tables only (not game_config_meta — avoids wiping slash_commands_ui, loki_url, etc.).
# Order respects FK: loot_tables before enemies (loot_table_key); loot_entries last.
_CATALOG_IMPORT_TABLES: tuple[str, ...] = (
    "game_config_stats",
    "game_config_skills",
    "game_config_dc",
    "game_config_xp_rewards",
    "game_config_weapons",
    "game_config_conditions",
    "game_config_items",
    "game_config_consumables",
    "game_config_loot_tables",
    "game_config_enemies",
    "game_config_loot_entries",
)


def _validate_catalog_snapshot_import(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return False, ["Payload must be a JSON object"]
    kind = payload.get("export_kind")
    if kind is not None and kind != "catalog_snapshot":
        errors.append("export_kind must be 'catalog_snapshot' (or omit if the file is otherwise valid)")
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        errors.append("Missing or invalid 'tables' object")
        return False, errors
    stats = tables.get("game_config_stats")
    if not isinstance(stats, list) or len(stats) < 1:
        errors.append("tables.game_config_stats must be a non-empty array")
    for name in _CATALOG_IMPORT_TABLES:
        if name in tables and not isinstance(tables[name], list):
            errors.append(f"Table {name} must be an array when present")
    if isinstance(tables, dict):
        errors.extend(
            _validate_effect_json_rows(
                tables.get("game_config_conditions") or [],
                table_name="game_config_conditions",
                effect_required=True,
            )
        )
        errors.extend(
            _validate_effect_json_rows(
                tables.get("game_config_items") or [],
                table_name="game_config_items",
                effect_required=False,
            )
        )
    return len(errors) == 0, errors


def _default_for_missing_required(ctype: str | None) -> Any:
    c = (ctype or "").upper()
    if "INT" in c:
        return 0
    if "REAL" in c or "FLOA" in c or "DOUB" in c:
        return 0.0
    return ""


def _insert_catalog_row(conn: sqlite3.Connection, table: str, row: dict[str, Any]) -> None:
    cols_meta = conn.execute(f"PRAGMA table_info({table})").fetchall()
    names: list[str] = []
    vals: list[Any] = []
    for _cid, name, ctype, notnull, dflt_value, pk in cols_meta:
        if name in row:
            names.append(name)
            vals.append(row[name])
            continue
        if int(pk or 0) == 1 and int(notnull or 0) == 1:
            continue
        if int(notnull or 0) == 0:
            names.append(name)
            vals.append(None)
            continue
        if dflt_value is not None:
            continue
        names.append(name)
        vals.append(_default_for_missing_required(ctype))
    if not names:
        return
    placeholders = ",".join(["?"] * len(names))
    conn.execute(
        f"INSERT INTO {table} ({','.join(names)}) VALUES ({placeholders})",
        vals,
    )


def import_catalog_snapshot(payload: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    """
    Replace game-design catalogue tables from ``export_catalog_snapshot`` JSON.
    Does **not** import ``game_config_meta`` even if present in the file.
    """
    ok, errors = _validate_catalog_snapshot_import(payload)
    if not ok:
        return {"ok": False, "dry_run": dry_run, "errors": errors}

    tables_in = payload["tables"]
    if not isinstance(tables_in, dict):
        return {"ok": False, "dry_run": dry_run, "errors": ["Internal: tables is not a dict"]}
    warnings = _catalog_snapshot_warnings(payload)

    counts = {
        t: len([x for x in (tables_in.get(t) or []) if isinstance(x, dict)]) for t in _CATALOG_IMPORT_TABLES
    }
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "warnings": warnings,
            "would_import_rows": counts,
            "note": "game_config_meta in the file is ignored on import.",
        }

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        backup_meta = _create_pre_import_backup(conn, "catalog_snapshot")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("PRAGMA foreign_keys=OFF")
        for t in reversed(_CATALOG_IMPORT_TABLES):
            conn.execute(f"DELETE FROM {t}")
        for t in _CATALOG_IMPORT_TABLES:
            rows = tables_in.get(t) or []
            if not isinstance(rows, list):
                continue
            for raw in rows:
                if not isinstance(raw, dict):
                    continue
                row = dict(raw)
                if t == "game_config_conditions":
                    row["effect_json"] = normalize_effect_json_value(row.get("effect_json"))
                elif t == "game_config_items":
                    effect_json = row.get("effect_json")
                    if effect_json is not None and not (isinstance(effect_json, str) and not effect_json.strip()):
                        row["effect_json"] = normalize_effect_json_value(effect_json)
                _insert_catalog_row(conn, t, row)
        conn.execute("PRAGMA foreign_keys=ON")
        _audit(
            conn,
            "IMPORT_CATALOG_SNAPSHOT",
            None,
            {"tables": list(_CATALOG_IMPORT_TABLES), "counts": counts},
        )
        conn.commit()
        return {
            "ok": True,
            "dry_run": False,
            "warnings": warnings,
            "imported_rows": counts,
            "note": "game_config_meta was not applied.",
            "backup": backup_meta,
        }
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        return {"ok": False, "dry_run": False, "errors": [str(e)]}
    finally:
        conn.close()
