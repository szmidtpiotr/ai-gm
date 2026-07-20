"""#1484 — badge krainy na wizytówce idzie za statusem krainy w grze.

Wizytówka (`frontend/showcase/data/swiat.json`) trzyma treść w pliku, nie w DB.
Pole ``available`` było ustawiane ręcznie i rozjechało się ze stanem gry — Siwe
Granie były `live` w `world_regions`, a strona nadal mówiła „WKRÓTCE".

Podział ról w pliku krainy:

  * ``available``          — LUSTRO ``world_regions.status`` (`live` → True).
    Utrzymywane automatycznie po każdej zmianie statusu; nie edytuj ręcznie.
    Służy też jako fallback, gdy strona nie doczyta się do backendu.
  * ``available_override`` — ręczna decyzja (True/False). Wygrywa ze wszystkim;
    sync jej nie dotyka. Do sytuacji „grywalne, ale jeszcze niezapowiedziane".
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

DEFAULT_SWIAT_PATH = os.environ.get(
    "SHOWCASE_SWIAT_PATH", "/app/showcase_data/swiat.json"
)


def _region_states(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT key, label, status FROM world_regions ORDER BY sort_order"
    ).fetchall()
    return [
        {"key": r["key"], "label": r["label"], "available": r["status"] == "live"}
        for r in rows
    ]


def public_region_states(conn: sqlite3.Connection) -> list[dict]:
    """Publiczna prawda dla wizytówki: która kraina jest grywalna.

    Zwraca pustą listę zamiast rzucać, gdy tabeli nie ma (świeży clone) — strona
    marketingowa nie może paść przez brak seeda mapy.
    """
    try:
        return _region_states(conn)
    except sqlite3.Error:
        return []


def sync_region_mirror(
    conn: sqlite3.Connection,
    path: str = DEFAULT_SWIAT_PATH,
) -> bool:
    """Przepisz ``available`` w swiat.json wg aktualnych statusów krain.

    Dopasowanie po ``key``, a gdy go brak — po ``name`` (starszy plik bez kluczy).
    Kraina z wizytówki bez odpowiednika w `world_regions` zostaje nietknięta.
    Zwraca True, gdy plik został zapisany.
    """
    try:
        states = _region_states(conn)
    except sqlite3.Error:
        logger.warning("showcase_mirror_skipped: brak world_regions")
        return False
    if not states:
        return False

    by_key = {s["key"]: s for s in states}
    by_label = {s["label"].casefold(): s for s in states}

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        logger.warning("showcase_mirror_skipped: nie mogę wczytać %s", path)
        return False

    krainy = data.get("krainy")
    if not isinstance(krainy, list):
        return False

    changed = False
    for entry in krainy:
        if not isinstance(entry, dict):
            continue
        state = by_key.get(entry.get("key")) or by_label.get(
            str(entry.get("name") or "").casefold()
        )
        if state is None:
            continue  # kraina spoza gry (np. czysto marketingowa) — nie ruszamy
        if entry.get("available") is not state["available"]:
            entry["available"] = state["available"]
            changed = True

    if not changed:
        return True  # plik już zgodny — nie przepisujemy go bez potrzeby

    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except OSError:
        logger.warning("showcase_mirror_skipped: nie mogę zapisać %s", path)
        return False
    return True
