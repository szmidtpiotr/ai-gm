"""WL-8 (#1504) — Ekonomia Wybrzeża Łez: sól morska + kontrabanda.

Źródło prawdy: docs/world/regions/wybrzeze_lez.md §3, §6 (ZATWIERDZONE) oraz
docs/world/regions/koronne_niziny.md §6 (glejty/rogatki — smaczki #1500/#1501).

Ten moduł to CZYTNIK/HOOK ekonomii krainy (wzorzec jak ``tide_service`` /
``wasteland_service`` — nie buduje nowego silnika sklepu ani podróży, tylko
dokłada bramki do istniejących ścieżek ``shop_service.sell_item`` i
``hex_travel_service.execute_travel``).

Dwa tory handlu:

1. **Sól morska** (``sol_morska``) — LEGALNY towar. Najtańsza klasa soli świata:
   gradacja handlowa **Pustkowia > Granie > Wybrzeże** (lore §3 „trzy krainy = trzy
   klasy tego samego towaru bez nowej ekonomii"). Warzelnie na ``plycizna`` = źródło.
   Tanio na Wybrzeżu, drożej w Koronnych Nizinach → drobny, bezpieczny zysk (bez
   rogatki — sól jest legalna). WERSJA BAZOWA: tylko dolny szczebel drabiny (sól
   morska) jest zaimplementowany jako towar; górskiej z Grań i blizny z Pustkowi
   jako TOWARÓW HANDLOWYCH jeszcze nie ma (patrz :data:`SALT_LADDER`) — odnotowane.

2. **Kontrabanda** („towar z głębin" z Czarnego Targu, lore §2 hak) — NIELEGALNA.
   Tania w Czarnogrodzie, droga w Nizinach. Przewóz działa PRZECIW graczowi na
   **rogatkach** (#1500): kontrola → konfiskata + utrata reputacji. Papiery z Nizin
   pomagają: List żelazny = przejście bez pytań; Glejt kupiecki = mniejsza czujność;
   Fałszywe papiery = test (sukces przechodzi, wpadka = konfiskata + gorsza reputacja).
   **Szmugiel-loop domyka się**: kup w Czarnogrodzie → przewieź przez rogatkę →
   sprzedaj w Volhynii/Vilnogradzie.

WARTOŚCI STARTOWE (Numbers Policy) — wszystkie ceny/DC/bonusy do strojenia w
Sandboksie.
"""

from __future__ import annotations

import json
import random
import sqlite3
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()

# ── Regiony osi handlowej ─────────────────────────────────────────────────────
#: Źródło (tanio): Wybrzeże Łez — warzelnie soli i Czarny Targ.
SOURCE_REGION = "wybrzeze_lez"
#: Popyt (drogo) i rogatki: Koronne Niziny — cywilizacyjny sufit ekonomii.
DEMAND_REGION = "koronne_niziny"
#: Regiony z rogatkami (kontrola kontrabandy przy WJEŹDZIE). Startowo tylko Niziny.
TOLL_REGIONS = {DEMAND_REGION}


# ── Model towaru handlowego ───────────────────────────────────────────────────

@dataclass(frozen=True)
class TradeGood:
    """Towar o cenie zależnej od regionu (arbitraż międzykrainowy).

    ``buy_at_source`` = docelowa cena kupna u źródła (Czarny Targ / warzelnia /
    warsztat solny) — seed wpisuje ją jako ``price`` w ``shop_inventory_json``
    (narzut per-sklep bije cenę katalogową, patrz shop_service). Ceny SPRZEDAŻY są
    region-zależne: w regionie RODOWYM (``home_region``) nadpodaż → tanio, w regionie
    popytu (Niziny) → drogo, gdzie indziej → średnio.
    """
    label: str
    contraband: bool
    home_region: str
    buy_at_source: int
    sell_source: int
    sell_demand: int
    sell_default: int


#: Katalog towarów krainy. Klucze = klucze ``game_items`` (seed_wl8_economy.py,
#: seed_wl8b_salt_ladder.py). Sól = 3 klasy tego samego towaru (gradacja handlowa,
#: lore §3): Pustkowia (blizna) > Granie (górska) > Wybrzeże (morska). Ceny SPRZEDAŻY
#: w Nizinach rosną wraz z klasą; każda sól najtańsza w swoim regionie rodowym.
TRADE_GOODS: dict[str, TradeGood] = {
    # ── SÓL (legalna, bez rogatki) — pełna drabina 3 klas ────────────────────
    "sol_morska": TradeGood(  # najtańsza klasa — Wybrzeże (warzelnie na plycizna)
        label="Sól morska", contraband=False, home_region="wybrzeze_lez",
        buy_at_source=2, sell_source=1, sell_demand=6, sell_default=3,
    ),
    "sol_gorska": TradeGood(  # średnia klasa — Siwe Granie (sól kopalniana)
        label="Sól górska", contraband=False, home_region="siwe_granie",
        buy_at_source=5, sell_source=3, sell_demand=14, sell_default=8,
    ),
    "sol_blizny": TradeGood(  # najdroższa klasa — Martwe Pustkowia (sól z blizny)
        label="Sól z blizny", contraband=False, home_region="martwe_pustkowia",
        buy_at_source=9, sell_source=5, sell_demand=24, sell_default=14,
    ),
    # ── KONTRABANDA „z głębin" (Wybrzeże → Niziny, rogatka gra przeciw) ───────
    "perla_glebin": TradeGood(
        label="Perła z Głębin", contraband=True, home_region="wybrzeze_lez",
        buy_at_source=40, sell_source=25, sell_demand=140, sell_default=70,
    ),
    "zywica_topielcow": TradeGood(
        label="Żywica topielców", contraband=True, home_region="wybrzeze_lez",
        buy_at_source=20, sell_source=12, sell_demand=80, sell_default=40,
    ),
}

#: Zbiór kluczy kontrabandy — szybki test w rogatce.
CONTRABAND_KEYS = frozenset(k for k, g in TRADE_GOODS.items() if g.contraband)

#: Drabina soli (gradacja handlowa, lore §3) — od najdroższej klasy do najtańszej.
#: WL-8b: wszystkie trzy szczeble to realne towary (górska z Grań i blizna z Pustkowi
#: dopięte). Ceny SPRZEDAŻY w Nizinach: blizna > górska > morska.
SALT_LADDER: list[tuple[str, str, bool]] = [
    ("martwe_pustkowia", "sol_blizny", True),   # blizna Pustkowi — najdroższa
    ("siwe_granie", "sol_gorska", True),         # sól górska — średnia
    ("wybrzeze_lez", "sol_morska", True),        # sól morska — najtańsza
]


def cheapest_salt_key() -> str:
    """Klucz najtańszej klasy soli (dół drabiny) — sól morska Wybrzeża."""
    return SALT_LADDER[-1][1]


# ── Papiery Nizin (#1500/#1501 — smaczki koronne_niziny §6) ──────────────────
#: List żelazny — przejście przez rogatki bez pytań (auto-pass, nie zużywa się).
PASS_ITEM = "list_zelazny"
#: Glejt kupiecki — licencja: mniejsza czujność celników (bonus do ukrycia).
PERMIT_ITEM = "glejt_kupiecki"
#: Fałszywe papiery — wersja łotrzyka: kontrola = test i ryzyko.
FORGED_ITEM = "falszywe_papiery"

# ── Rogatka: liczby startowe (Numbers Policy, Sandbox-tunable) ────────────────
#: Bazowe DC kontroli celnej (Medium wg skali DC).
TOLL_DC_BASE = 12
#: Każda dodatkowa sztuka kontrabandy ponad pierwszą podnosi DC (trudniej ukryć).
TOLL_DC_PER_EXTRA_UNIT = 1
#: Bonus do ukrycia z glejtu kupieckiego (licencjonowany kupiec = mniej podejrzeń).
PERMIT_CONCEAL_BONUS = 4
#: Bonus do ukrycia z fałszywych papierów (dobre, ale kontrola to test).
FORGED_CONCEAL_BONUS = 6
#: Kara reputacji regionu przy wpadce (konfiskata).
TOLL_REP_PENALTY = 8
#: Dodatkowa kara reputacji, gdy wpadną fałszywe papiery (fałszerstwo).
TOLL_FORGERY_REP_PENALTY = 6


# ── Odczyt ekwipunku / położenia ─────────────────────────────────────────────

def _has_item(conn: sqlite3.Connection, character_id: int, key: str) -> bool:
    try:
        row = conn.execute(
            """SELECT 1 FROM character_inventory
               WHERE character_id = ?
                 AND (item_key = ? OR consumable_key = ? OR weapon_key = ?)
                 AND COALESCE(quantity, 1) > 0 LIMIT 1""",
            (int(character_id), key, key, key),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None


def carried_contraband(conn: sqlite3.Connection, character_id: int) -> list[dict]:
    """Sztuki kontrabandy w plecaku: [{inventory_id, item_key, quantity, good}]."""
    try:
        rows = conn.execute(
            """SELECT id, item_key, COALESCE(quantity, 1) AS q
               FROM character_inventory
               WHERE character_id = ? AND item_key IS NOT NULL""",
            (int(character_id),),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    out: list[dict] = []
    for row in rows:
        key = str((row["item_key"] if isinstance(row, sqlite3.Row) else row[1]) or "")
        if key in CONTRABAND_KEYS:
            out.append({
                "inventory_id": int(row["id"] if isinstance(row, sqlite3.Row) else row[0]),
                "item_key": key,
                "quantity": int(row["q"] if isinstance(row, sqlite3.Row) else row[2]),
                "good": TRADE_GOODS[key],
            })
    return out


def _hex_region(conn: sqlite3.Connection, q: int, r: int) -> str:
    try:
        row = conn.execute(
            "SELECT region FROM world_hexes WHERE q=? AND r=? AND map_level=0 AND is_active=1 LIMIT 1",
            (int(q), int(r)),
        ).fetchone()
    except sqlite3.OperationalError:
        return ""
    return str((row["region"] if row else "") or "")


def _dex_mod(conn: sqlite3.Connection, character_id: int) -> int:
    """Modyfikator ZR bohatera (ukrywanie towaru). Brak danych → 0."""
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id=? LIMIT 1", (int(character_id),)
        ).fetchone()
        if not row:
            return 0
        sheet = json.loads((row["sheet_json"] if isinstance(row, sqlite3.Row) else row[0]) or "{}")
        stats = sheet.get("stats", {}) if isinstance(sheet, dict) else {}
        dex = int(stats.get("DEX", 10))
        return (dex - 10) // 2
    except Exception:
        return 0


# ── Tor 1: cena sprzedaży towaru handlowego (region-zależna) ──────────────────

def trade_good_sell_price(
    conn: sqlite3.Connection, character_id: int, item_key: str
) -> int | None:
    """Cena sprzedaży towaru handlowego w REGIONIE, w którym stoi bohater.

    Zwraca None, gdy przedmiot nie jest towarem krainy (wtedy shop_service liczy
    cenę zwykłą). Dla towaru: region popytu (Niziny) = drogo, źródło (Wybrzeże) =
    nadpodaż/tanio, gdzie indziej = średnio. To CELOWO omija zwykły cap arbitrażu
    shop_service (kupno-tanio/sprzedaż-drogo jest tu SENSEM gry — przemyt między
    krainami, nie exploitem w jednym sklepie).
    """
    good = TRADE_GOODS.get(str(item_key or "").strip())
    if good is None:
        return None
    region = _character_region(conn, character_id)
    if region == DEMAND_REGION:
        return good.sell_demand
    if region == good.home_region:
        return good.sell_source
    return good.sell_default


def _character_region(conn: sqlite3.Connection, character_id: int) -> str:
    """Region, w którym stoi bohater (przez kampanię → resolve_region)."""
    try:
        row = conn.execute(
            "SELECT campaign_id FROM characters WHERE id=? LIMIT 1", (int(character_id),)
        ).fetchone()
        cid = row["campaign_id"] if row and isinstance(row, sqlite3.Row) else (row[0] if row else None)
        if not cid:
            return ""
        from app.services.reputation_service import resolve_region
        return resolve_region(conn, int(cid))
    except Exception:
        return ""


# ── Tor 2: rogatka — kontrola kontrabandy przy wjeździe do Nizin ──────────────

def crossing_into_toll_region(from_region: str, to_region: str) -> bool:
    """True gdy podróż WCHODZI do regionu z rogatkami z regionu innego (granica)."""
    return to_region in TOLL_REGIONS and from_region != to_region


def _confiscate(conn: sqlite3.Connection, items: list[dict]) -> list[dict]:
    """Usuń kontrabandę z plecaka. Zwraca listę skonfiskowanych (klucz+ilość)."""
    taken: list[dict] = []
    for it in items:
        conn.execute("DELETE FROM character_inventory WHERE id=?", (it["inventory_id"],))
        taken.append({
            "item_key": it["item_key"],
            "label": it["good"].label,
            "quantity": it["quantity"],
            "value_gp": it["good"].sell_demand,
        })
    return taken


def rogatka_control(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    *,
    from_hex: tuple[int, int] | None = None,
    to_hex: tuple[int, int] | None = None,
    from_region: str | None = None,
    to_region: str | None = None,
    result: dict | None = None,
    rng: random.Random | None = None,
) -> dict | None:
    """Kontrola celna na rogatce przy wjeździe do regionu z rogatkami (Niziny).

    Zwraca RAPORT z liczbami (rzut, DC, wykryto?, konfiskata, reputacja) albo None,
    gdy kontrola się nie odbywa (nie przekracza granicy / brak kontrabandy).
    Commit robi ta funkcja (utrwala konfiskatę + reputację).

    Priorytet papierów:
      * List żelazny  → przejście bez pytań (bez rzutu),
      * Glejt kupiecki → mniejsza czujność (bonus do ukrycia),
      * Fałszywe papiery → bonus do ukrycia, ale wpadka = konfiskata + fałszerstwo,
      * brak papierów → zwykły test ukrycia.
    """
    rng = rng or random

    # regiony granicy — z argumentów albo z hexów
    fr = from_region if from_region is not None else (_hex_region(conn, *from_hex) if from_hex else "")
    to = to_region if to_region is not None else (_hex_region(conn, *to_hex) if to_hex else "")
    if not crossing_into_toll_region(fr, to):
        return None

    contraband = carried_contraband(conn, character_id)
    if not contraband:
        return None  # nie ma czego szukać — brak kontroli

    units = sum(int(it["quantity"]) for it in contraband)
    dc = TOLL_DC_BASE + max(0, units - 1) * TOLL_DC_PER_EXTRA_UNIT

    has_pass = _has_item(conn, character_id, PASS_ITEM)
    has_permit = _has_item(conn, character_id, PERMIT_ITEM)
    has_forged = _has_item(conn, character_id, FORGED_ITEM)

    # 1) List żelazny — przejście bez pytań, bez rzutu i bez konfiskaty.
    if has_pass:
        report = {
            "checked": True, "passed": True, "reason": "list_zelazny",
            "roll": None, "dc": dc, "units": units,
            "confiscated": [], "reputation_delta": 0,
        }
        if isinstance(result, dict):
            result["rogatka"] = report
        return report

    conceal = _dex_mod(conn, character_id)
    paper_bonus = 0
    used_forged = False
    if has_permit:
        paper_bonus += PERMIT_CONCEAL_BONUS
    if has_forged:
        paper_bonus += FORGED_CONCEAL_BONUS
        used_forged = True

    d20 = rng.randint(1, 20)
    total = d20 + conceal + paper_bonus
    detected = total < dc

    report: dict = {
        "checked": True,
        "passed": not detected,
        "reason": ("brak_papierow" if not (has_permit or has_forged) else
                   ("falszywe_papiery" if has_forged else "glejt")),
        "roll": d20,
        "conceal_mod": conceal,
        "paper_bonus": paper_bonus,
        "total": total,
        "dc": dc,
        "units": units,
        "confiscated": [],
        "reputation_delta": 0,
    }

    if not detected:
        if isinstance(result, dict):
            result["rogatka"] = report
        return report

    # WPADKA — konfiskata całej kontrabandy + utrata reputacji regionu.
    taken = _confiscate(conn, contraband)
    rep_pen = TOLL_REP_PENALTY
    if used_forged:
        rep_pen += TOLL_FORGERY_REP_PENALTY
        # fałszywe papiery skonfiskowane wraz z towarem
        conn.execute(
            "DELETE FROM character_inventory WHERE character_id=? AND item_key=?",
            (int(character_id), FORGED_ITEM),
        )
        report["forged_seized"] = True
    conn.commit()

    new_rep = 0
    try:
        from app.services.reputation_service import adjust_reputation
        new_rep = adjust_reputation(
            conn, character_id, DEMAND_REGION, -rep_pen,
            scope_type="region", reason="rogatka_kontrabanda",
        )
    except Exception as _rep_err:  # noqa: BLE001
        logger.warning("rogatka_reputation_failed", error=str(_rep_err))

    report["confiscated"] = taken
    report["reputation_delta"] = -rep_pen
    report["reputation_after"] = new_rep

    # narracja mechaniczna (bez LLM)
    seized_labels = ", ".join(f"{t['label']}×{t['quantity']}" for t in taken)
    msg = (
        f"Rogatka Wschodnia. Berta Twarda Pieczęć każe otworzyć juki. „A to co?” — "
        f"wyciąga {seized_labels}. Towar przepada, a twoje imię trafia do celnego "
        f"rejestru Korony (reputacja Koronnych Nizin −{rep_pen})."
    )
    if used_forged:
        msg += " Fałszywe papiery też idą do kosza — a fałszerstwo pamiętają dłużej."
    _record_turn(conn, campaign_id, character_id, msg)

    if isinstance(result, dict):
        result["rogatka"] = report
    return report


def _record_turn(conn: sqlite3.Connection, campaign_id: int, character_id: int, msg: str) -> None:
    try:
        tn = conn.execute(
            "SELECT COALESCE(MAX(turn_number),0)+1 FROM campaign_turns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO campaign_turns (campaign_id, character_id, turn_number, user_text, "
            "assistant_text, route, created_at) VALUES (?,?,?,?,?,?,datetime('now'))",
            (campaign_id, character_id, int(tn), "[Rogatka]",
             json.dumps({"narrative": msg}, ensure_ascii=False), "narrative"),
        )
        conn.commit()
    except Exception as _turn_err:  # noqa: BLE001
        logger.warning("rogatka_turn_failed", error=str(_turn_err))
