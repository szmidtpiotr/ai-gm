"""#1039 — dostępność krain (world_regions.status) w jednym miejscu.

Dwie odpowiedzialności:

  * ``set_region_status`` — admin flipuje krainę ``live``↔``coming``↔``locked``.
    Uwaga na warstwy: kanonem *domyślnego* statusu jest plik
    ``data/regions/region_<key>.json`` (R1 #1241) — git-committed i zamontowany
    **read-only**, więc backend go nie zapisuje. Decyzja admina jest trwałym
    **override'em w DB** (``world_regions.status_override``), którego migracja
    startowa ``_align_region_status_to_files`` celowo nie nadpisuje. Dzięki temu
    flip przeżywa restart, a kraina bez override'u nadal podąża za kanonem.
    ``reset_region_status`` zdejmuje override i wraca do kanonu.

  * ``region_block_for_hex`` — wspólna bramka travel: heks leżący w krainie
    ``coming``/``locked`` zwraca ustrukturyzowany payload blokady
    (``error_code='region_locked'`` + label/status), żeby ŻAR mógł pokazać
    dedykowany modal zamiast milczącego no-opa.
"""
from __future__ import annotations

import sqlite3

REGION_STATUSES = ("live", "coming", "locked")

#: Statusy, które zamykają granicę dla gracza (admin nadal widzi krainę).
BLOCKING_STATUSES = ("coming", "locked")


def list_region_rows(conn: sqlite3.Connection) -> list[dict]:
    """Wszystkie krainy ze statusem — admin preview (live + coming + locked)."""
    return [dict(r) for r in conn.execute(
        "SELECT key, label, color, status, status_override, entry_q, entry_r, sort_order, note "
        "FROM world_regions ORDER BY sort_order"
    ).fetchall()]


def _region_row(conn: sqlite3.Connection, key: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT key, label, status, status_override FROM world_regions WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        raise LookupError(f"nieznana kraina: {key!r}")
    return row


def set_region_status(conn: sqlite3.Connection, key: str, status: str) -> dict:
    """Ustaw status krainy jako decyzję admina (trwały override nad kanonem plików).

    Raises:
        ValueError: status spoza ``REGION_STATUSES``.
        LookupError: nieznany klucz krainy.
    """
    if status not in REGION_STATUSES:
        raise ValueError(f"status musi być jednym z {REGION_STATUSES}, jest {status!r}")

    row = _region_row(conn, key)
    conn.execute(
        "UPDATE world_regions SET status = ?, status_override = ? WHERE key = ?",
        (status, status, key),
    )
    conn.commit()
    return {
        "key": key,
        "label": row["label"],
        "status": status,
        "previous_status": row["status"],
        "overridden": True,
    }


def reset_region_status(conn: sqlite3.Connection, key: str) -> dict:
    """Zdejmij override — kraina wraca pod kanon z pliku przy najbliższym starcie."""
    row = _region_row(conn, key)
    conn.execute("UPDATE world_regions SET status_override = NULL WHERE key = ?", (key,))
    conn.commit()
    return {
        "key": key,
        "label": row["label"],
        "status": row["status"],
        "overridden": False,
    }


def region_block_for_hex(conn: sqlite3.Connection, q: int, r: int) -> dict | None:
    """Blokada travel dla heksa w niedostępnej krainie, albo None.

    None znaczy „ta bramka nie ma nic do powiedzenia" — heks jest w krainie
    ``live`` albo w ogóle nie istnieje (inne komunikaty travel go obsłużą).
    """
    try:
        row = conn.execute(
            "SELECT wh.region, wr.status, wr.label FROM world_hexes wh "
            "LEFT JOIN world_regions wr ON wr.key = wh.region "
            "WHERE wh.q = ? AND wh.r = ? AND wh.map_level = 0 AND wh.is_active = 1 LIMIT 1",
            (int(q), int(r)),
        ).fetchone()
    except sqlite3.Error:
        return None
    if not row or row["status"] not in BLOCKING_STATUSES:
        return None
    label = row["label"] or row["region"]
    return {
        "error": f"Kraina niedostępna — {label} jest za zamkniętą granicą.",
        "error_code": "region_locked",
        "region": row["region"],
        "region_label": label,
        "region_status": row["status"],
    }
