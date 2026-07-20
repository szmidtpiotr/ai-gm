"""U13 (#561) — seed_lint: jedna ścieżka walidacji treści seedów.

Cel: każdy rekord z `data/seeds/01–15` przechodzi przez te same checki co żywa
baza — walidatory U10 (effect_json) + lint U12 (db_lint_service.run_lint).

Jak działa:
  1. Buduje ŚWIEŻĄ tymczasową bazę kopiując schemat z bazy źródłowej
     (domyślnie żywa DEV DB) — żaden seed nie dotyka produkcyjnych danych.
  2. Aplikuje pliki seedów w kolejności nazw (01_… → 15_…).
     Plik z błędnym SQL ląduje w `rejected` (raport odrzutów), nie wywala biegu.
  3. Uruchamia run_lint() na zaaplikowanej bazie (FK, NULL, enum, range,
     duplikaty, effect_json U10).
  4. Filtruje ORPHAN-warningi: game_items jest budowane dual-writem w runtime,
     nie seedami — na etapie seedu byłyby szumem.

Funkcja główna: lint_seeds(seeds_dir, source_schema_db) → dict
  {"applied": [...], "rejected": [{file, error}], "errors": [...],
   "warnings": [...], "exit_code": int}
  exit_code: 0 = czysto, 1 = warnings, 2 = errors (lub odrzucony plik)

Uruchamialny jako skrypt: python scripts/lint_seeds.py
"""
from __future__ import annotations

import os
import sqlite3
import tempfile

from app.services.db_lint_service import run_lint

try:
    from app.core.db_runtime import resolve_db_path
    _DEFAULT_SOURCE_DB = resolve_db_path()
except Exception:
    _DEFAULT_SOURCE_DB = resolve_db_path()

# Domyślny katalog seedów względem korzenia repo (host) i obrazu (/app → /app/../data).
_DEFAULT_SEEDS_DIRS = (
    "data/seeds",
    "/app/data/seeds",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "seeds"),
)


def _resolve_seeds_dir(seeds_dir: str | None) -> str:
    if seeds_dir:
        return seeds_dir
    for cand in _DEFAULT_SEEDS_DIRS:
        if os.path.isdir(cand):
            return cand
    return _DEFAULT_SEEDS_DIRS[0]


def _copy_schema(source_db: str, dest_conn: sqlite3.Connection) -> None:
    """Skopiuj schemat (CREATE TABLE/INDEX/TRIGGER) z bazy źródłowej do świeżej."""
    src = sqlite3.connect(source_db)
    try:
        rows = src.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
            "ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END"
        ).fetchall()
    finally:
        src.close()
    for (sql,) in rows:
        try:
            dest_conn.execute(sql)
        except sqlite3.OperationalError:
            # np. index na widoku/kolumnie której seed nie tworzy — pomiń, nieistotne dla lintu
            continue
    dest_conn.commit()


# Tabele treści z kolumną created_by — reguła: rekord seedowy MUSI mieć created_by='seed'.
_SEED_OWNER_TABLES = ("game_locations", "campaign_templates")


def _check_seed_created_by(db_path: str) -> list[str]:
    """Każdy zaaplikowany rekord seedowy z created_by != 'seed' → warning."""
    warns: list[str] = []
    conn = sqlite3.connect(db_path)
    try:
        for table in _SEED_OWNER_TABLES:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                continue
            cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if "created_by" not in cols:
                continue
            key_col = "key" if "key" in cols else ("title" if "title" in cols else cols[0])
            rows = conn.execute(
                f"SELECT {key_col}, created_by FROM {table} "
                f"WHERE created_by IS NULL OR created_by != 'seed'"
            ).fetchall()
            for ident, owner in rows:
                warns.append(
                    f"[SEED_OWNER] {table} '{ident}': created_by='{owner}' "
                    f"(rekord seedowy musi mieć created_by='seed')"
                )
    finally:
        conn.close()
    return warns


def _seed_files(seeds_dir: str) -> list[str]:
    """Pliki seedów do przejazdu: NN_*.sql posortowane po nazwie; pomija *_backup.sql."""
    names = [
        n for n in os.listdir(seeds_dir)
        if n.endswith(".sql") and not n.endswith("_backup.sql")
    ]
    return sorted(names)


def lint_seeds(
    seeds_dir: str | None = None,
    source_schema_db: str | None = None,
    seed_files: list[str] | None = None,
) -> dict:
    """Przepuść seedy przez świeżą bazę + run_lint. Zwróć raport z exit_code."""
    seeds_dir = _resolve_seeds_dir(seeds_dir)
    source_schema_db = source_schema_db or _DEFAULT_SOURCE_DB

    files = seed_files if seed_files is not None else _seed_files(seeds_dir)

    fd, tmp_db = tempfile.mkstemp(suffix="_seedlint.db")
    os.close(fd)

    applied: list[str] = []
    rejected: list[dict] = []
    try:
        conn = sqlite3.connect(tmp_db)
        _copy_schema(source_schema_db, conn)
        for name in files:
            path = os.path.join(seeds_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    conn.executescript(fh.read())
                conn.commit()
                applied.append(name)
            except (sqlite3.Error, OSError) as exc:
                conn.rollback()
                rejected.append({"file": name, "error": str(exc)})
        conn.close()

        lint = run_lint(tmp_db)
        seed_owner_warnings = _check_seed_created_by(tmp_db)
    finally:
        try:
            os.remove(tmp_db)
        except OSError:
            pass

    errors = list(lint.get("errors", []))
    # ORPHAN: game_items budowane dual-writem w runtime, nie seedami → szum na etapie seedu.
    warnings = [w for w in lint.get("warnings", []) if "ORPHAN" not in w]
    warnings += seed_owner_warnings

    if rejected or errors:
        exit_code = 2
    elif warnings:
        exit_code = 1
    else:
        exit_code = 0

    return {
        "applied": applied,
        "rejected": rejected,
        "errors": errors,
        "warnings": warnings,
        "exit_code": exit_code,
    }


def format_report(result: dict) -> str:
    """Formatuj wynik lint_seeds() jako czytelny tekst."""
    lines = ["=" * 64, "SEED LINT REPORT (U13)", "=" * 64]
    applied = result.get("applied", [])
    rejected = result.get("rejected", [])
    errors = result.get("errors", [])
    warnings = result.get("warnings", [])
    exit_code = result.get("exit_code", 0)

    lines.append(f"Zaaplikowane seedy ({len(applied)}): {', '.join(applied) or '—'}")
    if rejected:
        lines.append(f"ODRZUCONE pliki ({len(rejected)}):")
        lines.extend(f"  {r['file']}: {r['error']}" for r in rejected)
    if errors:
        lines.append(f"ERRORS ({len(errors)}):")
        lines.extend(f"  {e}" for e in errors)
    if warnings:
        lines.append(f"WARNINGS ({len(warnings)}):")
        lines.extend(f"  {w}" for w in warnings)
    if not rejected and not errors and not warnings:
        lines.append("  ✅ Seedy wyglądają zdrowo — brak problemów.")
    lines.append("=" * 64)
    status = {0: "✅ CLEAN (exit 0)", 1: "⚠️  WARNINGS (exit 1)", 2: "❌ ERRORS (exit 2)"}
    lines.append(status.get(exit_code, f"exit {exit_code}"))
    return "\n".join(lines)
