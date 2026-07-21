"""#1474 — cechy rasowe elfa leśnego (poza odskokiem, który siedzi w silniku walki).

Trzy atuty, wszystkie zależne od TERENU albo PORY DNIA — elf jest mocny tam, gdzie
jest u siebie, i zwyczajny wszędzie indziej:

  * **Knieja pod stopami** — bonus do skradania / przetrwania / percepcji na heksach
    leśnych i bagiennych.
  * **Zmierzchowy wzrok** — noc i zmierzch nie utrudniają mu patrzenia; kara pory dnia
    do percepcji jest znoszona (lustro „wzroku górnika" krasnoluda, tyle że nad ziemią).
  * **Zniknięcie w kniei** — raz na dobę gwarantowana ucieczka z walki w dzikim terenie
    (bez rzutu przeciwnego DEX).

Wszystkie liczby są WARTOŚCIAMI STARTOWYMI (Numbers Policy #826) — strojne na Sandboxie.
Rasa nigdy nie blokuje contentu; daje bonusy tematyczne (zasada wspólna fali ras #1509).
"""
from __future__ import annotations

import json
import sqlite3

ELF_RACE = "elf"

#: Bonus do rzutu na heksie leśnym/bagiennym (wartość STARTOWA).
ELF_WILD_TERRAIN_BONUS = 2

#: Umiejętności objęte bonusem terenowym.
ELF_WILD_SKILLS = frozenset({
    "stealth", "survival", "perception", "awareness", "tracking", "spot", "search",
})

#: Typy heksów, które elf uznaje za dom. Dopasowanie po podciągu — `hex_type`
#: bywa złożony (`forest_dense`, `swamp_bog`), a dane krain nie są jednolite.
ELF_WILD_HEX_MARKERS = ("forest", "wood", "swamp", "marsh", "bog", "jungle", "grove")

#: Ile razy na dobę gry można zniknąć w kniei.
ELF_VANISH_USES_PER_DAY = 1

#: Klucz w `session_flags`, pod którym trzymamy dobę ostatniego zniknięcia.
VANISH_FLAG = "elf_vanish_day"


def is_elf(race: str | None) -> bool:
    return str(race or "").strip().lower() == ELF_RACE


# ── Teren ────────────────────────────────────────────────────────────────────

def _session_flags(conn: sqlite3.Connection, campaign_id: int) -> dict:
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (int(campaign_id),),
        ).fetchone()
    except sqlite3.Error:
        return {}
    if not row:
        return {}
    raw = row["session_flags"] if isinstance(row, sqlite3.Row) else row[0]
    if not raw:
        return {}
    try:
        flags = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return flags if isinstance(flags, dict) else {}


def current_hex_type(conn: sqlite3.Connection, campaign_id: int) -> str:
    """Typ heksa, na którym stoi drużyna. Brak danych → pusty string (zero bonusu)."""
    ch = (_session_flags(conn, campaign_id) or {}).get("current_hex") or {}
    if not isinstance(ch, dict) or ch.get("q") is None or ch.get("r") is None:
        return ""
    try:
        row = conn.execute(
            "SELECT hex_type FROM world_hexes WHERE q = ? AND r = ? AND map_level = 0 LIMIT 1",
            (int(ch["q"]), int(ch["r"])),
        ).fetchone()
    except (sqlite3.Error, TypeError, ValueError):
        return ""
    if not row:
        return ""
    return str((row["hex_type"] if isinstance(row, sqlite3.Row) else row[0]) or "").strip().lower()


def is_wild_home_terrain(hex_type: str | None) -> bool:
    """Czy ten typ heksa to knieja/bagno — dom leśnego elfa."""
    needle = str(hex_type or "").strip().lower()
    return any(marker in needle for marker in ELF_WILD_HEX_MARKERS)


def wild_terrain_bonus(race: str | None, skill_key: str | None, hex_type: str | None) -> int:
    """Bonus „Knieja pod stopami": +2 do skradania/przetrwania/percepcji w lesie i na bagnie."""
    if not is_elf(race):
        return 0
    if str(skill_key or "").strip().lower() not in ELF_WILD_SKILLS:
        return 0
    if not is_wild_home_terrain(hex_type):
        return 0
    return ELF_WILD_TERRAIN_BONUS


def twilight_sight_offset(race: str | None, skill_key: str | None, night_dc_penalty: int) -> int:
    """Zmierzchowy wzrok: znosi karę pory dnia do percepcji (podbicie DC).

    Zwraca liczbę, o którą należy OBNIŻYĆ DC testu (0 dla nie-elfa i gdy kary nie ma).
    Elf nie widzi lepiej niż w dzień — po prostu noc mu nie przeszkadza.
    """
    if not is_elf(race):
        return 0
    if str(skill_key or "").strip().lower() not in {
        "perception", "awareness", "investigation", "spot", "search",
    }:
        return 0
    return max(0, int(night_dc_penalty or 0))


# ── Zniknięcie w kniei ───────────────────────────────────────────────────────

def _ingame_day(conn: sqlite3.Connection, campaign_id: int) -> int:
    """Numer doby gry (zegar kampanii). Brak zegara → 0, czyli „jedna wspólna doba"."""
    try:
        from app.services.clock_service import get_clock_state
        hours = int(get_clock_state(int(campaign_id), conn=conn).get("ingame_hours", 0) or 0)
    except Exception:
        return 0
    return hours // 24


def vanish_available(
    conn: sqlite3.Connection, campaign_id: int, race: str | None, hex_type: str | None,
) -> bool:
    """Czy „Zniknięcie w kniei" jest teraz dostępne (elf + dziki teren + limit na dobę)."""
    if not is_elf(race) or not is_wild_home_terrain(hex_type):
        return False
    used_day = (_session_flags(conn, campaign_id) or {}).get(VANISH_FLAG)
    if used_day is None:
        return True
    try:
        return int(used_day) != _ingame_day(conn, campaign_id)
    except (TypeError, ValueError):
        return True


def consume_vanish(conn: sqlite3.Connection, campaign_id: int) -> None:
    """Zapisuje zużycie zniknięcia na bieżącą dobę gry (idempotentnie w obrębie doby)."""
    flags = _session_flags(conn, campaign_id)
    flags[VANISH_FLAG] = _ingame_day(conn, campaign_id)
    try:
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (json.dumps(flags, ensure_ascii=False), int(campaign_id)),
        )
        conn.commit()
    except sqlite3.Error:
        pass
