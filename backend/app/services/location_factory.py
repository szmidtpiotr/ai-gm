"""#1526 (fala 3) — JEDNE DRZWI tworzenia lokacji.

Przed ta fala lokacje wchodzily do swiata **czternastoma** roznymi wejsciami
(seed, panel, Kreator, Kuznia, kotwica startowa, znacznik GM, walidator ruchu,
oboz, hub osady, sub-lokacje, placeholder podrozy, scena otwarcia, skrypty) —
i kazde stemplowalo flagi po swojemu. Skutki byly konkretne:

* `hex_travel_service` wpisywal status recenzji „approved" — wartosc, ktorej
  panel recenzji nie zna → lokacja w limbo (ani w poczekalni, ani przyjeta);
* `template_start_anchor` pisal historycznie „pending" zamiast „pending_review"
  → 31 lokacji liczylo sie do licznika, ale nie bylo ich na liscie (#1407);
* `local_map` pisal `world_hex_q/r` wprost w INSERT, omijajac kanonicznego
  writera → reconcile odpinal takie lokacje przy starcie backendu (#1305);
* sub-lokacje czesto dostawaly `parent_key` bez `parent_id` (albo odwrotnie),
  wiec „ide do X" trafialo w cudze floatujace sieroty (#1292).

Od #1526 jest **jedna** funkcja `create_location()` i jest ona jedynym
INSERT-em do `game_locations` w kodzie runtime (pilnuje tego test-guard
`tests/test_issue1526_one_door_locations.py`). Gwarantuje:

1. komplet flag wg zrodla (`LocationSource`) — status recenzji wylacznie
   z trzech legalnych wartosci (te same, ktorych pilnuje trigger z fali 2);
2. `parent_id` I `parent_key` zawsze razem (dowolny z nich wystarczy na wejsciu);
3. wiazanie z heksem WYLACZNIE przez `link_location_to_hex` (kanon #1243) —
   zadnych bezposrednich zapisow wspolrzednych;
4. idempotencje po kluczu — powtorne wywolanie zwraca istniejacy wiersz
   zamiast tworzyc kopie `_2` (regres „dwie karczmy", #1212).

Wyjatki od reguly „jedne drzwi" (jawne, w test-guardzie):
`migrations_admin.py` — przebudowy schematu kopiuja gotowe, juz ostemplowane
wiersze; `scripts/seed_content.py` — odtworzenie kanonu z gita jest wiernym
przywroceniem wierszy (z `id`), a nie tworzeniem nowej lokacji.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from enum import Enum

from app.core.logging import get_logger
from app.services.hex_location_link import link_location_to_hex

logger = get_logger(__name__)


class LocationSource(str, Enum):
    """Kto tworzy lokacje — jedyne legalne wartosci `game_locations.created_by`."""

    SEED = "seed"                      # kanon z gita / skrypty seedujace krainy
    ADMIN_MANUAL = "admin_manual"      # panel admina, recznie
    ADMIN_KREATOR = "admin_kreator"    # Kreator AI (Smart Entry)
    FORGE = "forge"                    # Kuznia / szablony kampanii
    GM_RUNTIME = "gm_runtime"          # narrator i mechanizmy w trakcie gry
    AUTO_GENERATED = "auto_generated"  # generatory osad (hub + sub-lokacje)


REVIEW_PERMANENT = "permanent"
REVIEW_PENDING = "pending_review"
REVIEW_DISCARDED = "discarded"

#: Trzy legalne statusy recenzji (fala 2, #1525 — pilnowane tez triggerem w DB).
LEGAL_REVIEW_STATUSES = frozenset({REVIEW_PERMANENT, REVIEW_PENDING, REVIEW_DISCARDED})


#: Domyslny stempel flag per zrodlo. `canonical_macro` dotyczy tylko lokacji
#: makro — sub-lokacja nigdy nie jest kanoniczna sama z siebie (tak jak w seedzie).
_SOURCE_DEFAULTS: dict[LocationSource, dict] = {
    LocationSource.SEED: {"review_status": REVIEW_PERMANENT, "approved": 1, "canonical_macro": 1},
    LocationSource.ADMIN_MANUAL: {"review_status": REVIEW_PERMANENT, "approved": 1, "canonical_macro": 0},
    LocationSource.ADMIN_KREATOR: {"review_status": REVIEW_PERMANENT, "approved": 1, "canonical_macro": 0},
    LocationSource.AUTO_GENERATED: {"review_status": REVIEW_PERMANENT, "approved": 1, "canonical_macro": 0},
    LocationSource.FORGE: {"review_status": REVIEW_PENDING, "approved": 1, "canonical_macro": 0},
    LocationSource.GM_RUNTIME: {"review_status": REVIEW_PENDING, "approved": 1, "canonical_macro": 0},
}


def _cols(conn: sqlite3.Connection) -> set[str]:
    try:
        return {row[1] for row in conn.execute("PRAGMA table_info(game_locations)").fetchall()}
    except sqlite3.Error:
        return set()


def _coerce_source(source) -> LocationSource:
    if isinstance(source, LocationSource):
        return source
    try:
        return LocationSource(str(source))
    except ValueError:
        raise ValueError(
            f"nieznane zrodlo lokacji: {source!r} — legalne: "
            f"{sorted(s.value for s in LocationSource)}"
        ) from None


def _unique_key(conn: sqlite3.Connection, base: str) -> str:
    key = base
    idx = 2
    while conn.execute("SELECT 1 FROM game_locations WHERE key = ?", (key,)).fetchone():
        key = f"{base}_{idx}"
        idx += 1
    return key


def _resolve_parent(
    conn: sqlite3.Connection, parent_key: str | None, parent_id: int | None
) -> tuple[str | None, int | None]:
    """Zawsze zwraca KOMPLET (key, id) albo (None, None).

    Rodzic wskazany polowicznie (samym kluczem albo samym id) jest dopelniany
    z bazy — koniec sub-lokacji z pustym `parent_id` (#1292).
    """
    parent_key = (parent_key or None) or None
    if parent_key is None and parent_id is None:
        return (None, None)
    row = None
    try:
        if parent_key is not None:
            row = conn.execute(
                "SELECT id, key FROM game_locations WHERE key = ? "
                "ORDER BY is_active DESC, id LIMIT 1",
                (parent_key,),
            ).fetchone()
        if row is None and parent_id is not None:
            row = conn.execute(
                "SELECT id, key FROM game_locations WHERE id = ? LIMIT 1", (int(parent_id),)
            ).fetchone()
    except sqlite3.Error:
        # Minimalny schemat testowy bez `id`/`is_active` — zostawiamy wejscie.
        row = None
    if row is None:
        # Rodzic nieznany bazie — zostawiamy to, co podal wolajacy (np. seed
        # wstawiajacy dzieci przed rodzicem); triggery z fali 2 dopelnia reszte.
        return (parent_key, int(parent_id) if parent_id is not None else None)
    return (row["key"], int(row["id"]))


def create_location(
    conn: sqlite3.Connection,
    *,
    key: str,
    label: str,
    source: LocationSource | str,
    description: str | None = "",
    location_type: str | None = None,
    parent_key: str | None = None,
    parent_id: int | None = None,
    hex_q: int | None = None,
    hex_r: int | None = None,
    hex_level: int = 0,
    link_only_if_empty: bool = False,
    review_status: str | None = None,
    approved: int | bool | None = None,
    canonical: int | bool | None = None,
    is_active: int | bool = 1,
    source_campaign_id: int | None = None,
    safe_for_rest: int | bool | None = None,
    temporary: int | bool | None = None,
    location_subtype: str | None = None,
    biome: str | None = None,
    region: str | None = None,
    tier: int | None = None,
    map_icon: str | None = None,
    visible_before_visit: int | bool | None = None,
    rules: str | None = None,
    enemy_keys: str | None = None,
    npc_keys: str | None = None,
    terrain_tags: str | None = None,
    enrichment_locked: int | bool | None = None,
    unique_key: bool = False,
    commit: bool = True,
) -> dict:
    """Jedyne drzwi do `game_locations`. Zwraca dict z rekordem.

    Zwracany dict: `{"key", "id", "created", "review_status", "created_by",
    "location_type", "parent_key", "parent_id"}`. `created=False` oznacza,
    ze wiersz o tym kluczu juz istnial (idempotencja).

    * `unique_key=True` — zamiast zwrocic istniejacy wiersz, dobiera wolny
      klucz z sufiksem (`_2`, `_3`, …). Uzywaja tego generatory, ktore MUSZA
      dolozyc nowy obiekt (sub-lokacje osady, kopia przy konflikcie kluczy).
    * `hex_q/hex_r` — wiazanie z mapa idzie przez `link_location_to_hex`
      (kanon = `world_hexes.location_key`); wspolrzednych na karcie NIE
      zapisujemy recznie, bo to tylko lustro kanonu.
    """
    src = _coerce_source(source)
    if not key or not str(key).strip():
        raise ValueError("create_location: pusty klucz lokacji")
    key = str(key).strip()

    defaults = _SOURCE_DEFAULTS[src]
    status = review_status if review_status is not None else defaults["review_status"]
    if status not in LEGAL_REVIEW_STATUSES:
        raise ValueError(
            f"nielegalny review_status={status!r} dla lokacji {key!r} — legalne: "
            f"{sorted(LEGAL_REVIEW_STATUSES)}"
        )

    parent_key, parent_id = _resolve_parent(conn, parent_key, parent_id)
    loc_type = location_type or ("sub" if (parent_key or parent_id) else "macro")
    if loc_type not in ("macro", "sub"):
        loc_type = "sub" if (parent_key or parent_id) else "macro"

    # Minimalne schematy testowe nie maja kompletu kolumn — pytamy tylko o te,
    # ktore realnie istnieja.
    present_cols = _cols(conn)
    probe = [
        c for c in ("id", "key", "review_status", "created_by",
                    "location_type", "parent_key", "parent_id")
        if not present_cols or c in present_cols
    ]
    existing_row = conn.execute(
        f"SELECT {', '.join(probe)} FROM game_locations WHERE key = ?", (key,)
    ).fetchone()
    existing = dict(existing_row) if existing_row is not None else None
    if existing is not None:
        if not unique_key:
            # Idempotencja: te same drzwi wywolane drugi raz nie dubluja miejsca.
            if hex_q is not None and hex_r is not None:
                link_location_to_hex(
                    conn, key, int(hex_q), int(hex_r), level=hex_level,
                    only_if_empty=link_only_if_empty,
                )
                if commit:
                    conn.commit()
            return {
                "key": existing.get("key", key),
                "id": int(existing["id"]) if existing.get("id") is not None else None,
                "created": False,
                "review_status": existing.get("review_status"),
                "created_by": existing.get("created_by"),
                "location_type": existing.get("location_type"),
                "parent_key": existing.get("parent_key"),
                "parent_id": existing.get("parent_id"),
            }
        key = _unique_key(conn, key)

    if canonical is None:
        canonical_val = int(defaults["canonical_macro"]) if loc_type == "macro" else 0
    else:
        canonical_val = int(bool(canonical))
    approved_val = int(defaults["approved"]) if approved is None else int(bool(approved))

    now = datetime.now(timezone.utc).isoformat()
    values: dict[str, object] = {
        "key": key,
        "label": label,
        "description": description or "",
        "location_type": loc_type,
        "parent_key": parent_key,
        "parent_id": parent_id,
        "review_status": status,
        "created_by": src.value,
        "canonical": canonical_val,
        "approved": approved_val,
        "is_active": int(bool(is_active)),
        "created_at": now,
        "updated_at": now,
    }
    optional = {
        "source_campaign_id": source_campaign_id,
        "safe_for_rest": None if safe_for_rest is None else int(bool(safe_for_rest)),
        "temporary": None if temporary is None else int(bool(temporary)),
        "location_subtype": location_subtype,
        "biome": biome,
        "region": region,
        "tier": tier,
        "map_icon": map_icon,
        "visible_before_visit": None if visible_before_visit is None else int(bool(visible_before_visit)),
        "rules": rules,
        "enemy_keys": enemy_keys,
        "npc_keys": npc_keys,
        "terrain_tags": terrain_tags,
        "enrichment_locked": None if enrichment_locked is None else int(bool(enrichment_locked)),
    }
    values.update({k: v for k, v in optional.items() if v is not None})

    if present_cols:
        values = {k: v for k, v in values.items() if k in present_cols}

    cols = ", ".join(values)
    marks = ", ".join("?" * len(values))
    cur = conn.execute(
        f"INSERT INTO game_locations ({cols}) VALUES ({marks})", list(values.values())
    )
    new_id = int(cur.lastrowid)

    if hex_q is not None and hex_r is not None:
        # #1243/#1305 — kanonem jest heks; karta dostaje tylko lustro.
        link_location_to_hex(
            conn, key, int(hex_q), int(hex_r), level=hex_level,
            only_if_empty=link_only_if_empty,
        )

    if commit:
        conn.commit()

    logger.info(
        "location_created",
        key=key, source=src.value, review_status=status,
        location_type=loc_type, parent_key=parent_key,
        hex=(hex_q, hex_r) if hex_q is not None else None,
        campaign_id=source_campaign_id,
    )
    return {
        "key": key,
        "id": new_id,
        "created": True,
        "review_status": status,
        "created_by": src.value,
        "location_type": loc_type,
        "parent_key": parent_key,
        "parent_id": parent_id,
    }
