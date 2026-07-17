"""#1193 — Choroba (zaraza). Kondycja `chory` niosąca prymityw
`flat_test_penalty` — świadomie ODDZIELNA od zmęczenia (`fatigue_service`), by
długi odpoczynek jej NIE leczył. Zdjęcie: leczenie u zielarza/uzdrowiciela
(test medicine DC 12, przez istniejący mechanizm `cure`) lub mikstura z
`cures_disease`.

Zarażenie następuje przy odpoczynku w osadzie regionu objętego zarazą
(`world_event_service.disease_dc`): test CON przeciw DC; porażka → `chory`.

Numbers Policy: DC i kara — wartości startowe, strojone w adminie.
"""

from __future__ import annotations

import json
import random
import sqlite3
from typing import Any

CHORY_KEY = "chory"
FLAT_TEST_PENALTY = "flat_test_penalty"


def _decode(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        val = json.loads(raw or "{}")
        return val if isinstance(val, dict) else {}
    except (TypeError, ValueError):
        return {}


# ─── Odczyt / kara ────────────────────────────────────────────────────────────

def has_disease(conditions: list[dict] | None) -> bool:
    for c in conditions or []:
        if isinstance(c, dict) and str(c.get("key") or "").strip().lower() == CHORY_KEY:
            return True
    return False


def compute_disease_penalty(conditions: list[dict] | None) -> int:
    """Suma kar do testów umiejętności od kondycji chorobowych (≤0).

    Czyta prymityw `flat_test_penalty` — NIE `test_penalty` (fatigue), więc
    `clear_all_fatigue` (długi odpoczynek) go nie zdejmuje."""
    total = 0
    for c in conditions or []:
        if not isinstance(c, dict):
            continue
        for ef in _decode(c.get("effect_json")).get("effects") or []:
            if isinstance(ef, dict) and str(ef.get("type") or "").lower() == FLAT_TEST_PENALTY:
                try:
                    total += int(ef.get("value") or 0)
                except (TypeError, ValueError):
                    pass
    return total


# ─── Katalog kondycji ─────────────────────────────────────────────────────────

def _load_condition_instance(conn: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT key, label, effect_json FROM game_config_conditions WHERE key = ? AND is_active = 1",
        (key,),
    ).fetchone()
    if not row:
        return None
    return {
        "key": row["key"],
        "label": row["label"],
        "effect_json": _decode(row["effect_json"]),
        "runtime": {},
    }


# ─── Mutacje sheeta ───────────────────────────────────────────────────────────

def apply_disease(conn: sqlite3.Connection, sheet: dict) -> bool:
    """Nakłada kondycję `chory` na sheet (in-place). No-op gdy już chory lub brak
    kondycji w katalogu. Zwraca True gdy nałożono."""
    conditions = list(sheet.get("conditions") or [])
    if has_disease(conditions):
        return False
    inst = _load_condition_instance(conn, CHORY_KEY)
    if not inst:
        return False
    conditions.append(inst)
    sheet["conditions"] = conditions
    return True


def cure_disease(sheet: dict) -> bool:
    """Zdejmuje wszystkie kondycje `chory` (in-place). Zwraca True gdy coś zdjęto."""
    conditions = list(sheet.get("conditions") or [])
    kept = [c for c in conditions if not (isinstance(c, dict)
            and str(c.get("key") or "").strip().lower() == CHORY_KEY)]
    if len(kept) == len(conditions):
        return False
    sheet["conditions"] = kept
    return True


# ─── Test zarażenia przy odpoczynku ──────────────────────────────────────────

def _con_mod(sheet: dict) -> int:
    try:
        con = int((sheet.get("stats") or {}).get("CON", 10) or 10)
    except (TypeError, ValueError):
        con = 10
    return (con - 10) // 2


def maybe_infect_on_rest(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
) -> dict[str, Any]:
    """Rzut na zarażenie przy odpoczynku w regionie z zarazą.

    Zwraca {infected, active, dc?, roll?, total?}. `active=False` gdy region nie
    ma aktywnej zarazy (brak testu). Persystuje `chory` na sheet przy porażce.
    Defensywny — błąd → {infected:False, active:False}."""
    try:
        from app.services import world_event_service as wes
        from app.services.reputation_service import resolve_region
        region = resolve_region(conn, int(campaign_id))
        dc = wes.disease_dc(conn, region)
        if dc is None:
            return {"infected": False, "active": False}

        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ?", (int(character_id),)
        ).fetchone()
        if not row:
            return {"infected": False, "active": True, "dc": dc}
        sheet = _decode(row["sheet_json"])
        if has_disease(sheet.get("conditions")):
            return {"infected": False, "active": True, "dc": dc, "already": True}

        d20 = random.randint(1, 20)
        con_mod = _con_mod(sheet)
        total = d20 + con_mod
        # Nat 20 = auto-odporność, Nat 1 = auto-zarażenie; inaczej total vs DC.
        if d20 == 20:
            infected = False
        elif d20 == 1:
            infected = True
        else:
            infected = total < int(dc)

        if infected and apply_disease(conn, sheet):
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), int(character_id)),
            )
        return {"infected": infected, "active": True, "dc": int(dc),
                "roll": d20, "total": total}
    except Exception:
        return {"infected": False, "active": False}
