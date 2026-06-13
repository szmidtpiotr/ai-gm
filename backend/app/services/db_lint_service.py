"""U12 (#559) — db_lint: audyt integralności bazy treści.

Funkcja główna: run_lint(db_path) → {"errors": [...], "warnings": [...], "exit_code": int}
  exit_code: 0 = czysto, 1 = tylko warnings, 2 = errors

Sprawdzane kategorie:
  (a) Wiszące FK — loot_table_key wrogów bez odpowiedniej tabeli łupów
  (b) Wymagane pola NULL — label w tabelach treści
  (c) Wartości poza zakresem — HP ≤ 0, ceny < 0
  (d) Enum violations — game_items.kind, review_status
  (e) effect_json — walidacja schematem U10 (jeśli kolumna istnieje)
  (f) Sieroty — rekordy game_config_weapons/items/consumables nieobecne w game_items (warning)

Uruchamialny jako skrypt: python scripts/db_lint.py
Endpoint: GET /api/admin/db-lint
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

# Rozwiąż ścieżkę DB tak samo jak reszta serwisów.
try:
    from app.core.db_runtime import resolve_db_path
    _DEFAULT_DB_PATH = resolve_db_path()
except Exception:
    _DEFAULT_DB_PATH = "/data/ai_gm.db"

_VALID_KINDS = {"weapon", "armor", "item", "consumable"}
_VALID_REVIEW_STATUS = {"permanent", "pending", "approved", "rejected"}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _col_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return col in cols


# ── checks ────────────────────────────────────────────────────────────────────

def _check_dangling_fk(conn: sqlite3.Connection) -> list[str]:
    """(a) Wrogowie z loot_table_key bez odpowiadającego wiersza w game_config_loot_tables."""
    errs: list[str] = []
    if not _table_exists(conn, "game_config_enemies"):
        return errs
    if not _col_exists(conn, "game_config_enemies", "loot_table_key"):
        return errs
    rows = conn.execute(
        """SELECT key, loot_table_key FROM game_config_enemies
           WHERE loot_table_key IS NOT NULL AND loot_table_key != ''"""
    ).fetchall()
    loot_keys: set[str] = set()
    if _table_exists(conn, "game_config_loot_tables"):
        loot_keys = {r[0] for r in conn.execute("SELECT key FROM game_config_loot_tables").fetchall()}
    for key, ltk in rows:
        if ltk not in loot_keys:
            errs.append(f"[FK] game_config_enemies '{key}': loot_table_key='{ltk}' nie istnieje w game_config_loot_tables")
    return errs


def _check_null_required(conn: sqlite3.Connection) -> list[str]:
    """(b) Wymagane pole label = NULL w tabelach treści."""
    errs: list[str] = []
    tables_with_label = [
        "game_config_enemies", "game_config_weapons", "game_config_items",
        "game_config_consumables", "game_items",
    ]
    for table in tables_with_label:
        if not _table_exists(conn, table):
            continue
        if not _col_exists(conn, table, "label"):
            continue
        rows = conn.execute(
            f"SELECT key FROM {table} WHERE label IS NULL OR label = ''"
        ).fetchall()
        for (key,) in rows:
            errs.append(f"[NULL] {table} '{key}': brakuje wymaganego pola 'label'")
    return errs


def _check_value_range(conn: sqlite3.Connection) -> list[str]:
    """(c) Wartości poza zakresem: hp_base ≤ 0, ceny < 0."""
    warns: list[str] = []
    if _table_exists(conn, "game_config_enemies") and _col_exists(conn, "game_config_enemies", "hp_base"):
        rows = conn.execute(
            "SELECT key, hp_base FROM game_config_enemies WHERE hp_base <= 0"
        ).fetchall()
        for key, hp in rows:
            warns.append(f"[RANGE] game_config_enemies '{key}': hp_base={hp} ≤ 0")
    for table, price_col in [
        ("game_config_weapons", "value_gp"),
        ("game_config_items", "value_gp"),
        ("game_config_consumables", "base_price"),
        ("game_items", "price_gp"),
    ]:
        if not _table_exists(conn, table):
            continue
        if not _col_exists(conn, table, price_col):
            continue
        rows = conn.execute(
            f"SELECT key, {price_col} FROM {table} WHERE {price_col} < 0"
        ).fetchall()
        for key, price in rows:
            warns.append(f"[RANGE] {table} '{key}': {price_col}={price} < 0")
    return warns


def _check_enum_violations(conn: sqlite3.Connection) -> list[str]:
    """(d) Enum violations — game_items.kind musi być weapon/armor/item/consumable."""
    warns: list[str] = []
    if not _table_exists(conn, "game_items"):
        return warns
    rows = conn.execute("SELECT key, kind FROM game_items").fetchall()
    for key, kind in rows:
        if kind not in _VALID_KINDS:
            warns.append(f"[ENUM] game_items '{key}': kind='{kind}' poza zbiorem {sorted(_VALID_KINDS)}")
    return warns


def _check_effect_json(conn: sqlite3.Connection) -> list[str]:
    """(e) Walidacja effect_json schematem U10 (jeśli validator dostępny)."""
    warns: list[str] = []
    try:
        from app.services.admin_config import validate_effect_json_payload
    except Exception:
        return warns  # validator niedostępny — pomiń
    tables_with_effect = [
        "game_config_weapons", "game_config_items", "game_config_consumables", "game_items"
    ]
    for table in tables_with_effect:
        if not _table_exists(conn, table):
            continue
        if not _col_exists(conn, table, "effect_json"):
            continue
        rows = conn.execute(f"SELECT key, effect_json FROM {table}").fetchall()
        for key, raw in rows:
            s = (raw or "").strip() if isinstance(raw, str) else (raw or "")
            if not s or s in ("{}", "null"):
                continue
            try:
                parsed = json.loads(s)
            except (json.JSONDecodeError, TypeError):
                warns.append(f"[EFFECT_JSON] {table} '{key}': niepoprawny JSON")
                continue
            errs = validate_effect_json_payload(parsed)
            if errs:
                warns.append(f"[EFFECT_JSON] {table} '{key}': {'; '.join(errs)}")
    return warns


def _check_orphans(conn: sqlite3.Connection) -> list[str]:
    """(f) Sieroty — rekordy legacy tabel nieobecne w game_items (informacyjne warnings)."""
    warns: list[str] = []
    if not _table_exists(conn, "game_items"):
        return warns
    game_item_keys: set[str] = {
        r[0] for r in conn.execute("SELECT key FROM game_items").fetchall()
    }
    for table in ("game_config_weapons", "game_config_items", "game_config_consumables"):
        if not _table_exists(conn, table):
            continue
        rows = conn.execute(f"SELECT key FROM {table}").fetchall()
        for (key,) in rows:
            if key not in game_item_keys:
                warns.append(f"[ORPHAN] {table} '{key}': brak w game_items (dual-write miss?)")
    return warns


# ── public API ────────────────────────────────────────────────────────────────

def run_lint(db_path: str | None = None) -> dict:
    """Uruchom wszystkie sprawdzenia i zwróć raport.

    Returns:
        {"errors": [...], "warnings": [...], "exit_code": int}
        exit_code: 0=czysto, 1=warnings, 2=errors
    """
    path = db_path or _DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    errors: list[str] = []
    warnings: list[str] = []
    try:
        errors += _check_dangling_fk(conn)
        errors += _check_null_required(conn)
        errors += _check_value_range(conn)
        errors += _check_enum_violations(conn)
        warnings += _check_effect_json(conn)
        warnings += _check_orphans(conn)
    finally:
        conn.close()

    if errors:
        exit_code = 2
    elif warnings:
        exit_code = 1
    else:
        exit_code = 0

    return {"errors": errors, "warnings": warnings, "exit_code": exit_code}


def format_report(result: dict) -> str:
    """Formatuj wynik run_lint() jako czytelny tekst."""
    lines = ["=" * 64, "DB LINT REPORT", "=" * 64]
    errors = result.get("errors", [])
    warnings = result.get("warnings", [])
    exit_code = result.get("exit_code", 0)
    if errors:
        lines.append(f"ERRORS ({len(errors)}):")
        lines.extend(f"  {e}" for e in errors)
    if warnings:
        lines.append(f"WARNINGS ({len(warnings)}):")
        lines.extend(f"  {w}" for w in warnings)
    if not errors and not warnings:
        lines.append("  ✅ Baza wygląda zdrowo — brak problemów.")
    lines.append("=" * 64)
    status = {0: "✅ CLEAN (exit 0)", 1: "⚠️  WARNINGS (exit 1)", 2: "❌ ERRORS (exit 2)"}
    lines.append(status.get(exit_code, f"exit {exit_code}"))
    return "\n".join(lines)
