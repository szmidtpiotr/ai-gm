"""#1527 (fala 4) — LAMPKA W PANELU zamiast cichej samonaprawy.

Do tej pory swiat prostowal sie sam, po cichu, przy kazdym starcie backendu
(`reconcile_location_hex_links` + backfille regionow i terenow). Rozjazd znikal
z ekranu, ale przyczyna zostawala, a Piotr nigdy sie nie dowiadywal, ze cos bylo
nie tak. Rownolegle zaden lint nie pytal o jakosc TRESCI — stad 30 lokacji
uslugowych bez gospodarza (#1524) przelezalo miesiace niezauwazone.

Ten modul daje trzy rzeczy:

1. **`run_world_lint()`** — 7 regul, ktore nazywaja rozjazd po imieniu zamiast
   go cichcem zaklejac (lista trafia do panelu: Swiat → 🩺 Kontrola swiata).
2. **`fix_world_lint_issue()`** — jawna, deterministyczna naprawa POJEDYNCZEGO
   rozjazdu, uruchamiana guzikiem przez czlowieka. Reguly wymagajace decyzji
   tresciowej (dosiew gospodarza, wybor ktory duplikat zostawic) sa celowo
   `fixable=False` — maszyna ich nie zgaduje.
3. **Historia napraw** (`world_lint_history`) — reconcile przy starcie DOPISUJE
   co naprawil; kazda naprawa z panelu tez zostawia slad.

Reguly:

| klucz                            | co lapie                                        | naprawialne |
|----------------------------------|-------------------------------------------------|-------------|
| `service_without_host`           | karczma/kuznia/kram/swiatynia/stajnia/komora bez ani jednego NPC | nie |
| `orphan_npc_assignment`          | NPC przypisany do nieistniejacej lokacji         | tak |
| `hex_points_to_missing_location` | heks wskazuje lokacje, ktorej nie ma             | tak |
| `pin_not_backed_by_canon`        | lokacja twierdzi, ze stoi na heksie, ktorego kanon jej nie przyznaje | tak |
| `broken_sublocation_parent`      | sub-lokacja bez rodzica lub bez kompletu `parent_id`+`parent_key` | tak |
| `illegal_flag_value`             | `created_by` / `review_status` spoza legalnego zbioru | tak |
| `duplicate_label_in_region`      | dwie lokacje o (niemal) tej samej etykiecie w jednej krainie | nie |

**Bramka krain (korekta Piotra, 2026-07-21, #1527):** regula
`service_without_host` liczy sie WYLACZNIE dla krain o statusie `live`. Filtr
stoi na `world_regions.status`, nie na liscie nazw — Czarnobor i Martwe
Pustkowia wejda do lintu automatycznie w dniu otwarcia, bez zmian w kodzie.
Powodem wylaczenia nie jest lore (kanon obu krain MA osady i uslugi), tylko
stan swiata: 0 heksow i brak lokacji-hubow.

Numbers Policy: `DUPLICATE_SIMILARITY_THRESHOLD` (0.85) i `LINT_LIST_LIMIT`
(200) to wartosci STARTOWE, do strojenia po pierwszym przebiegu na zywych
danych.
"""
from __future__ import annotations

import sqlite3
from difflib import SequenceMatcher

from app.core.logging import get_logger

logger = get_logger(__name__)

__all__ = [
    "DUPLICATE_SIMILARITY_THRESHOLD",
    "LINT_LIST_LIMIT",
    "SERVICE_SUBTYPES",
    "assign_host",
    "create_host",
    "duplicate_compare",
    "fix_world_lint_issue",
    "fix_world_lint_rule",
    "host_candidates",
    "host_suggestion_context",
    "lint_flags",
    "lint_history",
    "lint_issue_count",
    "record_reconcile_report",
    "record_repair",
    "record_startup_cleanup",
    "resolve_duplicate",
    "run_world_lint",
]

#: Wartosci STARTOWE (Numbers Policy #1527) — do strojenia na zywych danych.
DUPLICATE_SIMILARITY_THRESHOLD = 0.85
LINT_LIST_LIMIT = 200

#: Podtypy lokacji, ktore bez gospodarza sa martwe dla gracza
#: (karczma / kuznia / kram / swiatynia / stajnia / komora — #1527).
SERVICE_SUBTYPES: dict[str, str] = {
    "tavern": "karczma",
    "inn": "gospoda",
    "wayside-inn": "zajazd",
    "smithy": "kuźnia",
    "forge": "kuźnia",
    "shop": "kram",
    "stall": "kram",
    "market": "targ",
    "temple": "świątynia",
    "shrine": "kapliczka",
    "stable": "stajnia",
    "storehouse": "komora",
    "granary": "komora",
}

#: Legalne wartosci flag (zrodlo prawdy: `location_factory.LocationSource`
#: oraz trigger `review_status` z fali 2).
LEGAL_CREATED_BY = {
    "seed", "admin_manual", "admin_kreator", "forge", "gm_runtime", "auto_generated",
}
LEGAL_REVIEW_STATUS = {"permanent", "pending_review", "discarded"}

_SEVERITY_ERROR = "error"
_SEVERITY_WARNING = "warning"

#: Reguly, ktorych maszyna NIE naprawia — wymagaja decyzji tresciowej czlowieka.
_UNFIXABLE = {"service_without_host", "duplicate_label_in_region"}


# ─── pomocnicze ──────────────────────────────────────────────────────────────

def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def _issue(rule: str, target: str, label: str, detail: str, severity: str) -> dict:
    return {
        "id": f"{rule}:{target}",
        "rule": rule,
        "severity": severity,
        "label": label,
        "detail": detail,
        "target": target,
        "fixable": rule not in _UNFIXABLE,
    }


def _norm_label(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


# ─── historia napraw ─────────────────────────────────────────────────────────

_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS world_lint_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    source     TEXT NOT NULL,
    rule       TEXT NOT NULL,
    target     TEXT,
    detail     TEXT
)
"""


def _ensure_history_table(conn: sqlite3.Connection) -> None:
    conn.execute(_HISTORY_DDL)


def record_repair(
    conn: sqlite3.Connection, source: str, rule: str, target: str, detail: str = ""
) -> None:
    """Dopisz wpis do historii napraw (koniec cichej samonaprawy)."""
    _ensure_history_table(conn)
    conn.execute(
        "INSERT INTO world_lint_history (source, rule, target, detail) VALUES (?,?,?,?)",
        (source, rule, target, detail),
    )
    conn.commit()


def record_reconcile_report(conn: sqlite3.Connection, report: dict) -> int:
    """Przelej raport `reconcile_location_hex_links()` do historii napraw.

    Zwraca liczbe dopisanych wpisow (0 = reconcile nic nie ruszyl).
    """
    _ensure_history_table(conn)
    rows: list[tuple[str, str, str, str]] = []
    for entry in report.get("smears") or []:
        rows.append((
            "startup_reconcile", "reconcile_smear", str(entry.get("key", "")),
            f"lokacja siedziala na kilku heksach; zostal {entry.get('kept')}, "
            f"zwolniony {entry.get('cleared_hex')}",
        ))
    for entry in report.get("backfilled") or []:
        rows.append((
            "startup_reconcile", "reconcile_backfill", str(entry.get("key", "")),
            f"pin przepisany z {entry.get('from')} na kanoniczny {entry.get('to')}",
        ))
    for entry in report.get("promoted") or []:
        rows.append((
            "startup_reconcile", "reconcile_promote", str(entry.get("key", "")),
            f"pin bez kanonu awansowal na kanon heksa {entry.get('hex')}",
        ))
    for entry in report.get("cleared") or []:
        rows.append((
            "startup_reconcile", "reconcile_clear", str(entry.get("key", "")),
            f"pin {entry.get('was')} bez pokrycia w kanonie — odpiety od mapy",
        ))
    if not rows:
        return 0
    conn.executemany(
        "INSERT INTO world_lint_history (source, rule, target, detail) VALUES (?,?,?,?)",
        rows,
    )
    conn.commit()
    logger.info("world_lint_reconcile_recorded", entries=len(rows))
    return len(rows)


def record_startup_cleanup(
    conn: sqlite3.Connection, rule: str, targets, detail: str = ""
) -> int:
    """Wpisz do kroniki to, co wyprostowala migracja startowa (#1525 i pochodne).

    Reconcile to nie jedyny cichy uzdrowiciel — sprzatanie w `migrations_admin`
    gasilo piny i zwalnialo heksy przy KAZDYM starcie, nie mowiac o tym nikomu.
    Zwraca liczbe dopisanych wpisow.
    """
    rows = [
        ("startup_migration", rule, str(t), detail)
        for t in (targets or []) if str(t or "").strip()
    ]
    if not rows:
        return 0
    _ensure_history_table(conn)
    conn.executemany(
        "INSERT INTO world_lint_history (source, rule, target, detail) VALUES (?,?,?,?)",
        rows,
    )
    conn.commit()
    logger.info("world_lint_startup_cleanup_recorded", rule=rule, entries=len(rows))
    return len(rows)


def lint_history(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """Ostatnie naprawy — najnowsze pierwsze."""
    _ensure_history_table(conn)
    rows = conn.execute(
        "SELECT id, created_at, source, rule, target, detail FROM world_lint_history "
        "ORDER BY id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── reguly ──────────────────────────────────────────────────────────────────

def _live_regions(conn: sqlite3.Connection) -> set[str]:
    if not _table_exists(conn, "world_regions"):
        return set()
    return {
        r[0] for r in conn.execute(
            "SELECT key FROM world_regions WHERE status = 'live'"
        ).fetchall()
    }


def _rule_service_without_host(conn: sqlite3.Connection) -> list[dict]:
    """Lokacja uslugowa w krainie `live`, w ktorej nie stoi ani jeden NPC.

    Hub (makro z sub-lokacjami) jest z zalozenia pusty (#1524) — pomijany.
    """
    if not _table_exists(conn, "game_locations"):
        return []
    live = _live_regions(conn)
    if not live:
        return []
    cols = _cols(conn, "game_locations")
    if "location_subtype" not in cols or "region" not in cols:
        return []
    placeholders = ",".join("?" * len(SERVICE_SUBTYPES))
    region_ph = ",".join("?" * len(live))
    sql = (
        f"SELECT key, label, location_subtype, region FROM game_locations "
        f"WHERE is_active = 1 AND location_subtype IN ({placeholders}) "
        f"AND region IN ({region_ph})"
    )
    if "review_status" in cols:
        sql += " AND review_status = 'permanent'"
    sql += " ORDER BY region, key"
    rows = conn.execute(sql, [*SERVICE_SUBTYPES.keys(), *sorted(live)]).fetchall()

    issues: list[dict] = []
    for row in rows:
        key = row["key"]
        if _has_children(conn, key):
            continue  # hub osady — gospodarze siedza w jego sub-lokacjach
        if _host_count(conn, key) > 0:
            continue
        pl = SERVICE_SUBTYPES.get(row["location_subtype"], row["location_subtype"])
        issues.append(_issue(
            "service_without_host", key,
            f"{row['label']} — {pl} bez gospodarza",
            f"Lokacja usługowa ({row['location_subtype']}) w krainie „{row['region']}” "
            f"nie ma przypisanego żadnego NPC. Gracz wejdzie do pustego wnętrza. "
            f"Dosiew gospodarza to zadanie treściowe (fala po #1524).",
            _SEVERITY_WARNING,
        ))
    return issues


def _has_children(conn: sqlite3.Connection, key: str) -> bool:
    if "parent_key" not in _cols(conn, "game_locations"):
        return False
    row = conn.execute(
        "SELECT 1 FROM game_locations WHERE parent_key = ? AND is_active = 1 LIMIT 1", (key,)
    ).fetchone()
    return row is not None


def _host_count(conn: sqlite3.Connection, key: str) -> int:
    if not _table_exists(conn, "location_npc_assignments"):
        return 0
    row = conn.execute(
        "SELECT COUNT(*) FROM location_npc_assignments "
        "WHERE location_key = ? AND COALESCE(is_active, 1) = 1",
        (key,),
    ).fetchone()
    return int(row[0] or 0)


def _rule_orphan_npc_assignment(conn: sqlite3.Connection) -> list[dict]:
    """Obsada wskazujaca lokacje, ktorej juz nie ma (sierota po fali 0/1)."""
    if not _table_exists(conn, "location_npc_assignments") or not _table_exists(conn, "game_locations"):
        return []
    rows = conn.execute(
        "SELECT a.location_key, a.npc_key FROM location_npc_assignments a "
        "WHERE COALESCE(a.is_active, 1) = 1 AND NOT EXISTS ("
        "  SELECT 1 FROM game_locations l WHERE l.key = a.location_key AND l.is_active = 1) "
        "ORDER BY a.location_key, a.npc_key"
    ).fetchall()
    return [
        _issue(
            "orphan_npc_assignment", f"{r['location_key']}|{r['npc_key']}",
            f"NPC „{r['npc_key']}” przypisany do nieistniejącej lokacji",
            f"Przypisanie wskazuje lokację „{r['location_key']}”, której nie ma "
            f"w aktywnym świecie. Naprawa dezaktywuje przypisanie.",
            _SEVERITY_ERROR,
        )
        for r in rows
    ]


def _rule_hex_points_to_missing_location(conn: sqlite3.Connection) -> list[dict]:
    """Heks kanonu wskazuje lokacje nieistniejaca lub nieaktywna."""
    if not _table_exists(conn, "world_hexes") or not _table_exists(conn, "game_locations"):
        return []
    rows = conn.execute(
        "SELECT h.q, h.r, h.location_key FROM world_hexes h "
        "WHERE h.map_level = 0 AND h.is_active = 1 "
        "AND h.location_key IS NOT NULL AND h.location_key != '' "
        "AND NOT EXISTS (SELECT 1 FROM game_locations l "
        "                WHERE l.key = h.location_key AND l.is_active = 1) "
        "ORDER BY h.q, h.r"
    ).fetchall()
    return [
        _issue(
            "hex_points_to_missing_location", f"{r['q']},{r['r']}",
            f"Heks ({r['q']},{r['r']}) wskazuje nieistniejącą lokację „{r['location_key']}”",
            "Kanon mapy trzyma klucz lokacji, której nie ma. Naprawa zwalnia heks "
            "(kasuje wskazanie), sama mapa zostaje nietknięta.",
            _SEVERITY_ERROR,
        )
        for r in rows
    ]


def _rule_pin_not_backed_by_canon(conn: sqlite3.Connection) -> list[dict]:
    """Lokacja twierdzi, ze stoi na heksie, ktorego kanon jej nie przyznaje."""
    if not _table_exists(conn, "game_locations") or not _table_exists(conn, "world_hexes"):
        return []
    if "world_hex_q" not in _cols(conn, "game_locations"):
        return []
    rows = conn.execute(
        "SELECT l.key, l.label, l.world_hex_q AS q, l.world_hex_r AS r FROM game_locations l "
        "WHERE l.is_active = 1 AND l.world_hex_q IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM world_hexes h "
        "                WHERE h.map_level = 0 AND h.is_active = 1 "
        "                  AND h.location_key = l.key "
        "                  AND h.q = l.world_hex_q AND h.r = l.world_hex_r) "
        "ORDER BY l.key"
    ).fetchall()
    return [
        _issue(
            "pin_not_backed_by_canon", r["key"],
            f"{r['label']} — pin ({r['q']},{r['r']}) bez pokrycia w kanonie",
            "Współrzędne w lokacji to tylko kopia kanonu heksów (#1243), a kanon "
            "nie przyznaje jej tego heksa. Naprawa odpina pin — lokacja zostaje "
            "grywalna narracyjnie, tylko bez znacznika na mapie świata.",
            _SEVERITY_ERROR,
        )
        for r in rows
    ]


def _rule_broken_sublocation_parent(conn: sqlite3.Connection) -> list[dict]:
    """Sub-lokacja bez rodzica albo bez kompletu `parent_id` + `parent_key`."""
    cols = _cols(conn, "game_locations")
    if not {"parent_id", "parent_key", "location_type"} <= cols:
        return []
    rows = conn.execute(
        "SELECT key, label, parent_id, parent_key FROM game_locations "
        "WHERE is_active = 1 AND location_type = 'sub' ORDER BY key"
    ).fetchall()
    issues: list[dict] = []
    for r in rows:
        by_key = _parent_by_key(conn, r["parent_key"])
        by_id = _parent_by_id(conn, r["parent_id"])
        if by_key and by_id and by_key["id"] == by_id["id"]:
            continue
        if by_key or by_id:
            detail = ("Wiązanie z rodzicem jest niekompletne albo rozjechane "
                      "(`parent_id` != `parent_key`). Naprawa uzupełnia brakującą połowę.")
        else:
            detail = ("Rodzic nie istnieje w aktywnym świecie. Naprawa awansuje "
                      "sierotę na lokację makro — przestaje wskazywać zmarłego rodzica.")
        issues.append(_issue(
            "broken_sublocation_parent", r["key"],
            f"{r['label']} — sub-lokacja z zepsutym rodzicem",
            detail, _SEVERITY_ERROR,
        ))
    return issues


def _parent_by_key(conn: sqlite3.Connection, parent_key: object) -> sqlite3.Row | None:
    key = str(parent_key or "").strip()
    if not key:
        return None
    return conn.execute(
        "SELECT id, key FROM game_locations WHERE key = ? AND is_active = 1", (key,)
    ).fetchone()


def _parent_by_id(conn: sqlite3.Connection, parent_id: object) -> sqlite3.Row | None:
    if parent_id in (None, ""):
        return None
    return conn.execute(
        "SELECT id, key FROM game_locations WHERE id = ? AND is_active = 1", (int(parent_id),)
    ).fetchone()


def _rule_illegal_flag_value(conn: sqlite3.Connection) -> list[dict]:
    """`created_by` / `review_status` spoza legalnego zbioru (fala 3)."""
    cols = _cols(conn, "game_locations")
    issues: list[dict] = []
    for column, legal, fallback in (
        ("created_by", LEGAL_CREATED_BY, "admin_manual"),
        ("review_status", LEGAL_REVIEW_STATUS, "permanent"),
    ):
        if column not in cols:
            continue
        rows = conn.execute(
            f"SELECT key, label, {column} AS val FROM game_locations WHERE is_active = 1 "
            f"ORDER BY key"
        ).fetchall()
        for r in rows:
            if str(r["val"] or "") in legal:
                continue
            issues.append(_issue(
                "illegal_flag_value", f"{r['key']}|{column}",
                f"{r['label']} — `{column}` = „{r['val']}” poza legalnym zbiorem",
                f"Legalne wartości: {', '.join(sorted(legal))}. "
                f"Naprawa ustawia „{fallback}”.",
                _SEVERITY_ERROR,
            ))
    return issues


def _rule_duplicate_label_in_region(conn: sqlite3.Connection) -> list[dict]:
    """Dwie aktywne lokacje o (niemal) tej samej etykiecie w jednej krainie."""
    cols = _cols(conn, "game_locations")
    if "region" not in cols:
        return []
    rows = conn.execute(
        "SELECT key, label, region FROM game_locations WHERE is_active = 1 ORDER BY region, key"
    ).fetchall()
    by_region: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        by_region.setdefault(str(r["region"] or ""), []).append(r)

    #: Kanoniczne pinezki — dwie karty stojące na RÓŻNYCH heksach to z definicji
    #: dwa różne miejsca, choćby nazywały się prawie tak samo (#1527: cztery
    #: hołdy rodowe „X — Wyssany Hołd", każdy na własnym heksie).
    on_map: dict[str, tuple[int, int]] = {}
    if _table_exists(conn, "world_hexes"):
        for h in conn.execute(
            "SELECT q, r, location_key FROM world_hexes "
            "WHERE map_level = 0 AND is_active = 1 "
            "AND location_key IS NOT NULL AND location_key != ''"
        ).fetchall():
            on_map[h["location_key"]] = (int(h["q"]), int(h["r"]))

    issues: list[dict] = []
    for region, items in by_region.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                pin_a, pin_b = on_map.get(a["key"]), on_map.get(b["key"])
                if pin_a and pin_b and pin_a != pin_b:
                    continue   # dwa osadzone miejsca = dwa miejsca, nie kopia
                if not _labels_look_like_the_same_place(a["label"], b["label"]):
                    continue
                ratio = SequenceMatcher(
                    None, _norm_label(a["label"]), _norm_label(b["label"])
                ).ratio()
                if ratio < DUPLICATE_SIMILARITY_THRESHOLD:
                    continue
                issues.append(_issue(
                    "duplicate_label_in_region", f"{region}|{a['key']}|{b['key']}",
                    f"„{a['label']}” ≈ „{b['label']}” w krainie „{region}”",
                    f"Podobieństwo etykiet {ratio:.2f} ≥ {DUPLICATE_SIMILARITY_THRESHOLD}. "
                    f"Klucze: {a['key']} / {b['key']}. "
                    + ("Obie karty są poza mapą świata. "
                       if not pin_a and not pin_b else
                       f"Na mapie stoi: {a['key'] if pin_a else b['key']} "
                       f"(heks {(pin_a or pin_b)[0]},{(pin_a or pin_b)[1]}). ")
                    + "Którą kopię zostawić — decyzja człowieka.",
                    _SEVERITY_WARNING,
                ))
    return issues


#: Separatory członu wyróżniającego w nazwach seryjnych („Frosthold — Wyssany Hołd").
_LABEL_SEPARATORS = ("—", "–", " - ", ":")


def _labels_look_like_the_same_place(label_a: str, label_b: str) -> bool:
    """Czy to ta sama nazwa, czy dwie pozycje jednej SERII?

    Kanon lubi nazwy seryjne: „Frosthold — Wyssany Hołd", „Grauhold — Wyssany
    Hołd". Wspólny ogon ciągnie podobieństwo całych etykiet powyżej progu, więc
    przy wspólnym ogonie porównujemy wyłącznie CZŁON WYRÓŻNIAJĄCY.
    """
    a, b = _norm_label(label_a), _norm_label(label_b)
    if a == b:
        return True
    for sep in _LABEL_SEPARATORS:
        if sep in a and sep in b:
            head_a, tail_a = (p.strip() for p in a.split(sep, 1))
            head_b, tail_b = (p.strip() for p in b.split(sep, 1))
            if tail_a == tail_b:   # ten sam ogon = seria; decyduje głowa
                return SequenceMatcher(None, head_a, head_b).ratio() >= DUPLICATE_SIMILARITY_THRESHOLD
    return True


_RULES = (
    _rule_orphan_npc_assignment,
    _rule_hex_points_to_missing_location,
    _rule_pin_not_backed_by_canon,
    _rule_broken_sublocation_parent,
    _rule_illegal_flag_value,
    _rule_service_without_host,
    _rule_duplicate_label_in_region,
)


# ─── API publiczne ───────────────────────────────────────────────────────────

def run_world_lint(conn: sqlite3.Connection, *, limit: int = LINT_LIST_LIMIT) -> dict:
    """Uruchom wszystkie reguly i zwroc raport dla panelu.

    Returns:
        {"issues": [...], "counts": {rule: n}, "total": int,
         "truncated": bool, "fixable": int}
    """
    found: list[dict] = []
    for rule in _RULES:
        try:
            found.extend(rule(conn))
        except sqlite3.Error as exc:  # brak tabeli/kolumny nie moze zgasic calego lintu
            logger.warning("world_lint_rule_failed", rule=rule.__name__, error=str(exc))

    counts: dict[str, int] = {}
    for issue in found:
        counts[issue["rule"]] = counts.get(issue["rule"], 0) + 1

    #: ile w KAZDEJ grupie da sie naprawic jednym klikiem — panel rysuje z tego
    #: guzik „Napraw wszystkie (N)" nad grupa (#1527, naprawa masowa per regula).
    fixable_by_rule: dict[str, int] = {}
    for issue in found:
        if issue["fixable"]:
            fixable_by_rule[issue["rule"]] = fixable_by_rule.get(issue["rule"], 0) + 1

    return {
        "issues": found[:limit],
        "counts": counts,
        "fixable_by_rule": fixable_by_rule,
        "total": len(found),
        "truncated": len(found) > limit,
        "fixable": sum(1 for i in found if i["fixable"]),
    }


def lint_issue_count(conn: sqlite3.Connection) -> int:
    """Sama liczba rozjazdow — do badge'a w nawigacji."""
    return run_world_lint(conn)["total"]


def fix_world_lint_issue(conn: sqlite3.Connection, issue_id: str) -> dict:
    """Napraw JEDEN rozjazd wskazany identyfikatorem `rule:target`.

    Zwraca `{"fixed": bool, "rule": str, "target": str, "message": str}`.
    Kazda udana naprawa zostawia wpis w historii (`source='manual_fix'`).
    """
    rule, _, target = str(issue_id or "").partition(":")
    handler = _FIXERS.get(rule)
    if handler is None:
        return {
            "fixed": False, "rule": rule, "target": target,
            "message": (
                "Ta reguła wymaga decyzji treściowej — panel jej nie zgaduje."
                if rule in _UNFIXABLE else f"Nieznana reguła: {rule!r}"
            ),
        }
    try:
        ok, message = handler(conn, target)
    except sqlite3.Error as exc:
        logger.warning("world_lint_fix_failed", rule=rule, target=target, error=str(exc))
        return {"fixed": False, "rule": rule, "target": target, "message": f"Błąd bazy: {exc}"}

    if ok:
        conn.commit()
        record_repair(conn, "manual_fix", rule, target, message)
        logger.info("world_lint_fix_applied", rule=rule, target=target)
    return {"fixed": ok, "rule": rule, "target": target, "message": message}


def fix_world_lint_rule(conn: sqlite3.Connection, rule: str) -> dict:
    """Napraw CALA grupe rozjazdow jednej reguly (guzik „Napraw wszystkie").

    Swiadomie NIE ma odpowiednika „napraw wszystko" dla calego lintu — globalny
    guzik odtworzylby ciche zamiatanie, tylko z jednym klikiem zamiast crona.
    Naprawa masowa dziala wylacznie w obrebie JEDNEJ reguly, ktora czlowiek
    swiadomie wskazal, i wylacznie dla regul deterministycznych: dosiew
    gospodarza i wybor duplikatu do zostawienia nadal nalezy do czlowieka.

    Kazda naprawa zostawia WLASNY wpis w kronice — grupa nie chowa sie za
    jednym zbiorczym „naprawiono 14 rzeczy".

    Returns:
        {"rule", "fixed": int, "failed": int, "refused": bool, "messages": [...]}
    """
    if rule not in _FIXERS:
        return {
            "rule": rule, "fixed": 0, "failed": 0, "refused": True,
            "messages": [
                "Ta reguła wymaga decyzji treściowej — nie ma dla niej naprawy masowej."
                if rule in _UNFIXABLE else f"Nieznana reguła: {rule!r}"
            ],
        }

    targets = [i["id"] for i in run_world_lint(conn, limit=10_000)["issues"] if i["rule"] == rule]
    fixed = failed = 0
    messages: list[str] = []
    for issue_id in targets:
        result = fix_world_lint_issue(conn, issue_id)
        if result["fixed"]:
            fixed += 1
        else:
            failed += 1
            messages.append(result["message"])

    logger.info("world_lint_bulk_fix", rule=rule, fixed=fixed, failed=failed)
    return {"rule": rule, "fixed": fixed, "failed": failed, "refused": False, "messages": messages}


# ─── naprawa WSPOMAGANA (reguły treściowe — decyzja człowieka, ale bez ────────
#     skakania po zakładkach)

def lint_flags(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Mapa `klucz lokacji → jej problemy` — znacznik 🩺 w innych zakładkach.

    Dzięki temu admin pracujący w Lokacjach / Floating / Do zatwierdzenia widzi
    od razu, która karta jest chora, zamiast przełączać się do Kontroli świata
    i z powrotem.
    """
    flags: dict[str, list[dict]] = {}
    for issue in run_world_lint(conn, limit=10_000)["issues"]:
        key = _location_key_of(issue)
        if not key:
            continue
        flags.setdefault(key, []).append({
            "rule": issue["rule"],
            "label": issue["label"],
            "severity": issue["severity"],
            "fixable": issue["fixable"],
        })
    return flags


def _location_key_of(issue: dict) -> str:
    """Której lokacji dotyczy rozjazd (o ile dotyczy pojedynczej karty)."""
    rule, target = issue["rule"], issue["target"]
    if rule in ("service_without_host", "pin_not_backed_by_canon", "broken_sublocation_parent"):
        return target
    if rule in ("orphan_npc_assignment", "illegal_flag_value"):
        return target.split("|", 1)[0]
    return ""  # heks i duplikat (para) nie wskazują jednej karty


def host_candidates(conn: sqlite3.Connection, location_key: str) -> list[dict]:
    """NPC, których można obsadzić w tej lokacji — tylko ci, którzy NIGDZIE nie stoją.

    Świadomie nie proponujemy NPC już obsadzonych: „naprawa" polegająca na
    przeniesieniu gospodarza z innej karczmy tylko przesuwa dziurę.
    """
    if not _table_exists(conn, "npcs"):
        return []
    npc_type_col = "n.npc_type" if "npc_type" in _cols(conn, "npcs") else "'' AS npc_type"
    rows = conn.execute(
        f"SELECT n.key, n.label, {npc_type_col} FROM npcs n "
        "WHERE n.is_active = 1 AND NOT EXISTS ("
        "  SELECT 1 FROM location_npc_assignments a "
        "  WHERE a.npc_key = n.key AND COALESCE(a.is_active, 1) = 1) "
        "ORDER BY n.label"
    ).fetchall()
    return [dict(r) for r in rows]


def _location_row(conn: sqlite3.Connection, key: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM game_locations WHERE key = ? AND is_active = 1", (key,)
    ).fetchone()


def _resync_npc_keys(conn: sqlite3.Connection, location_key: str) -> None:
    """Odśwież lustro `game_locations.npc_keys` (kanon = tabela przypisań, #1524)."""
    import json as _json
    keys = [r[0] for r in conn.execute(
        "SELECT npc_key FROM location_npc_assignments "
        "WHERE location_key = ? AND COALESCE(is_active, 1) = 1 ORDER BY npc_key",
        (location_key,),
    ).fetchall()]
    conn.execute(
        "UPDATE game_locations SET npc_keys = ? WHERE key = ?",
        (_json.dumps(keys, ensure_ascii=False), location_key),
    )


def assign_host(conn: sqlite3.Connection, location_key: str, npc_key: str) -> dict:
    """Obsadź istniejącego NPC w lokacji (wybór człowieka z listy kandydatów)."""
    if _location_row(conn, location_key) is None:
        return {"ok": False, "message": f"Nie ma aktywnej lokacji „{location_key}”."}
    npc = conn.execute(
        "SELECT key, label FROM npcs WHERE key = ? AND is_active = 1", (npc_key,)
    ).fetchone()
    if npc is None:
        return {"ok": False, "message": f"Nie ma aktywnego NPC „{npc_key}”."}

    conn.execute(
        "INSERT INTO location_npc_assignments (location_key, npc_key, assignment_type, is_active) "
        "VALUES (?,?,'resident',1) "
        "ON CONFLICT(location_key, npc_key) DO UPDATE SET is_active = 1",
        (location_key, npc_key),
    )
    _resync_npc_keys(conn, location_key)
    conn.commit()
    message = f"{npc['label']} objął(-ęła) posadę w „{location_key}”."
    record_repair(conn, "manual_fix", "service_without_host", location_key, message)
    logger.info("world_lint_host_assigned", location=location_key, npc=npc_key)
    return {"ok": True, "npc_key": npc_key, "message": message}


def _slugify(text: str) -> str:
    trans = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    base = str(text or "").translate(trans).lower()
    out = "".join(ch if ch.isalnum() else "_" for ch in base)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def create_host(
    conn: sqlite3.Connection,
    location_key: str,
    *,
    label: str,
    npc_type: str = "neutral",
    description: str = "",
) -> dict:
    """Utwórz nowego NPC i od razu obsadź go w lokacji (formularz z panelu)."""
    label = str(label or "").strip()
    if not label:
        return {"ok": False, "message": "Gospodarz musi mieć imię."}
    if _location_row(conn, location_key) is None:
        return {"ok": False, "message": f"Nie ma aktywnej lokacji „{location_key}”."}
    if npc_type not in ("neutral", "merchant", "quest_giver", "ally"):
        npc_type = "neutral"

    base = _slugify(label) or "gospodarz"
    key, n = base, 1
    while conn.execute("SELECT 1 FROM npcs WHERE key = ?", (key,)).fetchone():
        n += 1
        key = f"{base}_{n}"

    cols = _cols(conn, "npcs")
    fields = {"key": key, "label": label}
    if "npc_type" in cols:
        fields["npc_type"] = npc_type
    if "description" in cols:
        fields["description"] = description
    if "review_status" in cols:
        fields["review_status"] = "permanent"
    placeholders = ",".join("?" * len(fields))
    conn.execute(
        f"INSERT INTO npcs ({','.join(fields)}) VALUES ({placeholders})",
        list(fields.values()),
    )
    conn.commit()

    assigned = assign_host(conn, location_key, key)
    if not assigned["ok"]:
        return assigned
    return {
        "ok": True, "npc_key": key,
        "message": f"{label} utworzony(-a) i obsadzony(-a) w „{location_key}”.",
    }


def host_suggestion_context(conn: sqlite3.Connection, location_key: str) -> dict:
    """Fakty o miejscu dla podpowiedzi AI — deterministyczne, bez wołania modelu.

    Sam prompt buduje router; tutaj zbieramy to, co model MUSI wiedzieć, żeby
    karczmarz z Kresów nie brzmiał jak karczmarz z Siwych Grań.
    """
    row = _location_row(conn, location_key)
    if row is None:
        return {}
    subtype = (row["location_subtype"] if "location_subtype" in row.keys() else None) or ""
    parent_label = ""
    if "parent_key" in row.keys() and row["parent_key"]:
        parent = conn.execute(
            "SELECT label FROM game_locations WHERE key = ? AND is_active = 1",
            (row["parent_key"],),
        ).fetchone()
        parent_label = parent["label"] if parent else ""
    return {
        "key": location_key,
        "label": row["label"],
        "region": (row["region"] if "region" in row.keys() else None) or "",
        "subtype": subtype,
        "role_pl": SERVICE_SUBTYPES.get(subtype, subtype),
        "parent_label": parent_label,
        "description": (row["description"] if "description" in row.keys() else "") or "",
    }


def duplicate_compare(conn: sqlite3.Connection, key_a: str, key_b: str) -> dict:
    """Dwie karty obok siebie + fakty, na których człowiek oprze decyzję.

    Nie oceniamy, która jest „lepsza" — pokazujemy, co każda ze sobą niesie
    (obsada, wnętrza, pinezka na mapie, źródło, status recenzji).
    """
    return {"a": _duplicate_card(conn, key_a), "b": _duplicate_card(conn, key_b)}


def _duplicate_card(conn: sqlite3.Connection, key: str) -> dict | None:
    row = _location_row(conn, key)
    if row is None:
        return None
    cols = row.keys()
    npc_count = int(conn.execute(
        "SELECT COUNT(*) FROM location_npc_assignments "
        "WHERE location_key = ? AND COALESCE(is_active, 1) = 1", (key,),
    ).fetchone()[0] or 0) if _table_exists(conn, "location_npc_assignments") else 0
    children = int(conn.execute(
        "SELECT COUNT(*) FROM game_locations WHERE parent_key = ? AND is_active = 1", (key,),
    ).fetchone()[0] or 0) if "parent_key" in cols else 0
    hexrow = conn.execute(
        "SELECT q, r FROM world_hexes WHERE map_level = 0 AND is_active = 1 AND location_key = ?",
        (key,),
    ).fetchone() if _table_exists(conn, "world_hexes") else None
    def _get(name: str, default=None):
        return row[name] if name in cols else default
    return {
        "key": key,
        "label": row["label"],
        "location_type": _get("location_type", ""),
        "location_subtype": _get("location_subtype", ""),
        "region": _get("region", ""),
        "created_by": _get("created_by", ""),
        "review_status": _get("review_status", ""),
        "description": (_get("description", "") or "")[:300],
        "npc_count": npc_count,
        "children_count": children,
        "on_map": {"q": hexrow["q"], "r": hexrow["r"]} if hexrow else None,
    }


def resolve_duplicate(
    conn: sqlite3.Connection, *, keep: str, drop: str, move_assets: bool = True
) -> dict:
    """Rozstrzygnij duplikat: zostaw jedną kartę, wygaś drugą.

    Człowiek wybiera, którą zostawić — my tylko wykonujemy i pilnujemy, żeby przy
    okazji nie zgubić obsady ani wnętrz. Karty stojącej na mapie NIE kasujemy:
    kanon heksa jest własnością Piotra i wymaga świadomego ruchu na Mapie.
    """
    if keep == drop:
        return {"ok": False, "reason": "same_card",
                "message": "Do rozstrzygnięcia potrzebne są dwie różne karty."}
    keep_row, drop_row = _location_row(conn, keep), _location_row(conn, drop)
    if keep_row is None or drop_row is None:
        return {"ok": False, "reason": "missing",
                "message": "Jedna z kart już nie istnieje — odśwież listę."}

    on_map = conn.execute(
        "SELECT q, r FROM world_hexes WHERE map_level = 0 AND is_active = 1 AND location_key = ?",
        (drop,),
    ).fetchone()
    if on_map is not None:
        return {
            "ok": False, "reason": "on_map",
            "message": (f"„{drop_row['label']}” stoi na mapie świata (heks "
                        f"{on_map['q']},{on_map['r']}). Najpierw zdejmij ją z heksa "
                        f"w zakładce Mapa albo zostaw tę kartę zamiast drugiej."),
        }

    moved_npcs = moved_children = 0
    if move_assets:
        for row in conn.execute(
            "SELECT npc_key FROM location_npc_assignments "
            "WHERE location_key = ? AND COALESCE(is_active, 1) = 1", (drop,),
        ).fetchall():
            conn.execute(
                "INSERT INTO location_npc_assignments (location_key, npc_key, assignment_type, is_active) "
                "VALUES (?,?,'resident',1) "
                "ON CONFLICT(location_key, npc_key) DO UPDATE SET is_active = 1",
                (keep, row["npc_key"]),
            )
            moved_npcs += 1
        conn.execute(
            "UPDATE location_npc_assignments SET is_active = 0 WHERE location_key = ?", (drop,)
        )
        moved_children = conn.execute(
            "UPDATE game_locations SET parent_key = ?, parent_id = ? "
            "WHERE parent_key = ? AND is_active = 1",
            (keep, keep_row["id"], drop),
        ).rowcount or 0
        _resync_npc_keys(conn, keep)
        _resync_npc_keys(conn, drop)

    conn.execute("UPDATE game_locations SET is_active = 0 WHERE key = ?", (drop,))
    conn.commit()

    message = (f"„{drop_row['label']}” ({drop}) wygaszona; została „{keep_row['label']}” ({keep})."
               + (f" Przeniesiono: {moved_npcs} NPC, {moved_children} wnętrz." if move_assets else ""))
    record_repair(conn, "manual_fix", "duplicate_label_in_region", f"{keep}|{drop}", message)
    logger.info("world_lint_duplicate_resolved", keep=keep, drop=drop,
                moved_npcs=moved_npcs, moved_children=moved_children)
    return {"ok": True, "message": message,
            "moved_npcs": moved_npcs, "moved_children": moved_children}


# ─── naprawy ─────────────────────────────────────────────────────────────────

def _fix_orphan_npc_assignment(conn: sqlite3.Connection, target: str) -> tuple[bool, str]:
    location_key, _, npc_key = target.partition("|")
    cur = conn.execute(
        "UPDATE location_npc_assignments SET is_active = 0 "
        "WHERE location_key = ? AND npc_key = ? AND COALESCE(is_active, 1) = 1",
        (location_key, npc_key),
    )
    if not cur.rowcount:
        return False, "Nie znaleziono aktywnego przypisania — mogło już zniknąć."
    return True, f"Przypisanie {npc_key} → {location_key} dezaktywowane."


def _fix_hex_points_to_missing_location(conn: sqlite3.Connection, target: str) -> tuple[bool, str]:
    q_raw, _, r_raw = target.partition(",")
    try:
        q, r = int(q_raw), int(r_raw)
    except ValueError:
        return False, f"Nieczytelne współrzędne heksa: {target!r}"
    cur = conn.execute(
        "UPDATE world_hexes SET location_key = NULL "
        "WHERE q = ? AND r = ? AND map_level = 0 AND is_active = 1",
        (q, r),
    )
    if not cur.rowcount:
        return False, f"Heks ({q},{r}) już nie trzyma wskazania."
    return True, f"Heks ({q},{r}) zwolniony — wskazanie na nieistniejącą lokację skasowane."


def _fix_pin_not_backed_by_canon(conn: sqlite3.Connection, target: str) -> tuple[bool, str]:
    cur = conn.execute(
        "UPDATE game_locations SET world_hex_q = NULL, world_hex_r = NULL "
        "WHERE key = ? AND is_active = 1 AND world_hex_q IS NOT NULL",
        (target,),
    )
    if not cur.rowcount:
        return False, f"Lokacja {target} nie ma już pinu."
    return True, f"Pin lokacji {target} odpięty — kanon heksów go nie potwierdzał."


def _fix_broken_sublocation_parent(conn: sqlite3.Connection, target: str) -> tuple[bool, str]:
    row = conn.execute(
        "SELECT key, parent_id, parent_key FROM game_locations WHERE key = ? AND is_active = 1",
        (target,),
    ).fetchone()
    if row is None:
        return False, f"Nie ma aktywnej lokacji {target}."
    by_key = _parent_by_key(conn, row["parent_key"])
    by_id = _parent_by_id(conn, row["parent_id"])
    parent = by_key or by_id
    if parent is not None:
        conn.execute(
            "UPDATE game_locations SET parent_id = ?, parent_key = ? WHERE key = ?",
            (parent["id"], parent["key"], target),
        )
        return True, f"Wiązanie uzupełnione: rodzic = {parent['key']} (id={parent['id']})."
    conn.execute(
        "UPDATE game_locations SET parent_id = NULL, parent_key = NULL, location_type = 'macro' "
        "WHERE key = ?",
        (target,),
    )
    return True, f"Sierota {target} awansowana na lokację makro — rodzic nie istniał."


def _fix_illegal_flag_value(conn: sqlite3.Connection, target: str) -> tuple[bool, str]:
    key, _, column = target.partition("|")
    fallback = {"created_by": "admin_manual", "review_status": "permanent"}.get(column)
    if fallback is None:
        return False, f"Nieznana kolumna flagi: {column!r}"
    cur = conn.execute(
        f"UPDATE game_locations SET {column} = ? WHERE key = ? AND is_active = 1",
        (fallback, key),
    )
    if not cur.rowcount:
        return False, f"Nie ma aktywnej lokacji {key}."
    return True, f"{key}.{column} ustawione na „{fallback}”."


_FIXERS = {
    "orphan_npc_assignment": _fix_orphan_npc_assignment,
    "hex_points_to_missing_location": _fix_hex_points_to_missing_location,
    "pin_not_backed_by_canon": _fix_pin_not_backed_by_canon,
    "broken_sublocation_parent": _fix_broken_sublocation_parent,
    "illegal_flag_value": _fix_illegal_flag_value,
}
