"""S11 (#606) — FAZA S: prymityw `reroll` (nadany i wymuszony).

Prymityw raz, kondycja danymi (Zasada 1 FAZY S): silnik czyta efekty typu `reroll`
z aktywnych kondycji aktora i działa na nich generycznie — zero `if condition_key == ...`.
Kondycje `inspired` / `cursed` wnoszą ten efekt wyłącznie jako DANE (seed effect_json).

Tryby (`mode`):
  - ``player_keep_best``  — gracz może raz przerzucić NIEUDANY test i zachować LEPSZY
                            wynik (kondycja ``inspired``). Konsumuje ``uses``.
  - ``forced_keep_worst`` — mechanika przerzuca UDANY test gracza i zachowuje GORSZY
                            ("zły omen" klątwy). Limit budżetem 1×/scenę.

Zakres (`scope`): ``skill_test`` (egzekwowane teraz), ``attack`` / ``all`` zarezerwowane.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

REROLL_MODES = {"player_keep_best", "forced_keep_worst"}
REROLL_SCOPES = {"skill_test", "attack", "all"}


# ── Czyste helpery rzutu ───────────────────────────────────────────────────────

def keep_better(a: int, b: int) -> int:
    """Zachowaj lepszy (wyższy) z dwóch surowych d20."""
    return a if int(a) >= int(b) else b


def keep_worse(a: int, b: int) -> int:
    """Zachowaj gorszy (niższy) z dwóch surowych d20."""
    return a if int(a) <= int(b) else b


# ── Ekstrakcja efektów reroll z kondycji (klucz danymi) ────────────────────────

def _effects_from_effect_json(ej: object) -> list[dict]:
    if isinstance(ej, str):
        try:
            ej = json.loads(ej or "{}")
        except (TypeError, ValueError):
            return []
    if not isinstance(ej, dict):
        return []
    return [e for e in (ej.get("effects") or []) if isinstance(e, dict)]


def extract_reroll_effects(
    conditions: list[dict] | None,
    mode: Optional[str] = None,
    scope: str = "skill_test",
) -> list[tuple[dict, dict]]:
    """Z listy kondycji (każda z ``effect_json`` jako str lub dict) zwróć pary
    ``(condition, reroll_effect)`` dla efektów typu ``reroll`` pasujących do mode+scope.

    Generyczne — żadnego ``if condition_key == ...``. Scope ``all`` pasuje do każdego."""
    out: list[tuple[dict, dict]] = []
    want_scope = str(scope or "skill_test").strip().lower()
    for cond in conditions or []:
        if not isinstance(cond, dict):
            continue
        for eff in _effects_from_effect_json(cond.get("effect_json")):
            if str(eff.get("type", "")).strip().lower() != "reroll":
                continue
            eff_scope = str(eff.get("scope") or "skill_test").strip().lower()
            if want_scope and eff_scope not in (want_scope, "all"):
                continue
            if mode and str(eff.get("mode", "")).strip().lower() != str(mode).strip().lower():
                continue
            out.append((cond, eff))
    return out


# ── Aktywne kondycje gracza z dociągniętym effect_json z katalogu ──────────────

def load_active_conditions(conn: sqlite3.Connection, character_id: int) -> list[dict]:
    """Aktywne kondycje gracza z ``sheet_json.conditions`` (źródło prawdy poza walką),
    z dociągniętym ``effect_json`` z katalogu, gdy wiersz sheet go nie niesie."""
    if not character_id:
        return []
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (int(character_id),)
        ).fetchone()
    except Exception:
        return []
    if not row:
        return []
    raw = row[0] if not hasattr(row, "keys") else row["sheet_json"]
    try:
        sheet = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return []
    out: list[dict] = []
    for c in (sheet.get("conditions") or []):
        if not isinstance(c, dict) or not c.get("key"):
            continue
        key = str(c["key"]).strip().lower()
        ej = c.get("effect_json")
        if not ej:
            try:
                crow = conn.execute(
                    "SELECT effect_json FROM game_config_conditions WHERE key = ? AND is_active = 1 LIMIT 1",
                    (key,),
                ).fetchone()
                if crow:
                    ej = crow[0] if not hasattr(crow, "keys") else crow["effect_json"]
            except Exception:
                ej = None
        out.append({
            "key": key,
            "label": c.get("label") or key,
            "effect_json": ej,
            "runtime": c.get("runtime") if isinstance(c.get("runtime"), dict) else {},
        })
    return out


# ── Budżet "zły omen" — 1×/scenę, reset przy zmianie lokacji ───────────────────

def omen_available(session_flags: dict | None, location_key: str) -> bool:
    """Czy wymuszony przerzut ("zły omen") może jeszcze procować w tej scenie?
    Reset następuje, gdy bohater zmieni lokację (inny ``location_key``)."""
    st = (session_flags or {}).get("omen_state") or {}
    if str(st.get("loc") or "") != str(location_key or ""):
        return True
    return not bool(st.get("used"))


def consume_omen(session_flags: dict, location_key: str) -> None:
    """Oznacz budżet omenu jako zużyty w bieżącej scenie/lokacji."""
    session_flags["omen_state"] = {"loc": str(location_key or ""), "used": True}


# ── Oferta i konsumpcja przerzutu gracza (inspired) ────────────────────────────

def player_reroll_offer(conn: sqlite3.Connection, character_id: int) -> Optional[dict]:
    """Jeśli gracz ma aktywną kondycję z efektem ``reroll`` mode=player_keep_best i
    pozostałym ``uses`` — zwróć ofertę ``{condition_key, label, mode}``; inaczej None."""
    for cond, eff in extract_reroll_effects(
        load_active_conditions(conn, character_id), mode="player_keep_best"
    ):
        uses = int(eff.get("uses", 1) or 1)
        used = int((cond.get("runtime") or {}).get("reroll_used", 0) or 0)
        if used < uses:
            return {
                "condition_key": cond["key"],
                "label": cond.get("label") or cond["key"],
                "mode": "player_keep_best",
            }
    return None


def consume_player_reroll(
    conn: sqlite3.Connection, character_id: int, campaign_id: int
) -> Optional[str]:
    """Zużyj jeden ``uses`` przerzutu gracza: podbij ``runtime.reroll_used`` na kondycji,
    a gdy wyczerpany — zdejmij kondycję (inspired znika po wykorzystaniu). Deklaratywne.

    Zwraca klucz kondycji, z której skonsumowano przerzut, albo None."""
    if not character_id:
        return None
    try:
        row = conn.execute(
            "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (int(character_id),)
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    raw = row[0] if not hasattr(row, "keys") else row["sheet_json"]
    try:
        sheet = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return None

    conds = [c for c in (sheet.get("conditions") or []) if isinstance(c, dict)]
    target_key: Optional[str] = None
    exhausted = False
    for c in conds:
        key = str(c.get("key") or "").strip().lower()
        if not key:
            continue
        ej = c.get("effect_json")
        if not ej:
            try:
                crow = conn.execute(
                    "SELECT effect_json FROM game_config_conditions WHERE key = ? AND is_active = 1 LIMIT 1",
                    (key,),
                ).fetchone()
                if crow:
                    ej = crow[0] if not hasattr(crow, "keys") else crow["effect_json"]
            except Exception:
                ej = None
        hits = extract_reroll_effects([{"key": key, "effect_json": ej}], mode="player_keep_best")
        if not hits:
            continue
        eff = hits[0][1]
        uses = int(eff.get("uses", 1) or 1)
        runtime = c.get("runtime") if isinstance(c.get("runtime"), dict) else {}
        used = int(runtime.get("reroll_used", 0) or 0)
        if used >= uses:
            continue
        used += 1
        runtime["reroll_used"] = used
        c["runtime"] = runtime
        target_key = key
        exhausted = used >= uses
        break

    if not target_key:
        return None

    if exhausted:
        sheet["conditions"] = [
            c for c in conds
            if str(c.get("key") or "").strip().lower() != target_key
        ]
    else:
        sheet["conditions"] = conds

    try:
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), int(character_id)),
        )
        conn.commit()
    except Exception:
        return None

    # Gdy wyczerpane podczas walki — zdejmij też z aktywnego combatanta (parytet z S10 cure).
    if exhausted and campaign_id:
        try:
            from app.services.combat_service import remove_condition_from_character
            remove_condition_from_character(conn, int(character_id), int(campaign_id), target_key)
        except Exception:
            pass

    return target_key
