"""WL-8b (#1504) — Weksle kantorów (koronne_niziny §6, smaczki #1500/#1501).

„Weksel kantorów — zamiana złota na papier wymienialny w kantorach enklawy —
bezpieczny transport majątku (kradzież/śmierć nie zabiera weksla)."

Fikcja: enklawa krasnoludzka Vilnogradu prowadzi kantory (Gundrik Złota Waga).
Gracz wpłaca złoto → dostaje weksel na okaziciela; wymienia go w dowolnym kantorze
z powrotem na złoto. Za wystawienie kantor bierze prowizję.

DLACZEGO TO BEZPIECZNE (kluczowa własność):
  Weksle żyją w ``sheet_json["weksle"]`` — a WSZYSTKIE ścieżki utraty majątku ruszają
  wyłącznie ``characters.gold_gp`` (napad — robbery_service, podatek wskrzeszenia —
  resurrection_service) albo ``character_inventory`` (konfiskata na rogatce). Śmierć
  solo (solo_death_service) rusza tylko tabelę ``campaigns``. Żadna z nich nie dotyka
  ``sheet_json``, więc wartość w wekslu jest STRUKTURALNIE odporna — nie trzeba
  dokładać strażników. To jest cała mechanika „bezpiecznego transportu".

WARTOŚCI STARTOWE (Numbers Policy, Sandbox-tunable): prowizja i minimalny nominał.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import structlog

from app.services.economy_service import change_gold, get_character_gold

logger = structlog.get_logger()

# ── liczby startowe ───────────────────────────────────────────────────────────
#: Prowizja kantoru za wystawienie weksla (od nominału). 2% = koszt bezpieczeństwa.
KANTOR_FEE_PCT = 0.02
#: Minimalna prowizja (żeby drobne weksle nie były darmowe).
KANTOR_MIN_FEE = 1
#: Najmniejszy sensowny nominał weksla (drobniaków się nie „papieruje").
MIN_WEKSEL_AMOUNT = 10
#: Słowa w kluczu/labelu/subtypie lokacji rozpoznające kantor.
KANTOR_KEYWORDS = ("kantor", "wekslarz", "lichwiarz", "mennica", "enklawa_krasnoludzka", "złota waga", "zlota waga")


# ── sheet_json: odczyt/zapis listy weksli ────────────────────────────────────

def _load_sheet(conn: sqlite3.Connection, character_id: int) -> dict:
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (int(character_id),)
    ).fetchone()
    if not row:
        raise ValueError("character_not_found")
    from app.services.dice import parse_character_sheet
    return parse_character_sheet(row["sheet_json"] if isinstance(row, sqlite3.Row) else row[0]) or {}


def _save_sheet(conn: sqlite3.Connection, character_id: int, sheet: dict) -> None:
    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), int(character_id)),
    )


def _weksle(sheet: dict) -> list[dict]:
    raw = sheet.get("weksle")
    return [w for w in raw if isinstance(w, dict)] if isinstance(raw, list) else []


def list_weksle(conn: sqlite3.Connection, character_id: int) -> list[dict]:
    """Wszystkie weksle bohatera (na okaziciela) — dla UI/API."""
    return _weksle(_load_sheet(conn, character_id))


def total_weksle_value(conn: sqlite3.Connection, character_id: int) -> int:
    """Łączna wartość nominalna weksli (majątek „w papierze")."""
    return sum(int(w.get("amount", 0) or 0) for w in list_weksle(conn, character_id))


def _fee_for(amount: int) -> int:
    return max(KANTOR_MIN_FEE, int(round(int(amount) * KANTOR_FEE_PCT)))


# ── operacje kantoru ──────────────────────────────────────────────────────────

def buy_weksel(conn: sqlite3.Connection, character_id: int, amount: int) -> dict:
    """Zamień złoto na weksel na okaziciela. Pobiera nominał + prowizję z gold_gp.

    Zwraca {weksel, fee, gold}. Rzuca ValueError:
      * ``amount_too_small`` — poniżej minimalnego nominału,
      * ``insufficient_gold`` — brak złota na nominał + prowizję.
    Commit robi wołający (router).
    """
    amount = int(amount)
    if amount < MIN_WEKSEL_AMOUNT:
        raise ValueError("amount_too_small")
    fee = _fee_for(amount)
    total = amount + fee
    if get_character_gold(conn, character_id) < total:
        raise ValueError("insufficient_gold")

    # zdejmij złoto (nominał + prowizja) jednym chokepointem
    new_gold = change_gold(conn, character_id, -total, "kantor_weksel_buy",
                           meta={"amount": amount, "fee": fee})

    sheet = _load_sheet(conn, character_id)
    seq = int(sheet.get("weksel_seq", 0)) + 1
    sheet["weksel_seq"] = seq
    weksel = {
        "id": seq,
        "amount": amount,
        "fee": fee,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    weksle = _weksle(sheet)
    weksle.append(weksel)
    sheet["weksle"] = weksle
    _save_sheet(conn, character_id, sheet)

    logger.info("kantor_weksel_bought", character_id=int(character_id), amount=amount, fee=fee)
    return {"weksel": weksel, "fee": fee, "gold": int(new_gold),
            "weksle_total": total_weksle_value(conn, character_id)}


def redeem_weksel(conn: sqlite3.Connection, character_id: int, weksel_id: int) -> dict:
    """Wymień weksel z powrotem na złoto (pełny nominał — prowizję wzięto przy wystawieniu).

    Zwraca {amount, gold}. Rzuca ValueError ``weksel_not_found``.
    Commit robi wołający (router).
    """
    weksel_id = int(weksel_id)
    sheet = _load_sheet(conn, character_id)
    weksle = _weksle(sheet)
    match = next((w for w in weksle if int(w.get("id", -1)) == weksel_id), None)
    if match is None:
        raise ValueError("weksel_not_found")
    amount = int(match.get("amount", 0) or 0)

    sheet["weksle"] = [w for w in weksle if int(w.get("id", -1)) != weksel_id]
    _save_sheet(conn, character_id, sheet)

    new_gold = change_gold(conn, character_id, amount, "kantor_weksel_redeem",
                           meta={"weksel_id": weksel_id, "amount": amount})

    logger.info("kantor_weksel_redeemed", character_id=int(character_id), amount=amount)
    return {"amount": amount, "gold": int(new_gold),
            "weksle_total": total_weksle_value(conn, character_id)}


# ── bramka lokacji: czy tu jest kantor ───────────────────────────────────────

def kantor_available(conn: sqlite3.Connection, campaign_id: int) -> bool:
    """Czy bohater stoi w miejscu z kantorem (enklawa krasnoludzka / wekslarz)."""
    try:
        from app.services.location_state_service import get_current_location_key
        loc_key = get_current_location_key(conn, int(campaign_id))
    except Exception:
        loc_key = None
    if not loc_key:
        return False
    try:
        row = conn.execute(
            "SELECT key, label, location_subtype FROM game_locations WHERE key = ? AND is_active = 1 LIMIT 1",
            (loc_key,),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if not row:
        return False
    hay = f"{row['key'] or ''} {row['label'] or ''} {row['location_subtype'] or ''}".lower()
    return any(k in hay for k in KANTOR_KEYWORDS)
