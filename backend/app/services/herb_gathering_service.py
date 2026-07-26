"""#1337 BL-C2 — zbieranie ziół w podróży.

Akcja terenowa zasilająca rzemiosło (#1199). Bohater deklaruje zbieranie ziół
na hexie; silnik wystawia test **WIS** (umiejętność ``survival`` / Przetrwanie)
z DC wg terenu hexa, a po rzucie przyznaje 1–3 zioła wg marginesu sukcesu:

  • Nat 20 → dodatkowo rzadkie zioło,
  • Nat 1  → trująca pomyłka (1 obrażenie),
  • zwykła porażka → nic.

Cooldown 1×/hex/dzień gry (``session_flags['herb_cooldowns']``) — kolejna próba
tego samego dnia zwraca „to miejsce już ogołocone" bez testu.

Zioła = komponenty rzemieślnicze (``game_config_items.component_type='herb'``)
z BL-B3 — zasilają przepisy z BL-C1.

Detekcja intencji jest deterministyczna (słowa kluczowe, nie prompt LLM) —
konwencja ``trigger_keywords``. Każde wejście jest tolerancyjne na błędy DB:
awaria tutaj nie może wywrócić tury.
"""

from __future__ import annotations

import json
import random
import sqlite3

from app.core.logging import get_logger

logger = get_logger(__name__)

# Test WIS — Przetrwanie/foraging.
GATHER_SKILL_KEY = "survival"

# ── Numbers Policy — wartości startowe (Sandbox-tunable w przyszłości) ──────────
# DC wg terenu hexa (world_hexes.hex_type). Domyślnie Medium 12.
TERRAIN_DC = {
    # Easy 8 — bujna/wilgotna roślinność.
    "forest": 8, "swamp": 8, "river": 8, "lake": 8,
    # Hard 16 — góry i pustkowia.
    "mountain": 16, "przelecz": 16, "grania": 16, "snow": 16,
    "sea": 16, "ruins": 16,
    # SG-1 #1481 — lód i siarka to jałowizna; bór iglasty uboższy w runo niż las liściasty.
    "lodowiec": 16, "siarka": 16, "las_iglasty": 12,
    # CB-1 #Czarnobór — martwy bór skąpy w runo (Medium 12); trzęsawisko wilgotne
    # i bujne jak bagno (Easy 8). Step nie wpisany — DEFAULT_DC 12 (Medium, jak równiny).
    "czarny_las": 12, "trzesawisko": 8,
    # MP-1 #1495 — Martwe Pustkowia: jałowizna. Sól i popiół nie rodzą runa (Hard 16).
    "sol": 16, "martwa_ziemia": 16,
}
DEFAULT_DC = 12  # Medium — równiny/wzgórza/wrzosowiska/drogi itd.

MAX_HERBS = 3          # sufit sztuk na jedną udaną próbę
MARGIN_PER_HERB = 5    # +1 zioło za każde pełne 5 pkt marginesu ponad DC
NAT1_DAMAGE = 1        # trująca pomyłka

COOLDOWN_MSG = "To miejsce jest już ogołocone z ziół — wróć innego dnia."

# Rdzenie słów-kluczy (na tekście bez znaków diakrytycznych, lowercase).
_VERB_STEMS = ("zbier", "zryw", "nazbier", "uzbier", "poszuk", "szuk", "zna",
               "wykop", "pozbier", "zdzier")
# #1394: obiekt = ROŚLINA, nigdy OSOBA. Rdzeń "ziel"/"zielarz" łapał „zielarkę"
# („gdzie znajdę zielarkę?" + rdzeń czasownika "zna" w „znajdę" → fałszywy test
# zbierania zamiast odpowiedzi narratora). "ziele"/"zielsk" nie matchują
# "zielark*"/"zielarz*" (piąty znak), więc pytania o NPC idą do LLM.
_OBJ_STEMS = ("ziol", "ziele", "zielsk", "roslin", "grzyb")
# Twarda blokada: tekst wspomina zielarza/zielarkę (OSOBĘ) → interakcja z NPC
# (szukanie, zakup, rozmowa), nie zbieranie w polu — nawet gdy pada też słowo
# zielne („poszukam zielarki, może ma zioła"). Narrator/modal obsłuży.
_PERSON_STEMS = ("zielark", "zielarz")

_PL_MAP = str.maketrans("ąćęłńóśźż", "acelnoszz")


def _norm(text: str) -> str:
    return (text or "").translate(_PL_MAP).lower()


def is_gather_intent(text: str) -> bool:
    """Deterministyczne wykrycie intencji „zbieram zioła" (dane, nie prompt).

    Wymaga zarówno czasownika zbierania, jak i obiektu zielnego, by uniknąć
    fałszywych trafień typu „zioła leżą w mojej torbie".
    """
    n = _norm(text)
    if not n:
        return False
    if any(p in n for p in _PERSON_STEMS):
        return False
    if not any(v in n for v in _VERB_STEMS):
        return False
    return any(o in n for o in _OBJ_STEMS)


def _conn_terrain(conn: sqlite3.Connection, q, r) -> str | None:
    """hex_type dla hexa overworld (map_level=0), fallback dowolny poziom."""
    if q is None or r is None:
        return None
    try:
        row = conn.execute(
            "SELECT hex_type FROM world_hexes "
            "WHERE q=? AND r=? ORDER BY (map_level=0) DESC LIMIT 1",
            (int(q), int(r)),
        ).fetchone()
    except Exception as e:
        logger.warning("herb_terrain_lookup_error", error=str(e))
        return None
    if not row:
        return None
    try:
        return str(row["hex_type"] or "").strip().lower() or None
    except Exception:
        return str(row[0] or "").strip().lower() or None


def _game_day(session_flags: dict) -> int:
    return int(session_flags.get("ingame_hours", 0) or 0) // 24


def prepare_gather(conn: sqlite3.Connection, campaign_id: int) -> dict:
    """Zbierz plan testu zbierania na aktualnym hexie.

    Zwraca dict:
      • ``cooldown_hit``=True + ``msg``   — hex ogołocony dziś (bez testu),
      • inaczej ``dc``/``terrain``/``hex_key``/``game_day`` do wystawienia testu.
    """
    row = conn.execute(
        "SELECT session_flags FROM game_sessions WHERE campaign_id=? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    sf = {}
    if row:
        try:
            sf = json.loads(row["session_flags"] or "{}")
        except Exception:
            sf = {}
    ch = sf.get("current_hex") or {}
    q, r = ch.get("q"), ch.get("r")
    terrain = _conn_terrain(conn, q, r)
    dc = TERRAIN_DC.get(terrain or "", DEFAULT_DC)
    game_day = _game_day(sf)
    hex_key = f"{q},{r}" if q is not None and r is not None else "unknown"

    cds = sf.get("herb_cooldowns") or {}
    if cds.get(hex_key) == game_day:
        return {"cooldown_hit": True, "msg": COOLDOWN_MSG,
                "hex_key": hex_key, "game_day": game_day, "terrain": terrain}

    return {"cooldown_hit": False, "dc": int(dc), "terrain": terrain,
            "hex_key": hex_key, "game_day": game_day}


def _herb_pool(conn: sqlite3.Connection) -> tuple[list[str], list[str]]:
    """(common, rare) klucze ziół wg rzadkości.

    Tylko zioła FAKTYCZNIE nadające się do przyznania — komponent zielny
    (``game_config_items.component_type='herb'``, aktywny) obecny w zunifikowanym
    katalogu ``game_items`` (aktywny), bo tamtędy waliduje ``grant_loot_to_character``.
    Nowe zioła aktywowane w BL-B3 automatycznie poszerzają pulę.
    """
    common, rare = [], []
    try:
        rows = conn.execute(
            "SELECT gci.key AS key, COALESCE(gci.rarity,1) AS rarity "
            "FROM game_config_items gci "
            "JOIN game_items gi ON gi.key = gci.key AND gi.is_active = 1 "
            "WHERE gci.component_type='herb' AND COALESCE(gci.is_active,1)=1 "
            "ORDER BY rarity DESC, gci.key"
        ).fetchall()
    except Exception as e:
        logger.warning("herb_pool_lookup_error", error=str(e))
        rows = []
    for row in rows:
        key = str(row["key"])
        if int(row["rarity"] or 1) >= 2:
            rare.append(key)
        else:
            common.append(key)
    return common, rare


def _herbs_for_margin(margin: int) -> int:
    return max(1, min(MAX_HERBS, 1 + max(0, margin) // MARGIN_PER_HERB))


def resolve_gather(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    pending: dict,
    result: dict,
    session_flags: dict,
) -> dict:
    """Rozstrzygnij zbieranie po rzucie: przyznaj zioła / obrażenie, ustaw cooldown.

    Mutuje ``session_flags`` (cooldown) — zapis do DB po stronie wołającego.
    Zwraca podsumowanie do narracji i odpowiedzi API.
    """
    hex_key = str(pending.get("hex_key") or "unknown")
    game_day = int(pending.get("game_day") or 0)

    # Cooldown: udana LUB nieudana próba ogołaca hex na resztę dnia gry.
    cds = session_flags.get("herb_cooldowns")
    if not isinstance(cds, dict):
        cds = {}
    cds[hex_key] = game_day
    session_flags["herb_cooldowns"] = cds

    summary: dict = {"herbs": [], "rare": None, "damage": 0, "outcome": "fail"}

    nat1 = bool(result.get("nat1"))
    nat20 = bool(result.get("nat20"))
    success = bool(result.get("success"))
    try:
        margin = int(result.get("margin", 0) or 0)
    except (TypeError, ValueError):
        margin = 0

    if nat1:
        # Trująca pomyłka — 1 obrażenie, brak ziół.
        summary["outcome"] = "nat1"
        summary["damage"] = _apply_poison_damage(conn, character_id, campaign_id)
        return summary

    if not success:
        summary["outcome"] = "fail"
        return summary

    common, rare = _herb_pool(conn)
    grant: list[dict] = []

    if common:
        count = _herbs_for_margin(margin)
        picks: dict[str, int] = {}
        for _ in range(count):
            k = random.choice(common)
            picks[k] = picks.get(k, 0) + 1
        for k, qty in picks.items():
            grant.append({"item_key": k, "quantity": qty})

    # Nat 20 → dodatkowo rzadkie zioło (fallback: dorodny okaz z puli zwykłej).
    if nat20:
        rare_key = random.choice(rare) if rare else (random.choice(common) if common else None)
        if rare_key:
            grant.append({"item_key": rare_key, "quantity": 1})
            summary["rare"] = rare_key
        summary["outcome"] = "nat20"
    else:
        summary["outcome"] = "success"

    if grant:
        try:
            from app.services.loot_service import grant_loot_to_character
            granted = grant_loot_to_character(
                int(character_id), grant, source="herb_gather"
            )
            summary["herbs"] = granted
        except Exception as e:
            logger.warning("herb_grant_error", error=str(e))

    return summary


def _apply_poison_damage(conn: sqlite3.Connection, character_id: int, campaign_id: int) -> int:
    """Nat 1 — 1 obrażenie od trującego zioła. Zwraca zadane obrażenie."""
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id=?", (int(character_id),)
        ).fetchone()
        if not row:
            return 0
        sheet = json.loads(row["sheet_json"] or "{}")
        before = int(sheet.get("current_hp", 0) or 0)
        after = max(0, before - NAT1_DAMAGE)
        sheet["current_hp"] = after
        conn.execute(
            "UPDATE characters SET sheet_json=? WHERE id=?",
            (json.dumps(sheet, ensure_ascii=False), int(character_id)),
        )
        try:
            from app.services.state_log_service import record_state_change
            record_state_change(
                campaign_id=campaign_id, resource="hp", character_id=int(character_id),
                before_val=before, after_val=after, cause="herb_poison",
                meta={"source": "herb_gathering"},
            )
        except Exception:
            pass
        _dmg = before - after
        # #1379 — dymek o obrażeniach z trującego zioła (dotąd tylko proza).
        if _dmg > 0:
            try:
                from app.services import system_events as _se
                _se.emit("hp_loss", f"−{_dmg} HP — trujące zioło")
            except Exception:
                pass
        return _dmg
    except Exception as e:
        logger.warning("herb_poison_damage_error", error=str(e))
        return 0


def build_narrator_hint(summary: dict) -> str:
    """Fragment kontekstu dla narratora — CO bohater znalazł (bez liczb/kości)."""
    outcome = summary.get("outcome")
    if outcome == "nat1":
        return ("\n[ZIOŁA] Bohater pomylił rośliny i dotknął/zerwał trujący okaz — "
                "opisz ukłucie bólu/podrażnienie i brak użytecznego zbioru.")
    if outcome == "fail":
        return ("\n[ZIOŁA] Poszukiwanie ziół spełzło na niczym — teren okazał się jałowy "
                "albo rośliny bezwartościowe.")
    n = len(summary.get("herbs") or [])
    base = ("\n[ZIOŁA] Bohater nazbierał użytecznych ziół zielarskich (do rzemiosła). "
            "Opisz zbiór ziół/korzeni/kwiatów pasujących do terenu.")
    if summary.get("rare"):
        base += " Wśród nich trafił się rzadki, wyjątkowo dorodny okaz."
    return base
