#!/usr/bin/env python3
"""U10 — Effect schema audit (decyzja C: hybryda).

Read-only audyt wszystkich kolumn `effect_json` w bazie. Dynamicznie wykrywa
tabele z taką kolumną, waliduje każdy niepusty rekord walidatorem U10
(`validate_effect_json_payload`) i raportuje rekordy nienormalizowalne — NIE
kasuje i NIE przepisuje (wariant C nie zmienia nazw typów, więc migracja =
audyt). Gwarancja: count rekordów przed == po (skrypt nic nie zapisuje).

Uruchom w kontenerze backendu:
    docker exec ai-gm-dev-backend-1 python scripts/effect_json_audit.py

Exit code: 0 = czysto, 2 = znaleziono rekordy invalid.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# Działa zarówno w repo (backend/app/...) jak i w kontenerze (/app/app/...).
_ROOT = Path(__file__).resolve().parent.parent
for _cand in (_ROOT / "backend", _ROOT):
    if (_cand / "app" / "services" / "admin_config.py").exists():
        sys.path.insert(0, str(_cand))
        break

from app.services.admin_config import DB_PATH, validate_effect_json_payload  # noqa: E402


def _tables_with_effect_json(conn: sqlite3.Connection) -> list[str]:
    out: list[str] = []
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for (table,) in rows:
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if "effect_json" in cols:
            out.append(table)
    return out


def _row_key(conn: sqlite3.Connection, table: str) -> str:
    cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    for cand in ("key", "id", "rowid"):
        if cand in cols:
            return cand
    return "rowid"


def audit(db_path: str = DB_PATH) -> int:
    conn = sqlite3.connect(db_path)
    try:
        tables = _tables_with_effect_json(conn)
        total_rows = 0
        total_nonempty = 0
        invalid: list[tuple[str, str, list[str]]] = []

        for table in tables:
            key_col = _row_key(conn, table)
            rows = conn.execute(
                f"SELECT {key_col} AS k, effect_json FROM {table}"
            ).fetchall()
            for k, raw in rows:
                total_rows += 1
                s = (raw or "").strip() if isinstance(raw, str) else raw
                if not s or s in ("{}", "null"):
                    continue
                total_nonempty += 1
                try:
                    parsed = json.loads(s)
                except (json.JSONDecodeError, TypeError):
                    invalid.append((table, str(k), ["effect_json nie jest poprawnym JSON"]))
                    continue
                errs = validate_effect_json_payload(parsed)
                if errs:
                    invalid.append((table, str(k), errs))

        print("=" * 64)
        print("U10 EFFECT_JSON AUDIT (read-only — nic nie zapisano)")
        print("=" * 64)
        print(f"Tabele z kolumną effect_json: {len(tables)}")
        for t in tables:
            print(f"  - {t}")
        print(f"Rekordów łącznie:        {total_rows}")
        print(f"Rekordów z efektem:      {total_nonempty}")
        print(f"Rekordów nienormalizowalnych: {len(invalid)}")
        print(f"Count przed == po:       {total_rows} == {total_rows}  (audyt read-only)")
        if invalid:
            print("-" * 64)
            print("DO RĘCZNEJ DECYZJI (NIE skasowano):")
            for table, k, errs in invalid:
                print(f"  [{table}] {k}: {'; '.join(errs)}")
        print("=" * 64)
        return 2 if invalid else 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(audit())
