"""Sprzątanie danych zostawionych przez przebieg testów UI (#1488).

Playwright uruchamiany z panelu admina klika ŻYWY DEV, więc każdy przebieg zostawia
w bazie rekordy (`test_loc_pw_*`, konta `test<cyfry>_*`, klony postaci…). Skrypt
`scripts/cleanup_test_data.py` sprząta zaległości z zewnątrz; ten moduł robi to
w locie: robi zdjęcie bazy przed przebiegiem i usuwa tylko to, co **powstało w jego
trakcie i wygląda na testowe**.

Dwa ograniczenia są celowe:
  * kasujemy wyłącznie wiersze spoza zdjęcia — cudze dane (Piotr grający równolegle)
    są nietykalne,
  * i tylko takie, których klucz/nazwa pasuje do wzorca testowego — przebieg
    dotykający realnej kampanii nie kasuje jej tury.
"""
from __future__ import annotations

import sqlite3

from app.core.db_runtime import resolve_db_path

# Tabela → (kolumna id, kolumna po której poznajemy śmieć). Wzorce muszą być zgodne
# z JUNK_PREDICATE w scripts/cleanup_test_data.py i _not_junk w scripts/content_seed_lib.py.
WATCHED: dict[str, tuple[str, str]] = {
    "game_locations": ("id", "key"),
    "npcs": ("id", "key"),
    "users": ("id", "username"),
    "characters": ("id", "name"),
}

# UWAGA: klasy znaków `[0-9]` działają w GLOB, NIE w LIKE — `LIKE 'test[0-9]%'`
# nie dopasuje `test960_h1`. Stąd wszystkie wzorce z cyframi jako GLOB.
# `ai_test_*` to konta seedowe trybu testowego — nigdy nie są śmieciem, a wzorzec
# `%_test_%` łapałby je jako pierwsze (wykryte testem, zanim skasowało to DEV).
_JUNK_SQL = (
    "({col} LIKE 'test\\_%' ESCAPE '\\' "
    " OR {col} GLOB 'test[0-9]*' "
    " OR {col} LIKE '\\_\\_test%' ESCAPE '\\' "
    " OR {col} LIKE '%\\_test\\_%' ESCAPE '\\' "
    " OR {col} GLOB 'issue[0-9]*' "
    " OR {col} GLOB 'TEST[0-9]*' "
    " OR {col} LIKE '[[]SBX]%' "
    " OR {col} LIKE '[[]SCN]%') "
    "AND {col} NOT LIKE 'ai\\_test%' ESCAPE '\\'"
)


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(resolve_db_path())


def snapshot() -> dict[str, set]:
    """Zdjęcie identyfikatorów w obserwowanych tabelach (przed przebiegiem)."""
    out: dict[str, set] = {}
    con = _connect()
    try:
        for table, (id_col, _) in WATCHED.items():
            try:
                out[table] = {r[0] for r in con.execute(f"SELECT {id_col} FROM {table}")}
            except sqlite3.Error:
                out[table] = set()
    finally:
        con.close()
    return out


def cleanup_since(before: dict[str, set]) -> dict[str, int]:
    """Usuń testowe rekordy powstałe po zdjęciu `before`. Zwraca {tabela: ile}."""
    removed: dict[str, int] = {}
    con = _connect()
    try:
        for table, (id_col, junk_col) in WATCHED.items():
            known = before.get(table)
            if known is None:
                continue
            try:
                rows = con.execute(
                    f"SELECT {id_col} FROM {table} WHERE {_JUNK_SQL.format(col=junk_col)}"
                ).fetchall()
            except sqlite3.Error:
                continue
            fresh = [r[0] for r in rows if r[0] not in known]
            if not fresh:
                continue
            marks = ",".join("?" * len(fresh))
            if table == "characters":
                # Postać zostawia ślady w character_* — usuwamy je razem z nią,
                # inaczej robimy z jednego śmiecia kilka sierot.
                for (child,) in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'character%'"
                ).fetchall():
                    if child == "characters":
                        continue
                    cols = [c[1] for c in con.execute(f"PRAGMA table_info('{child}')")]
                    if "character_id" in cols:
                        con.execute(f'DELETE FROM "{child}" WHERE character_id IN ({marks})', fresh)
            con.execute(f"DELETE FROM {table} WHERE {id_col} IN ({marks})", fresh)
            removed[table] = len(fresh)
        con.commit()
    finally:
        con.close()
    return removed


def summarize(removed: dict[str, int]) -> str:
    if not removed:
        return "brak śmieci do posprzątania"
    return ", ".join(f"{t} {n}" for t, n in sorted(removed.items()))
