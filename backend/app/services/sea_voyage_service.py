"""WL-4 (#1504) — Rejsy: fast-travel port↔port na Wybrzeżu Łez.

MINIMALNA mechanika: bez systemu statków, bez walki morskiej, bez sterowania łodzią.
Rejs = pojedynczy skok między dwoma portami-lokacjami: koszt złota + czas na zegarze
+ jeden rzut na zdarzenie rejsu (sztorm / rafa / piraci). Ryzyko rośnie nocą.
Mapa Smolnego (przedmiot) obniża ryzyko rafy i odblokowuje trasy skrótowe.

Silniki reużyte:
  • economy_service.change_gold        — opłata za rejs (jedyny chokepoint złota)
  • clock_service.advance_clock        — czas rejsu na zegarze
  • clock_service.get_clock_state      — wykrycie nocy (ryzyko rośnie nocą)
  • location_state_service.set_position — pozycja po zejściu na ląd w porcie docelowym
  • hex_location_link.resolve_location_to_hex — port → hex

Heksy morskie są POZA grafem A* (is_passable=0), więc rejs NIE jedzie przez
resolve_chain_travel — to własny, jednoetapowy skok port→port.

Wszystkie liczby to WARTOŚCI STARTOWE (Numbers Policy) — do strojenia po testach.
"""

from __future__ import annotations

import json
import random
import sqlite3
import structlog

logger = structlog.get_logger()

# ── Przedmiot-hak ────────────────────────────────────────────────────────────
MAPA_SMOLNEGO_KEY = "mapa_smolnego"

# ── Numbers Policy (wartości startowe, Sandbox-tunable) ──────────────────────
# Jeden rzut na rejs: czy w ogóle coś się wydarzy.
VOYAGE_EVENT_CHANCE = 0.35
# Ryzyko rośnie nocą (mnożnik szansy zdarzenia).
VOYAGE_NIGHT_MULT = 1.5
# Wagi typów zdarzeń przy losowaniu, GDY zdarzenie wypadło.
VOYAGE_EVENT_WEIGHTS = {"sztorm": 3, "rafa": 3, "piraci": 2}
# Mapa Smolnego mnoży wagę rafy → obniża ryzyko rafy (nie zeruje).
MAPA_SMOLNEGO_REEF_MULT = 0.25
# Skutki zdarzeń.
STORM_EXTRA_HOURS = 3.0        # sztorm znosi z kursu — dodatkowe godziny na zegarze
STORM_HP_LOSS = "1d4"          # obicia, wychłodzenie
REEF_HP_LOSS = "1d6"           # otarcie o rafę
PIRATE_GOLD_PCT = 0.20         # danina/rozbój — % niesionego złota
PIRATE_GOLD_MIN = 10           # ...ale nie mniej niż tyle (o ile stać)

# ── Trasy rejsów ─────────────────────────────────────────────────────────────
# Dwukierunkowe krawędzie port↔port. `shortcut=True` wymaga Mapy Smolnego.
#   fare_gp — opłata za rejs, hours — czas rejsu na zegarze.
SEA_ROUTES: list[dict] = [
    {
        "key": "czarnogrod_zatoka",
        "a": "czarnogrod_port",
        "b": "zatoka_topielcow",
        "fare_gp": 40,
        "hours": 8.0,
        "shortcut": False,
    },
    {
        "key": "czarnogrod_zatoka_skrot",
        "a": "czarnogrod_port",
        "b": "zatoka_topielcow",
        "fare_gp": 25,
        "hours": 5.0,
        "shortcut": True,   # skrót przez rafy — tylko z Mapą Smolnego
    },
]

# TODO WL-4b: Port Rzeczny Vilnogradu (Koronne Niziny). Region `koronne_niziny` i stolica
# `vilnograd_stolica` SĄ zaseedowane, ale konkretnej lokacji portu rzecznego NIE ma jeszcze
# w game_locations. Gdy powstanie (np. `vilnograd_port_rzeczny`), dopisać trasę:
#   {"key":"czarnogrod_vilnograd","a":"czarnogrod_port","b":"vilnograd_port_rzeczny",
#    "fare_gp":60,"hours":14.0,"shortcut":False}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _port_keys() -> set[str]:
    """Wszystkie klucze lokacji będące portami (implicytnie z tabeli tras)."""
    keys: set[str] = set()
    for r in SEA_ROUTES:
        keys.add(r["a"])
        keys.add(r["b"])
    return keys


def is_sail_port(location_key: str | None) -> bool:
    """True gdy z tej lokacji da się wypłynąć (jest portem w tabeli tras)."""
    return bool(location_key) and location_key in _port_keys()


def has_mapa_smolnego(conn: sqlite3.Connection, character_id: int) -> bool:
    """Czy bohater niesie Mapę Smolnego (obniża ryzyko rafy + odblokowuje skróty)."""
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) AS q FROM character_inventory "
            "WHERE character_id = ? AND item_key = ?",
            (character_id, MAPA_SMOLNEGO_KEY),
        ).fetchone()
        return bool(row and int(row["q"] or 0) > 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("has_mapa_smolnego_error", error=str(exc))
        return False


def _dest_of(route: dict, from_key: str) -> str | None:
    """Drugi port trasy względem `from_key` (None gdy from_key nie należy do trasy)."""
    if route["a"] == from_key:
        return route["b"]
    if route["b"] == from_key:
        return route["a"]
    return None


def _routes_from(from_key: str, has_map: bool) -> list[tuple[dict, str]]:
    """Dostępne (trasa, port_docelowy) z `from_key`. Skróty tylko z Mapą Smolnego."""
    out: list[tuple[dict, str]] = []
    for r in SEA_ROUTES:
        if r.get("shortcut") and not has_map:
            continue
        dest = _dest_of(r, from_key)
        if dest:
            out.append((r, dest))
    return out


def _location_label(conn: sqlite3.Connection, key: str) -> str:
    try:
        row = conn.execute(
            "SELECT label FROM game_locations WHERE key = ? LIMIT 1", (key,)
        ).fetchone()
        if row and row["label"]:
            return str(row["label"])
    except Exception:  # noqa: BLE001
        pass
    return key


def _location_id(conn: sqlite3.Connection, key: str) -> int | None:
    try:
        row = conn.execute(
            "SELECT id FROM game_locations WHERE key = ? LIMIT 1", (key,)
        ).fetchone()
        if row:
            return int(row["id"])
    except Exception:  # noqa: BLE001
        pass
    return None


def _is_night(campaign_id: int, conn: sqlite3.Connection) -> bool:
    try:
        from app.services.clock_service import get_clock_state
        return get_clock_state(campaign_id, conn=conn).get("period") == "Noc"
    except Exception:  # noqa: BLE001
        return False


def _roll(dice: str, rng: random.Random) -> int:
    """Prosty rzut 'NdM' → suma. Fallback 0 przy złym formacie."""
    try:
        n, m = dice.lower().split("d")
        n_i, m_i = int(n or 1), int(m)
        return sum(rng.randint(1, m_i) for _ in range(max(1, n_i)))
    except Exception:  # noqa: BLE001
        return 0


def _voyage_event_chance(is_night: bool) -> float:
    p = VOYAGE_EVENT_CHANCE
    if is_night:
        p *= VOYAGE_NIGHT_MULT
    return min(0.95, p)


def _pick_event_kind(has_map: bool, rng: random.Random) -> str:
    """Wybierz typ zdarzenia rejsu ważoną losowością. Mapa Smolnego obniża wagę rafy."""
    weights = dict(VOYAGE_EVENT_WEIGHTS)
    if has_map:
        weights["rafa"] = max(0.0, weights["rafa"] * MAPA_SMOLNEGO_REEF_MULT)
    kinds = list(weights.keys())
    return rng.choices(kinds, weights=[weights[k] for k in kinds], k=1)[0]


def _risk_label(is_night: bool) -> str:
    p = _voyage_event_chance(is_night)
    if p >= 0.5:
        return "wysokie"
    if p >= 0.3:
        return "umiarkowane"
    return "niskie"


# ── Odczyt tras dla UI ────────────────────────────────────────────────────────

def list_sea_routes(
    conn: sqlite3.Connection, campaign_id: int, character_id: int
) -> dict:
    """Trasy dostępne z bieżącego portu (dla panelu „Wypłyń").

    Zwraca {is_port, port_key, port_label, gold, is_night, has_map, risk, routes:[...]}.
    routes: [{route_key, dest_key, dest_label, fare_gp, hours, shortcut, affordable}]
    Gdy gracz nie stoi w porcie → {is_port: False, routes: []}.
    """
    from app.services.location_state_service import get_current_location_key
    from app.services.economy_service import get_character_gold

    cur_key = get_current_location_key(conn, campaign_id) or ""
    if not is_sail_port(cur_key):
        return {"is_port": False, "routes": []}

    has_map = has_mapa_smolnego(conn, character_id)
    gold = get_character_gold(conn, character_id)
    is_night = _is_night(campaign_id, conn)

    routes_out: list[dict] = []
    for route, dest in _routes_from(cur_key, has_map):
        fare = int(route["fare_gp"])
        routes_out.append({
            "route_key": route["key"],
            "dest_key": dest,
            "dest_label": _location_label(conn, dest),
            "fare_gp": fare,
            "hours": float(route["hours"]),
            "shortcut": bool(route.get("shortcut")),
            "affordable": gold >= fare,
        })

    return {
        "is_port": True,
        "port_key": cur_key,
        "port_label": _location_label(conn, cur_key),
        "gold": gold,
        "is_night": is_night,
        "has_map": has_map,
        "risk": _risk_label(is_night),
        "routes": routes_out,
    }


# ── Błędy ──────────────────────────────────────────────────────────────────────

class VoyageError(Exception):
    """Zwracany do endpointu jako 4xx. `.code` → status, `.message` → PL komunikat."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


VOYAGE_ERROR_STATUS: dict[str, int] = {
    "character_not_found": 404,
    "not_in_port": 409,
    "dead": 409,
    "in_combat": 409,
    "unknown_route": 400,
    "needs_map": 403,
    "not_enough_gold": 402,
    "dest_not_placed": 400,
}


# ── Wykonanie rejsu ────────────────────────────────────────────────────────────

def execute_sea_voyage(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    route_key: str,
    *,
    rng: random.Random | None = None,
) -> dict:
    """Wykonaj rejs po trasie `route_key` z bieżącego portu do drugiego portu trasy.

    Sekwencja: bramki → weryfikacja portu wyjścia → opłata (change_gold) →
    zegar (advance_clock) → jeden rzut na zdarzenie rejsu → skutek → set_position →
    scena → syntetyczna tura. `rng` wstrzykiwalny do testów.
    """
    rng = rng or random
    from app.services.location_state_service import get_current_location_key, set_position
    from app.services.economy_service import change_gold, get_character_gold
    from app.services.clock_service import advance_clock
    from app.services.hex_location_link import resolve_location_to_hex

    # (0) bohater + status
    char = conn.execute(
        "SELECT sheet_json, status FROM characters WHERE id = ? AND campaign_id = ?",
        (character_id, campaign_id),
    ).fetchone()
    if char is None:
        raise VoyageError("character_not_found", "Nie znaleziono bohatera.")
    sheet = json.loads(char["sheet_json"] or "{}")
    _hp = sheet.get("current_hp")
    if (
        str(char["status"] or "") == "dead"
        or sheet.get("status") == "dead"
        or (isinstance(_hp, (int, float)) and _hp <= 0)
    ):
        raise VoyageError("dead", "Bohater nie żyje — nie może wypłynąć.")

    from app.services.combat_service import get_active_combat
    if get_active_combat(campaign_id):
        raise VoyageError("in_combat", "Nie można wypłynąć w trakcie walki.")

    # (1) port wyjścia = bieżąca lokacja i musi być portem
    cur_key = get_current_location_key(conn, campaign_id) or ""
    if not is_sail_port(cur_key):
        raise VoyageError("not_in_port", "Musisz być w porcie, żeby wypłynąć.")

    # (2) trasa
    route = next((r for r in SEA_ROUTES if r["key"] == route_key), None)
    if route is None:
        raise VoyageError("unknown_route", "Nieznana trasa rejsu.")
    dest_key = _dest_of(route, cur_key)
    if dest_key is None:
        raise VoyageError("unknown_route", "Ta trasa nie wychodzi z tego portu.")

    has_map = has_mapa_smolnego(conn, character_id)
    if route.get("shortcut") and not has_map:
        raise VoyageError("needs_map", "Ten skrót bez Mapy Smolnego to samobójstwo — nie znasz go.")

    dest = resolve_location_to_hex(conn, dest_key)
    if dest is None:
        raise VoyageError("dest_not_placed", f"Port docelowy '{dest_key}' nie jest na mapie.")
    dest_q, dest_r = dest

    # (3) opłata — change_gold to jedyny chokepoint; rzuca ValueError gdy brak środków
    fare = int(route["fare_gp"])
    try:
        gold_after = change_gold(
            conn, character_id, -fare, "sea_voyage",
            campaign_id=campaign_id, meta={"route": route_key, "dest": dest_key},
        )
    except ValueError:
        raise VoyageError("not_enough_gold", f"Za mało złota — rejs kosztuje {fare} zł.")

    # (4) zegar — czas rejsu (+ ewentualny sztorm dojdzie niżej)
    is_night = _is_night(campaign_id, conn)
    hours = float(route["hours"])

    # (5) jeden rzut na zdarzenie rejsu
    event: dict | None = None
    if rng.random() < _voyage_event_chance(is_night):
        picked = _pick_event_kind(has_map, rng)
        event = _apply_event(conn, character_id, sheet, picked, gold_after, rng)
        if event.get("extra_hours"):
            hours += float(event["extra_hours"])
        if "gold_after" in event:
            gold_after = event["gold_after"]

    # zegar po ustaleniu ewentualnych dodatkowych godzin sztormu
    clock_state = None
    try:
        clock_state = advance_clock(campaign_id, hours, "sea_voyage", conn=conn)
    except Exception as exc:  # noqa: BLE001
        logger.warning("voyage_clock_failed", error=str(exc), campaign_id=campaign_id)

    # (6) pozycja: zejście na ląd w porcie docelowym (opuszcza mapę lokalną)
    dest_loc_id = _location_id(conn, dest_key)
    set_position(
        conn, campaign_id,
        current_hex={"q": dest_q, "r": dest_r},
        current_location_id=dest_loc_id,
        clear_local_hex=True,
        character_id=character_id,
    )

    # scena: wyjdź ze starej, wejdź do docelowej
    scene_loaded = None
    try:
        from app.services.world_state_service import enter_location_scene, exit_location_scene
        exit_location_scene(campaign_id)
        scene_loaded = enter_location_scene(campaign_id, dest_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("voyage_scene_failed", error=str(exc), campaign_id=campaign_id)

    dest_label = _location_label(conn, dest_key)
    _record_voyage_turn(conn, campaign_id, character_id, dest_label, hours, event)
    conn.commit()

    return {
        "ok": True,
        "route_key": route_key,
        "dest_key": dest_key,
        "dest_label": dest_label,
        "fare_gp": fare,
        "hours": hours,
        "is_night": is_night,
        "used_map": has_map,
        "event": event,
        "gold": gold_after,
        "current_hp": sheet.get("current_hp"),
        "clock": clock_state,
        "scene_loaded": scene_loaded,
    }


def _apply_event(
    conn: sqlite3.Connection,
    character_id: int,
    sheet: dict,
    kind: str,
    gold: int,
    rng: random.Random,
) -> dict:
    """Zastosuj skutek zdarzenia rejsu. Zwraca opis zdarzenia dla UI/narracji.

    HP nigdy nie schodzi poniżej 1 (rejs nie zabija — brak walki morskiej).
    """
    ev: dict = {"kind": kind}

    if kind == "sztorm":
        dmg = _roll(STORM_HP_LOSS, rng)
        _lose_hp(conn, character_id, sheet, dmg)
        ev["extra_hours"] = STORM_EXTRA_HOURS
        ev["hp_loss"] = dmg
        ev["label"] = "Sztorm"
        ev["narrative"] = (
            f"Sztorm znosi łódź z kursu — tracisz {STORM_EXTRA_HOURS:g} h i "
            f"{dmg} pkt. życia na miotanym pokładzie."
        )

    elif kind == "rafa":
        dmg = _roll(REEF_HP_LOSS, rng)
        _lose_hp(conn, character_id, sheet, dmg)
        ev["hp_loss"] = dmg
        ev["label"] = "Rafa"
        ev["narrative"] = (
            f"Kadłub ociera o ukrytą rafę — wstrząs zwala załogę z nóg, "
            f"tracisz {dmg} pkt. życia."
        )

    elif kind == "piraci":
        loss = 0
        if gold > 0:
            loss = min(gold, max(PIRATE_GOLD_MIN, int(gold * PIRATE_GOLD_PCT)))
        if loss > 0:
            from app.services.economy_service import change_gold
            try:
                new_gold = change_gold(
                    conn, character_id, -loss, "sea_voyage_pirates",
                    campaign_id=None,
                )
                ev["gold_after"] = new_gold
            except ValueError:
                loss = 0
        ev["gold_loss"] = loss
        ev["label"] = "Piraci"
        ev["narrative"] = (
            f"Piracka galera zachodzi drogę i żąda daniny — oddajesz {loss} zł, "
            f"żeby przepłynąć bez rozlewu krwi."
        ) if loss else (
            "Piracka galera przygląda się z daleka, ale pusta sakwa nie kusi — "
            "odpływają bez słowa."
        )

    return ev


def _lose_hp(conn: sqlite3.Connection, character_id: int, sheet: dict, dmg: int) -> None:
    """Odejmij HP w sheet_json (min 1 — rejs nie zabija). Zapis best-effort."""
    if dmg <= 0:
        return
    try:
        cur = sheet.get("current_hp")
        if not isinstance(cur, (int, float)):
            return
        sheet["current_hp"] = max(1, int(cur) - int(dmg))
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), character_id),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("voyage_hp_apply_failed", error=str(exc))


def _record_voyage_turn(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    dest_label: str,
    hours: float,
    event: dict | None,
) -> None:
    """Syntetyczna tura narracyjna — inaczej narrator nie wie, że gracz wypłynął."""
    narr = (
        f"Wypływasz z portu. Po {hours:g} h rejsu łódź dobija do brzegu: {dest_label}."
    )
    if event and event.get("narrative"):
        narr += " " + str(event["narrative"])
    try:
        tn = conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 AS n FROM campaign_turns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        conn.execute(
            "INSERT INTO campaign_turns (campaign_id, character_id, user_text, route, assistant_text, turn_number) "
            "VALUES (?,?,?,?,?,?)",
            (
                campaign_id, character_id,
                "[Rejs — wypływam z portu]",
                "narrative",
                json.dumps({"narrative": narr}, ensure_ascii=False),
                int(tn["n"]),
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("voyage_turn_record_failed", error=str(exc))
