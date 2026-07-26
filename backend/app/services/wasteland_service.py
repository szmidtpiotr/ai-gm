"""MP-7 (#1494) — smaczki Martwych Pustkowi: kościany kompas + bezwodne hexy.

Źródło prawdy: docs/world/regions/martwe_pustkowia.md §5-6 (ZATWIERDZONE).

  * **Bezwodne hexy** (`sol`, `martwa_ziemia`): pełny (długi) odpoczynek wymaga
    **bukłaka** (consumable). Woda tylko w enklawie (Solny Próg) i Misji Światła —
    tam bukłak zbędny. Bez bukłaka na bezwodnym hexie → odpoczynek CZĘŚCIOWY
    (leczy o połowę mniej HP/many).
  * **Kościany kompas** (item ``kosciany_kompas``): igła z kości Pradawnych drga
    przy pęknięciach — obniża szansę zasadzki nieumarłych (camp encounter) i daje
    bonus percepcji w ruinach.

Ten moduł to CZYTNIK stanu (jak ``salt_service``): NIE buduje nowej mechaniki
odpoczynku ani rzutu — dokłada tylko warunki do istniejących ścieżek
(``rest_service.perform_long_rest`` i percepcja w ``skill_service``).

WARTOŚCI STARTOWE (Numbers Policy): mnożniki i bonusy niżej — wszystko do
strojenia w Sandboksie.
"""

from __future__ import annotations

import json
import sqlite3

import structlog

logger = structlog.get_logger()

# ── konfiguracja (wartości startowe) ─────────────────────────────────────────
#: Bezwodne typy terenu — tu pełny odpoczynek wymaga wody.
WATERLESS_TERRAIN = {"sol", "martwa_ziemia"}
#: Lokacje ze stałym dostępem do wody (enklawa + Misja); tam bukłak zbędny.
#: Sublokacje Solnego Progu (``solny_prog_*``) rozpoznawane po prefiksie.
WATER_SOURCE_LOCATION_KEYS = {"solny_prog", "misja_swiatla"}
WATER_SOURCE_PREFIXES = ("solny_prog",)
#: Klucz bukłaka w katalogu (game_config_items, item_type=misc).
WATERSKIN_KEY = "waterskin"
#: Ile HP/many regeneruje odpoczynek na bezwodnym hexie BEZ bukłaka (część pełni).
WATERLESS_PARTIAL_MULT = 0.5

#: Klucz kościanego kompasu (game_config_items).
BONE_COMPASS_KEY = "kosciany_kompas"
#: Mnożnik szansy zasadzki (camp encounter), gdy niesiesz kompas.
COMPASS_AMBUSH_MULT = 0.5
#: Bonus do percepcji w ruinach z kompasem.
COMPASS_RUINS_PERCEPTION_BONUS = 2
#: Typy terenu liczone jako „ruiny" dla bonusu percepcji.
RUINS_TERRAIN = {"ruins"}
#: Umiejętności objęte bonusem percepcji (lustro _PERCEPTION_SKILLS w skill_service).
PERCEPTION_SKILLS = {"perception", "awareness", "investigation", "spot", "search", "tracking"}


# ── ekwipunek ────────────────────────────────────────────────────────────────

def character_has_item(conn: sqlite3.Connection, character_id: int, key: str) -> bool:
    """Czy bohater ma w plecaku przedmiot ``key`` (item / consumable / weapon, qty > 0)."""
    key = str(key or "").strip()
    if not key:
        return False
    try:
        row = conn.execute(
            """SELECT 1 FROM character_inventory
               WHERE character_id = ?
                 AND (item_key = ? OR consumable_key = ? OR weapon_key = ?)
                 AND COALESCE(quantity, 1) > 0
               LIMIT 1""",
            (int(character_id), key, key, key),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None


def has_bone_compass(conn: sqlite3.Connection, character_id: int) -> bool:
    """Czy bohater niesie kościany kompas."""
    return character_has_item(conn, character_id, BONE_COMPASS_KEY)


def consume_waterskin(conn: sqlite3.Connection, character_id: int) -> bool:
    """Zużyj jeden bukłak (qty−1, usuń przy zerze). Zwraca True, gdy coś zużyto.

    Operuje na przekazanym połączeniu — commit robi wołający (rest_service).
    """
    try:
        row = conn.execute(
            """SELECT id, COALESCE(quantity, 1) AS q FROM character_inventory
               WHERE character_id = ? AND item_key = ? AND COALESCE(quantity, 1) > 0
               ORDER BY id ASC LIMIT 1""",
            (int(character_id), WATERSKIN_KEY),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if not row:
        return False
    inv_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
    qty = int(row["q"] if isinstance(row, sqlite3.Row) else row[1])
    if qty <= 1:
        conn.execute("DELETE FROM character_inventory WHERE id = ?", (inv_id,))
    else:
        conn.execute(
            "UPDATE character_inventory SET quantity = quantity - 1 WHERE id = ?", (inv_id,)
        )
    return True


# ── położenie: teren i lokacja ───────────────────────────────────────────────

def current_hex_terrain(conn: sqlite3.Connection, campaign_id: int) -> str:
    """Typ terenu heksa, na którym stoi drużyna. Brak danych → pusty string."""
    try:
        sess = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (int(campaign_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return ""
    if not sess:
        return ""
    try:
        flags = json.loads((sess["session_flags"] if isinstance(sess, sqlite3.Row) else sess[0]) or "{}")
        hexp = flags.get("current_hex") or {}
        q, r = int(hexp.get("q")), int(hexp.get("r"))
    except (TypeError, ValueError, KeyError):
        return ""
    try:
        hx = conn.execute(
            "SELECT hex_type FROM world_hexes WHERE q = ? AND r = ? AND is_active = 1 LIMIT 1",
            (q, r),
        ).fetchone()
    except sqlite3.OperationalError:
        return ""
    if not hx:
        return ""
    val = hx["hex_type"] if isinstance(hx, sqlite3.Row) else hx[0]
    return str(val or "").strip().lower()


def current_location_key(conn: sqlite3.Connection, campaign_id: int) -> str | None:
    """Klucz aktualnej lokacji drużyny (game_sessions.current_location_id)."""
    try:
        sess = conn.execute(
            "SELECT current_location_id FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (int(campaign_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not sess:
        return None
    loc_id = sess["current_location_id"] if isinstance(sess, sqlite3.Row) else sess[0]
    if not loc_id:
        return None
    try:
        loc = conn.execute(
            "SELECT key FROM game_locations WHERE id = ? LIMIT 1", (int(loc_id),)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not loc:
        return None
    return str((loc["key"] if isinstance(loc, sqlite3.Row) else loc[0]) or "").strip().lower() or None


def is_waterless_terrain(terrain: str | None) -> bool:
    return str(terrain or "").strip().lower() in WATERLESS_TERRAIN


def location_provides_water(loc_key: str | None) -> bool:
    """Czy lokacja ma stały dostęp do wody (enklawa / Misja / sublokacje Solnego Progu)."""
    key = str(loc_key or "").strip().lower()
    if not key:
        return False
    if key in WATER_SOURCE_LOCATION_KEYS:
        return True
    return any(key.startswith(p) for p in WATER_SOURCE_PREFIXES)


# ── stan wody dla odpoczynku ─────────────────────────────────────────────────

def rest_water_status(conn: sqlite3.Connection, character_id: int, campaign_id: int) -> dict:
    """Czy pełny odpoczynek tu wymaga bukłaka i czy bohater go ma.

    ``needs_waterskin`` = stoisz na bezwodnym hexie (sol/martwa_ziemia) i NIE jesteś
    w lokacji z wodą. Enklawa i Misja zawsze mają wodę.
    """
    terrain = current_hex_terrain(conn, campaign_id)
    loc_key = current_location_key(conn, campaign_id)
    needs = is_waterless_terrain(terrain) and not location_provides_water(loc_key)
    return {
        "terrain": terrain,
        "location_key": loc_key,
        "needs_waterskin": bool(needs),
        "has_waterskin": bool(needs) and character_has_item(conn, character_id, WATERSKIN_KEY),
    }


# ── kościany kompas ──────────────────────────────────────────────────────────

def camp_ambush_multiplier(conn: sqlite3.Connection, character_id: int) -> float:
    """Mnożnik szansy zasadzki na obozie: 0.5 z kompasem, 1.0 bez."""
    return COMPASS_AMBUSH_MULT if has_bone_compass(conn, character_id) else 1.0


def ruins_perception_bonus(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
    skill_key: str | None,
) -> int:
    """+2 do percepcji w ruinach, gdy niesiesz kompas (inaczej 0)."""
    if str(skill_key or "").strip().lower() not in PERCEPTION_SKILLS:
        return 0
    if current_hex_terrain(conn, campaign_id) not in RUINS_TERRAIN:
        return 0
    if not has_bone_compass(conn, character_id):
        return 0
    return COMPASS_RUINS_PERCEPTION_BONUS
